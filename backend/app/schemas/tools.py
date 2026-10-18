"""Closed read-only tool arguments and standard result envelopes (§8.1)."""

from typing import Annotated, Any, Literal

from pydantic import Field, StrictBool, StrictInt, StringConstraints, model_validator

from app.schemas.evidence import CounterpartyView
from app.schemas.forecast import Amount
from app.schemas.ledger import BusinessDate, LedgerModel
from app.schemas.queries import DateRangeView, Direction

Period = Annotated[
    str,
    StringConstraints(
        strict=True,
        pattern=(
            r"^(today|yesterday|this_week|last_week|this_month|last_month|"
            r"last_n_days:([1-9]|[1-8][0-9]|90)|next_n_days:([1-9]|[12][0-9]|30)|"
            r"next_weekday:(sat|sun|mon|tue|wed|thu|fri)|explicit)$"
        ),
    ),
]


class DateArguments(LedgerModel):
    start_date: BusinessDate | None = None
    end_date: BusinessDate | None = None


class SalesArguments(DateArguments):
    period: Period
    kind: Literal["cash", "credit", "all"] = "all"


class MarginArguments(DateArguments):
    period: Period


class DebtsArguments(DateArguments):
    counterparty_query: (
        Annotated[str, StringConstraints(strict=True, min_length=1, max_length=200)]
        | None
    ) = None
    overdue_only: StrictBool = False
    direction: Direction = "receivable"
    due_period: Period | None = None


class Figure(Amount):
    key: str


class Metric(LedgerModel):
    key: str
    value: StrictInt | None
    unit: Literal["percent", "count", "days"]
    kind: Literal["verified", "expected", "calculated", "missing", "flagged"]
    label_key: str
    source_ids: tuple[str, ...]
    formula: str


class ErrorDetail(LedgerModel):
    code: str
    message_key: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(LedgerModel):
    error: ErrorDetail


class ToolEnvelope(LedgerModel):
    ok: StrictBool
    data_version: Literal["synthetic-ledger-v1"] = "synthetic-ledger-v1"
    currency: Literal["IQD"] = "IQD"
    result: dict[str, Any] | None
    evidence_source_ids: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    figures: tuple[Figure, ...] = ()
    metrics: tuple[Metric, ...] = ()
    dates: dict[str, BusinessDate] = Field(default_factory=dict)
    resolved_range: DateRangeView | None = None
    resolved_counterparty: CounterpartyView | None = None
    error: ErrorDetail | None = None
    clarification_key: str | None = None

    @model_validator(mode="after")
    def validate_failure(self):
        if self.ok:
            if (
                self.result is None
                or self.error is not None
                or self.clarification_key is not None
            ):
                raise ValueError("Success requires data and no failure")
        elif (
            self.result is not None
            or self.error is None
            or not self.clarification_key
            or self.figures
            or self.metrics
            or self.dates
        ):
            raise ValueError("Failure cannot fabricate result values")
        return self
