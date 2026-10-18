"""Thin synthetic CSV upload and batch-receipt routes (roadmap §7.1/B.2)."""

from inspect import isawaitable
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.dependencies import AuditTime, Clock, Database, mapping_model
from app.schemas.csv_mapping import MappingPreview
from app.schemas.imports import ImportReceipt
from app.services.csv_mapping import (
    MappingProposer,
    SuppliedMappingProposer,
    confirm_mapping,
    mapping_input,
    propose_mapping,
)
from app.services.errors import FinancialRuleError
from app.services.ingest import MAX_FILE_BYTES, get_import_receipt, import_csv_bytes

router = APIRouter(prefix="/api/imports", tags=["imports"])


@router.post("/csv", response_model=ImportReceipt)
async def upload_csv(
    file: Annotated[UploadFile, File()],
    db: Database,
    clock: Clock,
    now: AuditTime,
):
    try:
        content = await file.read(MAX_FILE_BYTES + 1)
        return import_csv_bytes(
            db,
            content,
            filename=file.filename or "",
            clock=clock,
            imported_at=now,
        )
    finally:
        await file.close()


@router.get("/{batch_id}", response_model=ImportReceipt)
async def batch_receipt(batch_id: str, db: Database):
    return get_import_receipt(db, batch_id)


@router.post("/csv/mapping", response_model=MappingPreview)
async def map_csv(
    file: Annotated[UploadFile, File()],
    db: Database,
    clock: Clock,
    now: AuditTime,
    proposer: Annotated[MappingProposer, Depends(mapping_model)],
):
    try:
        content = await file.read(MAX_FILE_BYTES + 1)
        headers, rows = mapping_input(content, file.filename or "")
        try:
            proposal = proposer.propose(
                headers=tuple(headers), sample_rows=tuple(rows[:3])
            )
            if isawaitable(proposal):
                proposal = await proposal
        except (TimeoutError, ConnectionError):
            raise FinancialRuleError("LLM_UNAVAILABLE") from None
        return propose_mapping(
            db,
            content,
            filename=file.filename or "",
            proposer=SuppliedMappingProposer(proposal),
            clock=clock,
            created_at=now,
        )
    finally:
        await file.close()


@router.post("/csv/mapping/{mapping_id}/confirm", response_model=ImportReceipt)
async def confirm_csv(mapping_id: str, db: Database, clock: Clock, now: AuditTime):
    return confirm_mapping(db, mapping_id, clock=clock, confirmed_at=now)
