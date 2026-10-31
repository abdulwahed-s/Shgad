"""Roadmap Appendix B.2 canonical importer receipt."""

from pydantic import model_serializer

from app.schemas.evidence import CounterpartyView
from app.schemas.ledger import (
    Identifier,
    LedgerModel,
    NonnegativeInteger,
    PositiveInteger,
)


class ImportErrorDetail(LedgerModel):
    row: PositiveInteger
    code: str
    message: str
    field: str | None = None
    candidates: tuple[CounterpartyView, ...] = ()

    @model_serializer(mode="wrap")
    def optional_mapping_metadata(self, handler):
        data = handler(self)
        if self.field is None:
            data.pop("field", None)
        if not self.candidates:
            data.pop("candidates", None)
        return data


class ImportReceipt(LedgerModel):
    batch_id: Identifier
    accepted: NonnegativeInteger
    rejected: NonnegativeInteger
    exact_duplicates: NonnegativeInteger
    flagged_for_review: NonnegativeInteger
    errors: tuple[ImportErrorDetail, ...] = ()
