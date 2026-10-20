"""Report contracts: estimated gross margin and deterministic weekly data."""

from typing import Literal

from pydantic import StrictBool, StrictInt

from app.schemas.forecast import Amount
from app.schemas.ledger import LedgerModel
from app.schemas.queries import FlagView, ReportRange


class PriceBasis(LedgerModel):
    category_id: str
    buy_price: Amount


class MarginReport(LedgerModel):
    range: ReportRange
    gross_margin: Amount
    coverage_pct: StrictInt | None
    unpriced_sales_count: StrictInt
    after_recorded_expenses: Amount | None
    note_key: Literal["margin_excludes_unrecorded_costs"] = (
        "margin_excludes_unrecorded_costs"
    )
    priced_sales: Amount
    cost_of_goods: Amount
    price_basis: tuple[PriceBasis, ...]
    unexplained_difference_excluded: Literal[True] = True


class WeeklyMargin(LedgerModel):
    shown: StrictBool
    margin: Amount
    coverage_pct: StrictInt | None
    note_key: str
    unexplained_difference_excluded: Literal[True] = True


class DebtTop(LedgerModel):
    counterparty_id: str
    display_name: str
    outstanding: Amount
    days_overdue: StrictInt | None


class WeeklyReport(LedgerModel):
    range: ReportRange
    cash_sales: Amount
    unexplained_cash_difference: Amount
    credit_sales: Amount
    collections: Amount
    supplier_payments: Amount
    operating_expenses: Amount
    owner_drawings: Amount
    capital_injections: Amount
    outstanding_receivables: Amount
    overdue_receivables: Amount
    debt_aging_top: tuple[DebtTop, ...]
    gross_margin: WeeklyMargin
    flags: tuple[FlagView, ...]
    flags_count: StrictInt
    suggestion_key: str
