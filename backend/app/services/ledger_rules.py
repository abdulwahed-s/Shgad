"""Deterministic financial primitives for verified ledger records.

Inputs are verified synthetic domain records. FINANCIAL_RULES §2–5 governs the
arithmetic; only verified payment-link allocations may be passed to outstanding.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from app.schemas.ledger import (
    EntryVoid,
    EventType,
    Obligation,
    OpeningBalance,
    PaymentLink,
    Transaction,
)
from app.services.errors import FinancialRuleError
from app.services.validation import BAGHDAD, SQLITE_MAX_INTEGER, parse_timestamp


@dataclass(frozen=True)
class EventEffect:
    cash_delta_iqd: int = 0
    revenue_delta_iqd: int = 0
    receivable_created_iqd: int = 0
    payable_created_iqd: int = 0
    operating_expenses_iqd: int = 0
    owner_drawings_iqd: int = 0
    collections_iqd: int = 0
    cash_count_iqd: int | None = None


@dataclass(frozen=True)
class CashPosition:
    amount_iqd: int
    source_ids: tuple[str, ...]
    basis: str
    counted_on: date | None = None


@dataclass(frozen=True)
class DailyClose:
    business_date: date
    previous_count_iqd: int | None
    count_iqd: int | None
    expected_close_iqd: int | None
    unexplained_difference_iqd: int | None
    recorded_cash_sales_iqd: int
    kind: Literal["flagged", "missing"]
    source_ids: tuple[str, ...]
    previous_count_transaction_id: str | None
    closing_count_transaction_id: str | None


@dataclass(frozen=True)
class CashDifference:
    amount_iqd: int | None
    kind: Literal["flagged", "missing"]
    source_ids: tuple[str, ...]


def knowledge_cutoff(as_of: date, known_at: datetime | str | None = None) -> datetime:
    if type(as_of) is not date:
        raise FinancialRuleError("VALIDATION_ERROR")
    if known_at is None:
        return datetime.combine(as_of, time.max, tzinfo=BAGHDAD)
    try:
        return parse_timestamp(known_at)
    except ValueError as exc:
        raise FinancialRuleError("VALIDATION_ERROR") from exc


def transaction_status(
    transaction: Transaction, *, voids: Iterable[EntryVoid], known_at: datetime | str
) -> Literal["valid", "flagged", "voided"]:
    try:
        cutoff = parse_timestamp(known_at)
    except ValueError as exc:
        raise FinancialRuleError("VALIDATION_ERROR") from exc
    for audit in voids:
        if audit.transaction_id == transaction.transaction_id:
            if audit.source_id != transaction.source_id:
                raise FinancialRuleError("VALIDATION_ERROR")
            if audit.voided_at <= cutoff:
                return "voided"
    return transaction.status


def active_transactions(
    transactions: Iterable[Transaction],
    *,
    as_of: date,
    voids: Iterable[EntryVoid] = (),
    known_at: datetime | str | None = None,
) -> tuple[Transaction, ...]:
    """Filter financial time and knowledge time without modifying evidence (§11)."""
    cutoff = knowledge_cutoff(as_of, known_at)
    rows, audits = tuple(transactions), tuple(voids)
    if len({r.transaction_id for r in rows}) != len(rows):
        raise FinancialRuleError(
            "VALIDATION_ERROR", details={"reason": "DUPLICATE_TRANSACTION"}
        )
    return tuple(
        sorted(
            (
                row
                for row in rows
                if row.business_date <= as_of
                and row.occurred_at <= cutoff
                and row.recorded_at <= cutoff
                and transaction_status(row, voids=audits, known_at=cutoff) != "voided"
            ),
            key=lambda row: (row.occurred_at, row.transaction_id),
        )
    )


def event_effect(transaction: Transaction) -> EventEffect:
    amount = transaction.amount_iqd
    match transaction.type:
        case EventType.CASH_SALE:
            return EventEffect(cash_delta_iqd=amount, revenue_delta_iqd=amount)
        case EventType.CREDIT_SALE:
            return EventEffect(revenue_delta_iqd=amount, receivable_created_iqd=amount)
        case EventType.CREDIT_COLLECTION:
            return EventEffect(cash_delta_iqd=amount, collections_iqd=amount)
        case EventType.CAPITAL_INJECTION:
            return EventEffect(cash_delta_iqd=amount)
        case EventType.SUPPLIER_INVOICE:
            return EventEffect(payable_created_iqd=amount)
        case EventType.SUPPLIER_PAYMENT:
            return EventEffect(cash_delta_iqd=-amount)
        case EventType.OPERATING_EXPENSE:
            return EventEffect(cash_delta_iqd=-amount, operating_expenses_iqd=amount)
        case EventType.OWNER_DRAWING:
            return EventEffect(cash_delta_iqd=-amount, owner_drawings_iqd=amount)
        case EventType.DAILY_CASH_COUNT:
            return EventEffect(cash_count_iqd=amount)
        case _:
            raise FinancialRuleError("VALIDATION_ERROR")


def cash_on_hand(
    transactions: Iterable[Transaction],
    *,
    as_of: date,
    opening_balance: OpeningBalance | None = None,
    voids: Iterable[EntryVoid] = (),
    known_at: datetime | str | None = None,
) -> CashPosition:
    """Latest count plus subsequent flows, otherwise explicit opening plus flows."""
    observed = active_transactions(
        transactions, as_of=as_of, voids=voids, known_at=known_at
    )
    counts = [row for row in observed if row.type == EventType.DAILY_CASH_COUNT]
    if counts:
        anchor = counts[-1]
        if len(counts) > 1 and counts[-2].occurred_at == anchor.occurred_at:
            raise FinancialRuleError(
                "VALIDATION_ERROR", details={"reason": "AMBIGUOUS_CASH_COUNT"}
            )
        amount = anchor.amount_iqd
        rows = [row for row in observed if row.occurred_at > anchor.occurred_at]
        source_id = anchor.source_id
        counted_on = anchor.business_date
        basis = "counted"
    elif opening_balance is not None and opening_balance.business_date <= as_of:
        amount = opening_balance.amount_iqd
        rows = [
            row
            for row in observed
            if row.business_date >= opening_balance.business_date
        ]
        source_id = opening_balance.source_id
        counted_on = None
        basis = "opening_balance"
    else:
        raise FinancialRuleError("MISSING_OPENING_BALANCE")
    evidence = [source_id]
    for row in rows:
        delta = event_effect(row).cash_delta_iqd
        if delta:
            amount += delta
            evidence.append(row.source_id)
    if len(evidence) > 1:
        basis += "_and_recorded_since"
    return CashPosition(amount, tuple(evidence), basis, counted_on)


def _nonnegative_iqd(value: int) -> None:
    if type(value) is not int or not 0 <= value <= SQLITE_MAX_INTEGER:
        raise FinancialRuleError("VALIDATION_ERROR")


def outstanding_balance(
    original_amount_iqd: int, verified_link_amounts: Iterable[int]
) -> int:
    _nonnegative_iqd(original_amount_iqd)
    paid = 0
    for amount in verified_link_amounts:
        _nonnegative_iqd(amount)
        paid += amount
    if paid > original_amount_iqd:
        raise FinancialRuleError("VALIDATION_ERROR", details={"reason": "OVERPAYMENT"})
    return original_amount_iqd - paid


def recorded_cash_sales(
    transactions: Iterable[Transaction],
    *,
    as_of: date,
    start: date | None = None,
    voids: Iterable[EntryVoid] = (),
    known_at: datetime | str | None = None,
) -> int:
    rows = active_transactions(
        transactions, as_of=as_of, voids=voids, known_at=known_at
    )
    if start is not None and (type(start) is not date or start > as_of):
        raise FinancialRuleError("VALIDATION_ERROR")
    return sum(
        row.amount_iqd
        for row in rows
        if row.type == EventType.CASH_SALE
        and (start is None or row.business_date >= start)
    )


def _closing_count(rows: Iterable[Transaction], day: date) -> Transaction | None:
    counts = [
        r
        for r in rows
        if r.business_date == day and r.type == EventType.DAILY_CASH_COUNT
    ]
    if not counts:
        return None
    if len(counts) > 1 and counts[-1].occurred_at == counts[-2].occurred_at:
        raise FinancialRuleError(
            "VALIDATION_ERROR", details={"reason": "AMBIGUOUS_CASH_COUNT"}
        )
    return counts[-1]


def daily_close(
    transactions: Iterable[Transaction],
    *,
    business_date: date,
    voids: Iterable[EntryVoid] = (),
    known_at: datetime | str | None = None,
) -> DailyClose:
    """FINANCIAL_RULES §3: recorded flows versus consecutive closing counts."""
    rows = active_transactions(
        transactions, as_of=business_date, voids=voids, known_at=known_at
    )
    previous = _closing_count(rows, business_date - timedelta(days=1))
    closing = _closing_count(rows, business_date)
    flows = [
        r
        for r in rows
        if r.business_date == business_date and event_effect(r).cash_delta_iqd
    ]
    expected = (
        previous.amount_iqd + sum(event_effect(r).cash_delta_iqd for r in flows)
        if previous is not None
        else None
    )
    difference = (
        closing.amount_iqd - expected
        if closing is not None and expected is not None
        else None
    )
    evidence = [r.source_id for r in (previous, closing) if r is not None]
    evidence.extend(r.source_id for r in flows)
    return DailyClose(
        business_date=business_date,
        previous_count_iqd=previous.amount_iqd if previous else None,
        count_iqd=closing.amount_iqd if closing else None,
        expected_close_iqd=expected,
        unexplained_difference_iqd=difference,
        recorded_cash_sales_iqd=sum(
            r.amount_iqd for r in flows if r.type == EventType.CASH_SALE
        ),
        kind="missing" if difference is None else "flagged",
        source_ids=tuple(evidence),
        previous_count_transaction_id=previous.transaction_id if previous else None,
        closing_count_transaction_id=closing.transaction_id if closing else None,
    )


def cash_difference_in_range(
    transactions: Iterable[Transaction],
    *,
    start: date,
    end: date,
    voids: Iterable[EntryVoid] = (),
    known_at: datetime | str | None = None,
) -> CashDifference:
    if type(start) is not date or type(end) is not date or start > end:
        raise FinancialRuleError("VALIDATION_ERROR")
    rows, audits = tuple(transactions), tuple(voids)
    cutoff = knowledge_cutoff(end, known_at)
    closes = [
        daily_close(
            rows, business_date=start + timedelta(days=i), voids=audits, known_at=cutoff
        )
        for i in range((end - start).days + 1)
    ]
    sources = tuple(dict.fromkeys(s for close in closes for s in close.source_ids))
    if any(close.unexplained_difference_iqd is None for close in closes):
        return CashDifference(None, "missing", sources)
    return CashDifference(
        sum(close.unexplained_difference_iqd for close in closes), "flagged", sources
    )


def obligation_outstanding(
    obligation: Obligation,
    transactions: Iterable[Transaction],
    links: Iterable[PaymentLink],
    *,
    as_of: date,
    voids: Iterable[EntryVoid] = (),
    known_at: datetime | str | None = None,
) -> int | None:
    """A voided origin is excluded; voided collections restore outstanding (§5/§11)."""
    cutoff = knowledge_cutoff(as_of, known_at)
    rows = {
        r.transaction_id: r
        for r in active_transactions(
            transactions, as_of=as_of, voids=voids, known_at=cutoff
        )
    }
    if obligation.origin_transaction_id not in rows:
        return None
    amounts = [
        link.amount_iqd
        for link in links
        if link.obligation_id == obligation.obligation_id
        and link.created_at <= cutoff
        and link.payment_transaction_id in rows
    ]
    return outstanding_balance(obligation.original_amount_iqd, amounts)
