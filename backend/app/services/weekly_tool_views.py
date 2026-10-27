"""D54 transport projections of existing weekly facts; no new calculations."""

from app.schemas.reports import WeeklyMarginResult, WeeklyMovements, WeeklySalesResult
from app.services.business_clock import BusinessClock
from app.services.errors import FinancialRuleError
from app.services.financial_queries import QuerySnapshot, amount, sale_totals
from app.services.margin import margin_report
from app.services.summary import weekly_report


def movement_result(snapshot, resolved):
    """D58 period movements: the weekly event sums over any resolved range."""

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
            f"sum recorded {kind} in resolved range",
        )

    return WeeklySalesResult(
        **sale_totals(snapshot, resolved).model_dump(),
        weekly=WeeklyMovements(
            collections=total("CREDIT_COLLECTION", "collections"),
            supplier_payments=total("SUPPLIER_PAYMENT", "supplier_payments"),
            operating_expenses=total("OPERATING_EXPENSE", "operating_expenses"),
            owner_drawings=total("OWNER_DRAWING", "owner_drawings"),
            capital_injections=total("CAPITAL_INJECTION", "capital_injections"),
        ),
    )


def weekly_tool_result(snapshot, resolved, name):
    report = weekly_report(
        snapshot.connection,
        clock=BusinessClock(snapshot.day),
        known_at=snapshot.known,
        week=resolved.start.isoformat(),
    )
    if report.range.start != resolved.start or report.range.end != resolved.end:
        raise FinancialRuleError("VALIDATION_ERROR")
    if name == "get_sales":
        return WeeklySalesResult(
            **sale_totals(snapshot, resolved).model_dump(),
            weekly=WeeklyMovements(
                **{key: getattr(report, key) for key in WeeklyMovements.model_fields}
            ),
        )
    if name == "get_margin":
        closing = QuerySnapshot(
            snapshot.connection,
            clock=BusinessClock(resolved.end),
            known_at=snapshot.known,
        )
        try:
            unpriced = margin_report(closing, resolved).unpriced_sales_count
        except FinancialRuleError as error:
            if error.code != "MISSING_COSTS":
                raise
            unpriced = error.details["unpriced_sales_count"]
        return WeeklyMarginResult(
            range=report.range,
            gross_margin=report.gross_margin.margin,
            coverage_pct=report.gross_margin.coverage_pct,
            unpriced_sales_count=unpriced,
            shown=report.gross_margin.shown,
            note_key=report.gross_margin.note_key,
        )
    raise FinancialRuleError("VALIDATION_ERROR")
