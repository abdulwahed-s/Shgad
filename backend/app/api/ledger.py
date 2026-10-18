"""Thin immutable ledger evidence routes (API_CONTRACT ledger)."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import AuditTime, Clock, Database
from app.schemas.evidence import LedgerDetail, LedgerPage
from app.schemas.ledger import BusinessDate, EventType
from app.services.evidence import transaction_detail, transaction_page

router = APIRouter(prefix="/api/ledger/transactions", tags=["ledger"])


@router.get("", response_model=LedgerPage)
async def ledger_page(
    db: Database,
    clock: Clock,
    now: AuditTime,
    start: Annotated[BusinessDate | None, Query(alias="from")] = None,
    end: Annotated[BusinessDate | None, Query(alias="to")] = None,
    event_type: Annotated[EventType | None, Query(alias="type")] = None,
    counterparty_id: str | None = None,
    ids: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
):
    return transaction_page(
        db,
        clock=clock,
        known_at=now,
        start=start,
        end=end,
        event_type=event_type,
        counterparty_id=counterparty_id,
        ids=ids,
        limit=limit,
        cursor=cursor,
    )


@router.get("/{source_id}", response_model=LedgerDetail)
async def ledger_detail(source_id: str, db: Database, clock: Clock, now: AuditTime):
    return transaction_detail(db, source_id, clock=clock, known_at=now)
