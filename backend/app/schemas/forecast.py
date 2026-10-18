"""API_CONTRACT forecast shapes; amounts are exact integer IQD estimates."""

from typing import Literal

from pydantic import Field, StrictInt, model_validator

from app.schemas.ledger import BusinessDate, LedgerModel

ScenarioName = Literal["base", "conservative", "stress"]


class Amount(LedgerModel):
    amount_iqd: StrictInt | None
    kind: Literal["verified", "expected", "calculated", "missing", "flagged"]
    label_key: str
    source_ids: tuple[str, ...]
    formula: str

    @model_validator(mode="after")
    def missing_is_unavailable(self):
        if (self.kind == "missing") != (self.amount_iqd is None):
            raise ValueError("Only missing amounts are null")
        return self


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
    days: tuple[ForecastDay, ...] = Field(min_length=30, max_length=30)
    lowest: Lowest
    first_shortfall_date: BusinessDate | None
    top_inflows: tuple[Driver, ...] = Field(max_length=3)
    top_outflows: tuple[Driver, ...] = Field(max_length=3)


class OverdueExcluded(LedgerModel):
    obligation_id: str
    outstanding: Amount


class ForecastReport(LedgerModel):
    as_of: BusinessDate
    horizon_days: Literal[30] = 30
    scenarios: dict[ScenarioName, Forecast]
    overdue_excluded: tuple[OverdueExcluded, ...]
    assumption_keys: tuple[str, ...]
