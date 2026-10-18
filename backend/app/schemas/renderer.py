"""Server-rendered text and the exact figure/date evidence it used (§8.2a)."""

from typing import Annotated

from pydantic import Field, StrictBool, StrictInt

from app.schemas.evidence import CounterpartyView
from app.schemas.ledger import BusinessDate, LedgerModel
from app.schemas.queries import DateRangeView
from app.schemas.tools import Figure, Metric


class ResolvedContext(LedgerModel):
    range: DateRangeView
    counterparty: CounterpartyView | None


class RendererStats(LedgerModel):
    attempts: Annotated[StrictInt, Field(ge=1, le=2)]
    fell_back_to_template: StrictBool


class RenderedReply(LedgerModel):
    reply_ar: str
    figures: tuple[Figure, ...]
    metrics: tuple[Metric, ...]
    dates: dict[str, BusinessDate]
    contexts: tuple[ResolvedContext, ...]
    resolved_range: DateRangeView | None
    resolved_counterparty: CounterpartyView | None
    renderer: RendererStats
