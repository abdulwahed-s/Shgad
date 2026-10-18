"""Merchant-only writes; the eventual agent registry remains read-only."""

from fastapi import APIRouter, Response

from app.api.dependencies import AuditTime, Clock, Database
from app.db.records import atomic_import
from app.schemas.entries import EntryReceipt, EntryRequest, VoidReceipt
from app.schemas.ledger import VoidRequest
from app.services.entries import create_entry
from app.services.evidence import find_source
from app.services.ledger_audit import void_entry
from app.services.validation import parse_timestamp

router = APIRouter(prefix="/api/entries", tags=["entries"])


@router.post("", response_model=EntryReceipt, status_code=201)
async def save_entry(
    request: EntryRequest,
    response: Response,
    db: Database,
    clock: Clock,
    now: AuditTime,
):
    receipt = create_entry(db, request, clock=clock, recorded_at=now)
    response.status_code = 200 if receipt.duplicate else 201
    return receipt


@router.post("/{source_id}/void", response_model=VoidReceipt)
async def void_saved_entry(
    source_id: str,
    request: VoidRequest,
    db: Database,
    clock: Clock,
    now: AuditTime,
):
    with atomic_import(db):
        original = find_source(
            db, source_id, clock=clock, known_at=parse_timestamp(now)
        )
        result = void_entry(
            db, request, transaction_id=original.transaction_id, voided_at=now
        )
        return VoidReceipt(
            source_id=result.audit.source_id,
            void_id=result.audit.void_id,
            reason=result.audit.reason,
            duplicate=result.duplicate,
        )
