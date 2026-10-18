"""Exact-party receivables/payables and confirmed-versus-expected obligations."""

from app.schemas.queries import DebtsResult
from app.services.errors import FinancialRuleError
from app.services.financial_queries import debt_report, upcoming_obligations


def run(snapshot, *, clock, arguments, dates_from_user=False):
    args = arguments
    party = snapshot.resolve_party(args.counterparty_query, args.direction)
    resolved = None
    if args.due_period is not None:
        resolved = clock.resolve(
            args.due_period,
            start_date=args.start_date,
            end_date=args.end_date,
            dates_from_user=dates_from_user,
        )
    elif args.start_date is not None or args.end_date is not None:
        raise FinancialRuleError("VALIDATION_ERROR")
    reports = {"receivable": None, "payable": None}
    for direction in reports:
        if args.direction in (direction, "both"):
            reports[direction] = debt_report(
                snapshot,
                direction=direction,
                overdue_only=args.overdue_only,
                due_range=resolved,
                party_id=party.id if party else None,
            )
    upcoming = None
    if (
        args.direction == "both"
        and args.due_period
        and args.due_period.startswith("next_n_days:")
    ):
        if args.overdue_only:
            raise FinancialRuleError(
                "VALIDATION_ERROR", details={"reason": "CONFLICTING_FILTERS"}
            )
        upcoming = upcoming_obligations(
            snapshot,
            days=int(args.due_period.split(":")[1]),
            party_id=party.id if party else None,
        )
    return (
        DebtsResult(
            direction=args.direction,
            receivables=reports["receivable"],
            payables=reports["payable"],
            upcoming=upcoming,
        ),
        resolved,
        party,
    )
