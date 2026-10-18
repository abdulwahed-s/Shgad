"""Deterministic daily-workflow query endpoints with no provider dependency."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import AuditTime, Clock, Database
from app.schemas.queries import DebtReport, UpcomingObligations
from app.services.financial_queries import (
    QuerySnapshot,
    debt_report,
    upcoming_obligations,
)

router = APIRouter(tags=["financial queries"])


@router.get("/api/debts", response_model=DebtReport)
async def debts(db: Database, clock: Clock, now: AuditTime, overdue_only: bool = False):
    return debt_report(
        QuerySnapshot(db, clock=clock, known_at=now), overdue_only=overdue_only
    )


@router.get("/api/obligations/upcoming", response_model=UpcomingObligations)
async def upcoming(
    db: Database,
    clock: Clock,
    now: AuditTime,
    days: Annotated[int, Query(ge=1, le=30)] = 7,
):
    return upcoming_obligations(QuerySnapshot(db, clock=clock, known_at=now), days=days)
