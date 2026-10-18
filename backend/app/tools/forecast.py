"""Reuse D23's production estimate; J1 confirmed cash/debts stay separate."""

from datetime import timedelta

from app.schemas.forecast import ForecastReport
from app.schemas.queries import PaymentCapacity
from app.services.business_clock import DateRange
from app.services.errors import FinancialRuleError
from app.services.financial_queries import payment_capacity
from app.services.forecast import forecast


class ForecastResult(ForecastReport):
    j1: PaymentCapacity | None


def run(snapshot, *, clock, arguments, dates_from_user=False):
    args = arguments
    if args.until is None:
        if args.start_date is not None or args.end_date is not None:
            raise FinancialRuleError("VALIDATION_ERROR")
        resolved = DateRange(
            snapshot.day + timedelta(days=1), snapshot.day + timedelta(days=30)
        )
    else:
        until = clock.resolve(
            args.until,
            start_date=args.start_date,
            end_date=args.end_date,
            dates_from_user=dates_from_user,
        )
        if (
            not snapshot.day
            <= until.start
            <= until.end
            <= snapshot.day + timedelta(days=30)
        ):
            raise FinancialRuleError("VALIDATION_ERROR")
        resolved = DateRange(snapshot.day, until.end)
    report = forecast(snapshot.connection, clock=clock, scenario=args.scenario)
    j1 = (
        payment_capacity(snapshot, resolved.end)
        if args.until and args.until.startswith("next_weekday:")
        else None
    )
    return ForecastResult(**report.model_dump(), j1=j1), resolved, None
