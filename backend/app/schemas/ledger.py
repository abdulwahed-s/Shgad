"""Canonical synthetic ledger records (roadmap §5; FINANCIAL_RULES §1–5)."""

import json
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StringConstraints,
    field_serializer,
    model_validator,
)

from app.services.validation import (
    BAGHDAD,
    SQLITE_MAX_INTEGER,
    parse_business_date,
    parse_timestamp,
)

Identifier = Annotated[
    str, StringConstraints(strict=True, min_length=1, pattern=r"^\S+$")
]
NonemptyText = Annotated[str, StringConstraints(strict=True, min_length=1)]
PositiveIQD = Annotated[StrictInt, Field(gt=0, le=SQLITE_MAX_INTEGER)]
NonnegativeIQD = Annotated[StrictInt, Field(ge=0, le=SQLITE_MAX_INTEGER)]
PositiveInteger = Annotated[StrictInt, Field(gt=0, le=SQLITE_MAX_INTEGER)]
NonnegativeInteger = Annotated[StrictInt, Field(ge=0, le=SQLITE_MAX_INTEGER)]
BusinessDate = Annotated[date, BeforeValidator(parse_business_date)]
Timestamp = Annotated[AwareDatetime, BeforeValidator(parse_timestamp)]
SourceSystem = Literal["synthetic_csv", "synthetic_wallet", "synthetic_entry"]
ToolName = Literal["get_sales", "get_debts", "reconcile", "forecast", "get_margin"]


def _invalid_json_constant(value: str) -> None:
    raise ValueError(f"Nonstandard JSON constant: {value}")


def _json_object(value: str) -> str:
    if not isinstance(json.loads(value, parse_constant=_invalid_json_constant), dict):
        raise ValueError("Expected a JSON object")
    return value


def _json_array(value: str) -> str:
    if not isinstance(json.loads(value, parse_constant=_invalid_json_constant), list):
        raise ValueError("Expected a JSON array")
    return value


JSONObjectText = Annotated[str, AfterValidator(_json_object)]
JSONArrayText = Annotated[str, AfterValidator(_json_array)]


class LedgerModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    @field_serializer("*", when_used="json")
    def canonical_timestamp(self, value):
        # Use one sortable UTC representation in models and SQLite.
        return value.isoformat() if isinstance(value, datetime) else value


class EventType(StrEnum):
    CASH_SALE = "CASH_SALE"
    CREDIT_SALE = "CREDIT_SALE"
    CREDIT_COLLECTION = "CREDIT_COLLECTION"
    SUPPLIER_INVOICE = "SUPPLIER_INVOICE"
    SUPPLIER_PAYMENT = "SUPPLIER_PAYMENT"
    OPERATING_EXPENSE = "OPERATING_EXPENSE"
    DAILY_CASH_COUNT = "DAILY_CASH_COUNT"
    OWNER_DRAWING = "OWNER_DRAWING"
    CAPITAL_INJECTION = "CAPITAL_INJECTION"
    CASH_ADJUSTMENT = "CASH_ADJUSTMENT"
    INTERNAL_TRANSFER = "INTERNAL_TRANSFER"


class SourceRecord(LedgerModel):
    source_id: Identifier
    source_system: SourceSystem
    source_row: PositiveInteger
    import_batch_id: Identifier


class Transaction(SourceRecord):
    transaction_id: Identifier
    occurred_at: Timestamp
    recorded_at: Timestamp | None = None
    source: Literal["synthetic_csv", "manual_entry", "daily_close_review"] = (
        "synthetic_csv"
    )
    client_entry_id: Identifier | None = None
    business_date: BusinessDate | None = None
    type: EventType
    amount_iqd: PositiveIQD
    counterparty_id: Identifier | None = None
    obligation_id: Identifier | None = None
    due_date: BusinessDate | None = None
    category_id: Identifier | None = None
    quantity: PositiveInteger | None = None
    description: str = ""
    status: Literal["valid", "flagged"] = "valid"
    idempotency_key: Identifier

    @model_validator(mode="after")
    def validate_event_semantics(self) -> Self:
        if self.type in {EventType.CASH_ADJUSTMENT, EventType.INTERNAL_TRANSFER}:
            raise ValueError(
                "Event is deferred until its prerequisites are implemented"
            )
        local_date = self.occurred_at.astimezone(BAGHDAD).date()
        if self.business_date is not None and self.business_date != local_date:
            raise ValueError("business_date disagrees with Baghdad timestamp")
        object.__setattr__(self, "business_date", local_date)
        if self.recorded_at is None:
            object.__setattr__(self, "recorded_at", self.occurred_at)
        sales = {EventType.CASH_SALE, EventType.CREDIT_SALE}
        origins = {EventType.CREDIT_SALE, EventType.SUPPLIER_INVOICE}
        payments = {EventType.CREDIT_COLLECTION, EventType.SUPPLIER_PAYMENT}
        if self.type in origins | payments and self.counterparty_id is None:
            raise ValueError("This event requires a counterparty ID")
        if self.type in origins and self.obligation_id is None:
            raise ValueError("An originating event requires an obligation ID")
        if (
            self.type in payments
            and self.obligation_id is None
            and self.status != "flagged"
        ):
            raise ValueError("An unlinked payment must be flagged for review")
        if self.type not in origins | payments and self.obligation_id is not None:
            raise ValueError(
                "Obligation references apply only to credit and payment events"
            )
        if self.type not in origins and self.due_date is not None:
            raise ValueError("Due dates belong to originating obligations")
        if (self.category_id is None) != (self.quantity is None):
            raise ValueError("Sale category and quantity must be supplied together")
        if self.type not in sales and self.category_id is not None:
            raise ValueError("Category and quantity apply only to sales")
        if self.source == "daily_close_review" and (
            self.source_system != "synthetic_entry"
            or self.client_entry_id is None
            or self.type
            not in {
                EventType.CASH_SALE,
                EventType.CAPITAL_INJECTION,
                EventType.OPERATING_EXPENSE,
                EventType.OWNER_DRAWING,
            }
            or self.category_id is not None
        ):
            raise ValueError(
                "Review rows require client provenance and an unitemized event"
            )
        return self


class DifferenceResolution(StrEnum):
    CASH_SALE_UNITEMIZED = "cash_sale_unitemized"
    CAPITAL_INJECTION = "capital_injection"
    EXPENSE_UNRECORDED = "expense_unrecorded"
    OWNER_DRAWING_UNRECORDED = "owner_drawing_unrecorded"
    LEAVE_UNEXPLAINED = "leave_unexplained"


class DifferenceReviewRequest(LedgerModel):
    client_entry_id: Identifier
    resolution: DifferenceResolution
    amount_iqd: PositiveIQD | None
    note: str | None = None

    @model_validator(mode="after")
    def validate_amount(self) -> Self:
        if (self.resolution == DifferenceResolution.LEAVE_UNEXPLAINED) != (
            self.amount_iqd is None
        ):
            raise ValueError("Only leave_unexplained requires a null amount")
        return self


class DifferenceReview(DifferenceReviewRequest):
    review_id: Identifier
    business_date: BusinessDate
    created_at: Timestamp
    previous_count_transaction_id: Identifier
    closing_count_transaction_id: Identifier
    transaction_id: Identifier | None

    @model_validator(mode="after")
    def validate_created_row(self) -> Self:
        if (self.resolution == DifferenceResolution.LEAVE_UNEXPLAINED) != (
            self.transaction_id is None
        ):
            raise ValueError("Only leave_unexplained has no created row")
        return self


class VoidRequest(LedgerModel):
    client_entry_id: Identifier
    reason: Annotated[str, StringConstraints(strict=True, min_length=1, pattern=r"\S")]


class EntryVoid(VoidRequest):
    void_id: Identifier
    transaction_id: Identifier
    source_id: Identifier
    voided_at: Timestamp


class Counterparty(LedgerModel):
    counterparty_id: Identifier
    display_name: NonemptyText
    kind: Literal["customer", "supplier"]


class Category(LedgerModel):
    category_id: Identifier
    name: NonemptyText
    buy_price_iqd: NonnegativeIQD | None = None
    sell_price_iqd: PositiveIQD | None = None


class Obligation(LedgerModel):
    obligation_id: Identifier
    kind: Literal["receivable", "payable"]
    origin_transaction_id: Identifier
    counterparty_id: Identifier
    original_amount_iqd: PositiveIQD
    due_date: BusinessDate | None = None


class PaymentLink(LedgerModel):
    payment_link_id: Identifier
    payment_transaction_id: Identifier
    obligation_id: Identifier
    amount_iqd: PositiveIQD
    match_basis: Literal["definite", "strong", "confirmed"]
    created_at: Timestamp


class OpeningBalance(SourceRecord):
    opening_balance_id: Identifier
    business_date: BusinessDate
    account: Literal["aggregate_cash"] = "aggregate_cash"
    amount_iqd: NonnegativeIQD


class ImportBatch(LedgerModel):
    import_batch_id: Identifier
    source_system: SourceSystem
    account_scope: Literal["aggregate_cash"] = "aggregate_cash"
    file_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    imported_at: Timestamp
    row_count: NonnegativeInteger
    accepted_count: NonnegativeInteger = 0
    flagged_count: NonnegativeInteger = 0
    rejected_count: NonnegativeInteger = 0
    status: Literal["pending", "completed", "rejected"] = "pending"

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        accounted = self.accepted_count + self.flagged_count + self.rejected_count
        if accounted > self.row_count or (
            self.status != "pending" and accounted != self.row_count
        ):
            raise ValueError("Import counts must account for disjoint source rows")
        return self


class RawImportRow(LedgerModel):
    raw_row_id: Identifier
    import_batch_id: Identifier
    source_row: PositiveInteger
    row_json: JSONObjectText
    errors_json: JSONArrayText = "[]"
    status: Literal["accepted", "flagged", "rejected"]


class ReconciliationFlag(LedgerModel):
    flag_id: Identifier
    type: Literal[
        "unmatched", "suspected_duplicate", "partially_paid", "overdue", "ambiguous"
    ]
    reason_key: NonemptyText
    amount_iqd: NonnegativeIQD | None = None
    transaction_id: Identifier | None = None
    obligation_id: Identifier | None = None
    raw_row_id: Identifier | None = None
    confidence_basis: str = ""
    next_step_key: Literal["review", "provide_details"] = "review"

    @model_validator(mode="after")
    def require_evidence(self) -> Self:
        if (
            self.transaction_id is None
            and self.obligation_id is None
            and self.raw_row_id is None
        ):
            raise ValueError("A flag requires source evidence")
        return self


class AgentRun(LedgerModel):
    run_id: Identifier
    started_at: Timestamp
    completed_at: Timestamp | None = None
    status: Literal["completed", "error"]
    model_id: str | None = None
    prompt_version: str | None = None
    error_code: str | None = None


class ToolCall(LedgerModel):
    tool_call_id: Identifier
    run_id: Identifier
    tool_name: ToolName
    started_at: Timestamp
    completed_at: Timestamp | None = None
    ok: StrictBool
    error_code: str | None = None
    sanitized_arguments_json: JSONObjectText = "{}"
    sanitized_result_json: JSONObjectText = "{}"
