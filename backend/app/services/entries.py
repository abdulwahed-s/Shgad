"""Validated, atomic merchant entry and partial-payment workflow (§7/§11)."""

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
from uuid import uuid4

from pydantic import ValidationError

from app.db.records import atomic_import, insert_record
from app.schemas.entries import EntryReceipt, EntryRequest
from app.schemas.ledger import (
    EntryCorrection,
    EventType,
    ImportBatch,
    Obligation,
    PaymentLink,
    RawImportRow,
    Transaction,
)
from app.services.business_clock import BusinessClock
from app.services.errors import FinancialRuleError
from app.services.evidence import find_source
from app.services.ingest import _check_references, _payment_match, _RowProblem
from app.services.observed import OBSERVED_START, observed_day
from app.services.validation import BAGHDAD, parse_timestamp

ORIGINS = {EventType.CREDIT_SALE, EventType.SUPPLIER_INVOICE}
PAYMENTS = {EventType.CREDIT_COLLECTION, EventType.SUPPLIER_PAYMENT}


def create_entry(
    connection: sqlite3.Connection,
    request: EntryRequest,
    *,
    clock: BusinessClock,
    recorded_at: datetime | str,
) -> EntryReceipt:
    request = EntryRequest.model_validate(request)
    today = observed_day(clock)
    if not OBSERVED_START <= request.business_date <= today:
        raise FinancialRuleError(
            "VALIDATION_ERROR", details={"reason": "OUTSIDE_OBSERVED_DATA"}
        )
    audit = parse_timestamp(recorded_at)
    raw = json.dumps(
        request.model_dump(mode="json"), ensure_ascii=False, sort_keys=True
    )
    with atomic_import(connection):
        prior = connection.execute(
            """SELECT t.*, r.row_json FROM transactions t JOIN raw_import_rows r
            ON r.import_batch_id = t.import_batch_id AND r.source_row = t.source_row
            WHERE t.client_entry_id = ?""",
            (request.client_entry_id,),
        ).fetchone()
        if prior:
            if (
                prior["source"] != "manual_entry"
                or EntryRequest.model_validate_json(prior["row_json"]) != request
            ):
                raise FinancialRuleError(
                    "VALIDATION_ERROR", details={"reason": "IDEMPOTENCY_CONFLICT"}
                )
            return EntryReceipt(
                transaction_id=prior["transaction_id"],
                source_id=prior["source_id"],
                duplicate=True,
            )
        if connection.execute(
            "SELECT 1 FROM difference_reviews WHERE client_entry_id = ?",
            (request.client_entry_id,),
        ).fetchone():
            raise FinancialRuleError(
                "VALIDATION_ERROR", details={"reason": "IDEMPOTENCY_CONFLICT"}
            )
        token = uuid4().hex
        source_id, batch_id = f"ENT-{token}", f"ENTRY-BATCH-{token}"
        obligation_id = request.obligation_id
        if request.type in ORIGINS and obligation_id is None:
            obligation_id = f"OB-{token}"
        # The request supplies a business date, never a model-computed timestamp.
        # Within that date retain request ordering through the boundary audit time.
        occurred = datetime.combine(
            request.business_date, audit.astimezone(BAGHDAD).timetz()
        )
        latest = connection.execute(
            """SELECT MAX(occurred_at) FROM transactions WHERE business_date = ?
            AND occurred_at <= ? AND recorded_at <= ?""",
            (request.business_date.isoformat(), audit.isoformat(), audit.isoformat()),
        ).fetchone()[0]
        if (
            request.correction_of_source_id is None
            and latest is not None
            and parse_timestamp(latest) >= occurred
        ):
            occurred = min(parse_timestamp(latest) + timedelta(microseconds=1), audit)
            if occurred.astimezone(BAGHDAD).date() != request.business_date:
                raise FinancialRuleError(
                    "VALIDATION_ERROR", details={"reason": "BUSINESS_DAY_FULL"}
                )
        original = None
        if request.correction_of_source_id is not None:
            original = find_source(
                connection, request.correction_of_source_id, clock=clock, known_at=audit
            )
            if not connection.execute(
                "SELECT 1 FROM entry_voids WHERE transaction_id = ? AND voided_at <= ?",
                (original.transaction_id, audit.isoformat()),
            ).fetchone():
                raise FinancialRuleError(
                    "VALIDATION_ERROR", details={"reason": "CORRECTION_REQUIRES_VOID"}
                )
            if request.business_date != original.business_date:
                raise FinancialRuleError(
                    "VALIDATION_ERROR", details={"reason": "CORRECTION_DATE_MISMATCH"}
                )
            if connection.execute(
                "SELECT 1 FROM entry_corrections WHERE original_transaction_id = ?",
                (original.transaction_id,),
            ).fetchone():
                raise FinancialRuleError(
                    "VALIDATION_ERROR", details={"reason": "ALREADY_CORRECTED"}
                )
            occurred = original.occurred_at
        try:
            row = Transaction(
                transaction_id=source_id,
                source_id=source_id,
                source_system="synthetic_entry",
                source="manual_entry",
                client_entry_id=request.client_entry_id,
                source_row=1,
                import_batch_id=batch_id,
                occurred_at=occurred,
                recorded_at=audit,
                type=request.type,
                amount_iqd=request.amount_iqd,
                counterparty_id=request.counterparty_id,
                obligation_id=obligation_id,
                due_date=request.due_date,
                description=request.note or "",
                idempotency_key=f"manual_entry:{request.client_entry_id}",
            )
            _check_references(connection, row)
        except (ValidationError, _RowProblem) as exc:
            raise FinancialRuleError(
                "VALIDATION_ERROR", details={"reason": "INVALID_REFERENCE_OR_EVENT"}
            ) from exc
        if audit < occurred:
            raise FinancialRuleError(
                "VALIDATION_ERROR", details={"reason": "INVALID_DATE"}
            )
        if (
            row.type == EventType.DAILY_CASH_COUNT
            and connection.execute(
                """SELECT 1 FROM transactions t WHERE t.business_date = ?
            AND t.type = 'DAILY_CASH_COUNT' AND t.recorded_at <= ?
            AND NOT EXISTS (SELECT 1 FROM entry_voids v WHERE
            v.transaction_id = t.transaction_id AND v.voided_at <= ?)""",
                (
                    request.business_date.isoformat(),
                    audit.isoformat(),
                    audit.isoformat(),
                ),
            ).fetchone()
        ):
            raise FinancialRuleError(
                "VALIDATION_ERROR", details={"reason": "EXISTING_CASH_COUNT"}
            )
        if row.type in PAYMENTS:
            match = _payment_match(connection, row, audit, clock=clock)
            if match.reason_key is not None or match.obligation_id is None:
                raise FinancialRuleError(
                    "VALIDATION_ERROR",
                    details={
                        "reason": "OVERPAYMENT"
                        if match.reason_key == "payment_exceeds_outstanding"
                        else "INVALID_REFERENCE"
                    },
                )
        insert_record(
            connection,
            ImportBatch(
                import_batch_id=batch_id,
                source_system="synthetic_entry",
                file_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                imported_at=audit,
                row_count=1,
                accepted_count=1,
                status="completed",
            ),
        )
        insert_record(
            connection,
            RawImportRow(
                raw_row_id=f"ENTRY-RAW-{token}",
                import_batch_id=batch_id,
                source_row=1,
                row_json=raw,
                status="accepted",
            ),
        )
        insert_record(connection, row)
        if row.type in ORIGINS:
            insert_record(
                connection,
                Obligation(
                    obligation_id=obligation_id,
                    kind="receivable"
                    if row.type == EventType.CREDIT_SALE
                    else "payable",
                    origin_transaction_id=row.transaction_id,
                    counterparty_id=row.counterparty_id,
                    original_amount_iqd=row.amount_iqd,
                    due_date=row.due_date,
                ),
            )
        if row.type in PAYMENTS:
            insert_record(
                connection,
                PaymentLink(
                    payment_link_id=f"LINK-{token}",
                    payment_transaction_id=row.transaction_id,
                    obligation_id=obligation_id,
                    amount_iqd=row.amount_iqd,
                    match_basis="definite",
                    created_at=audit,
                ),
            )
        if original is not None:
            insert_record(
                connection,
                EntryCorrection(
                    original_transaction_id=original.transaction_id,
                    replacement_transaction_id=row.transaction_id,
                    created_at=audit,
                ),
            )
        return EntryReceipt(transaction_id=row.transaction_id, source_id=row.source_id)
