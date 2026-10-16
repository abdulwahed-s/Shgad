"""SQLite ledger relationships without an importer or LLM (roadmap §5.3)."""

import sqlite3

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
        ledger.execute(
            """INSERT INTO transactions
            (transaction_id, source_id, source_system, source_row, import_batch_id,
             occurred_at, business_date, type, amount_iqd, counterparty_id,
             obligation_id, due_date, category_id, quantity, description, status,
             idempotency_key)
            VALUES (:transaction_id, :source_id, :source_system, :source_row,
             :import_batch_id, :occurred_at, :business_date, :type, :amount_iqd,
             :counterparty_id, :obligation_id, :due_date, :category_id, :quantity,
             :description, :status, :idempotency_key)""",
            event.model_dump(mode="json"),
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


def add_link(connection, link_id, payment, obligation_id, amount):
    connection.execute(
        "INSERT INTO payment_links VALUES (?, ?, ?, ?, ?, ?)",
        (
            link_id,
            payment.transaction_id,
            obligation_id,
            amount,
            "confirmed",
            "2026-09-28T12:00:00+00:00",
        ),
    )


def outstanding_sql(connection, obligation_id):
    return connection.execute(
        """SELECT o.original_amount_iqd - COALESCE(SUM(p.amount_iqd), 0)
        FROM obligations o LEFT JOIN payment_links p USING (obligation_id)
        WHERE o.obligation_id = ? GROUP BY o.obligation_id""",
        (obligation_id,),
    ).fetchone()[0]


def test_migrations_create_all_strict_tables_and_are_repeatable(tmp_path):
    path = tmp_path / "synthetic.sqlite"
    connection = connect_database(path)
    apply_migrations(connection)
    expected = {
        "transactions",
        "obligations",
        "payment_links",
        "counterparties",
        "categories",
        "opening_balances",
        "import_batches",
        "raw_import_rows",
        "reconciliation_flags",
        "agent_runs",
        "tool_calls",
    }
    tables = {row["name"]: row for row in connection.execute("PRAGMA table_list")}
    assert expected <= tables.keys()
    assert all(tables[name]["strict"] == 1 for name in expected)
    schema = connection.execute(
        "SELECT sql FROM sqlite_schema ORDER BY name"
    ).fetchall()
    apply_migrations(connection)
    assert (
        connection.execute("SELECT sql FROM sqlite_schema ORDER BY name").fetchall()
        == schema
    )
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    connection.close()
    reopened = connect_database(path)
    assert reopened.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    apply_migrations(reopened)
    reopened.close()


def test_migrations_are_atomic_and_reject_unknown_newer_versions(tmp_path):
    connection = connect_database(tmp_path / "synthetic.sqlite")
    connection.execute("CREATE TABLE transactions (legacy TEXT)")
    with pytest.raises(sqlite3.DatabaseError):
        apply_migrations(connection)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
    assert (
        connection.execute(
            "SELECT name FROM sqlite_schema WHERE name = 'counterparties'"
        ).fetchone()
        is None
    )
    connection.execute("PRAGMA user_version = 999")
    with pytest.raises(ValueError, match="newer"):
        apply_migrations(connection)
    connection.close()


def test_foreign_keys_and_unique_idempotency_are_database_constraints(
    ledger, insert_event
):
    event = insert_event()
    with pytest.raises(sqlite3.IntegrityError, match="idempotency_key"):
        insert_event(idempotency_key=event.idempotency_key)
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        insert_event(counterparty_id="DOES-NOT-EXIST")
    assert ledger.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 1


def test_t03_multiple_partial_collections_settle_one_receivable(
    ledger, insert_event, create_obligation
):
    create_obligation()
    first = insert_event(
        type="CREDIT_COLLECTION",
        amount_iqd=30_000,
        counterparty_id="CUST-01",
        obligation_id="OB-001",
    )
    add_link(ledger, "LINK-1", first, "OB-001", 30_000)
    assert outstanding_sql(ledger, "OB-001") == 40_000
    second = insert_event(
        type="CREDIT_COLLECTION",
        amount_iqd=40_000,
        counterparty_id="CUST-01",
        obligation_id="OB-001",
    )
    add_link(ledger, "LINK-2", second, "OB-001", 40_000)
    ledger.commit()
    assert outstanding_sql(ledger, "OB-001") == 0
    assert ledger.execute("SELECT COUNT(*) FROM payment_links").fetchone()[0] == 2


def test_t17_partial_supplier_payment_leaves_unpaid_dues(
    ledger, insert_event, create_obligation
):
    create_obligation("OB-SUP", kind="payable", amount=650_000)
    assert outstanding_sql(ledger, "OB-SUP") == 650_000
    payment = insert_event(
        type="SUPPLIER_PAYMENT",
        amount_iqd=200_000,
        counterparty_id="SUP-01",
        obligation_id="OB-SUP",
    )
    # A reference alone is not a verified settlement.
    assert outstanding_sql(ledger, "OB-SUP") == 650_000
    add_link(ledger, "LINK-SUP", payment, "OB-SUP", 200_000)
    assert outstanding_sql(ledger, "OB-SUP") == 450_000


def test_one_payment_can_allocate_to_two_same_customer_obligations(
    ledger, insert_event, create_obligation
):
    create_obligation("OB-001", amount=40_000)
    create_obligation("OB-002", amount=30_000)
    payment = insert_event(
        type="CREDIT_COLLECTION",
        amount_iqd=70_000,
        counterparty_id="CUST-01",
        obligation_id="OB-001",
    )
    add_link(ledger, "LINK-1", payment, "OB-001", 40_000)
    add_link(ledger, "LINK-2", payment, "OB-002", 30_000)
    assert outstanding_sql(ledger, "OB-001") == outstanding_sql(ledger, "OB-002") == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"counterparty_id": "CUST-02"},
        {"type": "SUPPLIER_PAYMENT", "counterparty_id": "SUP-01"},
        {"occurred_at": "2026-09-28T09:00:00+03:00"},
    ],
)
def test_link_rejects_wrong_identity_type_or_payment_before_sale(
    ledger, insert_event, create_obligation, overrides
):
    create_obligation()
    fields = {
        "type": "CREDIT_COLLECTION",
        "amount_iqd": 30_000,
        "counterparty_id": "CUST-01",
        "obligation_id": "OB-001",
    } | overrides
    # Wrong payment references are rejected either at event validation or at linking.
    with pytest.raises(sqlite3.IntegrityError):
        payment = insert_event(**fields)
        add_link(ledger, "BAD-LINK", payment, "OB-001", 30_000)
    assert outstanding_sql(ledger, "OB-001") == 70_000


def test_overallocation_is_rejected_without_deleting_payment(
    ledger, insert_event, create_obligation
):
    create_obligation()
    first = insert_event(
        type="CREDIT_COLLECTION",
        amount_iqd=30_000,
        counterparty_id="CUST-01",
        obligation_id="OB-001",
    )
    add_link(ledger, "LINK-1", first, "OB-001", 30_000)
    second = insert_event(
        type="CREDIT_COLLECTION",
        amount_iqd=50_000,
        counterparty_id="CUST-01",
        obligation_id="OB-001",
    )
    with pytest.raises(sqlite3.IntegrityError, match="over"):
        add_link(ledger, "BAD-EXCESS", second, "OB-001", 50_000)
    assert outstanding_sql(ledger, "OB-001") == 40_000
    assert (
        ledger.execute(
            "SELECT amount_iqd FROM transactions WHERE transaction_id = ?",
            (second.transaction_id,),
        ).fetchone()[0]
        == 50_000
    )
    with pytest.raises(sqlite3.IntegrityError, match="over"):
        add_link(ledger, "BAD-PAYMENT-EXCESS", first, "OB-001", 1)


def test_origin_obligation_must_match_its_credit_sale(ledger, insert_event):
    source = insert_event(
        type="CREDIT_SALE",
        amount_iqd=70_000,
        counterparty_id="CUST-01",
        obligation_id="OB-001",
    )
    with pytest.raises(sqlite3.IntegrityError):
        ledger.execute(
            "INSERT INTO obligations VALUES (?, ?, ?, ?, ?, ?)",
            ("OB-001", "receivable", source.transaction_id, "CUST-01", 99_000, None),
        )
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        ledger.commit()
    ledger.rollback()


@pytest.mark.parametrize(
    "table", ["raw_import_rows", "transactions", "obligations", "payment_links"]
)
def test_source_records_and_verified_allocations_are_immutable(
    ledger, insert_event, create_obligation, table
):
    create_obligation()
    payment = insert_event(
        type="CREDIT_COLLECTION",
        amount_iqd=30_000,
        counterparty_id="CUST-01",
        obligation_id="OB-001",
    )
    add_link(ledger, "LINK-1", payment, "OB-001", 30_000)
    # Table names come only from this fixed test parametrization.
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        ledger.execute(f"DELETE FROM {table}")
    column = {
        "raw_import_rows": "row_json",
        "transactions": "description",
        "obligations": "original_amount_iqd",
        "payment_links": "amount_iqd",
    }[table]
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        ledger.execute(f"UPDATE {table} SET {column} = {column}")


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("amount_iqd", 1.5),
        ("amount_iqd", -1),
        ("type", "UNKNOWN"),
        ("business_date", "2026-02-30"),
        ("business_date", "2026-09-27"),
        ("occurred_at", "2026-09-28T10:00:00"),
    ],
)
def test_sql_constraints_also_reject_invalid_canonical_values(
    ledger, insert_event, column, value
):
    event = insert_event()
    payload = event.model_dump(mode="json")
    payload.update(
        transaction_id="INVALID",
        source_id="INVALID",
        idempotency_key="INVALID",
        source_row=2,
    )
    payload[column] = value
    ledger.execute(
        "INSERT INTO raw_import_rows VALUES (?, ?, ?, ?, ?, ?)",
        ("RAW-2", "BATCH-001", 2, "{}", "[]", "accepted"),
    )
    with pytest.raises(sqlite3.IntegrityError):
        ledger.execute(
            """INSERT INTO transactions
            (transaction_id, source_id, source_system, source_row, import_batch_id,
             occurred_at, business_date, type, amount_iqd, counterparty_id,
             obligation_id, due_date, category_id, quantity, description, status,
             idempotency_key)
            VALUES (:transaction_id, :source_id, :source_system, :source_row,
             :import_batch_id, :occurred_at, :business_date, :type, :amount_iqd,
             :counterparty_id, :obligation_id, :due_date, :category_id, :quantity,
             :description, :status, :idempotency_key)""",
            payload,
        )


def test_batch_provenance_and_raw_rows_cannot_be_replaced(ledger, insert_event):
    insert_event()
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        ledger.execute("UPDATE import_batches SET file_sha256 = ?", ("1" * 64,))
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        ledger.execute(
            "INSERT OR REPLACE INTO raw_import_rows VALUES (?, ?, ?, ?, ?, ?)",
            ("RAW-1", "BATCH-001", 1, '{"changed":true}', "[]", "accepted"),
        )
    ledger.execute("UPDATE import_batches SET accepted_count = 1")
    assert (
        ledger.execute("SELECT accepted_count FROM import_batches").fetchone()[0] == 1
    )
    assert (
        ledger.execute("SELECT row_json FROM raw_import_rows").fetchone()[0]
        == '{"synthetic":true}'
    )


def test_migration_never_commits_a_callers_pending_work(ledger):
    ledger.execute(
        "INSERT INTO counterparties VALUES ('CUST-NEW', 'Synthetic new', 'customer')"
    )
    with pytest.raises(ValueError, match="transaction"):
        apply_migrations(ledger)
    assert ledger.in_transaction
    ledger.rollback()
    assert (
        ledger.execute(
            "SELECT * FROM counterparties WHERE counterparty_id = 'CUST-NEW'"
        ).fetchone()
        is None
    )
