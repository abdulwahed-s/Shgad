"""API_CONTRACT forecast shapes; amounts are exact integer IQD estimates."""

from typing import Literal

from pydantic import StrictInt

from app.schemas.ledger import BusinessDate, LedgerModel

ScenarioName = Literal["base", "conservative", "stress"]


class Amount(LedgerModel):
    amount_iqd: StrictInt | None
    kind: Literal["verified", "expected", "calculated", "missing", "flagged"]
    label_key: str
    source_ids: tuple[str, ...]
    formula: str


class ForecastDay(LedgerModel):
    date: BusinessDate
    opening_iqd: StrictInt
    cash_sales_iqd: StrictInt
    unlinked_cash_iqd: StrictInt
    collections_iqd: StrictInt
    supplier_payments_iqd: StrictInt
    expenses_iqd: StrictInt
    owner_drawings_iqd: StrictInt
    closing_iqd: StrictInt


class Lowest(LedgerModel):
    date: BusinessDate
    closing_iqd: StrictInt


class Driver(LedgerModel):
    label_key: str
    amount: Amount


class Forecast(LedgerModel):
    days: tuple[ForecastDay, ...]
    lowest: Lowest
    first_shortfall_date: BusinessDate | None
    top_inflows: tuple[Driver, ...]
    top_outflows: tuple[Driver, ...]


class OverdueExcluded(LedgerModel):
    obligation_id: str
    outstanding: Amount


class ForecastReport(LedgerModel):
    as_of: BusinessDate
    horizon_days: Literal[30] = 30
    scenarios: dict[ScenarioName, Forecast]
    overdue_excluded: tuple[OverdueExcluded, ...]
    assumption_keys: tuple[str, ...]
