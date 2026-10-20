"""Explicit observed inputs and an isolated, cutoff-only production SQLite adapter.

Outcome loading belongs to the CLI's independently gated final branch. Production
code never imports this module or receives a path, truth ledger or future record.
"""

import json
from datetime import date, timedelta
from pathlib import Path

from scripts.data_contract import read_csv, read_json, sha256
from scripts.make_ground_truth import TruthLedger, cutoff, stamp

OBSERVED_FILES = (
    "observed_90d.csv",
    "opening_balance.json",
    "categories.csv",
    "counterparties.csv",
    "payment_links.csv",
    "entry_voids.csv",
)
OBSERVED_END = date(2026, 9, 28)


def load_observed_inputs(folder):
    """Positive filename allowlist, no discovery, profiles, answers or cause labels."""
    folder = Path(folder).resolve()
    paths = {name: folder / name for name in OBSERVED_FILES}
    if any(path.resolve().parent != folder for path in paths.values()):
        raise ValueError("INPUT_OUTSIDE_ALLOWLIST")
    rows = read_csv(paths["observed_90d.csv"])
    if any(date.fromisoformat(r["business_date"]) > OBSERVED_END for r in rows):
        raise ValueError("FUTURE_DATA_REJECTED")
    opening = read_json(paths["opening_balance.json"])
    categories = read_csv(paths["categories.csv"])
    parties = read_csv(paths["counterparties.csv"])
    links = read_csv(paths["payment_links.csv"])
    voids = read_csv(paths["entry_voids.csv"])
    if any(stamp(r["created_at"]) > cutoff(OBSERVED_END) for r in links) or any(
        stamp(r["voided_at"]) > cutoff(OBSERVED_END) for r in voids
    ):
        raise ValueError("FUTURE_KNOWLEDGE_REJECTED")
    return (
        TruthLedger(
            rows, opening=opening, categories=categories, links=links, voids=voids
        ),
        parties,
        {name: sha256(path) for name, path in paths.items()},
    )


def cutoff_history(truth, day):
    """Physically remove later financial/audit records before the app handoff.

    Keep known voids and their immutable originals, rather than projecting a future
    void into an earlier snapshot. Links need both their own and their rows' knowledge.
    """
    known = cutoff(day)
    rows = [
        r
        for r in truth.rows
        if r["business_date"] <= str(day)
        and stamp(r["occurred_at"]) <= known
        and stamp(r["recorded_at"]) <= known
    ]
    ids = {r["transaction_id"] for r in rows}
    return TruthLedger(
        rows,
        opening=truth.opening
        if truth.opening and truth.opening["business_date"] <= str(day)
        else None,
        categories=truth.categories.values(),
        links=[
            r
            for r in truth.links
            if r["payment_transaction_id"] in ids and stamp(r["created_at"]) <= known
        ],
        voids=[
            r
            for r in truth.voids
            if r["transaction_id"] in ids and stamp(r["voided_at"]) <= known
        ],
    )


def production_predictions(history, parties, day):
    """Real production services on validated normalized synthetic records, query-only.

    Preserve canonical allocation/void knowledge instead of re-matching payments at
    the evaluator's later import time. Only the already-cutoff history enters SQLite.
    """
    from app.db.connection import connect_database
    from app.db.migrations import apply_migrations
    from app.db.records import insert_record
    from app.schemas.ledger import (
        Category,
        Counterparty,
        EntryVoid,
        ImportBatch,
        Obligation,
        OpeningBalance,
        PaymentLink,
        RawImportRow,
        Transaction,
    )
    from app.services.business_clock import BusinessClock
    from app.services.errors import FinancialRuleError
    from app.services.financial_queries import (
        QuerySnapshot,
        payment_capacity,
        upcoming_obligations,
    )
    from app.services.forecast import forecast

    # Defense in depth: even an accidental full-history caller is cut again.
    history = cutoff_history(history, day)
    db = connect_database(":memory:")
    try:
        apply_migrations(db)
        batch_id = "FORECAST-EVAL"
        insert_record(
            db,
            ImportBatch(
                import_batch_id=batch_id,
                source_system="synthetic_csv",
                file_sha256="0" * 64,
                imported_at=cutoff(day),
                row_count=len(history.rows) + bool(history.opening),
            ),
        )
        for model, table, values in (
            (Counterparty, "counterparties", parties),
            (Category, "categories", history.categories.values()),
        ):
            for value in values:
                payload = model.model_validate(value).model_dump(mode="json")
                columns = ", ".join(payload)
                slots = ", ".join(f":{key}" for key in payload)
                db.execute(f"INSERT INTO {table} ({columns}) VALUES ({slots})", payload)
        indexed = list(enumerate(history.rows, 1))
        # Origins must exist before payments; preserve actual event/audit times.
        indexed.sort(
            key=lambda pair: (
                pair[1]["type"] in {"CREDIT_COLLECTION", "SUPPLIER_PAYMENT"}
            )
        )
        for index, raw in indexed:
            insert_record(
                db,
                RawImportRow(
                    raw_row_id=f"EVAL-RAW-{index}",
                    import_batch_id=batch_id,
                    source_row=index,
                    row_json=json.dumps(raw, ensure_ascii=False),
                    status="accepted",
                ),
            )
            row = Transaction.model_validate(
                raw | {"import_batch_id": batch_id, "source_row": index}
            )
            insert_record(db, row)
            if row.type in {"CREDIT_SALE", "SUPPLIER_INVOICE"}:
                insert_record(
                    db,
                    Obligation(
                        obligation_id=row.obligation_id,
                        kind="receivable" if row.type == "CREDIT_SALE" else "payable",
                        origin_transaction_id=row.transaction_id,
                        counterparty_id=row.counterparty_id,
                        original_amount_iqd=row.amount_iqd,
                        due_date=row.due_date,
                    ),
                )
        if history.opening:
            index = len(history.rows) + 1
            insert_record(
                db,
                RawImportRow(
                    raw_row_id="EVAL-OPEN",
                    import_batch_id=batch_id,
                    source_row=index,
                    row_json=json.dumps(history.opening),
                    status="accepted",
                ),
            )
            opening = OpeningBalance.model_validate(
                history.opening
                | {
                    "import_batch_id": batch_id,
                    "source_row": index,
                }
            ).model_dump(mode="json")
            columns = ", ".join(opening)
            slots = ", ".join(f":{key}" for key in opening)
            db.execute(
                f"INSERT INTO opening_balances ({columns}) VALUES ({slots})", opening
            )
        for raw in history.voids:
            payload = EntryVoid.model_validate(raw).model_dump(mode="json")
            columns = ", ".join(payload)
            slots = ", ".join(f":{key}" for key in payload)
            db.execute(f"INSERT INTO entry_voids ({columns}) VALUES ({slots})", payload)
        for raw in sorted(history.links, key=lambda r: stamp(r["created_at"])):
            insert_record(db, PaymentLink.model_validate(raw))
        db.commit()
        db.execute("PRAGMA query_only=ON")
        clock = BusinessClock(day)
        snapshot = QuerySnapshot(db, clock=clock, known_at=cutoff(day))
        scenarios = {}
        metadata = None
        for name in ("base", "conservative", "stress"):
            try:
                value = forecast(db, clock=clock, scenario=name)
                # Repeat against the same real repository to verify reproducibility.
                if forecast(db, clock=clock, scenario=name) != value:
                    raise ValueError("NON_REPRODUCIBLE_FORECAST")
                scenarios[name] = value.scenarios[name].model_dump(mode="json")
                metadata = value.model_dump(mode="json", exclude={"scenarios"})
            except FinancialRuleError as exc:
                scenarios[name] = {"error_code": exc.code, "details": exc.details}
        try:
            seven_day = upcoming_obligations(snapshot).model_dump(mode="json")
        except FinancialRuleError as exc:
            seven_day = {"error_code": exc.code}
        thursday = day + timedelta(days=(3 - day.weekday()) % 7 or 7)
        try:
            j1 = payment_capacity(snapshot, thursday).model_dump(mode="json")
        except FinancialRuleError as exc:
            j1 = {"error_code": exc.code}
        if "days" in scenarios["base"] and "days" in scenarios["stress"]:
            for base, stress in zip(
                scenarios["base"]["days"], scenarios["stress"]["days"], strict=True
            ):
                if (
                    stress["collections_iqd"] != 0
                    or stress["closing_iqd"] > base["closing_iqd"]
                ):
                    raise ValueError("INVALID_STRESS_SCENARIO")
                for field in (
                    "cash_sales_iqd",
                    "unlinked_cash_iqd",
                    "supplier_payments_iqd",
                    "expenses_iqd",
                    "owner_drawings_iqd",
                ):
                    if stress[field] != base[field]:
                        raise ValueError("STRESS_CHANGED_NON_COLLECTION_DRIVER")
        return {
            "forecast_metadata": metadata,
            "scenarios": scenarios,
            "seven_day": seven_day,
            "j1": j1,
        }
    finally:
        db.close()
