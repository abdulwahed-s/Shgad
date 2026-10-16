"""Synthetic SQLite fixtures shared by constraint and audit tests."""

import pytest

from app.db.connection import connect_database
from app.db.migrations import apply_migrations


@pytest.fixture
def ledger(tmp_path):
    connection = connect_database(tmp_path / "synthetic.sqlite")
    apply_migrations(connection)
    with connection:
        connection.execute(
            """INSERT INTO import_batches
            (import_batch_id, source_system, account_scope, file_sha256, imported_at,
             row_count, accepted_count, flagged_count, rejected_count, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "BATCH-001",
                "synthetic_csv",
                "aggregate_cash",
                "0" * 64,
                "2026-09-28T12:00:00+00:00",
                100,
                0,
                0,
                0,
                "pending",
            ),
        )
        connection.executemany(
            "INSERT INTO counterparties VALUES (?, ?, ?)",
            [
                ("CUST-01", "أبو حيدر", "customer"),
                ("CUST-02", "أبو حيدر", "customer"),
                ("SUP-01", "Synthetic supplier", "supplier"),
            ],
        )
        connection.execute(
            "INSERT INTO categories VALUES (?, ?, ?, ?)",
            ("CAT-01", "Synthetic goods", 1_000, 5_000),
        )
    yield connection
    connection.close()


@pytest.fixture
def insert_event(ledger, transaction_factory):
    next_row = 0

    def insert(**overrides):
        nonlocal next_row
        next_row += 1
        source_id = overrides.pop("source_id", f"TX-{next_row:03}")
        event = transaction_factory(source_id, source_row=next_row, **overrides)
        ledger.execute(
            """INSERT INTO raw_import_rows
            (raw_row_id, import_batch_id, source_row, row_json, errors_json, status)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                f"RAW-{next_row}",
                "BATCH-001",
                next_row,
                '{"synthetic":true}',
                "[]",
                "accepted",
            ),
        )
        payload = event.model_dump(mode="json")
        columns = ", ".join(payload)
        values = ", ".join(f":{key}" for key in payload)
        ledger.execute(
            f"INSERT INTO transactions ({columns}) VALUES ({values})", payload
        )
        return event

    return insert


@pytest.fixture
def create_obligation(ledger, insert_event):
    def create(obligation_id="OB-001", *, kind="receivable", amount=70_000):
        customer = kind == "receivable"
        source = insert_event(
            type="CREDIT_SALE" if customer else "SUPPLIER_INVOICE",
            amount_iqd=amount,
            counterparty_id="CUST-01" if customer else "SUP-01",
            obligation_id=obligation_id,
            due_date="2026-09-30",
        )
        ledger.execute(
            "INSERT INTO obligations VALUES (?, ?, ?, ?, ?, ?)",
            (
                obligation_id,
                kind,
                source.transaction_id,
                source.counterparty_id,
                amount,
                "2026-09-30",
            ),
        )
        return source

    return create
