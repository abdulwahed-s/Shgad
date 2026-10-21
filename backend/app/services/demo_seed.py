"""Restore only the fictional observed snapshot; never import evaluation code/data.

The scratch database preserves canonical event/allocation/void knowledge times.
It is validated completely before SQLite backup replaces the demo database.
Individual merchant edits still use immutable void/correction endpoints.
"""

import csv
import hashlib
import io
import json
from collections import defaultdict
from pathlib import Path

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
    ReconciliationFlag,
    Transaction,
)
from app.services.errors import FinancialRuleError
from app.services.ledger_rules import knowledge_cutoff
from app.services.observed import OBSERVED_END, OBSERVED_START, observed_day
from app.services.validation import parse_iqd, parse_timestamp

_ROOT = Path(__file__).resolve().parents[3] / "data" / "synthetic"
_FILES = (
    "observed_90d.csv",
    "opening_balance.json",
    "categories.csv",
    "counterparties.csv",
    "payment_links.csv",
    "entry_voids.csv",
)
_NULLABLE = frozenset(
    {
        "recorded_at",
        "client_entry_id",
        "counterparty_id",
        "obligation_id",
        "due_date",
        "category_id",
        "quantity",
        "buy_price_iqd",
        "sell_price_iqd",
    }
)
_MONEY = frozenset({"amount_iqd", "buy_price_iqd", "sell_price_iqd"})


def _typed(row):
    result = {}
    for key, value in row.items():
        if value == "" and key in _NULLABLE:
            result[key] = None
        elif key in _MONEY:
            result[key] = parse_iqd(value, allow_zero=True)
        elif key in {"source_row", "quantity"}:
            result[key] = int(value)
        else:
            result[key] = value
    return result


def _reference(db, table, record):
    # Table names are supplied only by the closed calls in this module.
    payload = record.model_dump(mode="json")
    columns = ", ".join(payload)
    slots = ", ".join(":" + key for key in payload)
    db.execute(f"INSERT INTO {table} ({columns}) VALUES ({slots})", payload)


def restore_demo(destination, *, clock):
    day = observed_day(clock)
    known = parse_timestamp(knowledge_cutoff(day))
    folder = _ROOT.resolve()
    contents = {}
    for name in _FILES:
        path = folder / name
        if path.resolve().parent != folder:
            raise FinancialRuleError("IMPORT_REJECTED")
        contents[name] = path.read_bytes()
    csv_rows = {
        name: list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
        for name, content in contents.items()
        if name.endswith(".csv")
    }
    rows = [
        Transaction.model_validate(_typed(raw)) for raw in csv_rows["observed_90d.csv"]
    ]
    if any(not OBSERVED_START <= row.business_date <= OBSERVED_END for row in rows):
        raise FinancialRuleError("IMPORT_REJECTED")
    rows = [
        row
        for row in rows
        if row.business_date <= day
        and row.occurred_at <= known
        and row.recorded_at <= known
    ]
    raw_by_id = {raw["transaction_id"]: raw for raw in csv_rows["observed_90d.csv"]}
    opening = OpeningBalance.model_validate(
        json.loads(contents["opening_balance.json"])
    )
    groups = defaultdict(list)
    for row in rows:
        groups[row.import_batch_id].append(row)
    if opening.business_date <= day:
        groups[opening.import_batch_id].append(opening)
    scratch = connect_database(":memory:")
    try:
        apply_migrations(scratch)
        with scratch:
            for model, table, name in [
                (Counterparty, "counterparties", "counterparties.csv"),
                (Category, "categories", "categories.csv"),
            ]:
                for raw in csv_rows[name]:
                    _reference(scratch, table, model.model_validate(_typed(raw)))
            for batch_id, records in groups.items():
                filename = (
                    "opening_balance.json"
                    if isinstance(records[0], OpeningBalance)
                    else "observed_90d.csv"
                )
                earliest = min(
                    (
                        row.recorded_at
                        for row in records
                        if isinstance(row, Transaction)
                    ),
                    default=None,
                )
                imported_at = earliest or f"{opening.business_date}T00:00:00+03:00"
                insert_record(
                    scratch,
                    ImportBatch(
                        import_batch_id=batch_id,
                        source_system="synthetic_csv",
                        file_sha256=hashlib.sha256(contents[filename]).hexdigest(),
                        imported_at=imported_at,
                        row_count=len(records),
                    ),
                )
            # Origins precede payment references; event/audit timestamps are unchanged.
            for row in sorted(
                rows,
                key=lambda row: row.type in {"CREDIT_COLLECTION", "SUPPLIER_PAYMENT"},
            ):
                raw_id = f"{row.transaction_id}-RAW"
                near = scratch.execute(
                    """SELECT 1 FROM transactions WHERE type=?
                    AND amount_iqd=? AND counterparty_id IS ?
                    AND business_date=? LIMIT 1""",
                    (
                        row.type,
                        row.amount_iqd,
                        row.counterparty_id,
                        str(row.business_date),
                    ),
                ).fetchone()
                insert_record(
                    scratch,
                    RawImportRow(
                        raw_row_id=raw_id,
                        import_batch_id=row.import_batch_id,
                        source_row=row.source_row,
                        row_json=json.dumps(
                            raw_by_id[row.transaction_id], ensure_ascii=False
                        ),
                        status="flagged" if row.status == "flagged" else "accepted",
                    ),
                )
                insert_record(scratch, row)
                if row.type in {"CREDIT_SALE", "SUPPLIER_INVOICE"}:
                    insert_record(
                        scratch,
                        Obligation(
                            obligation_id=row.obligation_id,
                            kind="receivable"
                            if row.type == "CREDIT_SALE"
                            else "payable",
                            origin_transaction_id=row.transaction_id,
                            counterparty_id=row.counterparty_id,
                            original_amount_iqd=row.amount_iqd,
                            due_date=row.due_date,
                        ),
                    )
                if near:
                    insert_record(
                        scratch,
                        ReconciliationFlag(
                            flag_id=f"{row.transaction_id}-DUP",
                            type="suspected_duplicate",
                            reason_key="suspected_duplicate",
                            amount_iqd=row.amount_iqd,
                            transaction_id=row.transaction_id,
                            raw_row_id=raw_id,
                            confidence_basis="same_amount_party_day",
                        ),
                    )
            if opening.business_date <= day:
                insert_record(
                    scratch,
                    RawImportRow(
                        raw_row_id="DEMO-OPEN-RAW",
                        import_batch_id=opening.import_batch_id,
                        source_row=opening.source_row,
                        row_json=json.dumps(
                            json.loads(contents["opening_balance.json"])
                        ),
                        status="accepted",
                    ),
                )
                _reference(scratch, "opening_balances", opening)
            ids = {row.transaction_id for row in rows}
            for raw in csv_rows["payment_links.csv"]:
                link = PaymentLink.model_validate(_typed(raw))
                if link.payment_transaction_id in ids and link.created_at <= known:
                    insert_record(scratch, link)
            for raw in csv_rows["entry_voids.csv"]:
                void = EntryVoid.model_validate(_typed(raw))
                if void.transaction_id in ids and void.voided_at <= known:
                    _reference(scratch, "entry_voids", void)
            for batch_id, records in groups.items():
                flagged = sum(
                    isinstance(row, Transaction) and row.status == "flagged"
                    for row in records
                )
                scratch.execute(
                    """UPDATE import_batches SET accepted_count=?,flagged_count=?,
                    status='completed' WHERE import_batch_id=?""",
                    (len(records) - flagged, flagged, batch_id),
                )
        if scratch.execute("PRAGMA foreign_key_check").fetchall():
            raise FinancialRuleError("IMPORT_REJECTED")
        if destination.in_transaction:
            raise FinancialRuleError("INTERNAL")
        scratch.backup(destination)
    finally:
        scratch.close()
