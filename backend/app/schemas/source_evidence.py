"""Read-only source navigation, preserving frozen financial schemas."""

from typing import Literal, Self

from pydantic import model_validator

from app.schemas.evidence import LedgerItem
from app.schemas.ledger import Category, Identifier, LedgerModel, OpeningBalance


class SourceEvidence(LedgerModel):
    kind: Literal["transaction", "opening_balance", "category"]
    source_id: Identifier
    transaction: LedgerItem | None = None
    opening_balance: OpeningBalance | None = None
    category: Category | None = None

    @model_validator(mode="after")
    def one_source_kind(self) -> Self:
        for kind in ("transaction", "opening_balance", "category"):
            if (getattr(self, kind) is not None) != (self.kind == kind):
                raise ValueError("Exactly the declared source kind is required")
        return self


class SourceEvidencePage(LedgerModel):
    items: tuple[SourceEvidence, ...]
