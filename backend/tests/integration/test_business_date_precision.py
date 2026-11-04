"""FINANCIAL_RULES §1: UTC evidence keeps its exact Baghdad calendar date."""

import sqlite3

import pytest


@pytest.mark.parametrize(
    ("occurred_at", "business_date", "wrong_date"),
    [
        ("2026-09-28T20:59:59.999999+00:00", "2026-09-28", "2026-09-29"),
        ("2026-09-28T21:00:00.000001+00:00", "2026-09-29", "2026-09-28"),
        ("2026-09-28T23:59:59.999999+00:00", "2026-09-29", "2026-09-28"),
        ("2026-12-31T20:59:59.999999+00:00", "2026-12-31", "2027-01-01"),
        ("2026-12-31T21:00:00.000001+00:00", "2027-01-01", "2026-12-31"),
        ("2026-02-28T20:59:59.999999+00:00", "2026-02-28", "2026-03-01"),
        ("2026-02-28T21:00:00.000001+00:00", "2026-03-01", "2026-02-28"),
    ],
)
def test_calendar_boundaries_preserve_microseconds_and_reject_wrong_dates(
    ledger, insert_event, occurred_at, business_date, wrong_date
):
    event = insert_event(occurred_at=occurred_at)
    row = ledger.execute(
        "SELECT occurred_at, business_date FROM transactions WHERE transaction_id = ?",
        (event.transaction_id,),
    ).fetchone()
    assert tuple(row) == (occurred_at, business_date)

    # Bypass Pydantic to prove the database still rejects a mismatched date.
    payload = event.model_dump(mode="json")
    payload.update(
        transaction_id="WRONG-DATE",
        source_id="WRONG-DATE",
        source_row=2,
        idempotency_key="WRONG-DATE",
        business_date=wrong_date,
    )
    ledger.execute(
        "INSERT INTO raw_import_rows VALUES (?, ?, ?, ?, ?, ?)",
        ("RAW-2", "BATCH-001", 2, "{}", "[]", "accepted"),
    )
    columns = ", ".join(payload)
    values = ", ".join(f":{key}" for key in payload)
    with pytest.raises(sqlite3.IntegrityError, match="business_date"):
        ledger.execute(
            f"INSERT INTO transactions ({columns}) VALUES ({values})", payload
        )
