"""Read-only period/type projection of the existing reconciliation service."""

from app.schemas.queries import FlagsReport
from app.services.financial_queries import historical_range
from app.services.reconcile import reconciliation_report


def run(snapshot, *, clock, arguments, dates_from_user=False, trusted_range=None):
    resolved = historical_range(
        clock,
        arguments.period,
        start_date=arguments.start_date,
        end_date=arguments.end_date,
        dates_from_user=dates_from_user,
        trusted_range=trusted_range,
    )
    selected = {
        r.source_id
        for r in snapshot.rows
        if resolved.start <= r.business_date <= resolved.end
    }
    flags = reconciliation_report(
        snapshot.connection, clock=clock, known_at=snapshot.known
    ).flags
    return (
        FlagsReport(
            items=tuple(
                f
                for f in flags
                if selected.intersection(f.source_ids)
                and (arguments.types is None or f.type in arguments.types)
            )
        ),
        resolved,
        None,
    )
