"""API_CONTRACT /api/chat and the closed provider draft protocol."""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from app.schemas.evidence import CounterpartyView
from app.schemas.ledger import BusinessDate, LedgerModel, ToolName
from app.schemas.queries import DateRangeView
from app.schemas.renderer import RendererStats, ResolvedContext
from app.schemas.tools import Figure, Metric


class ChatRequest(LedgerModel):
    message: Annotated[
        str,
        StringConstraints(
            strict=True, strip_whitespace=True, min_length=1, max_length=4000
        ),
    ]
    conversation_id: Annotated[
        str,
        StringConstraints(
            strict=True, min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_-]+$"
        ),
    ]


class ClarificationOption(LedgerModel):
    label_ar: str
    value: str


class Clarification(LedgerModel):
    question_ar: str
    options: tuple[ClarificationOption, ...] = ()


class InterpretationView(LedgerModel):
    """D58: what the assistant understood, also on clarify/refuse (no figures)."""

    behavior: Literal["answer", "clarify", "refuse", "help"]
    intent: str
    reason: str | None = None
    tools: tuple[ToolName, ...] = ()
    counterparty_ids: tuple[str, ...] = ()
    period: DateRangeView | None = None


class ChatResponse(LedgerModel):
    status: Literal["answered", "clarification", "refused", "llm_unavailable", "error"]
    reply_ar: str
    figures: tuple[Figure, ...] = ()
    metrics: tuple[Metric, ...] = ()
    dates: dict[str, BusinessDate] = Field(default_factory=dict)
    contexts: tuple[ResolvedContext, ...] = ()
    resolved_range: DateRangeView | None = None
    resolved_counterparty: CounterpartyView | None = None
    clarification: Clarification | None = None
    assumptions_ar: tuple[str, ...] = ()
    used_tools: tuple[ToolName, ...] = ()
    renderer: RendererStats = RendererStats(attempts=1, fell_back_to_template=False)
    interpretation: InterpretationView | None = None


class DraftAction(LedgerModel):
    status: Literal["answered", "clarification", "refused", "help"]
    draft_ar: (
        Annotated[str, StringConstraints(strict=True, min_length=1, max_length=12000)]
        | None
    ) = None
    message_key: (
        Literal[
            "clarify_period",
            "clarify_customer",
            "clarify_request",
            "clarify_opening_balance",
            "clarify_costs",
            "clarify_history",
            "clarify_due_date",
            "clarify_counts",
            "unsupported_write",
            "unsafe_instruction",
            "help",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def validate_action(self):
        if self.status == "answered":
            if self.draft_ar is None or self.message_key is not None:
                raise ValueError("Answer needs a slot draft only")
        elif self.draft_ar is not None or self.message_key is None:
            raise ValueError("Non-answers use fixed server messages only")
        elif self.status == "clarification" and not self.message_key.startswith(
            "clarify_"
        ):
            raise ValueError("Expected a clarification")
        elif self.status == "refused" and self.message_key not in {
            "unsupported_write",
            "unsafe_instruction",
        }:
            raise ValueError("Expected a refusal")
        elif self.status == "help" and self.message_key != "help":
            raise ValueError("Expected help")
        return self
