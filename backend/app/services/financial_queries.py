"""Read-only normalized ledger queries, FINANCIAL_RULES §§2/3/5/7a/11.

All tables are read in one snapshot bounded by financial and audit knowledge.
No file paths, provider, arbitrary SQL or persistence are exposed to tools.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from app.schemas.evidence import CounterpartyView
from app.schemas.forecast import Amount
from app.schemas.ledger import Category, Obligation, OpeningBalance
from app.schemas.queries import (
    Aging,
    DateRangeView,
    DebtObligation,
    DebtParty,
    DebtReport,
    DueItem,
    OverdueItem,
    PaymentCapacity,
    PositionDay,
    ReportRange,
    SalesReport,
    UpcomingItem,
    UpcomingObligations,
)
from app.services.business_clock import BusinessClock
from app.services.errors import FinancialRuleError
from app.services.ledger_audit import read_ledger
from app.services.ledger_rules import (
    active_transactions,
    cash_difference_in_range,
    cash_on_hand,
    knowledge_cutoff,
    outstanding_balance,
)
from app.services.observed import OBSERVED_START, observed_day
from app.services.reconcile import normalize_name


def sources(*groups):
    return tuple(dict.fromkeys(s for group in groups for s in group))


def amount(value, label, ids, formula, *, kind="calculated"):
    return Amount(
        amount_iqd=value,
        kind="missing" if value is None else kind,
        label_key=label,
        source_ids=tuple(ids),
        formula=formula,
    )


@dataclass(frozen=True)
class Balance:
    obligation: Obligation
    amount_iqd: int
    source_ids: tuple[str, ...]
    collections: tuple[str, ...]
    original_source: str


class QuerySnapshot:
    def __init__(self, connection, *, clock: BusinessClock, known_at=None):
        self.connection = connection
        self.day = observed_day(clock)
        self.known = knowledge_cutoff(self.day, known_at)
        connection.execute("SAVEPOINT financial_query")
        try:
            self.ledger = read_ledger(connection, as_of=self.day, known_at=self.known)
            self.rows = active_transactions(
                self.ledger.transactions,
                as_of=self.day,
                voids=self.ledger.voids,
                known_at=self.known,
            )
            self.parties = {
                row["counterparty_id"]: (row["display_name"], row["kind"])
                for row in connection.execute("SELECT * FROM counterparties")
            }
            self.categories = {
                row["category_id"]: Category.model_validate(dict(row))
                for row in connection.execute("SELECT * FROM categories")
            }
            opening = connection.execute(
                """SELECT o.* FROM opening_balances o JOIN import_batches b
                USING (import_batch_id)
                WHERE o.business_date <= ? AND b.imported_at <= ?
                ORDER BY o.business_date DESC LIMIT 1""",
                (str(self.day), self.known.isoformat()),
            ).fetchone()
            self.opening = (
                OpeningBalance.model_validate(dict(opening)) if opening else None
            )
        finally:
            connection.execute("RELEASE SAVEPOINT financial_query")
        by_id = {r.transaction_id: r for r in self.rows}
        self.balances = []
        for obligation in self.ledger.obligations:
            if obligation.origin_transaction_id not in by_id:
                continue
            links = [
                link
                for link in self.ledger.payment_links
                if link.obligation_id == obligation.obligation_id
                and link.payment_transaction_id in by_id
            ]
            origin = by_id[obligation.origin_transaction_id].source_id
            payments = tuple(
                by_id[link.payment_transaction_id].source_id for link in links
            )
            remaining = outstanding_balance(
                obligation.original_amount_iqd, (link.amount_iqd for link in links)
            )
            if remaining:
                self.balances.append(
                    Balance(
                        obligation,
                        remaining,
                        sources((origin,), payments),
                        payments,
                        origin,
                    )
                )

    def party(self, party_id):
        return CounterpartyView(id=party_id, display_name=self.parties[party_id][0])

    def resolve_party(self, query, direction):
        if query is None:
            return None
        allowed = (
            {"customer", "supplier"}
            if direction == "both"
            else {"customer" if direction == "receivable" else "supplier"}
        )
        normalized = normalize_name(query)
        matches = [
            key
            for key, (name, kind) in self.parties.items()
            if kind in allowed and normalized and normalized in normalize_name(name)
        ]
        exact = [
            key for key in matches if normalize_name(self.parties[key][0]) == normalized
        ]
        matches = exact or matches
        if len(matches) > 1:
            raise FinancialRuleError(
                "AMBIGUOUS_COUNTERPARTY",
                details={
                    "options": [self.party(key).model_dump() for key in sorted(matches)]
                },
            )
        if not matches:
            raise FinancialRuleError("NOT_FOUND")
        return self.party(matches[0])

    def cash(self):
        position = cash_on_hand(
            self.rows, as_of=self.day, opening_balance=self.opening, known_at=self.known
        )
        counts = [r for r in self.rows if r.type == "DAILY_CASH_COUNT"]
        return amount(
            position.amount_iqd,
            "cash_on_hand",
            position.source_ids,
            "FINANCIAL_RULES §2: latest count/opening + later cash flows",
            kind="verified",
        ), counts[-1].occurred_at if counts else None


def historical_range(
    clock,
    period,
    *,
    start_date=None,
    end_date=None,
    dates_from_user=False,
    trusted_range=None,
):
    resolved = clock.resolve(
        period,
        start_date=start_date,
        end_date=end_date,
        dates_from_user=dates_from_user,
        trusted_range=trusted_range,
    )
    if not OBSERVED_START <= resolved.start <= resolved.end <= observed_day(clock):
        raise FinancialRuleError(
            "NOT_FOUND", details={"reason": "OUTSIDE_OBSERVED_DATA"}
        )
    return resolved


def sale_totals(snapshot, resolved, *, kind="all"):
    rows = [
        r for r in snapshot.rows if resolved.start <= r.business_date <= resolved.end
    ]

    def total(kind, label):
        selected = [r for r in rows if r.type == kind]
        return amount(
            sum(r.amount_iqd for r in selected),
            label,
            (r.source_id for r in selected),
            f"sum active recorded {kind} in resolved range",
        )

    cash, credit = (
        total("CASH_SALE", "recorded_cash_sales"),
        total("CREDIT_SALE", "credit_sales"),
    )
    gap = cash_difference_in_range(
        snapshot.rows, start=resolved.start, end=resolved.end, known_at=snapshot.known
    )
    total = amount(
        cash.amount_iqd + credit.amount_iqd,
        "total_recorded_sales",
        sources(cash.source_ids, credit.source_ids),
        "recorded cash sales + recorded credit sales",
    )
    return SalesReport(
        range=ReportRange(
            start=resolved.start, end=resolved.end, partial=resolved.partial
        ),
        cash_sales=cash,
        credit_sales=credit,
        unexplained_cash_difference=amount(
            gap.amount_iqd,
            "unexplained_cash_difference",
            gap.source_ids,
            "FINANCIAL_RULES §3: sum(count - previous count - inflows + outflows); "
            "consecutive counts required",
            kind=gap.kind,
        ),
        total_sales=total,
        kind=kind,
        selected_sales={"cash": cash, "credit": credit, "all": total}[kind],
    )


def aging_bucket(days):
    return (
        "not_due"
        if days == 0
        else "d1_7"
        if days <= 7
        else "d8_30"
        if days <= 30
        else "d31_60"
        if days <= 60
        else "d60_plus"
    )


def debt_report(
    snapshot,
    *,
    direction="receivable",
    overdue_only=False,
    due_range=None,
    party_id=None,
):
    selected = [
        b
        for b in snapshot.balances
        if b.obligation.kind == direction
        and (party_id is None or b.obligation.counterparty_id == party_id)
    ]
    if (due_range or overdue_only) and any(
        b.obligation.due_date is None for b in selected
    ):
        raise FinancialRuleError("MISSING_DUE_DATE")
    selected = [
        b
        for b in selected
        if (not overdue_only or b.obligation.due_date < snapshot.day)
        and (
            due_range is None
            or due_range.start <= b.obligation.due_date <= due_range.end
        )
    ]

    def subtotal(balances, label):
        return amount(
            sum(b.amount_iqd for b in balances),
            label,
            sources(*(b.source_ids for b in balances)),
            "FINANCIAL_RULES §5/§11: originals - active verified allocations",
        )

    buckets = {key: [] for key in ("not_due", "d1_7", "d8_30", "d31_60", "d60_plus")}
    groups = defaultdict(list)
    unknown_due = False
    for balance in selected:
        obligation = balance.obligation
        groups[obligation.counterparty_id].append(balance)
        if obligation.due_date is None:
            unknown_due = True
        else:
            buckets[
                aging_bucket(max(0, (snapshot.day - obligation.due_date).days))
            ].append(balance)
    parties = []
    for key, balances in groups.items():
        dues = [b.obligation.due_date for b in balances]
        oldest = min(dues) if all(dues) else None
        overdue = max(0, (snapshot.day - oldest).days) if oldest else None
        parties.append(
            DebtParty(
                counterparty_id=key,
                display_name=snapshot.parties[key][0],
                outstanding=subtotal(balances, "outstanding"),
                oldest_due_date=oldest,
                days_overdue=overdue,
                bucket=aging_bucket(overdue) if overdue is not None else None,
                obligations=tuple(
                    DebtObligation(
                        obligation_id=b.obligation.obligation_id,
                        original=amount(
                            b.obligation.original_amount_iqd,
                            "original_obligation",
                            (b.original_source,),
                            "recorded obligation amount",
                            kind="verified",
                        ),
                        outstanding=subtotal([b], "outstanding"),
                        due_date=b.obligation.due_date,
                        collections=b.collections,
                    )
                    for b in sorted(
                        balances,
                        key=lambda b: (
                            b.obligation.due_date or date.max,
                            b.obligation.obligation_id,
                        ),
                    )
                ),
            )
        )
    aging = {key: subtotal(balances, key) for key, balances in buckets.items()}
    if unknown_due:
        aging = {
            key: amount(
                None, key, value.source_ids, "missing due date prevents complete aging"
            )
            for key, value in aging.items()
        }
    return DebtReport(
        as_of=snapshot.day,
        total_outstanding=subtotal(selected, "total_outstanding"),
        aging=Aging(**aging),
        customers=tuple(
            sorted(
                parties,
                key=lambda p: (
                    -(p.days_overdue or 0),
                    -p.outstanding.amount_iqd,
                    p.counterparty_id,
                ),
            )
        ),
    )


def upcoming_obligations(snapshot, *, days=7, party_id=None):
    if type(days) is not int or not 1 <= days <= 30:
        raise FinancialRuleError("VALIDATION_ERROR")
    end = snapshot.day + timedelta(days=days - 1)
    balances = [
        b
        for b in snapshot.balances
        if party_id is None or b.obligation.counterparty_id == party_id
    ]
    if any(b.obligation.due_date is None for b in balances):
        raise FinancialRuleError("MISSING_DUE_DATE")
    dues, expected, overdue = [], [], []
    for balance in balances:
        o = balance.obligation
        item = dict(
            obligation_id=o.obligation_id,
            counterparty=snapshot.party(o.counterparty_id),
            due_date=o.due_date,
            outstanding=amount(
                balance.amount_iqd,
                "outstanding",
                balance.source_ids,
                "original obligation - cutoff-visible verified allocations",
                kind="expected" if o.kind == "receivable" else "verified",
            ),
        )
        if o.kind == "payable" and o.due_date <= end:
            dues.append(DueItem(**item, due_now=o.due_date < snapshot.day))
        elif o.kind == "receivable" and o.due_date < snapshot.day:
            overdue.append(OverdueItem(**item))
        elif o.kind == "receivable" and o.due_date <= end:
            expected.append(UpcomingItem(**item))
    for items in (dues, expected, overdue):
        items.sort(key=lambda i: (i.due_date, i.obligation_id))

    def subtotal(items, label, kind):
        return amount(
            sum(i.outstanding.amount_iqd for i in items),
            label,
            sources(*(i.outstanding.source_ids for i in items)),
            "sum eligible outstanding; overdue receivables excluded from expected",
            kind=kind,
        )

    due_total = subtotal(dues, "supplier_dues", "verified")
    expected_total = subtotal(expected, "expected_collections", "expected")
    try:
        cash, counted_at = snapshot.cash()
    except FinancialRuleError as exc:
        if exc.code != "MISSING_OPENING_BALANCE":
            raise
        cash, counted_at = (
            amount(None, "cash_on_hand", (), "missing count and opening balance"),
            None,
        )
    confirmed = cash.amount_iqd
    with_expected = cash.amount_iqd
    rows = []
    for offset in range(days):
        day = snapshot.day + timedelta(days=offset)
        due = sum(
            i.outstanding.amount_iqd
            for i in dues
            if max(snapshot.day, i.due_date) == day
        )
        incoming = sum(i.outstanding.amount_iqd for i in expected if i.due_date == day)
        if confirmed is not None:
            confirmed -= due
            with_expected += incoming - due
        rows.append(
            PositionDay(
                date=day,
                dues_iqd=due,
                expected_iqd=incoming,
                running_confirmed_iqd=confirmed,
                running_with_expected_iqd=with_expected,
            )
        )
    return UpcomingObligations(
        as_of=snapshot.day,
        range=DateRangeView(start=snapshot.day, end=end),
        cash_on_hand=cash,
        counted_at=counted_at,
        last_synced_at=snapshot.known,
        dues=tuple(dues),
        dues_total=due_total,
        expected=tuple(expected),
        expected_total=expected_total,
        overdue_receivables=tuple(overdue),
        position_confirmed=amount(
            confirmed,
            "position_confirmed",
            sources(cash.source_ids, due_total.source_ids),
            "cash_on_hand - supplier_dues",
        ),
        position_with_expected=amount(
            with_expected,
            "position_with_expected",
            sources(cash.source_ids, due_total.source_ids, expected_total.source_ids),
            "cash_on_hand + non-overdue expected collections - supplier_dues",
        ),
        days=tuple(rows),
        first_short_date_confirmed=next(
            (
                r.date
                for r in rows
                if r.running_confirmed_iqd is not None and r.running_confirmed_iqd < 0
            ),
            None,
        ),
        first_short_date_with_expected=next(
            (
                r.date
                for r in rows
                if r.running_with_expected_iqd is not None
                and r.running_with_expected_iqd < 0
            ),
            None,
        ),
    )


def payment_capacity(snapshot, due_date):
    """FINANCIAL_RULES §7: primary J1 figures contain no projected drivers."""
    if not snapshot.day <= due_date <= snapshot.day + timedelta(days=30):
        raise FinancialRuleError("VALIDATION_ERROR")
    if any(b.obligation.due_date is None for b in snapshot.balances):
        raise FinancialRuleError("MISSING_DUE_DATE")
    cash, _ = snapshot.cash()
    dues = [
        b
        for b in snapshot.balances
        if b.obligation.kind == "payable" and b.obligation.due_date == due_date
    ]
    expected = [
        b
        for b in snapshot.balances
        if b.obligation.kind == "receivable"
        and snapshot.day <= b.obligation.due_date <= due_date
    ]

    def total(balances, label, kind):
        return amount(
            sum(b.amount_iqd for b in balances),
            label,
            sources(*(b.source_ids for b in balances)),
            "sum eligible outstanding at cutoff",
            kind=kind,
        )

    due, incoming = (
        total(dues, "supplier_due", "verified"),
        total(expected, "expected_collection", "expected"),
    )
    return PaymentCapacity(
        due_date=due_date,
        cash_on_hand=cash,
        supplier_due=due,
        expected_collection=incoming,
        shortfall_with_collection=amount(
            max(0, due.amount_iqd - cash.amount_iqd - incoming.amount_iqd),
            "shortfall_with_collection",
            sources(cash.source_ids, due.source_ids, incoming.source_ids),
            "max(0, supplier_due - cash_on_hand - eligible expected collections)",
        ),
        shortfall_without_collection=amount(
            max(0, due.amount_iqd - cash.amount_iqd),
            "shortfall_without_collection",
            sources(cash.source_ids, due.source_ids),
            "max(0, supplier_due - cash_on_hand)",
        ),
    )
