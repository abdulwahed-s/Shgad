"""Schema-documented reports. Financial services have no LLM dependency."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import AuditTime, Clock, Database
from app.config import Settings, get_settings
from app.schemas.ledger import BusinessDate
from app.schemas.reports import MarginReport, WeeklyReport
from app.schemas.tools import Period
from app.services.financial_queries import QuerySnapshot, historical_range
from app.services.margin import margin_report
from app.services.summary import weekly_report

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/margin", response_model=MarginReport)
async def margin(
    db: Database,
    clock: Clock,
    now: AuditTime,
    period: Period = "this_week",
    start: Annotated[BusinessDate | None, Query(alias="from")] = None,
    end: Annotated[BusinessDate | None, Query(alias="to")] = None,
):
    explicit = start is not None or end is not None
    resolved = historical_range(
        clock,
        "explicit" if explicit else period,
        start_date=start,
        end_date=end,
        dates_from_user=explicit,
    )
    return margin_report(QuerySnapshot(db, clock=clock, known_at=now), resolved)


@router.get("/weekly", response_model=WeeklyReport)
async def weekly(
    db: Database,
    clock: Clock,
    now: AuditTime,
    settings: Annotated[Settings, Depends(get_settings)],
    week: str = "current",
):
    return weekly_report(
        db,
        clock=clock,
        known_at=now,
        week=week,
        coverage_threshold=settings.margin_min_coverage_pct,
    )
