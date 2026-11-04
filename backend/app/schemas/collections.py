"""D61 closed collection, merchant reminder and deterministic brief contracts."""

from typing import Annotated, Literal

from pydantic import Field, PrivateAttr, StrictBool, StrictInt, StringConstraints

from app.schemas.evidence import CounterpartyView
from app.schemas.ledger import BusinessDate, LedgerModel, Timestamp
from app.schemas.queries import DateRangeView
from app.schemas.renderer import RendererStats
from app.schemas.tools import Figure, KnownZeroDebtQuery, Metric

Tone = Literal["gentle", "normal", "firm"]
CustomerId = Annotated[
    str, StringConstraints(strict=True, min_length=1, max_length=120)
]


class EmptyFlagsQuery(LedgerModel):
    tool: Literal["reconcile"] = "reconcile"
    period: DateRangeView
    known_at: Timestamp
    matching_flags: Literal[0] = 0


class SourcedCount(Metric):
    query_evidence: KnownZeroDebtQuery | EmptyFlagsQuery | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class CollectionCustomer(LedgerModel):
    counterparty_id: str
    display_name: str
    overdue_amount: Figure
    oldest_due_date: BusinessDate
    days_overdue: StrictInt
    source_ids: tuple[str, ...]
    reminder_count: StrictInt
    last_reminder_business_date: BusinessDate | None
    days_since_last_reminder: StrictInt | None


class CollectionsReport(LedgerModel):
    as_of: BusinessDate
    total_overdue: Figure
    customer_count: SourcedCount
    items: tuple[CollectionCustomer, ...]


class ReminderRequest(LedgerModel):
    counterparty_id: CustomerId
    tone: Tone
    channel: Literal["whatsapp", "copy"]
    edited: StrictBool


class ReminderReceipt(ReminderRequest):
    reminder_id: StrictInt
    business_date: BusinessDate
    recorded_at: Timestamp
    overdue_amount: Figure


class ReminderArguments(LedgerModel):
    counterparty_ids: tuple[CustomerId, ...] = Field(max_length=200)


class ReminderSummary(LedgerModel):
    counterparty_id: str
    count: StrictInt
    last_business_date: BusinessDate | None
    days_since_last: StrictInt | None
    reminder_ids: tuple[StrictInt, ...]


class RemindersResult(LedgerModel):
    as_of: BusinessDate
    items: tuple[ReminderSummary, ...]


class CollectionDraftRequest(LedgerModel):
    counterparty_id: CustomerId
    tone: Tone = "gentle"


class CollectionDraft(LedgerModel):
    status: Literal["drafted", "nothing_owed", "not_due"]
    counterparty: CounterpartyView
    tone: Tone
    text: str
    draft_kind: Literal["model", "template"] | None = None
    figures: tuple[Figure, ...] = ()
    metrics: tuple[Metric, ...] = ()
    dates: dict[str, BusinessDate] = Field(default_factory=dict)
    renderer: RendererStats = RendererStats(attempts=1, fell_back_to_template=False)
    review_status: Literal["PENDING_REVIEW", "APPROVED"] = "PENDING_REVIEW"


class DraftBody(LedgerModel):
    body: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=1600)]


class CollectionAction(LedgerModel):
    kind: Literal["priorities", "draft"]
    counterparty_id: str | None = None
    tone: Tone = "gentle"


class MorningBrief(LedgerModel):
    _render_fingerprint: str | None = PrivateAttr(default=None)
    as_of: BusinessDate
    week: DateRangeView
    cash_on_hand: Figure
    dues_today: Figure
    dues_week: Figure
    overdue_total: Figure
    overdue_customer_count: SourcedCount
    top_customers: tuple[CollectionCustomer, ...]
    open_flags_count: SourcedCount
