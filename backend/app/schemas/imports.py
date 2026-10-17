"""Roadmap Appendix B.2 canonical importer receipt (no HTTP route yet)."""

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


class ImportReceipt(LedgerModel):
    batch_id: Identifier
    accepted: NonnegativeInteger
    rejected: NonnegativeInteger
    exact_duplicates: NonnegativeInteger
    flagged_for_review: NonnegativeInteger
    errors: tuple[ImportErrorDetail, ...] = ()
