"""Ledger evidence and audit projections from API_CONTRACT entries/ledger."""

from typing import Any, Literal

from app.schemas.forecast import Amount
from app.schemas.ledger import (
    BusinessDate,
    EventType,
    Identifier,
    LedgerModel,
    PositiveInteger,
    PositiveIQD,
    Timestamp,
)


class CounterpartyView(LedgerModel):
    id: Identifier
    display_name: str


class VoidEvidence(LedgerModel):
    void_id: Identifier
    reason: str
    voided_at: Timestamp


class FlagView(LedgerModel):
    flag_id: Identifier
    type: Literal[
        "unmatched", "suspected_duplicate", "partially_paid", "overdue", "ambiguous"
    ]
    reason_key: str
    amount: Amount
    source_ids: tuple[str, ...]
    confidence_basis: str
    next_step_key: Literal["review", "provide_details"]


class LedgerItem(LedgerModel):
    source_id: Identifier
    occurred_at: Timestamp
    business_date: BusinessDate
    type: EventType
    amount_iqd: PositiveIQD
    counterparty: CounterpartyView | None
    obligation_id: Identifier | None
    category_id: Identifier | None
    quantity: PositiveInteger | None
    status: Literal["valid", "flagged", "voided"]
    import_batch_id: Identifier
    source: Literal["synthetic_csv", "manual_entry", "daily_close_review"]
    description: str
    void: VoidEvidence | None


class LedgerDetail(LedgerItem):
    raw_row: dict[str, Any]
    flags: tuple[FlagView, ...]


class LedgerPage(LedgerModel):
    items: tuple[LedgerItem, ...]
    next_cursor: str | None
