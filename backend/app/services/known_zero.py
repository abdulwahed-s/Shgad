"""D55 closed empty-event queries, never missing-value defaults or model SQL.

Only these exact financial event sums qualify. Nonempty sourced arithmetic,
balances, margins, count gaps and future estimates keep their existing evidence.
The registry creates the proof; verification recomputes it from the read snapshot.
"""

from datetime import timedelta, timezone

from app.schemas.queries import DateRangeView, DebtFilters
from app.schemas.tools import EmptyQueryFilters, KnownZeroDebtQuery, KnownZeroQuery
from app.services.business_clock import DateRange
from app.services.observed import OBSERVED_START

_BAGHDAD = timezone(timedelta(hours=3))

_EVENTS = {
    "cash_sales": ("CASH_SALE",),
    "credit_sales": ("CREDIT_SALE",),
    "total_sales": ("CASH_SALE", "CREDIT_SALE"),
    "weekly.collections": ("CREDIT_COLLECTION",),
    "weekly.supplier_payments": ("SUPPLIER_PAYMENT",),
    "weekly.operating_expenses": ("OPERATING_EXPENSE",),
    "weekly.owner_drawings": ("OWNER_DRAWING",),
    "weekly.capital_injections": ("CAPITAL_INJECTION",),
}


def debt_evidence(figure, *, snapshot, result):
    """A zero debt total is shown only when its exact filters select nothing."""
    from app.services.financial_queries import debt_report

    group = figure.key.removesuffix(".total_outstanding")
    report = (result or {}).get(group)
    # Historical reconstructions (an earlier day seen with later knowledge, as in
    # weekly closings) keep their existing evidence rules and get no proof.
    same_day = snapshot.known.astimezone(_BAGHDAD).date() == snapshot.day
    if (
        not same_day
        or group not in {"receivables", "payables"}
        or figure.amount_iqd != 0
        or figure.source_ids
        or figure.kind == "missing"
        or not isinstance(report, dict)
    ):
        return None
    filters = DebtFilters.model_validate(report["filters"])
    due = (
        DateRange(filters.due_start, filters.due_end)
        if filters.due_start is not None and filters.due_end is not None
        else None
    )
    selected = debt_report(
        snapshot,
        direction=filters.direction,
        overdue_only=filters.overdue_only,
        due_range=due,
        party_id=filters.counterparty_id,
    )
    if selected.customers or selected.total_outstanding.amount_iqd != 0:
        return None
    return KnownZeroDebtQuery(
        tool="get_debts", as_of=snapshot.day, filters=filters, known_at=snapshot.known
    )


def query_evidence(figure, *, snapshot, tool_name, resolved, result):
    if tool_name == "get_debts":
        return debt_evidence(figure, snapshot=snapshot, result=result)
    if (
        tool_name != "get_sales"
        or figure.amount_iqd != 0
        or figure.source_ids
        or figure.kind == "missing"
        or not OBSERVED_START <= resolved.start <= resolved.end <= snapshot.day
    ):
        return None
    key = figure.key
    if key == "selected_sales":
        key = {
            "cash": "cash_sales",
            "credit": "credit_sales",
            "all": "total_sales",
        }.get(result.get("kind"))
    events = _EVENTS.get(key)
    if events is None or any(
        row.type in events and resolved.start <= row.business_date <= resolved.end
        for row in snapshot.rows
    ):
        return None
    return KnownZeroQuery(
        tool="get_sales",
        period=DateRangeView(start=resolved.start, end=resolved.end),
        filters=EmptyQueryFilters(event_types=events, known_at=snapshot.known),
    )
