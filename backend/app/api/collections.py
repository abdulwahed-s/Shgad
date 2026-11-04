"""Read-only collection priorities and merchant-only operational memory."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.agents.collection_agent import create_draft
from app.agents.llm_client import LLMClient
from app.api.dependencies import AuditTime, Clock, Database, llm_client
from app.schemas.collections import (
    CollectionDraft,
    CollectionDraftRequest,
    CollectionsReport,
    MorningBrief,
    ReminderReceipt,
    ReminderRequest,
)
from app.services.collections import collection_report, log_reminder
from app.services.morning_brief import morning_brief

router = APIRouter(tags=["collections"])


@router.get("/api/brief", response_model=MorningBrief)
async def brief(db: Database, clock: Clock, now: AuditTime):
    return morning_brief(db, clock=clock, known_at=now)


@router.get("/api/collections", response_model=CollectionsReport)
async def collections(db: Database, clock: Clock, now: AuditTime):
    return collection_report(db, clock=clock, known_at=now)


@router.post("/api/collections/draft", response_model=CollectionDraft)
async def draft(
    request: CollectionDraftRequest,
    db: Database,
    clock: Clock,
    now: AuditTime,
    client: Annotated[LLMClient, Depends(llm_client)],
):
    return await create_draft(
        request, client=client, connection=db, clock=clock, known_at=now
    )


@router.post("/api/reminders", response_model=ReminderReceipt, status_code=201)
async def remind(request: ReminderRequest, db: Database, clock: Clock, now: AuditTime):
    return log_reminder(db, request, clock=clock, now=now)
