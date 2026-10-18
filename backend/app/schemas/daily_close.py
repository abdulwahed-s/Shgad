"""Daily close and explicit merchant-review responses (FINANCIAL_RULES §3)."""

from pydantic import StrictBool

from app.schemas.entries import EntryReceipt
from app.schemas.evidence import LedgerItem
from app.schemas.forecast import Amount
from app.schemas.ledger import (
    BusinessDate,
    DifferenceResolution,
    Identifier,
    LedgerModel,
    Timestamp,
)


class ResolvedReview(LedgerModel):
    review_id: Identifier
    resolution: DifferenceResolution
    entry: LedgerItem | None
    note: str | None
    created_at: Timestamp


class DailyCloseView(LedgerModel):
    date: BusinessDate
    count: Amount
    previous_count: Amount
    expected_close: Amount
    unexplained_difference: Amount
    resolved: tuple[ResolvedReview, ...]
    remaining_difference: Amount
    rows: tuple[str, ...]


class ResolutionReceipt(LedgerModel):
    entry: EntryReceipt | None
    daily_close: DailyCloseView
    duplicate: StrictBool
