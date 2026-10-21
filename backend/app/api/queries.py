"""Deterministic daily-workflow query endpoints with no provider dependency."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.agents.llm_client import provider_configs
from app.api.dependencies import AuditTime, Clock, Database
from app.config import Settings, get_settings
from app.schemas.queries import DebtReport, FlagsReport, MetaReport, UpcomingObligations
from app.services.financial_queries import (
    QuerySnapshot,
    debt_report,
    upcoming_obligations,
)
from app.services.reconcile import reconciliation_report

router = APIRouter(tags=["financial queries"])


@router.get("/api/debts", response_model=DebtReport)
async def debts(
    db: Database,
    clock: Clock,
    now: AuditTime,
    overdue_only: bool = False,
    direction: Literal["receivable", "payable"] = "receivable",
):
    return debt_report(
        QuerySnapshot(db, clock=clock, known_at=now),
        overdue_only=overdue_only,
        direction=direction,
    )


@router.get("/api/obligations/upcoming", response_model=UpcomingObligations)
async def upcoming(
    db: Database,
    clock: Clock,
    now: AuditTime,
    days: Annotated[int, Query(ge=1, le=30)] = 7,
):
    return upcoming_obligations(QuerySnapshot(db, clock=clock, known_at=now), days=days)


@router.get("/api/flags", response_model=FlagsReport)
async def flags(db: Database, clock: Clock, now: AuditTime):
    return FlagsReport(items=reconciliation_report(db, clock=clock, known_at=now).flags)


@router.get("/api/meta", response_model=MetaReport)
async def meta(clock: Clock, settings: Annotated[Settings, Depends(get_settings)]):
    return MetaReport(
        business_as_of=clock.today, llm_available=bool(provider_configs(settings))
    )
