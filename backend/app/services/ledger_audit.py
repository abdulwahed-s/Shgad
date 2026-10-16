"""Merchant audit domain writes only; no HTTP/importer or agent write tools.

FINANCIAL_RULES §3/§11. Audit timestamps come from the caller, never the business
clock or a host-date fallback. Every source fact and audit record is append-only.
"""

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from uuid import uuid4

from app.schemas.ledger import (
    DifferenceResolution,
    DifferenceReview,
    DifferenceReviewRequest,
    EntryVoid,
    EventType,
    ImportBatch,
    LedgerModel,
    Obligation,
    PaymentLink,
    RawImportRow,
    Transaction,
    VoidRequest,
)
from app.services.errors import FinancialRuleError
from app.services.ledger_rules import DailyClose, daily_close
from app.services.validation import parse_business_date, parse_timestamp


@dataclass(frozen=True)
class LedgerSnapshot:
    transactions: tuple[Transaction, ...]
    obligations: tuple[Obligation, ...]
    payment_links: tuple[PaymentLink, ...]
    voids: tuple[EntryVoid, ...]
    reviews: tuple[DifferenceReview, ...]


@dataclass(frozen=True)
class ReviewResult:
    entry: Transaction | None
    review: DifferenceReview
    daily_close: DailyClose
    duplicate: bool


@dataclass(frozen=True)
class VoidResult:
    audit: EntryVoid
    duplicate: bool


_TABLES = {
    Transaction: "transactions",
    Obligation: "obligations",
    PaymentLink: "payment_links",
    EntryVoid: "entry_voids",
    DifferenceReview: "difference_reviews",
    ImportBatch: "import_batches",
    RawImportRow: "raw_import_rows",
}


def _records(connection: sqlite3.Connection, model):
    # Identifiers are a closed application allowlist; values use SQL parameters.
    return tuple(
        model.model_validate(dict(row))
        for row in connection.execute(f"SELECT * FROM {_TABLES[model]} ORDER BY rowid")
    )


def read_ledger(connection: sqlite3.Connection) -> LedgerSnapshot:
    """Retain original evidence; consumers apply the same explicit cutoff filters."""
    # A savepoint gives all table reads one SQLite snapshot, also within a
    # caller's transaction. It does not acquire a write lock or commit caller work.
    connection.execute("SAVEPOINT ledger_snapshot_read")
    try:
        snapshot = LedgerSnapshot(
            transactions=_records(connection, Transaction),
            obligations=_records(connection, Obligation),
            payment_links=_records(connection, PaymentLink),
            voids=_records(connection, EntryVoid),
            reviews=_records(connection, DifferenceReview),
        )
    except BaseException:
        connection.execute("ROLLBACK TO SAVEPOINT ledger_snapshot_read")
        raise
    finally:
        connection.execute("RELEASE SAVEPOINT ledger_snapshot_read")
    return snapshot


def _insert(connection: sqlite3.Connection, record: LedgerModel) -> None:
    payload = record.model_dump(mode="json")
    columns = ", ".join(payload)
    placeholders = ", ".join(f":{key}" for key in payload)
    connection.execute(
        f"INSERT INTO {_TABLES[type(record)]} ({columns}) VALUES ({placeholders})",
        payload,
    )


@contextmanager
def _atomic(connection: sqlite3.Connection) -> Iterator[None]:
    nested = connection.in_transaction
    connection.execute("SAVEPOINT ledger_audit_write" if nested else "BEGIN IMMEDIATE")
    try:
        yield
        if nested:
            connection.execute("RELEASE SAVEPOINT ledger_audit_write")
        else:
            connection.commit()
    except BaseException:
        if nested:
            connection.execute("ROLLBACK TO SAVEPOINT ledger_audit_write")
            connection.execute("RELEASE SAVEPOINT ledger_audit_write")
        else:
            connection.rollback()
        raise


def _close(
    connection: sqlite3.Connection, day: date, audit_time: datetime
) -> DailyClose:
    snapshot = read_ledger(connection)
    return daily_close(
        snapshot.transactions,
        business_date=day,
        voids=snapshot.voids,
        known_at=audit_time,
    )


def _create_review_entry(
    connection: sqlite3.Connection,
    request: DifferenceReviewRequest,
    closing: Transaction,
    audit_time: datetime,
) -> Transaction:
    event_types = {
        DifferenceResolution.CASH_SALE_UNITEMIZED: EventType.CASH_SALE,
        DifferenceResolution.CAPITAL_INJECTION: EventType.CAPITAL_INJECTION,
        DifferenceResolution.EXPENSE_UNRECORDED: EventType.OPERATING_EXPENSE,
        DifferenceResolution.OWNER_DRAWING_UNRECORDED: EventType.OWNER_DRAWING,
    }
    token = uuid4().hex
    batch_id, source_id = f"REVIEW-BATCH-{token}", f"ENT-{token}"
    # Preserve the confirmed request as data, including its untrusted note.
    raw = json.dumps(
        request.model_dump(mode="json")
        | {"business_date": closing.business_date.isoformat()},
        ensure_ascii=False,
        sort_keys=True,
    )
    _insert(
        connection,
        ImportBatch(
            import_batch_id=batch_id,
            source_system="synthetic_entry",
            file_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            imported_at=audit_time,
            row_count=1,
            accepted_count=1,
            status="completed",
        ),
    )
    _insert(
        connection,
        RawImportRow(
            raw_row_id=f"REVIEW-RAW-{token}",
            import_batch_id=batch_id,
            source_row=1,
            row_json=raw,
            status="accepted",
        ),
    )
    row = Transaction(
        transaction_id=source_id,
        source_id=source_id,
        source_system="synthetic_entry",
        source="daily_close_review",
        client_entry_id=request.client_entry_id,
        source_row=1,
        import_batch_id=batch_id,
        # The physical count includes the explained flow already.
        occurred_at=closing.occurred_at,
        recorded_at=audit_time,
        type=event_types[request.resolution],
        amount_iqd=request.amount_iqd,
        description=request.note or "",
        idempotency_key=f"daily_close_review:{request.client_entry_id}",
    )
    _insert(connection, row)
    return row


def resolve_difference(
    connection: sqlite3.Connection,
    request: DifferenceReviewRequest,
    *,
    business_date: date,
    recorded_at: datetime | str,
) -> ReviewResult:
    request = DifferenceReviewRequest.model_validate(request)
    day, audit_time = parse_business_date(business_date), parse_timestamp(recorded_at)
    with _atomic(connection):
        existing = connection.execute(
            "SELECT * FROM difference_reviews WHERE client_entry_id = ?",
            (request.client_entry_id,),
        ).fetchone()
        if existing is not None:
            review = DifferenceReview.model_validate(dict(existing))
            if (
                any(
                    getattr(review, key) != value
                    for key, value in request.model_dump().items()
                )
                or review.business_date != day
            ):
                raise FinancialRuleError(
                    "VALIDATION_ERROR", details={"reason": "IDEMPOTENCY_CONFLICT"}
                )
            entry = connection.execute(
                "SELECT * FROM transactions WHERE transaction_id = ?",
                (review.transaction_id,),
            ).fetchone()
            return ReviewResult(
                Transaction.model_validate(dict(entry)) if entry else None,
                review,
                _close(connection, day, audit_time),
                True,
            )
        close = _close(connection, day, audit_time)
        remaining = close.unexplained_difference_iqd
        if remaining is None:
            raise FinancialRuleError("MISSING_COUNT")
        entry = None
        if request.resolution != DifferenceResolution.LEAVE_UNEXPLAINED:
            positive = request.resolution in {
                DifferenceResolution.CASH_SALE_UNITEMIZED,
                DifferenceResolution.CAPITAL_INJECTION,
            }
            if remaining != 0 and (remaining > 0) != positive:
                raise FinancialRuleError("DIFFERENCE_SIGN_MISMATCH")
            if request.amount_iqd > abs(remaining):
                raise FinancialRuleError("DIFFERENCE_EXCEEDED")
            closing_row = connection.execute(
                "SELECT * FROM transactions WHERE transaction_id = ?",
                (close.closing_count_transaction_id,),
            ).fetchone()
            entry = _create_review_entry(
                connection,
                request,
                Transaction.model_validate(dict(closing_row)),
                audit_time,
            )
        review = DifferenceReview(
            **request.model_dump(),
            review_id=f"REVIEW-{uuid4().hex}",
            business_date=day,
            created_at=audit_time,
            previous_count_transaction_id=close.previous_count_transaction_id,
            closing_count_transaction_id=close.closing_count_transaction_id,
            transaction_id=entry.transaction_id if entry else None,
        )
        _insert(connection, review)
        return ReviewResult(entry, review, _close(connection, day, audit_time), False)


def void_entry(
    connection: sqlite3.Connection,
    request: VoidRequest,
    *,
    transaction_id: str,
    voided_at: datetime | str,
) -> VoidResult:
    request = VoidRequest.model_validate(request)
    audit_time = parse_timestamp(voided_at)
    with _atomic(connection):
        prior = connection.execute(
            "SELECT * FROM entry_voids WHERE client_entry_id = ?",
            (request.client_entry_id,),
        ).fetchone()
        if prior is not None:
            audit = EntryVoid.model_validate(dict(prior))
            if audit.transaction_id != transaction_id or audit.reason != request.reason:
                raise FinancialRuleError(
                    "VALIDATION_ERROR", details={"reason": "IDEMPOTENCY_CONFLICT"}
                )
            return VoidResult(audit, True)
        original = connection.execute(
            "SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)
        ).fetchone()
        if original is None:
            raise FinancialRuleError("NOT_FOUND")
        transaction = Transaction.model_validate(dict(original))
        if audit_time < max(transaction.occurred_at, transaction.recorded_at):
            raise FinancialRuleError(
                "VALIDATION_ERROR", details={"reason": "VOID_PRECEDES_ENTRY"}
            )
        if connection.execute(
            "SELECT 1 FROM entry_voids WHERE transaction_id = ?", (transaction_id,)
        ).fetchone():
            raise FinancialRuleError(
                "VALIDATION_ERROR", details={"reason": "ALREADY_VOIDED"}
            )
        audit = EntryVoid(
            **request.model_dump(),
            void_id=f"VOID-{uuid4().hex}",
            transaction_id=transaction_id,
            source_id=transaction.source_id,
            voided_at=audit_time,
        )
        _insert(connection, audit)
        return VoidResult(audit, False)
