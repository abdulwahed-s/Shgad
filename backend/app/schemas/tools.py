"""Closed read-only tool arguments and standard result envelopes (§8.1)."""

from typing import Annotated, Any, Literal

from pydantic import (
    Field,
    PrivateAttr,
    StrictBool,
    StrictInt,
    StringConstraints,
    model_validator,
)

from app.schemas.evidence import CounterpartyView
from app.schemas.forecast import Amount
from app.schemas.ledger import BusinessDate, LedgerModel, Timestamp
from app.schemas.queries import DateRangeView, DebtFilters, Direction

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


class ReconcileArguments(DateArguments):
    period: Period
    types: (
        tuple[
            Literal[
                "unmatched",
                "suspected_duplicate",
                "partially_paid",
                "overdue",
                "ambiguous",
            ],
            ...,
        ]
        | None
    ) = None


class ForecastArguments(DateArguments):
    scenario: Literal["base", "conservative", "stress", "all"] = "all"
    until: Period | None = None


class DebtsArguments(DateArguments):
    counterparty_query: (
        Annotated[str, StringConstraints(strict=True, min_length=1, max_length=200)]
        | None
    ) = None
    overdue_only: StrictBool = False
    direction: Direction = "receivable"
    due_period: Period | None = None


class EmptyQueryFilters(LedgerModel):
    event_types: tuple[
        Literal[
            "CASH_SALE",
            "CREDIT_SALE",
            "CREDIT_COLLECTION",
            "SUPPLIER_PAYMENT",
            "OPERATING_EXPENSE",
            "OWNER_DRAWING",
            "CAPITAL_INJECTION",
        ],
        ...,
    ]
    active_only: Literal[True] = True
    known_at: Timestamp


class KnownZeroQuery(LedgerModel):
    tool: Literal["get_sales", "reconcile"]
    period: DateRangeView
    filters: EmptyQueryFilters
    matching_rows: Literal[0] = 0


class KnownZeroDebtQuery(LedgerModel):
    """D58: no positive balance matches these exact filters at the cutoff."""

    tool: Literal["get_debts"]
    as_of: BusinessDate
    filters: DebtFilters
    known_at: Timestamp
    matching_obligations: Literal[0] = 0


class Figure(Amount):
    key: str
    query_evidence: KnownZeroQuery | KnownZeroDebtQuery | None = None


class Metric(LedgerModel):
    key: str
    value: StrictInt | None
    unit: Literal["percent", "count", "days"]
    kind: Literal["verified", "expected", "calculated", "missing", "flagged"]
    label_key: str
    source_ids: tuple[str, ...]
    formula: str

    @model_validator(mode="after")
    def missing_is_unavailable(self):
        if (self.kind == "missing") != (self.value is None):
            raise ValueError("Only missing metrics are null")
        return self


class ErrorDetail(LedgerModel):
    code: str
    message_key: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(LedgerModel):
    error: ErrorDetail


class ToolEnvelope(LedgerModel):
    _verified_fingerprint: str | None = PrivateAttr(default=None)
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
