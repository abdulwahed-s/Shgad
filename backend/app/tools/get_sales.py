"""Recorded sales query; a cash difference is always a separate figure."""

from app.services.financial_queries import historical_range, sale_totals


def run(snapshot, *, clock, arguments, dates_from_user=False):
    resolved = historical_range(
        clock,
        arguments.period,
        start_date=arguments.start_date,
        end_date=arguments.end_date,
        dates_from_user=dates_from_user,
    )
    return sale_totals(snapshot, resolved, kind=arguments.kind), resolved, None
