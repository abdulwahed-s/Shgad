"""Production secondary cash estimate, FINANCIAL_RULES §§2/3/5/6/11.

No file loading or evaluation dependency. The fixed method uses only the
repository's observed snapshot; all means/medians use exact rational arithmetic.
"""

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from fractions import Fraction

from app.db.forecast_repository import ForecastSnapshot, read_forecast_snapshot
from app.schemas.forecast import (
    Amount,
    Driver,
    Forecast,
    ForecastDay,
    ForecastReport,
    Lowest,
    OverdueExcluded,
)
from app.schemas.ledger import EventType
from app.services.business_clock import BusinessClock
from app.services.errors import FinancialRuleError
from app.services.ledger_rules import (
    cash_on_hand,
    daily_close,
    knowledge_cutoff,
    outstanding_balance,
)
from app.services.observed import OBSERVED_START, observed_day

_SCENARIOS = ("base", "conservative", "stress")


@dataclass(frozen=True)
class _SettlementLateness:
    days: int
    source_ids: tuple[str, ...]


def _rounded(value: Fraction) -> int:
    magnitude = (2 * abs(value.numerator) + value.denominator) // (
        2 * value.denominator
    )
    return magnitude if value >= 0 else -magnitude


def _median(values: list[int]) -> Fraction:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return (
        Fraction(ordered[middle])
        if len(ordered) % 2
        else Fraction(ordered[middle - 1] + ordered[middle], 2)
    )


def _missing(driver: str) -> None:
    raise FinancialRuleError("MISSING_FORECAST_HISTORY", details={"driver": driver})


def _historical_drivers(snapshot, cutoff):
    start = max(OBSERVED_START, cutoff - timedelta(days=55))
    days = [start + timedelta(days=i) for i in range((cutoff - start).days + 1)]
    sales = defaultdict(int)
    for row in snapshot.transactions:
        if row.type == EventType.CASH_SALE:
            sales[row.business_date] += row.amount_iqd
    weekday_sales, weekday_gaps = {}, {}
    gap_sources = []
    for weekday in range(7):
        dates = [day for day in days if day.weekday() == weekday]
        if not dates:
            _missing("cash_sales")
        weekday_sales[weekday] = _rounded(
            Fraction(sum(sales[d] for d in dates), len(dates))
        )
        available = []
        for day in dates:
            close = daily_close(
                snapshot.transactions,
                business_date=day,
                known_at=knowledge_cutoff(cutoff),
            )
            if close.unexplained_difference_iqd is not None:
                available.append(close.unexplained_difference_iqd)
                gap_sources.extend(close.source_ids)
        if not available:
            _missing("unlinked_cash")
        weekday_gaps[weekday] = _rounded(Fraction(sum(available), len(available)))
    expense_start = max(OBSERVED_START, cutoff - timedelta(days=27))
    expense_days = (cutoff - expense_start).days + 1
    expense_rows = [
        r for r in snapshot.transactions if r.business_date >= expense_start
    ]
    expenses = _rounded(
        Fraction(
            sum(
                r.amount_iqd
                for r in expense_rows
                if r.type == EventType.OPERATING_EXPENSE
            ),
            expense_days,
        )
    )
    drawings = _rounded(
        Fraction(
            sum(
                r.amount_iqd for r in expense_rows if r.type == EventType.OWNER_DRAWING
            ),
            expense_days,
        )
    )
    sources = {
        "cash_sales": tuple(
            r.source_id
            for r in snapshot.transactions
            if r.type == EventType.CASH_SALE and r.business_date >= start
        ),
        "unlinked_cash": tuple(dict.fromkeys(gap_sources)),
        "expenses": tuple(
            r.source_id for r in expense_rows if r.type == EventType.OPERATING_EXPENSE
        ),
        "owner_drawings": tuple(
            r.source_id for r in expense_rows if r.type == EventType.OWNER_DRAWING
        ),
    }
    return weekday_sales, weekday_gaps, expenses, drawings, sources


def _balances(snapshot: ForecastSnapshot):
    by_id = {r.transaction_id: r for r in snapshot.transactions}
    obligations = []
    lateness = defaultdict(list)
    for obligation in snapshot.obligations:
        links = [
            link
            for link in snapshot.payment_links
            if link.obligation_id == obligation.obligation_id
        ]
        balance = outstanding_balance(
            obligation.original_amount_iqd, (link.amount_iqd for link in links)
        )
        sources = tuple(
            dict.fromkeys(
                [by_id[obligation.origin_transaction_id].source_id]
                + [by_id[link.payment_transaction_id].source_id for link in links]
            )
        )
        obligations.append((obligation, balance, sources))
        if (
            balance == 0
            and obligation.kind == "receivable"
            and obligation.due_date is not None
        ):
            paid = 0
            for link in sorted(
                links,
                key=lambda link: (
                    by_id[link.payment_transaction_id].occurred_at,
                    link.payment_link_id,
                ),
            ):
                payment = by_id[link.payment_transaction_id]
                paid += link.amount_iqd
                if paid == obligation.original_amount_iqd:
                    lateness[obligation.counterparty_id].append(
                        _SettlementLateness(
                            max(0, (payment.business_date - obligation.due_date).days),
                            sources,
                        )
                    )
                    break
    return obligations, lateness


def _schedule(obligations, lateness, *, cutoff, scenario):
    collections, payables = defaultdict(int), defaultdict(int)
    collection_sources, payable_sources = [], []
    shop_lateness = [value for values in lateness.values() for value in values]
    for obligation, balance, sources in obligations:
        if not balance:
            continue
        due = obligation.due_date
        if due is None:
            raise FinancialRuleError(
                "MISSING_DUE_DATE", details={"obligation_id": obligation.obligation_id}
            )
        if obligation.kind == "payable":
            payables[due] += balance
            if cutoff < due <= cutoff + timedelta(days=31):
                payable_sources.extend(sources)
        elif due >= cutoff and scenario != "stress":
            arrival = due
            timing_sources = []
            if scenario == "conservative" and due <= cutoff + timedelta(days=30):
                customer_history = lateness.get(obligation.counterparty_id, [])
                values = (
                    customer_history if len(customer_history) >= 2 else shop_lateness
                )
                if not values:
                    _missing("collection_lateness")
                arrival += timedelta(days=_rounded(_median([r.days for r in values])))
                timing_sources.extend(s for r in values for s in r.source_ids)
            if cutoff < arrival <= cutoff + timedelta(days=30):
                collections[arrival] += balance
                collection_sources.extend(sources)
                collection_sources.extend(timing_sources)
    return (
        collections,
        payables,
        tuple(dict.fromkeys(collection_sources)),
        tuple(dict.fromkeys(payable_sources)),
    )


def _top_drivers(days, sources, *, inflows):
    fields = (
        ("cash_sales", "unlinked_cash", "collections")
        if inflows
        else ("supplier_payments", "expenses", "owner_drawings", "unlinked_cash")
    )
    drivers = []
    for field in fields:
        values = [getattr(row, f"{field}_iqd") for row in days]
        amount = sum(
            max(0, value if inflows or field != "unlinked_cash" else -value)
            for value in values
        )
        if amount:
            drivers.append(
                Driver(
                    label_key=field,
                    amount=Amount(
                        amount_iqd=amount,
                        kind="expected",
                        label_key=field,
                        source_ids=sources[field],
                        formula=(
                            f"FINANCIAL_RULES §6: sum projected {field} "
                            f"{'inflows' if inflows else 'outflows'} over 30 days"
                        ),
                    ),
                )
            )
    return tuple(sorted(drivers, key=lambda d: (-d.amount.amount_iqd, d.label_key))[:3])


def forecast(
    connection: sqlite3.Connection, *, clock: BusinessClock, scenario: str = "all"
) -> ForecastReport:
    """Return real base/conservative/stress forecasts, or a typed clarification.

    The cutoff cannot exceed the application's observed-data boundary. All input
    series come from the same repository snapshot; no state is cached across calls.
    """
    cutoff = observed_day(clock)
    if scenario not in (*_SCENARIOS, "all"):
        raise FinancialRuleError("VALIDATION_ERROR")
    snapshot = read_forecast_snapshot(connection, clock=clock)
    starting = cash_on_hand(
        snapshot.transactions, as_of=cutoff, opening_balance=snapshot.opening_balance
    )
    sales, gaps, expenses, drawings, sources = _historical_drivers(snapshot, cutoff)
    obligations, lateness = _balances(snapshot)
    overdue = tuple(
        OverdueExcluded(
            obligation_id=o.obligation_id,
            outstanding=Amount(
                amount_iqd=balance,
                kind="calculated",
                label_key="overdue_receivable",
                source_ids=evidence,
                formula=(
                    "FINANCIAL_RULES §5: original minus cutoff-visible "
                    "verified allocations"
                ),
            ),
        )
        for o, balance, evidence in obligations
        if o.kind == "receivable"
        and balance
        and o.due_date is not None
        and o.due_date < cutoff
    )
    forecasts = {}
    for name in _SCENARIOS if scenario == "all" else (scenario,):
        collections, payments, collection_sources, payable_sources = _schedule(
            obligations, lateness, cutoff=cutoff, scenario=name
        )
        driver_sources = sources | {
            "collections": collection_sources,
            "supplier_payments": payable_sources,
        }
        days = []
        opening = starting.amount_iqd
        for offset in range(1, 31):
            day = cutoff + timedelta(days=offset)
            closing = (
                opening
                + sales[day.weekday()]
                + gaps[day.weekday()]
                + collections[day]
                - payments[day]
                - expenses
                - drawings
            )
            days.append(
                ForecastDay(
                    date=day,
                    opening_iqd=opening,
                    cash_sales_iqd=sales[day.weekday()],
                    unlinked_cash_iqd=gaps[day.weekday()],
                    collections_iqd=collections[day],
                    supplier_payments_iqd=payments[day],
                    expenses_iqd=expenses,
                    owner_drawings_iqd=drawings,
                    closing_iqd=closing,
                )
            )
            opening = closing
        lowest = min(days, key=lambda d: d.closing_iqd)
        shortfall = next(
            (
                row.date
                for row in days
                if row.closing_iqd < 0
                or row.closing_iqd < payments[row.date + timedelta(days=1)]
            ),
            None,
        )
        forecasts[name] = Forecast(
            days=tuple(days),
            lowest=Lowest(date=lowest.date, closing_iqd=lowest.closing_iqd),
            first_shortfall_date=shortfall,
            top_inflows=_top_drivers(days, driver_sources, inflows=True),
            top_outflows=_top_drivers(days, driver_sources, inflows=False),
        )
    return ForecastReport(
        as_of=cutoff,
        scenarios=forecasts,
        overdue_excluded=overdue,
        assumption_keys=(
            "collections_expected_not_guaranteed",
            "sales_from_weekday_averages",
            "unlinked_cash_projected_from_counts",
        ),
    )
