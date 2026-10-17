"""Cutoff-filtered, read-only SQLite snapshot for production forecasting.

The service gets no paths or unfiltered ledger. Financial time, entry knowledge,
link knowledge and void knowledge are constrained inside SQL in one snapshot.
Future due dates are obligation attributes, never a reason to hide a known debt.
"""

import sqlite3
from dataclasses import dataclass
from datetime import UTC

from app.schemas.ledger import Obligation, OpeningBalance, PaymentLink, Transaction
from app.services.business_clock import BusinessClock
from app.services.ledger_rules import knowledge_cutoff
from app.services.observed import observed_day

_VISIBLE = """WITH visible AS (
    SELECT t.* FROM transactions t
    WHERE t.business_date <= :day AND t.occurred_at <= :known
    AND t.recorded_at <= :known
    AND NOT EXISTS (SELECT 1 FROM entry_voids v
        WHERE v.transaction_id = t.transaction_id AND v.voided_at <= :known)
) """


@dataclass(frozen=True)
class ForecastSnapshot:
    transactions: tuple[Transaction, ...]
    obligations: tuple[Obligation, ...]
    payment_links: tuple[PaymentLink, ...]
    opening_balance: OpeningBalance | None


def read_forecast_snapshot(
    connection: sqlite3.Connection, *, clock: BusinessClock
) -> ForecastSnapshot:
    day = observed_day(clock)
    params = {
        "day": day.isoformat(),
        "known": knowledge_cutoff(day).astimezone(UTC).isoformat(),
    }
    connection.execute("SAVEPOINT forecast_snapshot")
    try:
        transactions = tuple(
            Transaction.model_validate(dict(row))
            for row in connection.execute(
                _VISIBLE + "SELECT * FROM visible ORDER BY occurred_at, transaction_id",
                params,
            )
        )
        obligations = tuple(
            Obligation.model_validate(dict(row))
            for row in connection.execute(
                _VISIBLE
                + """SELECT o.* FROM obligations o JOIN visible origin
                ON origin.transaction_id = o.origin_transaction_id
                ORDER BY o.obligation_id""",
                params,
            )
        )
        links = tuple(
            PaymentLink.model_validate(dict(row))
            for row in connection.execute(
                _VISIBLE
                + """SELECT l.* FROM payment_links l
                JOIN visible p ON p.transaction_id = l.payment_transaction_id
                JOIN obligations o ON o.obligation_id = l.obligation_id
                JOIN visible origin ON origin.transaction_id = o.origin_transaction_id
                WHERE l.created_at <= :known ORDER BY l.payment_link_id""",
                params,
            )
        )
        opening = connection.execute(
            """SELECT o.* FROM opening_balances o
            JOIN import_batches b USING (import_batch_id)
            WHERE o.business_date <= :day AND b.imported_at <= :known
            ORDER BY o.business_date DESC LIMIT 1""",
            params,
        ).fetchone()
        return ForecastSnapshot(
            transactions,
            obligations,
            links,
            OpeningBalance.model_validate(dict(opening)) if opening else None,
        )
    finally:
        connection.execute("RELEASE SAVEPOINT forecast_snapshot")
