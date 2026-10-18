"""Synthetic SQLite fixtures shared by constraint and audit tests."""

import asyncio
from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.connection import connect_database
from app.db.migrations import apply_migrations


@pytest.fixture
def api(ledger):
    """Real HTTP/service/SQLite stack with only settings and audit time injected."""
    from app.api.dependencies import audit_timestamp, database
    from app.config import Settings, get_settings
    from app.main import app

    path = ledger.execute("PRAGMA database_list").fetchone()[2]

    async def connection():
        db = connect_database(path)
        try:
            yield db
        finally:
            db.close()

    class Client:
        def request(self, method, url, **kwargs):
            async def send():
                async with AsyncClient(
                    transport=ASGITransport(app=app, raise_app_exceptions=False),
                    base_url="http://test",
                ) as client:
                    return await client.request(method, url, **kwargs)

            return asyncio.run(send())

        def post(self, url, **kwargs):
            return self.request("POST", url, **kwargs)

        def get(self, url, **kwargs):
            return self.request("GET", url, **kwargs)

    app.dependency_overrides[database] = connection
    app.dependency_overrides[get_settings] = lambda: Settings()
    app.dependency_overrides[audit_timestamp] = lambda: datetime.fromisoformat(
        "2026-09-28T23:59:59+03:00"
    )
    try:
        yield Client()
    finally:
        app.dependency_overrides.clear()


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


@pytest.fixture
def debt_factory(ledger, insert_event):
    """Inline fictional obligations with exact identities and observed origins."""

    def create(key, amount, due, *, kind="receivable", party=None):
        row = insert_event(
            source_id=key,
            type="CREDIT_SALE" if kind == "receivable" else "SUPPLIER_INVOICE",
            amount_iqd=amount,
            counterparty_id=party or ("CUST-01" if kind == "receivable" else "SUP-01"),
            obligation_id=f"OB-{key}",
            due_date=due,
        )
        ledger.execute(
            "INSERT INTO obligations VALUES (?, ?, ?, ?, ?, ?)",
            (
                row.obligation_id,
                kind,
                row.transaction_id,
                row.counterparty_id,
                amount,
                due,
            ),
        )
        return row

    return create


@pytest.fixture
def j1_shop(ledger, insert_event, debt_factory):
    insert_event(
        source_id="CNT-090",
        type="DAILY_CASH_COUNT",
        amount_iqd=420000,
        occurred_at="2026-09-28T21:00:00+03:00",
    )
    debt_factory("J1-R", 150000, "2026-09-30")
    debt_factory("J1-P", 650000, "2026-10-01", kind="payable")
    ledger.commit()
    return ledger


@pytest.fixture
def tool_history(ledger, insert_event, debt_factory):
    from datetime import date, timedelta

    # Eight observed weekdays of gap history; no future realized outcomes.
    for offset in range(9):
        day = date(2026, 9, 20) + timedelta(days=offset)
        insert_event(
            source_id=f"SALE-{offset}",
            amount_iqd=10000,
            category_id="CAT-01",
            quantity=2,
            occurred_at=f"{day}T12:00:00+03:00",
        )
        insert_event(
            source_id=f"CNT-{offset}",
            type="DAILY_CASH_COUNT",
            amount_iqd=340000 + offset * 10000,
            occurred_at=f"{day}T21:00:00+03:00",
        )
    debt_factory("J1-R", 150000, "2026-09-30")
    debt_factory("J1-P", 650000, "2026-10-01", kind="payable")
    settled = debt_factory("SETTLED", 30000, "2026-09-25")
    payment = insert_event(
        source_id="SETTLEMENT",
        type="CREDIT_COLLECTION",
        amount_iqd=30000,
        counterparty_id="CUST-01",
        obligation_id=settled.obligation_id,
        occurred_at="2026-09-28T12:00:00+03:00",
    )
    ledger.execute(
        "INSERT INTO payment_links VALUES (?, ?, ?, ?, ?, ?)",
        (
            "TOOL-LINK",
            payment.transaction_id,
            settled.obligation_id,
            30000,
            "definite",
            "2026-09-28T09:00:00+00:00",
        ),
    )
    insert_event(
        source_id="UNALLOCATED",
        type="CREDIT_COLLECTION",
        amount_iqd=10000,
        counterparty_id="CUST-02",
        status="flagged",
    )
    ledger.commit()
    return ledger
