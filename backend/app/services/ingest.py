"""Real canonical synthetic CSV import: roadmap §7.1, FINANCIAL_RULES §10.

Verified rows and quarantined evidence commit together. Exact replays never add
financial rows; database uniqueness remains the final authority under contention.
There is no mapping/model call, supporting-file discovery, or runtime answer input.
"""

import csv
import hashlib
import io
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from app.db.records import atomic_import, insert_record
from app.schemas.imports import ImportErrorDetail, ImportReceipt
from app.schemas.ledger import (
    EventType,
    ImportBatch,
    Obligation,
    PaymentLink,
    RawImportRow,
    ReconciliationFlag,
    Transaction,
)
from app.services.business_clock import BusinessClock
from app.services.errors import FinancialRuleError
from app.services.import_limits import bounded_import, checkpoint
from app.services.ledger_rules import knowledge_cutoff
from app.services.observed import OBSERVED_START, observed_day
from app.services.reconcile import match_payment
from app.services.validation import parse_iqd, parse_timestamp

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10000
_DATA_ROOT = Path(__file__).resolve().parents[3] / "data"
_FIXTURES = frozenset(
    {
        "small_happy_path.csv",
        "duplicate_rows.csv",
        "overlapping_exports.csv",
        "bad_dates_and_amounts.csv",
        "ambiguous_customers.csv",
        "malicious_descriptions.csv",
        "three_instalments_void.csv",
        "cash_difference_review.csv",
        "seven_day_overdue.csv",
        "missing_costs.csv",
        "missing_opening_balance.csv",
        "unmatched_payment.csv",
    }
)
_REQUIRED = frozenset(
    {
        "source_id",
        "occurred_at",
        "type",
        "amount_iqd",
        "counterparty_id",
        "obligation_id",
        "due_date",
        "category_id",
        "quantity",
        "description",
    }
)
_ALLOWED = frozenset(Transaction.model_fields) | {"currency"}
_IDENTITY = (
    "source_id",
    "source_system",
    "occurred_at",
    "type",
    "amount_iqd",
    "counterparty_id",
    "obligation_id",
    "due_date",
    "category_id",
    "quantity",
    "description",
)
_PAYMENTS = {EventType.CREDIT_COLLECTION, EventType.SUPPLIER_PAYMENT}
_ORIGINS = {EventType.CREDIT_SALE, EventType.SUPPLIER_INVOICE}


@dataclass(frozen=True)
class _RowProblem(Exception):
    code: str
    field: str | None = None


def _file_rows(path: Path) -> tuple[str, list[dict[str, str]]]:
    path = path.resolve()
    # Positive packaged-file allowlist, checked before opening even one byte.
    data_root = _DATA_ROOT.resolve()
    if path.is_relative_to(data_root) and not (
        path == data_root / "synthetic" / "observed_90d.csv"
        or (path.parent == data_root / "fixtures" and path.name in _FIXTURES)
    ):
        raise FinancialRuleError(
            "IMPORT_REJECTED", details={"reason": "UNAPPROVED_INPUT"}
        )
    if path.suffix.lower() != ".csv":
        raise FinancialRuleError("IMPORT_REJECTED", details={"reason": "FILE_TYPE"})
    try:
        with path.open("rb") as stream:
            content = stream.read(MAX_FILE_BYTES + 1)
        return _csv_rows(content)
    except OSError as exc:
        raise FinancialRuleError(
            "IMPORT_REJECTED", details={"reason": "INVALID_FILE"}
        ) from exc


def _csv_rows(content: bytes) -> tuple[str, list[dict[str, str]]]:
    header, rows = read_csv_content(content)
    if not _REQUIRED <= set(header) <= _ALLOWED:
        raise FinancialRuleError("IMPORT_REJECTED", details={"reason": "CSV_COLUMNS"})
    return hashlib.sha256(content).hexdigest(), rows


@bounded_import
def read_csv_content(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Bounded strict CSV decoding shared by canonical import and mapping."""
    if len(content) > MAX_FILE_BYTES:
        raise FinancialRuleError("IMPORT_REJECTED", details={"reason": "FILE_SIZE"})
    try:
        decoded = content.decode("utf-8-sig")
        if any(ord(c) < 32 and c not in "\t\r\n" for c in decoded):
            raise FinancialRuleError(
                "IMPORT_REJECTED", details={"reason": "INVALID_FILE"}
            )
        if decoded.lstrip().startswith(("<", "{", "[", "PK\x03")):
            raise FinancialRuleError(
                "IMPORT_REJECTED", details={"reason": "INVALID_FILE"}
            )
        reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
        header = next(reader)
        if (
            not header
            or len(header) > 200
            or not all(header)
            or len(header) != len(set(header))
        ):
            raise FinancialRuleError(
                "IMPORT_REJECTED", details={"reason": "CSV_COLUMNS"}
            )
        rows = []
        for cells in reader:
            checkpoint()
            if len(cells) != len(header):
                raise FinancialRuleError(
                    "IMPORT_REJECTED", details={"reason": "CSV_COLUMNS"}
                )
            rows.append(dict(zip(header, cells, strict=True)))
            if len(rows) > MAX_ROWS:
                raise FinancialRuleError(
                    "IMPORT_REJECTED", details={"reason": "ROW_LIMIT"}
                )
        return header, rows
    except (OSError, UnicodeError, csv.Error, StopIteration) as exc:
        raise FinancialRuleError(
            "IMPORT_REJECTED", details={"reason": "INVALID_FILE"}
        ) from exc


def _parse(
    raw,
    *,
    batch_id,
    row_number,
    source_system,
    audit_time,
    cutoff,
    allow_late_audit=False,
):
    try:
        occurred_at = parse_timestamp(raw["occurred_at"])
    except ValueError as exc:
        raise _RowProblem("INVALID_DATE", "occurred_at") from exc
    try:
        recorded_at = parse_timestamp(raw.get("recorded_at") or audit_time)
    except ValueError as exc:
        raise _RowProblem("INVALID_DATE", "recorded_at") from exc
    if raw.get("currency") not in (None, "", "IQD"):
        raise _RowProblem("INVALID_CURRENCY", "currency")
    try:
        amount = parse_iqd(raw["amount_iqd"])
    except ValueError as exc:
        raise _RowProblem("INVALID_AMOUNT", "amount_iqd") from exc
    try:
        quantity = parse_iqd(raw["quantity"]) if raw["quantity"] else None
    except ValueError as exc:
        raise _RowProblem("INVALID_AMOUNT", "quantity") from exc
    if raw.get("source_system", source_system) != source_system:
        raise _RowProblem("VALIDATION_ERROR")
    token = hashlib.sha256(f"{source_system}:{raw['source_id']}".encode()).hexdigest()
    try:
        row = Transaction(
            transaction_id=f"TX-{token}",
            source_id=raw["source_id"],
            source_system=source_system,
            source_row=row_number,
            import_batch_id=batch_id,
            occurred_at=occurred_at,
            recorded_at=recorded_at,
            type=raw["type"],
            amount_iqd=amount,
            counterparty_id=raw["counterparty_id"] or None,
            obligation_id=raw["obligation_id"] or None,
            due_date=raw["due_date"] or None,
            category_id=raw["category_id"] or None,
            quantity=quantity,
            description=raw["description"],
            status="flagged"
            if raw["type"] in _PAYMENTS and not raw["obligation_id"]
            else "valid",
            idempotency_key=f"{source_system}:{raw['source_id']}",
            business_date=raw.get("business_date") or None,
        )
    except ValidationError as exc:
        failure = exc.errors()[0]
        location = failure["loc"]
        semantic_field = {
            "business_date disagrees with Baghdad timestamp": "business_date",
            "Due dates belong to originating obligations": "due_date",
            "Obligation references apply only to credit and payment events": (
                "obligation_id"
            ),
            "This event requires a counterparty ID": "counterparty_id",
            "An originating event requires an obligation ID": "obligation_id",
            "Sale category and quantity must be supplied together": "quantity"
            if raw["category_id"]
            else "category_id",
            "Category and quantity apply only to sales": "category_id",
        }.get(str(failure.get("ctx", {}).get("error", "")))
        field = (
            str(location[0])
            if location
            else semantic_field
            or (
                "source_id"
                if not raw["source_id"]
                else "counterparty_id"
                if raw["type"] in _ORIGINS | _PAYMENTS and not raw["counterparty_id"]
                else "obligation_id"
                if raw["type"] in _ORIGINS and not raw["obligation_id"]
                else "quantity"
                if raw["category_id"] and not raw["quantity"]
                else "category_id"
                if raw["quantity"]
                else "type"
            )
        )
        raise _RowProblem("VALIDATION_ERROR", field) from exc
    late_upload_audit = allow_late_audit and not raw.get("recorded_at")
    if not OBSERVED_START <= row.business_date <= cutoff.date() or (
        recorded_at > cutoff and not late_upload_audit
    ):
        raise _RowProblem(
            "OUTSIDE_OBSERVED_DATA",
            "business_date" if raw.get("business_date") else "occurred_at",
        )
    if recorded_at < occurred_at or recorded_at > audit_time:
        raise _RowProblem(
            "INVALID_DATE", "recorded_at" if raw.get("recorded_at") else "occurred_at"
        )
    return row


def _check_references(connection, row):
    if row.counterparty_id is not None:
        party = connection.execute(
            "SELECT kind FROM counterparties WHERE counterparty_id = ?",
            (row.counterparty_id,),
        ).fetchone()
        expected = (
            "customer"
            if row.type in {EventType.CREDIT_SALE, EventType.CREDIT_COLLECTION}
            else "supplier"
        )
        if party is None or (
            row.type in _PAYMENTS | _ORIGINS and party["kind"] != expected
        ):
            raise _RowProblem("INVALID_REFERENCE", "counterparty_id")
    if (
        row.category_id
        and not connection.execute(
            "SELECT 1 FROM categories WHERE category_id = ?", (row.category_id,)
        ).fetchone()
    ):
        raise _RowProblem("INVALID_REFERENCE", "category_id")
    if (
        row.type in _ORIGINS
        and connection.execute(
            "SELECT 1 FROM obligations WHERE obligation_id = ?", (row.obligation_id,)
        ).fetchone()
    ):
        raise _RowProblem("INVALID_REFERENCE", "obligation_id")


def _payment_match(connection, row, audit_time, *, clock):
    if row.type not in _PAYMENTS:
        return None
    return match_payment(connection, row, clock=clock, known_at=audit_time)


def get_import_receipt(connection, batch_id, *, replay=False) -> ImportReceipt:
    if not connection.execute(
        """SELECT 1 FROM import_batches WHERE import_batch_id = ?
        AND status = 'completed'""",
        (batch_id,),
    ).fetchone():
        raise FinancialRuleError("NOT_FOUND")
    counts = {"accepted": 0, "flagged": 0, "rejected": 0, "duplicate": 0}
    errors = []
    for row in connection.execute(
        "SELECT * FROM raw_import_rows WHERE import_batch_id = ? ORDER BY source_row",
        (batch_id,),
    ):
        problems = json.loads(row["errors_json"])
        duplicate = bool(problems and problems[0]["code"] == "EXACT_DUPLICATE")
        kind = "duplicate" if duplicate else row["status"]
        counts[kind] += 1
        if kind == "rejected":
            errors.extend(ImportErrorDetail(**problem) for problem in problems)
    return ImportReceipt(
        batch_id=batch_id,
        accepted=0 if replay else counts["accepted"],
        rejected=counts["rejected"],
        exact_duplicates=counts["duplicate"]
        + (counts["accepted"] + counts["flagged"] if replay else 0),
        flagged_for_review=0 if replay else counts["flagged"],
        errors=tuple(errors),
    )


def import_csv(
    connection: sqlite3.Connection,
    path: str | Path,
    *,
    clock: BusinessClock,
    imported_at: datetime | str,
    source_system: str = "synthetic_csv",
) -> ImportReceipt:
    """Import explicitly fictional canonical records; no automatic reference creation.

    Imported knowledge time is preserved when supplied by the synthetic export;
    otherwise the explicit import audit time is used. Neither extends observed history.
    """
    file_hash, rows = _file_rows(Path(path))
    return _import_rows(
        connection,
        file_hash,
        rows,
        clock=clock,
        imported_at=imported_at,
        source_system=source_system,
    )


@bounded_import
def import_csv_bytes(
    connection: sqlite3.Connection,
    content: bytes,
    *,
    filename: str,
    clock: BusinessClock,
    imported_at: datetime | str,
) -> ImportReceipt:
    """Synthetic HTTP uploads use the same parser/atomic importer without disk files."""
    if Path(filename).suffix.lower() != ".csv":
        raise FinancialRuleError("IMPORT_REJECTED", details={"reason": "FILE_TYPE"})
    file_hash, rows = _csv_rows(content)
    return _import_rows(
        connection,
        file_hash,
        rows,
        clock=clock,
        imported_at=imported_at,
        allow_late_audit=True,
    )


@bounded_import
def _import_rows(
    connection,
    file_hash,
    rows,
    *,
    clock,
    imported_at,
    source_system="synthetic_csv",
    allow_late_audit=False,
    raw_rows=None,
    row_errors=None,
):
    cutoff = knowledge_cutoff(observed_day(clock))
    audit_time = parse_timestamp(imported_at)
    if source_system not in {"synthetic_csv", "synthetic_wallet"}:
        raise FinancialRuleError("IMPORT_REJECTED")
    with atomic_import(connection):
        existing = connection.execute(
            """SELECT import_batch_id FROM import_batches WHERE file_sha256 = ?
            AND source_system = ? AND status = 'completed' ORDER BY rowid LIMIT 1""",
            (file_hash, source_system),
        ).fetchone()
        if existing:
            return get_import_receipt(connection, existing[0], replay=True)
        batch_id = f"CSV-{uuid4().hex}"
        insert_record(
            connection,
            ImportBatch(
                import_batch_id=batch_id,
                source_system=source_system,
                file_sha256=file_hash,
                imported_at=audit_time,
                row_count=len(rows),
            ),
        )
        accepted = flagged = rejected = 0
        for number, raw in enumerate(rows, 1):
            checkpoint()
            raw_id = f"{batch_id}-RAW-{number}"
            evidence = raw_rows[number - 1] if raw_rows is not None else raw
            try:
                if row_errors and number in row_errors:
                    raise _RowProblem("MAPPED_VALUE_ERROR")
                row = _parse(
                    raw,
                    batch_id=batch_id,
                    row_number=number,
                    source_system=source_system,
                    audit_time=audit_time,
                    cutoff=cutoff,
                    allow_late_audit=allow_late_audit,
                )
                prior = connection.execute(
                    """SELECT * FROM transactions
                    WHERE source_system = ? AND source_id = ?""",
                    (source_system, row.source_id),
                ).fetchone()
                if prior:
                    old = Transaction.model_validate(dict(prior))
                    # An unmatched reference is retained in raw evidence while
                    # its normalized payment is deliberately unallocated. Compare
                    # the original reference on overlapping exports as well.
                    original = connection.execute(
                        """SELECT row_json FROM raw_import_rows
                        WHERE import_batch_id = ? AND source_row = ?""",
                        (old.import_batch_id, old.source_row),
                    ).fetchone()
                    original_cells = json.loads(original[0])
                    original_cells = original_cells.get("canonical", original_cells)
                    old_reference = (
                        original_cells.get("obligation_id", old.obligation_id) or None
                    )
                    exact = all(
                        (old_reference if key == "obligation_id" else getattr(old, key))
                        == getattr(row, key)
                        for key in _IDENTITY
                    )
                    exact = exact and (
                        not raw.get("recorded_at") or old.recorded_at == row.recorded_at
                    )
                    raise _RowProblem(
                        "EXACT_DUPLICATE" if exact else "IDEMPOTENCY_CONFLICT",
                        "source_id",
                    )
                _check_references(connection, row)
                match = _payment_match(connection, row, audit_time, clock=clock)
                reason = match.reason_key if match else None
                if match is not None:
                    row = row.model_copy(
                        update={
                            "obligation_id": match.obligation_id,
                            "status": "flagged" if reason else "valid",
                        }
                    )
                near = connection.execute(
                    """SELECT 1 FROM transactions t WHERE type = ?
                    AND amount_iqd = ? AND counterparty_id IS ?
                    AND business_date = ? AND recorded_at <= ? AND occurred_at <= ?
                    AND NOT EXISTS (SELECT 1 FROM entry_voids v
                        WHERE v.transaction_id = t.transaction_id AND v.voided_at <= ?)
                    LIMIT 1""",
                    (
                        row.type,
                        row.amount_iqd,
                        row.counterparty_id,
                        row.business_date.isoformat(),
                        audit_time.isoformat(),
                        audit_time.isoformat(),
                        audit_time.isoformat(),
                    ),
                ).fetchone()
                reasons = ([reason] if reason else []) + (
                    ["suspected_duplicate"] if near else []
                )
                status = "flagged" if reasons else "accepted"
                row = row.model_copy(
                    update={"status": "flagged" if reasons else "valid"}
                )
                insert_record(
                    connection,
                    RawImportRow(
                        raw_row_id=raw_id,
                        import_batch_id=batch_id,
                        source_row=number,
                        row_json=json.dumps(evidence, ensure_ascii=False),
                        status=status,
                    ),
                )
                insert_record(connection, row)
                if row.type in _ORIGINS:
                    insert_record(
                        connection,
                        Obligation(
                            obligation_id=row.obligation_id,
                            kind="receivable"
                            if row.type == EventType.CREDIT_SALE
                            else "payable",
                            origin_transaction_id=row.transaction_id,
                            counterparty_id=row.counterparty_id,
                            original_amount_iqd=row.amount_iqd,
                            due_date=row.due_date,
                        ),
                    )
                if row.type in _PAYMENTS and reason is None:
                    insert_record(
                        connection,
                        PaymentLink(
                            payment_link_id=f"LINK-{uuid4().hex}",
                            payment_transaction_id=row.transaction_id,
                            obligation_id=row.obligation_id,
                            amount_iqd=row.amount_iqd,
                            match_basis=match.level,
                            created_at=audit_time,
                        ),
                    )
                for reason_key in reasons:
                    insert_record(
                        connection,
                        ReconciliationFlag(
                            flag_id=f"FLAG-{uuid4().hex}",
                            type="suspected_duplicate"
                            if reason_key == "suspected_duplicate"
                            else "ambiguous"
                            if match and match.level == "candidate"
                            else "unmatched",
                            reason_key=reason_key,
                            amount_iqd=row.amount_iqd,
                            transaction_id=row.transaction_id,
                            raw_row_id=raw_id,
                            confidence_basis=reason_key,
                        ),
                    )
                if reasons:
                    flagged += 1
                else:
                    accepted += 1
            except _RowProblem as problem:
                rejected += 1
                errors = (row_errors or {}).get(number) or (
                    ImportErrorDetail(
                        row=number,
                        code=problem.code,
                        message=problem.code,
                        field=(problem.field or "type")
                        if raw_rows is not None
                        else None,
                    ),
                )
                insert_record(
                    connection,
                    RawImportRow(
                        raw_row_id=raw_id,
                        import_batch_id=batch_id,
                        source_row=number,
                        row_json=json.dumps(evidence, ensure_ascii=False),
                        errors_json=json.dumps(
                            [error.model_dump(mode="json") for error in errors]
                        ),
                        status="rejected",
                    ),
                )
        checkpoint()
        connection.execute(
            """UPDATE import_batches SET accepted_count = ?, flagged_count = ?,
            rejected_count = ?, status = 'completed' WHERE import_batch_id = ?""",
            (accepted, flagged, rejected, batch_id),
        )
        receipt = get_import_receipt(connection, batch_id)
        checkpoint()
        return receipt
