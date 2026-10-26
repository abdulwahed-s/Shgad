"""D53 conservative safe outcomes, derived from financial/API rules.

Rule                         Outcome / evidence
Direct ledger-write command  refused / approved entry-form guidance
Explicit policy override     refused / approved unsafe-instruction text
Tax filing/software/other DB clarify_request; ordinary tax expenses stay readable
Unavailable historical range clarify_history / existing historical_range validator
Missing margin costs         clarify_costs / existing priced-sale eligibility rule
Unresolved named party       clarify_customer / exact existing identity resolver

Uncertain requests return None. This is not a general intent classifier. Only
merchant message text is examined; imported descriptions are never scanned for
commands. No evaluation files/labels, numerical answers, or new Arabic copy.
"""

import re
from dataclasses import dataclass
from datetime import date

from app.schemas.evidence import CounterpartyView
from app.services.errors import FinancialRuleError
from app.services.financial_queries import QuerySnapshot, historical_range
from app.services.margin import recorded_sales
from app.services.reconcile import normalize_name
from app.services.validation import normalize_digits


@dataclass(frozen=True)
class SafeDecision:
    key: str
    status: str = "clarification"
    options: tuple[CounterpartyView, ...] = ()


def normalized(message):
    return normalize_name(normalize_digits(message))


def debt_list_request(message):
    """J2 asks who owes: preserve each verified customer's outstanding value."""
    value = normalized(message)
    return _has(r"منو|اي\s+زبون|يا\s+زبون", value) and _has(
        r"(?:ال)?مديون(?:ين|ون)?|(?:ال)?مدين(?:ين|ون)?|ديون|بذمته|بذمتهم", value
    )


def _has(pattern, message):
    return re.search(r"(?<!\w)(?:" + pattern + r")(?!\w)", message) is not None


def margin_request(message):
    value = normalized(message)
    if not _has(r"ربح|ربحت|الربح|ارباح|الارباح|هامش|الهامش|هامشي", value):
        return False
    if _has(r"معني|تعريف|الفرق", value):
        return False
    # A compound request can legitimately need both sales and margin tools.
    if re.search(
        r"(?:المبيعات|الديون|التحصيلات)\s+و(?:الربح|الهامش)|"
        r"(?:الربح|الهامش).*\sو(?:المبيعات|الديون|التحصيلات)",
        value,
    ):
        return False
    return True


def _historical_request(value):
    return _has(
        r"مبيعات|المبيعات|بيع|البيع|بعت|بعنا|ربح|ربحت|الربح|هامش|الهامش|مصاريف|المصاريف|سحوبات",
        value,
    ) and not _has(
        r"توقع|التوقع|توقعات|تنبؤ|متوقع|المتوقع|متوقعه|المتوقعه|"
        r"استحقاق|المستحقه|التزامات",
        value,
    )


def _range_decision(clock, period, **arguments):
    try:
        historical_range(clock, period, **arguments)
    except FinancialRuleError as error:
        return SafeDecision(
            "clarify_history" if error.code == "NOT_FOUND" else "clarify_period"
        )
    return None


_NAME_STOPS = {
    "شكد",
    "كم",
    "شنو",
    "باقي",
    "بقي",
    "المتبقي",
    "عليه",
    "عليها",
    "عليهم",
    "دفع",
    "سدد",
    "الدين",
    "ديون",
    "المتاخر",
    "المتاخره",
    "الجديد",
    "الرئيسي",
    "اليوم",
    "امس",
    "البارحه",
    "هسه",
    "هالاسبوع",
    "الخميس",
    "الجمعه",
    "السبت",
    "الاحد",
    "الاثنين",
    "الثلاثاء",
    "الاربعاء",
    "الجاي",
    "لو",
    "اذا",
    "اكدر",
    "اللي",
    "الي",
    "شلون",
    "وين",
    "عنده",
    "كل",
    "كلهم",
}


def _named_queries(value, snapshot):
    queries = set()
    for match in re.finditer(
        r"(?<!\w)(?:ابو|ام|الزبون|العميل|المجهز|المورد)\s+", value
    ):
        tail = value[match.end() :].split()
        kept = []
        for token in tail[:4]:
            token = token.strip("؟?،,.!:")
            if not token or token in _NAME_STOPS or re.search(r"[0-9]", token):
                break
            kept.append(token)
        if kept:
            prefix = match[0].strip()
            query = " ".join(([prefix] if prefix in {"ابو", "ام"} else []) + kept)
            queries.add(query)
    # Full names cover non-kunya names without attempting arbitrary name generation.
    matches = []
    for name, _ in snapshot.parties.values():
        query = normalize_name(name)
        if query and _has(re.escape(query), value):
            matches.append(query)
    queries.update(
        q for q in matches if not any(q != other and q in other for other in matches)
    )
    return {
        q
        for q in queries
        if not any(q != other and _has(re.escape(q), other) for other in queries)
    }


def _party_decision(snapshot, query, direction):
    try:
        snapshot.resolve_party(query, direction)
    except FinancialRuleError as error:
        if error.code not in {"AMBIGUOUS_COUNTERPARTY", "NOT_FOUND"}:
            raise
        return SafeDecision(
            "clarify_customer",
            options=tuple(
                CounterpartyView.model_validate(row)
                for row in error.details.get("options", ())
            ),
        )
    return None


def before_provider(message, *, connection, clock, known_at, period):
    value = normalized(message)
    if re.search(r"(?:تجاهل|اترك|انس)\s+(?:القواعد|التعليمات|القوانين)", value):
        return SafeDecision("unsafe_instruction", "refused")
    write = re.match(
        r"^(?:(?:رجاء|لو سمحت|اريدك|ممكن)\s+)?"
        r"(?:سجل|امسح|احذف|عدل|الغي|الغ|غير|ادفع|سدد)(?!\w)",
        value,
    )
    # 'سجل المبيعات شنو بيه' is a noun/report request, not an instruction to write.
    register_question = (
        value.startswith("سجل ")
        and _has(r"شنو|شكد|كم|وريني|اعرض", value)
        and not re.search(r"[0-9]", value)
    )
    if write and not register_question:
        return SafeDecision("unsupported_write", "refused")
    if re.search(
        r"(?:جهز|قدم|سو|اكتب|احسب).*الاقرار\s+الضريبي|"
        r"(?:صمم|اكتب|انشئ|سوي).*برنامج\s+محاسبه|"
        r"حسابات\s+(?:محل|متجر)\s+(?:ثاني|اخر)",
        value,
    ):
        return SafeDecision("clarify_request")
    profit = margin_request(value)
    if profit and re.search(
        r"(?:ما|مو|لم)\s*(?:مسجل|مسجله|مسجلها|سجلت|سجلتهن)|"
        r"(?:بدون|ما بيها)\s+اسعار\s+شراء",
        value,
    ):
        return SafeDecision("clarify_costs")
    if _historical_request(value) or (profit and period.month is not None):
        dates = re.findall(r"(?<![0-9])[0-9]{4}-[0-9]{2}-[0-9]{2}(?![0-9])", value)
        if 1 <= len(dates) <= 2:
            try:
                first, last = (
                    date.fromisoformat(dates[0]),
                    date.fromisoformat(dates[-1]),
                )
            except ValueError:
                return SafeDecision("clarify_period")
            decision = _range_decision(
                clock, "explicit", start_date=first, end_date=last, dates_from_user=True
            )
            if decision:
                return decision
        elif period.status == "resolved":
            resolved = period.resolve(clock)
            decision = _range_decision(
                clock,
                "explicit",
                start_date=resolved.start,
                end_date=resolved.end,
                trusted_range=resolved,
            )
            if decision:
                return decision
        if re.search(r"قبل\s+(?:بدايه\s+الدفتر|هالدفتر|الدفتر|السجلات)", value):
            return SafeDecision("clarify_history")
    if not profit and not _has(r"ابو|ام|الزبون|العميل|المجهز|المورد|عليه|بذمته", value):
        return None
    snapshot = QuerySnapshot(connection, clock=clock, known_at=known_at)
    if profit and period.status == "resolved":
        selected = period.resolve(clock)
        resolved = historical_range(
            clock,
            "explicit",
            start_date=selected.start,
            end_date=selected.end,
            trusted_range=selected,
        )
        # Reuse the same eligible-sale filter as margin_report; never invent a zero.
        sales = recorded_sales(snapshot, resolved)
        if not any(
            row.category_id in snapshot.categories
            and snapshot.categories[row.category_id].buy_price_iqd is not None
            for row in sales
        ):
            return SafeDecision("clarify_costs")
    customer = _has(r"الزبون|العميل|عليه|بذمته", value)
    supplier = _has(r"المجهز|المورد|يطلبني", value)
    direction = (
        "receivable"
        if customer and not supplier
        else "payable"
        if supplier and not customer
        else "both"
    )
    for query in sorted(_named_queries(value, snapshot)):
        # A named customer paying in the if-clause is a receivable even when
        # the main clause mentions a supplier. Other explicit roles stay intact.
        conditional_collection = supplier and re.search(
            r"(?:اذا|لو)\s+(?:(?:الزبون|العميل)\s+)?"
            + re.escape(query)
            + r"\s+(?:دفع|سدد)(?!\w)",
            value,
        )
        decision = _party_decision(
            snapshot, query, "receivable" if conditional_collection else direction
        )
        if decision:
            return decision
    return None


def after_selection(
    message, name, arguments, *, connection, clock, known_at, trusted_party=None
):
    if name in {"get_sales", "get_margin", "reconcile"} and isinstance(
        arguments.get("period"), str
    ):
        # Explicit dates still require the unchanged registry's user-text proof.
        if arguments["period"] != "explicit":
            decision = _range_decision(clock, arguments["period"])
            if decision:
                return decision
    if name == "get_debts" and isinstance(arguments.get("counterparty_query"), str):
        query = arguments["counterparty_query"]
        if trusted_party is None and normalize_name(query) not in normalize_name(
            message
        ):
            return SafeDecision("clarify_customer")
        direction = arguments.get("direction", "receivable")
        if not isinstance(direction, str) or direction not in {
            "receivable",
            "payable",
            "both",
        }:
            return None  # The closed tool schema retains ownership of invalid args.
        snapshot = QuerySnapshot(connection, clock=clock, known_at=known_at)
        if trusted_party is not None:
            party = snapshot.resolve_party(query, direction)
            if party.id != trusted_party.id or query != trusted_party.display_name:
                return SafeDecision("clarify_customer")
        return _party_decision(snapshot, query, direction)
    return None
