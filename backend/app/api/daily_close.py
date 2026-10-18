"""Thin merchant daily-close and explicit difference-review routes."""

from fastapi import APIRouter

from app.api.dependencies import AuditTime, Clock, Database
from app.schemas.daily_close import DailyCloseView, ResolutionReceipt
from app.schemas.ledger import BusinessDate, DifferenceReviewRequest
from app.services.daily_close import daily_close_view, review_daily_close

router = APIRouter(prefix="/api/daily-close", tags=["daily-close"])


@router.get("/{business_date}", response_model=DailyCloseView)
async def close_for_day(
    business_date: BusinessDate, db: Database, clock: Clock, now: AuditTime
):
    return daily_close_view(db, business_date, clock=clock, known_at=now)


@router.post("/{business_date}/resolve", response_model=ResolutionReceipt)
async def resolve_for_day(
    business_date: BusinessDate,
    request: DifferenceReviewRequest,
    db: Database,
    clock: Clock,
    now: AuditTime,
):
    return review_daily_close(db, request, business_date, clock=clock, recorded_at=now)
