"""FINANCIAL_RULES §4: priced recorded sales only, with honest coverage."""

from app.schemas.queries import ReportRange
from app.schemas.reports import MarginReport, PriceBasis
from app.schemas.tools import Metric
from app.services.errors import FinancialRuleError
from app.services.financial_queries import amount, sources


def recorded_sales(snapshot, resolved):
    return tuple(
        r
        for r in snapshot.rows
        if r.type in {"CASH_SALE", "CREDIT_SALE"}
        and resolved.start <= r.business_date <= resolved.end
    )


def margin_report(snapshot, resolved):
    sales = recorded_sales(snapshot, resolved)
    priced = tuple(
        r
        for r in sales
        if r.category_id in snapshot.categories
        and snapshot.categories[r.category_id].buy_price_iqd is not None
    )
    total = sum(r.amount_iqd for r in sales)
    priced_total = sum(r.amount_iqd for r in priced)
    coverage = 100 * priced_total // total if total else None
    if not priced:
        raise FinancialRuleError(
            "MISSING_COSTS",
            details={"coverage_pct": coverage, "unpriced_sales_count": len(sales)},
        )
    categories = tuple(sorted({r.category_id for r in priced}))
    sale_sources = tuple(r.source_id for r in priced)
    cost = sum(
        r.quantity * snapshot.categories[r.category_id].buy_price_iqd for r in priced
    )
    evidence = sources(sale_sources, categories)
    expenses = tuple(
        r
        for r in snapshot.rows
        if r.type == "OPERATING_EXPENSE"
        and resolved.start <= r.business_date <= resolved.end
    )
    return MarginReport(
        range=ReportRange(
            start=resolved.start, end=resolved.end, partial=resolved.partial
        ),
        gross_margin=amount(
            priced_total - cost,
            "estimated_gross_margin",
            evidence,
            "FINANCIAL_RULES §4: priced sales - sum(quantity * category buy price)",
        ),
        coverage_pct=coverage,
        unpriced_sales_count=len(sales) - len(priced),
        after_recorded_expenses=amount(
            priced_total - cost - sum(r.amount_iqd for r in expenses),
            "after_recorded_expenses",
            sources(evidence, (r.source_id for r in expenses)),
            "estimated gross margin - recorded operating expenses; "
            "unrecorded costs excluded",
        ),
        priced_sales=amount(
            priced_total,
            "priced_recorded_sales",
            sale_sources,
            "sum recorded sales with a known category buy price",
        ),
        cost_of_goods=amount(
            cost,
            "cost_of_goods",
            evidence,
            "sum(quantity * category buy price) on priced recorded sales",
        ),
        price_basis=tuple(
            PriceBasis(
                category_id=key,
                buy_price=amount(
                    snapshot.categories[key].buy_price_iqd,
                    "category_buy_price",
                    (key,),
                    "verified category reference buy_price_iqd",
                    kind="verified",
                ),
            )
            for key in categories
        ),
    )


def margin_metrics(snapshot, resolved, report):
    evidence = tuple(r.source_id for r in recorded_sales(snapshot, resolved))
    return (
        Metric(
            key="coverage_pct",
            value=report.coverage_pct,
            unit="percent",
            kind="missing" if report.coverage_pct is None else "calculated",
            label_key="recorded_sales_coverage",
            source_ids=evidence,
            formula="floor(100 * priced recorded sales / total recorded cash "
            "and credit sales); count differences excluded",
        ),
        Metric(
            key="unpriced_sales_count",
            value=report.unpriced_sales_count,
            unit="count",
            kind="calculated",
            label_key="unpriced_sales_count",
            source_ids=evidence,
            formula="count recorded sale rows without a known category buy price",
        ),
    )
