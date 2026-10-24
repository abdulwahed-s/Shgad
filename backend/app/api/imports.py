"""Thin synthetic CSV upload and batch-receipt routes (roadmap §7.1/B.2)."""

import asyncio
from inspect import isawaitable
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

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
MAPPING_TIMEOUT_SECONDS = 125


def validate_media(file):
    # Native browser CSV pickers also use plain text or generic binary MIME.
    if (file.content_type or "").split(";", 1)[0].lower() not in {
        "text/csv",
        "application/csv",
        "text/plain",
        "application/octet-stream",
    }:
        raise FinancialRuleError("IMPORT_REJECTED", details={"reason": "FILE_TYPE"})


@router.post("/csv", response_model=ImportReceipt)
async def upload_csv(
    file: Annotated[UploadFile, File()],
    db: Database,
    clock: Clock,
    now: AuditTime,
):
    try:
        validate_media(file)
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
    columns_json: Annotated[str | None, Form(max_length=64000)] = None,
):
    try:
        validate_media(file)
        content = await file.read(MAX_FILE_BYTES + 1)
        headers, rows = mapping_input(content, file.filename or "")
        if columns_json is not None:
            proposal = columns_json
        else:
            try:
                proposal = proposer.propose(
                    headers=tuple(headers), sample_rows=tuple(rows[:3])
                )
                if isawaitable(proposal):
                    async with asyncio.timeout(MAPPING_TIMEOUT_SECONDS):
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
