"""Untrusted column proposals; deterministic preview and explicit confirmation.

Only header/three sample rows cross the proposer interface.
Preview financial writes always roll back; confirmation uses the normal importer.
"""

import hashlib
import json
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from pydantic import ValidationError

from app.db.records import atomic_import
from app.schemas.csv_mapping import MappingPreview, MappingProposal, PreviewRow
from app.schemas.imports import ImportErrorDetail
from app.services.errors import FinancialRuleError
from app.services.ingest import (
    _REQUIRED,
    _import_rows,
    _parse,
    _RowProblem,
    get_import_receipt,
    read_csv_content,
)
from app.services.ledger_rules import knowledge_cutoff
from app.services.observed import observed_day
from app.services.validation import parse_timestamp

_MAPPING_REQUIRED = {"source_id", "occurred_at", "type", "amount_iqd"}
_TARGETS = _REQUIRED | {"currency", "recorded_at", "business_date"}


class MappingProposer(Protocol):
    def propose(
        self, *, headers: tuple[str, ...], sample_rows: tuple[dict[str, str], ...]
    ) -> str | dict: ...


class UnavailableMappingProposer:
    def propose(self, *, headers, sample_rows):
        raise FinancialRuleError("LLM_UNAVAILABLE")


class SuppliedMappingProposer:
    """Bridge an already-awaited proposal into the existing sync preview pipeline."""

    def __init__(self, value):
        self.value = value

    def propose(self, *, headers, sample_rows):
        return self.value


def mapping_input(content, filename):
    if Path(filename).suffix.lower() != ".csv":
        raise FinancialRuleError("IMPORT_REJECTED", details={"reason": "FILE_TYPE"})
    return read_csv_content(content)


def _validate_proposal(value, headers):
    try:
        proposal = (
            MappingProposal.model_validate_json(value)
            if isinstance(value, str)
            else MappingProposal.model_validate(value)
        )
        sources = [c.source_header for c in proposal.columns]
        targets = [
            c.target_field for c in proposal.columns if c.target_field is not None
        ]
        if (
            len(sources) != len(headers)
            or set(sources) != set(headers)
            or len(targets) != len(set(targets))
            or not set(targets) <= _TARGETS
        ):
            raise ValueError
        return proposal
    except (ValidationError, ValueError, TypeError) as exc:
        raise FinancialRuleError(
            "MAPPING_UNRESOLVED", details={"reason": "INVALID_MAPPING"}
        ) from exc


def _mapped_input(content, proposal):
    _, original = read_csv_content(content)
    rows = [
        dict.fromkeys(_REQUIRED, "")
        | {
            c.target_field: raw[c.source_header]
            for c in proposal.columns
            if c.target_field is not None
        }
        for raw in original
    ]
    evidence = [
        {"original": raw, "canonical": mapped}
        for raw, mapped in zip(original, rows, strict=True)
    ]
    columns_json = json.dumps(
        [c.model_dump() for c in proposal.columns], ensure_ascii=False, sort_keys=True
    )
    identity = hashlib.sha256(content + b"\0" + columns_json.encode()).hexdigest()
    return rows, evidence, columns_json, identity


def _preview_rows(connection, content, proposal, *, clock, audit, missing):
    rows, evidence, _, identity = _mapped_input(content, proposal)
    if missing:
        return tuple(
            PreviewRow(
                row=i,
                parsed=None,
                errors=(
                    ImportErrorDetail(
                        row=i,
                        code="MAPPING_UNRESOLVED",
                        message="MAPPING_UNRESOLVED",
                    ),
                ),
            )
            for i in range(1, min(5, len(rows)) + 1)
        )
    connection.execute("SAVEPOINT mapping_preview")
    try:
        receipt = _import_rows(
            connection,
            identity,
            rows,
            clock=clock,
            imported_at=audit,
            allow_late_audit=True,
            raw_rows=evidence,
        )
        problems = {
            r["source_row"]: json.loads(r["errors_json"])
            for r in connection.execute(
                """SELECT source_row, errors_json FROM raw_import_rows
                WHERE import_batch_id = ?""",
                (receipt.batch_id,),
            )
        }
        preview = []
        for number, raw in enumerate(rows[:5], 1):
            errors = tuple(
                ImportErrorDetail(**p)
                for p in problems.get(number, [])
                if p["code"] != "EXACT_DUPLICATE"
            )
            parsed = None
            try:
                transaction = _parse(
                    raw,
                    batch_id="PREVIEW",
                    row_number=number,
                    source_system="synthetic_csv",
                    audit_time=audit,
                    cutoff=knowledge_cutoff(observed_day(clock)),
                    allow_late_audit=True,
                )
                parsed = {
                    k: v
                    for k, v in transaction.model_dump(mode="json").items()
                    if k in _TARGETS
                }
            except _RowProblem:
                pass  # The normal import already produced the typed raw-row error.
            preview.append(PreviewRow(row=number, parsed=parsed, errors=errors))
        return tuple(preview)
    finally:
        connection.execute("ROLLBACK TO SAVEPOINT mapping_preview")
        connection.execute("RELEASE SAVEPOINT mapping_preview")


def propose_mapping(
    connection, content, *, filename, proposer: MappingProposer, clock, created_at
) -> MappingPreview:
    headers, rows = mapping_input(content, filename)
    audit = parse_timestamp(created_at)
    try:
        output = proposer.propose(
            headers=tuple(headers), sample_rows=tuple(dict(r) for r in rows[:3])
        )
    except (TimeoutError, ConnectionError) as exc:
        raise FinancialRuleError("LLM_UNAVAILABLE") from exc
    proposal = _validate_proposal(output, headers)
    targets = {c.target_field for c in proposal.columns}
    missing = tuple(sorted(_MAPPING_REQUIRED - targets))
    with atomic_import(connection):
        preview_rows = _preview_rows(
            connection, content, proposal, clock=clock, audit=audit, missing=missing
        )
        preview = MappingPreview(
            mapping_id=f"MAP-{uuid4().hex}",
            columns=proposal.columns,
            unmapped_required=missing,
            preview_rows=preview_rows,
            can_confirm=bool(preview_rows)
            and not missing
            and all(not r.errors for r in preview_rows),
        )
        _, _, columns_json, _ = _mapped_input(content, proposal)
        connection.execute(
            """INSERT INTO csv_mappings
            (mapping_id, filename, content, columns_json, preview_json,
             business_as_of, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                preview.mapping_id,
                filename,
                content,
                columns_json,
                preview.model_dump_json(),
                observed_day(clock).isoformat(),
                audit.isoformat(),
            ),
        )
        return preview


def confirm_mapping(connection, mapping_id, *, clock, confirmed_at):
    audit = parse_timestamp(confirmed_at)
    with atomic_import(connection):
        saved = connection.execute(
            "SELECT * FROM csv_mappings WHERE mapping_id = ?", (mapping_id,)
        ).fetchone()
        if saved is None:
            raise FinancialRuleError("NOT_FOUND")
        if saved["business_as_of"] != observed_day(clock).isoformat():
            raise FinancialRuleError(
                "MAPPING_UNRESOLVED", details={"reason": "PREVIEW_CUTOFF_CHANGED"}
            )
        preview = MappingPreview.model_validate_json(saved["preview_json"])
        if not preview.can_confirm:
            raise FinancialRuleError(
                "MAPPING_UNRESOLVED",
                details={"unmapped_required": list(preview.unmapped_required)},
            )
        if parse_timestamp(saved["created_at"]) > audit:
            raise FinancialRuleError("VALIDATION_ERROR")
        existing = connection.execute(
            "SELECT import_batch_id FROM mapping_confirmations WHERE mapping_id = ?",
            (mapping_id,),
        ).fetchone()
        if existing:
            return get_import_receipt(connection, existing[0], replay=True)
        proposal = MappingProposal(columns=preview.columns)
        rows, evidence, _, identity = _mapped_input(saved["content"], proposal)
        receipt = _import_rows(
            connection,
            identity,
            rows,
            clock=clock,
            imported_at=audit,
            allow_late_audit=True,
            raw_rows=evidence,
        )
        connection.execute(
            "INSERT INTO mapping_confirmations VALUES (?, ?, ?)",
            (mapping_id, receipt.batch_id, audit.isoformat()),
        )
        return receipt
