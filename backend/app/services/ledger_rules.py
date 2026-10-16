"""Deterministic financial primitives for verified ledger records.

Inputs are verified synthetic domain records. FINANCIAL_RULES §2–5 governs the
arithmetic; only verified payment-link allocations may be passed to outstanding.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from app.schemas.ledger import EventType, OpeningBalance, Transaction
from app.services.errors import FinancialRuleError
from app.services.validation import SQLITE_MAX_INTEGER


@dataclass(frozen=True)
class EventEffect:
    cash_delta_iqd: int = 0
    revenue_delta_iqd: int = 0
    receivable_created_iqd: int = 0
    payable_created_iqd: int = 0
    operating_expenses_iqd: int = 0
    owner_drawings_iqd: int = 0
    cash_count_iqd: int | None = None


@dataclass(frozen=True)
class CashPosition:
    amount_iqd: int
    source_ids: tuple[str, ...]
    basis: str
    counted_on: date | None = None


def event_effect(transaction: Transaction) -> EventEffect:
    amount = transaction.amount_iqd
    match transaction.type:
        case EventType.CASH_SALE:
            return EventEffect(cash_delta_iqd=amount, revenue_delta_iqd=amount)
        case EventType.CREDIT_SALE:
            return EventEffect(revenue_delta_iqd=amount, receivable_created_iqd=amount)
        case EventType.CREDIT_COLLECTION:
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
) -> CashPosition:
    """Latest count plus subsequent flows, otherwise explicit opening plus flows."""
    if type(as_of) is not date:
        raise FinancialRuleError("VALIDATION_ERROR")
    observed = sorted(
        (row for row in transactions if row.business_date <= as_of),
        key=lambda row: (row.occurred_at, row.transaction_id),
    )
    if len({row.transaction_id for row in observed}) != len(observed):
        raise FinancialRuleError(
            "VALIDATION_ERROR", details={"reason": "DUPLICATE_TRANSACTION"}
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


def derived_cash_sales(
    *,
    previous_count_iqd: int,
    closing_count_iqd: int,
    collections_iqd: int,
    supplier_payments_iqd: int,
    operating_expenses_iqd: int,
    owner_drawings_iqd: int,
) -> int:
    """Exact FINANCIAL_RULES §3 formula; no recorded sale is added again."""
    for amount in (
        previous_count_iqd,
        closing_count_iqd,
        collections_iqd,
        supplier_payments_iqd,
        operating_expenses_iqd,
        owner_drawings_iqd,
    ):
        _nonnegative_iqd(amount)
    return (
        closing_count_iqd
        - previous_count_iqd
        - collections_iqd
        + supplier_payments_iqd
        + operating_expenses_iqd
        + owner_drawings_iqd
    )
