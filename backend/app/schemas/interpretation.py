"""D58 closed interpretation of one merchant question (LABEL_RULES_V2).

The model fills this object; it never contains money, computed dates or tool
arguments. Integers are copied from the merchant's own text and re-checked by
the server against the verbatim evidence before any resolution.
"""

from typing import Annotated, Literal

from pydantic import Field, StrictBool, StringConstraints, model_validator

from app.schemas.ledger import LedgerModel

Intent = Literal[
    "sales",
    "cash_on_hand",
    "debts",
    "upcoming_obligations",
    "supplier_sufficiency",
    "weekly_summary",
    "period_movements",
    "estimated_gross_margin",
    "reconciliation",
    "collection_priorities",
    "draft_reminder",
    "daily_brief",
    "unsupported_write",
    "unsafe_instruction",
    "out_of_scope",
    "help",
]
Reason = Literal[
    "AMBIGUOUS_COUNTERPARTY",
    "UNKNOWN_COUNTERPARTY",
    "AMBIGUOUS_DATE",
    "VALIDATION_ERROR",
    "NO_HISTORICAL_DATA",
    "MISSING_OPENING_BALANCE",
    "MISSING_COSTS",
    "REVIEW_REQUIRED",
    "OUT_OF_SCOPE",
]
Weekday = Literal["sat", "sun", "mon", "tue", "wed", "thu", "fri"]
TimeType = Literal[
    "none",
    "today",
    "yesterday",
    "day_before_yesterday",
    "tomorrow",
    "this_week",
    "last_week",
    "this_month",
    "last_month",
    "month",
    "last_n_days",
    "next_n_days",
    "since_day",
    "day",
    "day_range",
    "date_range",
    "weekday_past",
    "weekday_next",
]
Movement = Literal[
    "owner_drawings",
    "operating_expenses",
    "supplier_payments",
    "collections",
    "capital_injections",
    "drawings_and_expenses",
]
Verbatim = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=120)]

_NEEDS = {
    "month": {"month"},
    "last_n_days": {"n"},
    "next_n_days": {"n"},
    "since_day": {"day"},
    "day": {"day"},
    "day_range": {"day", "day_end"},
    "date_range": {"day", "month", "day_end", "month_end"},
    "weekday_past": {"weekday"},
    "weekday_next": {"weekday"},
}
_ALLOWED = {
    "month": {"month", "year"},
    "day": {"day", "month", "year"},
    "day_range": {"day", "day_end", "month", "year"},
    "date_range": {"day", "month", "day_end", "month_end", "year"},
}


class TimeExpression(LedgerModel):
    type: TimeType
    evidence: Verbatim | None = None
    n: Annotated[int, Field(strict=True, ge=1, le=366)] | None = None
    day: Annotated[int, Field(strict=True, ge=1, le=31)] | None = None
    day_end: Annotated[int, Field(strict=True, ge=1, le=31)] | None = None
    month: Annotated[int, Field(strict=True, ge=1, le=12)] | None = None
    month_end: Annotated[int, Field(strict=True, ge=1, le=12)] | None = None
    year: Annotated[int, Field(strict=True, ge=1900, le=2100)] | None = None
    weekday: Weekday | None = None

    @model_validator(mode="after")
    def fields_match_type(self):
        present = {
            key
            for key in ("n", "day", "day_end", "month", "month_end", "year", "weekday")
            if getattr(self, key) is not None
        }
        needed = _NEEDS.get(self.type, set())
        allowed = _ALLOWED.get(self.type, needed)
        if not needed <= present <= allowed:
            raise ValueError("Time fields do not match the expression type")
        return self


class Interpretation(LedgerModel):
    behavior: Literal["answer", "clarify", "refuse", "help"]
    intent: Intent
    reason: Reason | None = None
    sales_kind: Literal["cash", "credit", "all"] = "all"
    direction: Literal["receivable", "payable", "both"] = "receivable"
    overdue_only: StrictBool = False
    movement: Movement | None = None
    expense_kind_mention: Verbatim | None = None
    days: Annotated[int, Field(strict=True, ge=1, le=30)] | None = None
    party_mentions: tuple[Verbatim, ...] = Field(default=(), max_length=4)
    collection_party_mentions: tuple[Verbatim, ...] = Field(default=(), max_length=2)
    without_collection: StrictBool = False
    per_day: StrictBool = False
    time: TimeExpression = TimeExpression(type="none")

    @model_validator(mode="after")
    def consistent(self):
        if self.expense_kind_mention is not None and (
            self.intent != "period_movements" or self.movement != "operating_expenses"
        ):
            raise ValueError("Expense kinds require an operating-expense question")
        if self.behavior == "refuse" and self.intent not in {
            "unsupported_write",
            "unsafe_instruction",
        }:
            raise ValueError("Refusals use a refusal intent")
        if self.intent in {"unsupported_write", "unsafe_instruction"} and (
            self.behavior != "refuse"
        ):
            raise ValueError("Refusal intents must refuse")
        if (self.behavior == "clarify") != (self.reason is not None):
            raise ValueError("Exactly clarifications carry a reason")
        if self.behavior == "help" and self.intent != "help":
            raise ValueError("Help uses the help intent")
        if self.intent == "period_movements" and self.behavior == "answer":
            if self.movement is None:
                raise ValueError("Movement questions name a movement")
        return self
