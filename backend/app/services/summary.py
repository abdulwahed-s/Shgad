"""Deterministic weekly report, roadmap §8.3/§5.5 and FINANCIAL_RULES §§3–5."""

from datetime import timedelta

from app.schemas.queries import ReportRange
from app.schemas.reports import DebtTop, WeeklyMargin, WeeklyReport
from app.services.business_clock import BusinessClock, DateRange
from app.services.errors import FinancialRuleError
from app.services.financial_queries import (
    QuerySnapshot,
    amount,
    debt_report,
    sale_totals,
)
from app.services.margin import margin_report, recorded_sales
from app.services.observed import OBSERVED_START, observed_day
from app.services.reconcile import reconciliation_report
from app.services.validation import parse_business_date


def weekly_range(clock, week):
    today = observed_day(clock)
    if week in {"current", "previous"}:
        return clock.resolve("this_week" if week == "current" else "last_week")
    try:
        anchor = parse_business_date(week)
    except ValueError as exc:
        raise FinancialRuleError("VALIDATION_ERROR") from exc
    start = anchor - timedelta(days=(anchor.weekday() - 5) % 7)
    end = min(today, start + timedelta(days=6))
    return DateRange(start, end, partial=end < start + timedelta(days=6))


def weekly_report(
    connection, *, clock, known_at, week="current", coverage_threshold=80
):
    resolved = weekly_range(clock, week)
    if not OBSERVED_START <= resolved.start <= resolved.end <= clock.today:
        raise FinancialRuleError(
            "NOT_FOUND", details={"reason": "OUTSIDE_OBSERVED_DATA"}
        )
    if type(coverage_threshold) is not int or not 0 <= coverage_threshold <= 100:
        raise FinancialRuleError("VALIDATION_ERROR")
    connection.execute("SAVEPOINT weekly_report")
    try:
        report_clock = BusinessClock(resolved.end)
        snapshot = QuerySnapshot(connection, clock=report_clock, known_at=known_at)
        sales = sale_totals(snapshot, resolved)
        debts = debt_report(snapshot)
        overdue = debt_report(snapshot, overdue_only=True)
        flags = reconciliation_report(
            connection, clock=report_clock, known_at=snapshot.known
        ).flags
        try:
            margin = margin_report(snapshot, resolved)
            total = sum(r.amount_iqd for r in recorded_sales(snapshot, resolved))
            shown = 100 * margin.priced_sales.amount_iqd >= coverage_threshold * total
            coverage = margin.coverage_pct
            value = (
                margin.gross_margin
                if shown
                else amount(
                    None,
                    "estimated_gross_margin",
                    margin.gross_margin.source_ids,
                    "coverage below configured threshold",
                )
            )
        except FinancialRuleError as exc:
            if exc.code != "MISSING_COSTS":
                raise
            shown, coverage = False, exc.details["coverage_pct"]
            value = amount(
                None, "estimated_gross_margin", (), "missing priced recorded sales"
            )

        def total(kind, label):
            rows = tuple(
                r
                for r in snapshot.rows
                if r.type == kind and resolved.start <= r.business_date <= resolved.end
            )
            return amount(
                sum(r.amount_iqd for r in rows),
                label,
                (r.source_id for r in rows),
                f"sum recorded {kind} in resolved week",
            )

        return WeeklyReport(
            range=ReportRange(
                start=resolved.start, end=resolved.end, partial=resolved.partial
            ),
            cash_sales=sales.cash_sales,
            unexplained_cash_difference=sales.unexplained_cash_difference,
            credit_sales=sales.credit_sales,
            collections=total("CREDIT_COLLECTION", "collections"),
            supplier_payments=total("SUPPLIER_PAYMENT", "supplier_payments"),
            operating_expenses=total("OPERATING_EXPENSE", "operating_expenses"),
            owner_drawings=total("OWNER_DRAWING", "owner_drawings"),
            capital_injections=total("CAPITAL_INJECTION", "capital_injections"),
            outstanding_receivables=debts.total_outstanding,
            overdue_receivables=overdue.total_outstanding,
            debt_aging_top=tuple(
                DebtTop(
                    counterparty_id=p.counterparty_id,
                    display_name=p.display_name,
                    outstanding=p.outstanding,
                    days_overdue=p.days_overdue,
                )
                for p in debts.customers[:3]
            ),
            gross_margin=WeeklyMargin(
                shown=shown,
                margin=value,
                coverage_pct=coverage,
                note_key="margin_excludes_unrecorded_costs"
                if shown
                else "margin_insufficient_priced_sales",
            ),
            flags_count=len(flags),
            suggestion_key="review_unmatched_payment"
            if any(f.type in {"unmatched", "ambiguous"} for f in flags)
            else "review_debts"
            if debts.customers
            else "no_action_needed",
        )
    finally:
        connection.execute("RELEASE SAVEPOINT weekly_report")
