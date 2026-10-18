"""Thin synthetic CSV upload and batch-receipt routes (roadmap §7.1/B.2)."""

from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from app.api.dependencies import AuditTime, Clock, Database
from app.schemas.imports import ImportReceipt
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
