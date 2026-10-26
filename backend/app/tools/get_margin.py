"""Estimated gross margin on priced recorded sales, never a net result."""

from app.services.financial_queries import historical_range
from app.services.margin import margin_report


def run(snapshot, *, clock, arguments, dates_from_user=False, trusted_range=None):
    resolved = historical_range(
        clock,
        arguments.period,
        start_date=arguments.start_date,
        end_date=arguments.end_date,
        dates_from_user=dates_from_user,
        trusted_range=trusted_range,
    )
    return margin_report(snapshot, resolved), resolved, None
