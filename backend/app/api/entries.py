"""Merchant-only writes; the eventual agent registry remains read-only."""

from fastapi import APIRouter, Response

from app.api.dependencies import AuditTime, Clock, Database
from app.schemas.entries import EntryReceipt, EntryRequest
from app.services.entries import create_entry

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
