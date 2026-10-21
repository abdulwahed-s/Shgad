"""Inspect known sources without evaluating figures or reading any data file."""

from app.schemas.ledger import Category, OpeningBalance
from app.schemas.source_evidence import SourceEvidence, SourceEvidencePage
from app.services.errors import FinancialRuleError
from app.services.evidence import find_source, project_item
from app.services.observed import OBSERVED_START, observed_day
from app.services.validation import parse_timestamp


def source_page(connection, ids, *, clock, known_at):
    selected = ids.split(",")
    if (
        not 1 <= len(selected) <= 200
        or not all(selected)
        or len(set(selected)) != len(selected)
    ):
        raise FinancialRuleError("VALIDATION_ERROR")
    day, known = observed_day(clock), parse_timestamp(known_at)
    result = []
    connection.execute("SAVEPOINT source_evidence")
    try:
        for source_id in selected:
            transactions = connection.execute(
                """SELECT transaction_id FROM transactions WHERE source_id=?
                AND business_date BETWEEN ? AND ?
                AND occurred_at<=? AND recorded_at<=? LIMIT 2""",
                (
                    source_id,
                    str(OBSERVED_START),
                    str(day),
                    known.isoformat(),
                    known.isoformat(),
                ),
            ).fetchall()
            opening = connection.execute(
                """SELECT o.* FROM opening_balances o
                JOIN import_batches b USING(import_batch_id)
                WHERE o.source_id=? AND o.business_date<=?
                AND b.imported_at<=? LIMIT 2""",
                (source_id, str(day), known.isoformat()),
            ).fetchall()
            category = connection.execute(
                "SELECT * FROM categories WHERE category_id=?", (source_id,)
            ).fetchall()
            count = len(transactions) + len(opening) + len(category)
            if count == 0:
                raise FinancialRuleError("NOT_FOUND")
            if count != 1:
                raise FinancialRuleError(
                    "VALIDATION_ERROR", details={"reason": "AMBIGUOUS_SOURCE_ID"}
                )
            if transactions:
                row = find_source(connection, source_id, clock=clock, known_at=known)
                result.append(
                    SourceEvidence(
                        kind="transaction",
                        source_id=source_id,
                        transaction=project_item(connection, row, known_at=known),
                    )
                )
            elif opening:
                result.append(
                    SourceEvidence(
                        kind="opening_balance",
                        source_id=source_id,
                        opening_balance=OpeningBalance.model_validate(dict(opening[0])),
                    )
                )
            else:
                result.append(
                    SourceEvidence(
                        kind="category",
                        source_id=source_id,
                        category=Category.model_validate(dict(category[0])),
                    )
                )
        return SourceEvidencePage(items=tuple(result))
    finally:
        connection.execute("RELEASE SAVEPOINT source_evidence")
