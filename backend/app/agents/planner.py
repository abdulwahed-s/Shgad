"""D58 step 2: a verified interpretation -> resolved scope -> fixed tool calls.

Intent -> tools follows LABEL_RULES_V2 §2. BusinessClock (time_expressions)
owns every date, the ledger owns every identity, and the existing services own
every figure. The plan performs no arithmetic on money.
"""

import re
from dataclasses import dataclass, field
from datetime import timedelta

from app.schemas.evidence import CounterpartyView
from app.services.business_clock import BusinessClock, DateRange
from app.services.errors import FinancialRuleError
from app.services.financial_queries import QuerySnapshot
from app.services.reconcile import normalize_name
from app.services.time_expressions import resolve_time

TOOLS_BY_INTENT = {
    "sales": ("get_sales",),
    "cash_on_hand": ("get_debts",),
    "debts": ("get_debts",),
    "upcoming_obligations": ("get_debts",),
    "supplier_sufficiency": ("get_debts", "forecast"),
    "weekly_summary": ("get_sales", "get_debts", "get_margin", "reconcile"),
    "period_movements": ("get_sales",),
    "estimated_gross_margin": ("get_margin",),
    "reconciliation": ("reconcile",),
}
SCOPE = {
    "sales": "historical",
    "period_movements": "historical",
    "estimated_gross_margin": "historical",
    "reconciliation": "summary",
    "weekly_summary": "summary",
    "cash_on_hand": "snapshot",
    "debts": "snapshot",
    "upcoming_obligations": "forward",
    "supplier_sufficiency": "target",
}
REASON_KEYS = {
    "AMBIGUOUS_COUNTERPARTY": "clarify_customer",
    "UNKNOWN_COUNTERPARTY": "clarify_customer",
    "AMBIGUOUS_DATE": "clarify_period",
    "VALIDATION_ERROR": "clarify_period",
    "NO_HISTORICAL_DATA": "clarify_history",
    "MISSING_OPENING_BALANCE": "clarify_opening_balance",
    "MISSING_COSTS": "clarify_costs",
    "MISSING_DUE_DATE": "clarify_due_date",
    "REVIEW_REQUIRED": "clarify_request",
    "OUT_OF_SCOPE": "clarify_request",
}
_WEEKDAY_CODES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_ROLE_WORDS = {
    "ال",
    "مال",
    "حق",
    "المجهز",
    "مجهز",
    "للمجهز",
    "المورد",
    "مورد",
    "للمورد",
    "الزبون",
    "زبون",
    "للزبون",
    "العميل",
    "عميل",
    "الزباين",
    "زباين",
    "الزبائن",
    "الزبايين",
    "المجهزين",
    "مجهزين",
    "للمجهزين",
    "الموردين",
    "العملاء",
}


@dataclass(frozen=True)
class Call:
    name: str
    arguments: dict
    clock: BusinessClock
    server_range: DateRange | None = None
    plan: str = "interpretation"
    party: CounterpartyView | None = None


@dataclass(frozen=True)
class Plan:
    intent: str
    period: DateRange
    calls: tuple[Call, ...]
    parties: tuple[str, ...] = ()
    per_day: bool = False


@dataclass(frozen=True)
class Stop:
    """A clarification/refusal decided before any tool runs."""

    reason: str | None
    key: str
    status: str = "clarification"
    options: tuple[CounterpartyView, ...] = field(default=())


def clarify(reason, options=()):
    return Stop(reason, REASON_KEYS.get(reason, "clarify_request"), options=options)


def _words(value):
    return re.findall(r"[^\W_]+", normalize_name(value))


def _candidates(snapshot, mention, allowed):
    """Exact name, then substring, then every non-role word of the mention."""
    named = {
        key: normalize_name(name)
        for key, (name, kind) in snapshot.parties.items()
        if kind in allowed
    }
    form = normalize_name(mention)
    exact = [key for key, name in named.items() if name == form]
    if exact:
        return exact
    partial = [key for key, name in named.items() if form and form in name]
    if partial:
        return partial
    kept = [word for word in _words(mention) if word not in _ROLE_WORDS]
    if not kept:
        return []
    # Word containment, so "ابو علي دفتر ب" names only "ابو علي - دفتر ب".
    return [
        key
        for key, name in named.items()
        if " ".join(kept) in " ".join(_words(name))
        or all(word in _words(name) for word in kept)
    ]


def _generic(mention):
    return all(token in _ROLE_WORDS for token in normalize_name(mention).split())


def resolve_parties(snapshot, mentions, allowed):
    """Every mention must name exactly one party; never merge similar names."""
    found = []
    for mention in mentions:
        if _generic(mention):
            continue  # "المجهز" / "الزبون" alone names nobody in particular.
        matches = _candidates(snapshot, mention, allowed)
        if len(matches) > 1:
            return clarify(
                "AMBIGUOUS_COUNTERPARTY",
                tuple(snapshot.party(key) for key in sorted(matches)),
            )
        if not matches:
            return clarify("UNKNOWN_COUNTERPARTY")
        if matches[0] not in found:
            found.append(matches[0])
    return tuple(snapshot.party(key) for key in found)


def _explicit(resolved):
    return {
        "period": "explicit",
        "start_date": resolved.start.isoformat(),
        "end_date": resolved.end.isoformat(),
    }


def _is_week(resolved, today):
    start = resolved.start
    return start.weekday() == 5 and resolved.end == min(
        start + timedelta(days=6), today
    )


def plan(interpretation, *, connection, clock, known_at):
    intent = interpretation.intent
    if interpretation.behavior == "refuse":
        return Stop(None, intent, status="refused")
    if interpretation.behavior == "help":
        return Stop(None, "help", status="answered")
    if interpretation.behavior == "clarify":
        return clarify(interpretation.reason)
    if intent not in TOOLS_BY_INTENT:
        return clarify("OUT_OF_SCOPE")
    try:
        period = resolve_time(interpretation.time, clock, scope=SCOPE[intent])
    except FinancialRuleError as error:
        return clarify(error.code)
    snapshot = QuerySnapshot(connection, clock=clock, known_at=known_at)
    allowed = {"customer", "supplier"}
    parties = resolve_parties(snapshot, interpretation.party_mentions, allowed)
    if isinstance(parties, Stop):
        return parties
    collectors = resolve_parties(
        snapshot, interpretation.collection_party_mentions, {"customer"}
    )
    if isinstance(collectors, Stop):
        return collectors
    builder = _BUILDERS[intent]
    try:
        result = builder(interpretation, snapshot, clock, period, parties, collectors)
    except FinancialRuleError as error:
        return clarify(error.code)
    if isinstance(result, Stop):
        return result
    calls, named = result
    return Plan(
        intent,
        period,
        tuple(calls),
        tuple(sorted({p.id for p in named})),
        per_day=interpretation.per_day and intent == "upcoming_obligations",
    )


def _sales(interpretation, snapshot, clock, period, parties, collectors):
    arguments = _explicit(period) | {"kind": interpretation.sales_kind}
    return [Call("get_sales", arguments, clock, period)], ()


def _movements(interpretation, snapshot, clock, period, parties, collectors):
    arguments = _explicit(period) | {"kind": "all"}
    kind = (
        "expense_total" if interpretation.expense_kind_mention else "period_movements"
    )
    return [Call("get_sales", arguments, clock, period, kind)], ()


def _margin(interpretation, snapshot, clock, period, parties, collectors):
    return [Call("get_margin", _explicit(period), clock, period)], ()


def _reconcile(interpretation, snapshot, clock, period, parties, collectors):
    return [
        Call("reconcile", _explicit(period), clock, period, "reconciliation_summary")
    ], ()


def _cash(interpretation, snapshot, clock, period, parties, collectors):
    snapshot.cash()  # MISSING_OPENING_BALANCE clarifies, never a zero.
    arguments = {"direction": "both", "due_period": "next_n_days:1"}
    return [Call("get_debts", arguments, clock)], ()


def _direction(interpretation, snapshot, parties):
    kinds = {snapshot.parties[p.id][1] for p in parties}
    if kinds == {"supplier"}:
        return "payable"
    if kinds == {"customer"}:
        return "receivable"
    if kinds:
        return "both"
    return interpretation.direction


def _debts(interpretation, snapshot, clock, period, parties, collectors):
    direction = _direction(interpretation, snapshot, parties)
    base = {"direction": direction, "overdue_only": interpretation.overdue_only}
    if not parties:
        return [Call("get_debts", base, clock)], ()
    calls = []
    for party in parties:
        own = "payable" if snapshot.parties[party.id][1] == "supplier" else "receivable"
        arguments = base | {
            "direction": own if direction == "both" else direction,
            "counterparty_query": party.display_name,
        }
        calls.append(Call("get_debts", arguments, clock, party=party))
    return calls, parties


def _upcoming(interpretation, snapshot, clock, period, parties, collectors):
    days = (period.end - period.start).days + 1
    arguments = {"direction": "both", "due_period": f"next_n_days:{days}"}
    return [Call("get_debts", arguments, clock)], ()


def _sufficiency(interpretation, snapshot, clock, period, parties, collectors):
    target = period.end
    if (target - snapshot.day).days > 6:
        return clarify("OUT_OF_SCOPE")
    suppliers = [p for p in parties if snapshot.parties[p.id][1] == "supplier"]
    customers = [p for p in parties if snapshot.parties[p.id][1] == "customer"]
    customers += [c for c in collectors if c not in customers]
    if not suppliers:
        due = sorted(
            {
                b.obligation.counterparty_id
                for b in snapshot.balances
                if b.obligation.kind == "payable"
                and (target == snapshot.day or b.obligation.due_date == target)
            }
        )
        if len(due) > 1:
            return clarify(
                "AMBIGUOUS_COUNTERPARTY", tuple(snapshot.party(key) for key in due)
            )
        if not due:
            return clarify("MISSING_DUE_DATE")
        suppliers = [snapshot.party(due[0])]
    snapshot.cash()
    if target == snapshot.day:
        if len(suppliers) != 1:
            return clarify("AMBIGUOUS_COUNTERPARTY", tuple(suppliers))
        supplier = suppliers[0]
        return [
            Call(
                "get_debts",
                {"direction": "payable", "counterparty_query": supplier.display_name},
                clock,
                plan="payment_now",
                party=supplier,
            )
        ], (supplier,)
    calls = [
        Call(
            "get_debts",
            {"direction": "payable", "counterparty_query": s.display_name},
            clock,
            party=s,
        )
        for s in suppliers
    ]
    calls += [
        Call(
            "get_debts",
            {"direction": "receivable", "counterparty_query": c.display_name},
            clock,
            party=c,
        )
        for c in customers
    ]
    until = "next_weekday:" + _WEEKDAY_CODES[target.weekday()]
    calls.append(
        Call(
            "forecast",
            {"scenario": "all", "until": until},
            clock,
            plan="cash_sufficiency",
        )
    )
    return calls, (*suppliers, *customers)


def _summary(interpretation, snapshot, clock, period, parties, collectors):
    # Weeks reuse the D54 weekly views; other ranges use the same movement sums.
    # Balances are current (today), never a reconstructed earlier closing.
    week = _is_week(period, snapshot.day)
    sales_plan = "weekly_summary" if week else "period_movements"
    margin_plan = "weekly_summary" if week else "interpretation"
    return [
        Call(
            "get_sales", _explicit(period) | {"kind": "all"}, clock, period, sales_plan
        ),
        Call("get_debts", {"direction": "both"}, clock),
        Call("get_margin", _explicit(period), clock, period, margin_plan),
        Call("reconcile", _explicit(period), clock, period),
    ], ()


_BUILDERS = {
    "sales": _sales,
    "period_movements": _movements,
    "estimated_gross_margin": _margin,
    "reconciliation": _reconcile,
    "cash_on_hand": _cash,
    "debts": _debts,
    "upcoming_obligations": _upcoming,
    "supplier_sufficiency": _sufficiency,
    "weekly_summary": _summary,
}
