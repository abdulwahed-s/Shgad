"""D55 closed empty-event queries, never missing-value defaults or model SQL.

Only these exact financial event sums qualify. Nonempty sourced arithmetic,
balances, margins, count gaps and future estimates keep their existing evidence.
The registry creates the proof; verification recomputes it from the read snapshot.
"""

from app.schemas.queries import DateRangeView
from app.schemas.tools import EmptyQueryFilters, KnownZeroQuery
from app.services.observed import OBSERVED_START

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


def query_evidence(figure, *, snapshot, tool_name, resolved, result):
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
