"""Read-only, cutoff-bounded ledger evidence with stable filtered pagination."""

import base64
import hashlib
import json
from datetime import date, datetime

from app.schemas.evidence import (
    CounterpartyView,
    FlagView,
    LedgerDetail,
    LedgerItem,
    LedgerPage,
    VoidEvidence,
)
from app.schemas.forecast import Amount
from app.schemas.ledger import Transaction
from app.services.business_clock import BusinessClock
from app.services.errors import FinancialRuleError
from app.services.observed import OBSERVED_START, observed_day
from app.services.reconcile import reconciliation_report
from app.services.validation import SQLITE_MAX_INTEGER, parse_timestamp


def find_source(
    connection, source_id: str, *, clock: BusinessClock, known_at: datetime
) -> Transaction:
    rows = connection.execute(
        """SELECT * FROM transactions WHERE source_id = ?
        AND business_date BETWEEN ? AND ?
        AND occurred_at <= ? AND recorded_at <= ? LIMIT 2""",
        (
            source_id,
            OBSERVED_START.isoformat(),
            observed_day(clock).isoformat(),
            known_at.isoformat(),
            known_at.isoformat(),
        ),
    ).fetchall()
    if not rows:
        raise FinancialRuleError("NOT_FOUND")
    if len(rows) > 1:
        raise FinancialRuleError(
            "VALIDATION_ERROR", details={"reason": "AMBIGUOUS_SOURCE_ID"}
        )
    return Transaction.model_validate(dict(rows[0]))


def project_item(connection, row: Transaction, *, known_at: datetime) -> LedgerItem:
    party = connection.execute(
        "SELECT * FROM counterparties WHERE counterparty_id = ?", (row.counterparty_id,)
    ).fetchone()
    void = connection.execute(
        "SELECT * FROM entry_voids WHERE transaction_id = ? AND voided_at <= ?",
        (row.transaction_id, known_at.isoformat()),
    ).fetchone()
    correction = connection.execute(
        """SELECT original.source_id FROM entry_corrections c JOIN transactions original
        ON original.transaction_id = c.original_transaction_id
        WHERE c.replacement_transaction_id = ? AND c.created_at <= ?""",
        (row.transaction_id, known_at.isoformat()),
    ).fetchone()
    return LedgerItem(
        source_id=row.source_id,
        occurred_at=row.occurred_at,
        business_date=row.business_date,
        type=row.type,
        amount_iqd=row.amount_iqd,
        counterparty=CounterpartyView(
            id=party["counterparty_id"], display_name=party["display_name"]
        )
        if party
        else None,
        obligation_id=row.obligation_id,
        category_id=row.category_id,
        quantity=row.quantity,
        status="voided" if void else row.status,
        import_batch_id=row.import_batch_id,
        source=row.source,
        description=row.description,
        void=VoidEvidence(**{k: void[k] for k in ("void_id", "reason", "voided_at")})
        if void
        else None,
        correction_of_source_id=correction[0] if correction else None,
    )


def transaction_detail(connection, source_id, *, clock, known_at) -> LedgerDetail:
    known = parse_timestamp(known_at)
    connection.execute("SAVEPOINT evidence_detail")
    try:
        row = find_source(connection, source_id, clock=clock, known_at=known)
        item = project_item(connection, row, known_at=known)
        raw = connection.execute(
            """SELECT row_json FROM raw_import_rows
            WHERE import_batch_id = ? AND source_row = ?""",
            (row.import_batch_id, row.source_row),
        ).fetchone()
        flags = tuple(
            FlagView(
                flag_id=f["flag_id"],
                type=f["type"],
                reason_key=f["reason_key"],
                amount=Amount(
                    amount_iqd=f["amount_iqd"],
                    kind="missing" if f["amount_iqd"] is None else "flagged",
                    label_key="reconciliation_amount",
                    source_ids=(row.source_id,),
                    formula="recorded source amount",
                ),
                source_ids=(row.source_id,),
                confidence_basis=f["confidence_basis"],
                next_step_key=f["next_step_key"],
            )
            for f in connection.execute(
                """SELECT * FROM reconciliation_flags
                WHERE transaction_id = ? ORDER BY flag_id""",
                (row.transaction_id,),
            )
        )
        current_flags = tuple(
            flag
            for flag in reconciliation_report(
                connection,
                clock=clock,
                known_at=known,
            ).flags
            if row.source_id in flag.source_ids
        )
        current_reasons = {flag.reason_key for flag in current_flags}
        flags = current_flags + tuple(
            flag for flag in flags if flag.reason_key not in current_reasons
        )
        return LedgerDetail(
            **item.model_dump(), raw_row=json.loads(raw[0]), flags=flags
        )
    finally:
        connection.execute("RELEASE SAVEPOINT evidence_detail")


def transaction_page(
    connection,
    *,
    clock,
    known_at,
    start: date | None = None,
    end: date | None = None,
    event_type=None,
    counterparty_id=None,
    ids=None,
    limit=50,
    cursor=None,
) -> LedgerPage:
    today, known = observed_day(clock), parse_timestamp(known_at)
    start, end = start or OBSERVED_START, end or today
    if not OBSERVED_START <= start <= end <= today or not 1 <= limit <= 200:
        raise FinancialRuleError("VALIDATION_ERROR")
    selected = ids.split(",") if ids is not None else []
    if ids is not None and (not all(selected) or len(selected) > 200):
        raise FinancialRuleError("VALIDATION_ERROR")
    identity = hashlib.sha256(
        json.dumps(
            [str(start), str(end), event_type, counterparty_id, selected],
            sort_keys=True,
        ).encode()
    ).hexdigest()
    after = 0
    if cursor is not None:
        try:
            if len(cursor) > 2000:
                raise ValueError
            decoded = json.loads(base64.urlsafe_b64decode(cursor.encode()))
            previous_known = parse_timestamp(decoded["known"])
            if (
                decoded["filters"] != identity
                or decoded["day"] != str(today)
                or type(decoded["after"]) is not int
                or not 0 <= decoded["after"] <= SQLITE_MAX_INTEGER
                or previous_known > known
            ):
                raise ValueError
            after, known = decoded["after"], previous_known
        except (ValueError, KeyError, TypeError, UnicodeError) as exc:
            raise FinancialRuleError(
                "VALIDATION_ERROR", details={"reason": "INVALID_CURSOR"}
            ) from exc
    clauses = [
        "t.business_date BETWEEN ? AND ?",
        "t.occurred_at <= ?",
        "t.recorded_at <= ?",
        "t.rowid > ?",
    ]
    params = [str(start), str(end), known.isoformat(), known.isoformat(), after]
    if event_type is not None:
        clauses.append("t.type = ?")
        params.append(event_type)
    if counterparty_id is not None:
        clauses.append("t.counterparty_id = ?")
        params.append(counterparty_id)
    if selected:
        clauses.append("t.source_id IN (" + ",".join("?" for _ in selected) + ")")
        params.extend(selected)
    connection.execute("SAVEPOINT evidence_page")
    try:
        rows = connection.execute(
            "SELECT t.rowid AS position, t.* FROM transactions t WHERE "
            + " AND ".join(clauses)
            + " ORDER BY t.rowid LIMIT ?",
            [*params, limit + 1],
        ).fetchall()
        next_cursor = None
        if len(rows) > limit:
            next_cursor = base64.urlsafe_b64encode(
                json.dumps(
                    {
                        "after": rows[limit - 1]["position"],
                        "filters": identity,
                        "day": str(today),
                        "known": known.isoformat(),
                    }
                ).encode()
            ).decode()
        items = tuple(
            project_item(
                connection,
                Transaction.model_validate({k: r[k] for k in Transaction.model_fields}),
                known_at=known,
            )
            for r in rows[:limit]
        )
        return LedgerPage(items=items, next_cursor=next_cursor)
    finally:
        connection.execute("RELEASE SAVEPOINT evidence_page")
