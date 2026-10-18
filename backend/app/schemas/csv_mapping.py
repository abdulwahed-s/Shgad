"""Validated column proposals and bounded server-produced preview shapes."""

from typing import Any

from pydantic import StrictBool

from app.schemas.imports import ImportErrorDetail
from app.schemas.ledger import Identifier, LedgerModel, NonemptyText, PositiveInteger


class MappingColumn(LedgerModel):
    source_header: NonemptyText
    target_field: NonemptyText | None


class MappingProposal(LedgerModel):
    columns: tuple[MappingColumn, ...]


class PreviewRow(LedgerModel):
    row: PositiveInteger
    parsed: dict[str, Any] | None
    errors: tuple[ImportErrorDetail, ...]


class MappingPreview(MappingProposal):
    mapping_id: Identifier
    unmapped_required: tuple[str, ...]
    preview_rows: tuple[PreviewRow, ...]
    can_confirm: StrictBool
