"""Deterministic sales, debts and obligations: API_CONTRACT and §8.1."""

from typing import Literal

from pydantic import StrictBool, StrictInt

from app.schemas.evidence import CounterpartyView, FlagView
from app.schemas.forecast import Amount
from app.schemas.ledger import BusinessDate, LedgerModel, Timestamp

Direction = Literal["receivable", "payable", "both"]
Bucket = Literal["not_due", "d1_7", "d8_30", "d31_60", "d60_plus"]


class DateRangeView(LedgerModel):
    start: BusinessDate
    end: BusinessDate


class ReportRange(DateRangeView):
    partial: StrictBool = False


class SalesReport(LedgerModel):
    range: ReportRange
    cash_sales: Amount
    unexplained_cash_difference: Amount
    credit_sales: Amount
    total_sales: Amount
    kind: Literal["cash", "credit", "all"] = "all"
    selected_sales: Amount


class Aging(LedgerModel):
    not_due: Amount
    d1_7: Amount
    d8_30: Amount
    d31_60: Amount
    d60_plus: Amount


class DebtObligation(LedgerModel):
    obligation_id: str
    original: Amount
    outstanding: Amount
    due_date: BusinessDate | None
    collections: tuple[str, ...]


class DebtParty(LedgerModel):
    counterparty_id: str
    display_name: str
    outstanding: Amount
    oldest_due_date: BusinessDate | None
    days_overdue: StrictInt | None
    bucket: Bucket | None
    obligations: tuple[DebtObligation, ...]


class DebtFilters(LedgerModel):
    """The exact selection behind a debt report (D58 completeness/zero proof)."""

    direction: Literal["receivable", "payable"]
    overdue_only: StrictBool
    counterparty_id: str | None
    due_start: BusinessDate | None
    due_end: BusinessDate | None


class DebtReport(LedgerModel):
    as_of: BusinessDate
    filters: DebtFilters
    total_outstanding: Amount
    aging: Aging
    customers: tuple[DebtParty, ...]


class UpcomingItem(LedgerModel):
    obligation_id: str
    counterparty: CounterpartyView
    due_date: BusinessDate
    outstanding: Amount


class DueItem(UpcomingItem):
    due_now: StrictBool


class OverdueItem(UpcomingItem):
    timing: Literal["unknown"] = "unknown"


class PositionDay(LedgerModel):
    date: BusinessDate
    dues_iqd: StrictInt
    expected_iqd: StrictInt
    running_confirmed_iqd: StrictInt | None
    running_with_expected_iqd: StrictInt | None


class UpcomingObligations(LedgerModel):
    as_of: BusinessDate
    range: DateRangeView
    cash_on_hand: Amount
    counted_at: Timestamp | None
    last_synced_at: Timestamp
    dues: tuple[DueItem, ...]
    dues_total: Amount
    expected: tuple[UpcomingItem, ...]
    expected_total: Amount
    overdue_receivables: tuple[OverdueItem, ...]
    position_confirmed: Amount
    position_with_expected: Amount
    days: tuple[PositionDay, ...]
    first_short_date_confirmed: BusinessDate | None
    first_short_date_with_expected: BusinessDate | None


class DebtsResult(LedgerModel):
    direction: Direction
    receivables: DebtReport | None
    payables: DebtReport | None
    upcoming: UpcomingObligations | None


class ImmediatePaymentCapacity(LedgerModel):
    cash_on_hand: Amount
    supplier_due: Amount
    position_confirmed: Amount


class ImmediateDebtsResult(DebtsResult):
    """D59 private supplier-now projection; ordinary debt results stay unchanged."""

    payment_now: ImmediatePaymentCapacity


class FlagsReport(LedgerModel):
    items: tuple[FlagView, ...]


class ReconcileCollections(LedgerModel):
    collections: Amount


class CashDifferenceView(LedgerModel):
    date: BusinessDate
    amount: Amount


class ReconcileResult(FlagsReport):
    """D58 tool view: flags plus the period's collections total for audits."""

    weekly: ReconcileCollections
    cash_differences: tuple[CashDifferenceView, ...] = ()


class PaymentCapacity(LedgerModel):
    due_date: BusinessDate
    cash_on_hand: Amount
    supplier_due: Amount
    expected_collection: Amount
    shortfall_with_collection: Amount
    shortfall_without_collection: Amount


class MerchantMeta(LedgerModel):
    id: Literal["DEMO-01"] = "DEMO-01"
    display_name_key: Literal["demo_shop_name"] = "demo_shop_name"


class MetaReport(LedgerModel):
    business_as_of: BusinessDate
    week_start: Literal["saturday"] = "saturday"
    data_version: Literal["synthetic-ledger-v1"] = "synthetic-ledger-v1"
    llm_available: StrictBool = False
    merchant: MerchantMeta = MerchantMeta()
