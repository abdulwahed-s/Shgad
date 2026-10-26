"""Conservative D54 plans; interpretation stays with the model when uncertain.

Catalogue                        Plan (no arithmetic here)
Weekly overview + this/last week  sales, balances at week end, weekly margin, flags
Drawings vs store expenses/week   same weekly composition, separate sourced facts
Can pay supplier + weekday       exact identities, debts + existing global J1
Without collections + shortfall  same J1, always restate both existing scenarios

Only merchant text is matched. No evaluation-input access, generated dates,
amounts, selective counterfactuals, or new tools. BusinessClock and the existing
financial services own the meanings of every period, balance and calculation.
"""

import re
from dataclasses import dataclass

from app.agents import answer_policy
from app.agents.answer_policy import SafeDecision, normalized
from app.schemas.evidence import CounterpartyView
from app.services.business_clock import BusinessClock
from app.services.errors import FinancialRuleError
from app.services.financial_queries import QuerySnapshot, historical_range


@dataclass(frozen=True)
class PlannedCall:
    name: str
    arguments: dict
    clock: BusinessClock
    party: CounterpartyView | None = None


@dataclass(frozen=True)
class ToolPlan:
    kind: str
    calls: tuple[PlannedCall, ...]


def weekly_period(message, period):
    if period.status != "resolved" or period.period not in {"this_week", "last_week"}:
        return None
    value = normalized(message)
    if re.search(r"(?<!\w)(?:مو|ما\s+اريد)\s+(?:ملخص|لخص)", value):
        return None
    # Specific sales/debt summaries still belong to the normal tool-choice loop.
    specific = re.search(
        r"(?:لخص\s*لي|لخصلي|ملخص|تقرير\s+شامل)\s+(?:عن\s+)?(?:مبيعات|ديون|المبيعات|الديون)",
        value,
    )
    overview = re.search(
        r"لخص\s*لي|لخصلي|ملخص|تقرير\s+شامل|"
        r"شلون\s+(?:(?:جان|كان|مشي)\s+)?(?:الشغل|شغل|شغلنا|المحل)",
        value,
    )
    drawings = re.search(r"سحوبات|سحب\s+(?:المالك|صاحب\s+المحل)|فلوس\s+البيت", value)
    expenses = re.search(r"مصاريف\s+المحل|سحوبات\s+ومصاريف", value)
    return (
        period.period
        if (overview and not specific) or (drawings and expenses)
        else None
    )


def cash_request(message, period):
    if period.status != "resolved" or not period.period.startswith("next_weekday:"):
        return False
    value = normalized(message)
    supplier = re.search(r"(?<!\w)(?:للمجهز|المجهز|مجهز|المورد|للمورد)(?!\w)", value)
    ability = re.search(r"اكدر|اگدر|اقدر|نكدر|[يت]كفي|كافي", value)
    payment = re.search(r"ادفع|ندفع|اسدد|اوفي|اغطي|سداد|لدفع|تسديد", value)
    without = without_collection(value)
    shortfall = re.search(r"نقص|ينقص|عجز", value)
    cash = re.search(r"فلوس|نقد|رصيد", value)
    return bool(
        supplier and ((ability and (payment or cash)) or (without and shortfall))
    )


def without_collection(value):
    return (
        re.search(
            r"(?:بدون|بلا|من\s+غير)\s+(?:تحصيل|تسديد|ما\s+يدفع)|"
            r"(?:ما|مي)\s*(?:يجيني|يوصلني|وصلني|استلمت)\s+(?:التحصيل|التسديد)|"
            r"ما\s+(?:دفع\s+الزبون|حصلت\s+ديوني|انجبي\s+الدين|وصل\s+التحصيل)",
            value,
        )
        is not None
    )


def _choose(snapshot, parties):
    ids = tuple(dict.fromkeys(parties))
    if len(ids) == 1:
        return snapshot.party(ids[0])
    return SafeDecision(
        "clarify_customer", options=tuple(snapshot.party(key) for key in ids)
    )


def select_plan(message, *, period, connection, clock, known_at):
    week = weekly_period(message, period)
    if week:
        try:
            resolved = historical_range(clock, week)
        except FinancialRuleError:
            return SafeDecision("clarify_history")
        return ToolPlan(
            "weekly_summary",
            (
                PlannedCall("get_sales", {"period": week, "kind": "all"}, clock),
                PlannedCall(
                    "get_debts", {"direction": "both"}, BusinessClock(resolved.end)
                ),
                PlannedCall("get_margin", {"period": week}, clock),
                PlannedCall("reconcile", {"period": week}, clock),
            ),
        )
    if not cash_request(message, period):
        return None
    snapshot = QuerySnapshot(connection, clock=clock, known_at=known_at)
    target = clock.resolve(period.period).end
    suppliers = {
        b.obligation.counterparty_id
        for b in snapshot.balances
        if b.obligation.kind == "payable" and b.obligation.due_date == target
    }
    parties = {"supplier": [], "customer": []}
    for query in sorted(answer_policy._named_queries(normalized(message), snapshot)):
        try:
            party = snapshot.resolve_party(query, "both")
        except FinancialRuleError as error:
            return SafeDecision(
                "clarify_customer",
                options=tuple(
                    CounterpartyView.model_validate(row)
                    for row in error.details.get("options", ())
                ),
            )
        parties[snapshot.parties[party.id][1]].append(party.id)
    if not parties["supplier"] and not suppliers:
        return None
    supplier = _choose(snapshot, parties["supplier"] or sorted(suppliers))
    if isinstance(supplier, SafeDecision):
        return supplier
    customer = None
    value = normalized(message)
    if parties["customer"] or (
        not without_collection(value) and re.search(r"(?<!\w)(?:اذا|لو)(?!\w)", value)
    ):
        customer = _choose(
            snapshot,
            parties["customer"]
            or [
                key for key, (_, kind) in snapshot.parties.items() if kind == "customer"
            ],
        )
        if isinstance(customer, SafeDecision):
            return customer
    # §7 is global, not a selective "only this customer/invoice" counterfactual.
    # Defer to interpretation when named scope differs; never change the formula.
    customers = {
        b.obligation.counterparty_id
        for b in snapshot.balances
        if b.obligation.kind == "receivable"
        and b.obligation.due_date is not None
        and snapshot.day <= b.obligation.due_date <= target
    }
    if suppliers != {supplier.id} or (customer and customers != {customer.id}):
        return None
    try:
        snapshot.cash()
    except FinancialRuleError as error:
        if error.code != "MISSING_OPENING_BALANCE":
            raise
        return SafeDecision("clarify_opening_balance")
    calls = [
        PlannedCall(
            "get_debts",
            {
                "direction": "payable",
                "counterparty_query": supplier.display_name,
            },
            clock,
            supplier,
        )
    ]
    if customer:
        calls.append(
            PlannedCall(
                "get_debts",
                {
                    "direction": "receivable",
                    "counterparty_query": customer.display_name,
                },
                clock,
                customer,
            )
        )
    calls.append(
        PlannedCall("forecast", {"scenario": "all", "until": period.period}, clock)
    )
    return ToolPlan("cash_sufficiency", tuple(calls))
