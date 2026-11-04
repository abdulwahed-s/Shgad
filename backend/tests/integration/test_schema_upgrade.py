"""Fresh and preserved-v1 upgrades, replay and atomic schema/data rollback."""

import hashlib
import sqlite3

import pytest

from app.db import migrations
from app.db.connection import connect_database


def seed_v1(connection):
    connection.executescript(migrations._SCHEMA_V1 + "\nPRAGMA user_version = 1;")
    with connection:
        connection.execute(
            "INSERT INTO import_batches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "LEGACY-BATCH",
                "synthetic_csv",
                "aggregate_cash",
                "a" * 64,
                "2026-09-28T12:00:00+00:00",
                4,
                4,
                0,
                0,
                "completed",
            ),
        )
        connection.execute(
            "INSERT INTO counterparties "
            "VALUES ('CUST', 'Synthetic customer', 'customer')"
        )
        connection.execute(
            "INSERT INTO categories VALUES ('CAT', 'Synthetic goods', 1000, 5000)"
        )
        for index in range(1, 5):
            connection.execute(
                "INSERT INTO raw_import_rows VALUES (?, ?, ?, ?, ?, ?)",
                (
                    f"RAW-{index}",
                    "LEGACY-BATCH",
                    index,
                    '{"original":"١٠٠"}',
                    "[]",
                    "accepted",
                ),
            )
        connection.execute("""INSERT INTO transactions VALUES
            ('SALE', 'SOURCE-SALE', 'synthetic_csv', 1, 'LEGACY-BATCH',
            '2026-09-28T07:00:00+00:00', '2026-09-28', 'CREDIT_SALE', 90000,
            'CUST', 'OB', '2026-09-30', 'CAT', 20, 'original sale', 'valid',
            'legacy-sale')""")
        connection.execute(
            "INSERT INTO obligations "
            "VALUES ('OB', 'receivable', 'SALE', 'CUST', 90000, '2026-09-30')"
        )
        connection.execute("""INSERT INTO transactions VALUES
            ('PAY', 'SOURCE-PAY', 'synthetic_csv', 2, 'LEGACY-BATCH',
            '2026-09-28T08:00:00+00:00', '2026-09-28', 'CREDIT_COLLECTION', 30000,
            'CUST', 'OB', NULL, NULL, NULL, 'original collection', 'valid',
            'legacy-pay')""")
        connection.execute(
            "INSERT INTO payment_links VALUES "
            "('LINK', 'PAY', 'OB', 30000, 'confirmed', '2026-09-28T12:00:00+00:00')"
        )
        connection.execute(
            "INSERT INTO opening_balances VALUES "
            "('OPEN', 'SOURCE-OPEN', 'synthetic_csv', 3, 'LEGACY-BATCH', "
            "'2026-07-01', 'aggregate_cash', 200000)"
        )
        connection.execute(
            "INSERT INTO reconciliation_flags VALUES "
            "('FLAG', 'partially_paid', 'partial', 60000, 'PAY', 'OB', "
            "NULL, '', 'review')"
        )
        connection.execute(
            "INSERT INTO agent_runs VALUES "
            "('RUN', '2026-09-28T12:00:00+00:00', NULL, 'error', NULL, NULL, "
            "'LLM_UNAVAILABLE')"
        )
        connection.execute(
            "INSERT INTO tool_calls VALUES "
            "('CALL', 'RUN', 'get_sales', '2026-09-28T12:00:00+00:00', "
            "NULL, 0, 'INTERNAL', '{}', '{}')"
        )


def data_snapshot(connection):
    tables = [
        r[0]
        for r in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type = 'table' ORDER BY name"
        )
    ]
    return {
        t: [dict(r) for r in connection.execute(f"SELECT * FROM {t} ORDER BY rowid")]
        for t in tables
    }


def test_upgrade_preserves_v1_rows_evidence_relationships_and_replays(tmp_path):
    with connect_database(tmp_path / "legacy.sqlite") as connection:
        seed_v1(connection)
        before = data_snapshot(connection)
        migrations.apply_migrations(connection)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 5
        after = data_snapshot(connection)
        for table, rows in before.items():
            assert (
                [{k: row[k] for k in rows[0]} for row in after[table]] == rows
                if rows
                else after[table] == []
            )
        assert after["transactions"][0]["recorded_at"] == "2026-09-28T12:00:00+00:00"
        assert after["transactions"][0]["source"] == "synthetic_csv"
        assert after["transactions"][0]["client_entry_id"] is None
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        schema = connection.execute(
            "SELECT type, name, sql FROM sqlite_schema ORDER BY name"
        ).fetchall()
        migrations.apply_migrations(connection)
        assert data_snapshot(connection) == after
        assert (
            connection.execute(
                "SELECT type, name, sql FROM sqlite_schema ORDER BY name"
            ).fetchall()
            == schema
        )
        for table in (
            "transactions",
            "raw_import_rows",
            "payment_links",
            "obligations",
        ):
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                connection.execute(f"DELETE FROM {table}")


def test_upgrade_failure_rolls_back_v1_schema_data_and_version(tmp_path):
    connection = connect_database(tmp_path / "legacy.sqlite")
    seed_v1(connection)
    connection.execute("CREATE TABLE entry_voids (legacy TEXT)")
    before = data_snapshot(connection)
    schema = connection.execute(
        "SELECT type, name, sql FROM sqlite_schema ORDER BY name"
    ).fetchall()
    with pytest.raises(sqlite3.DatabaseError):
        migrations.apply_migrations(connection)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert connection.execute("PRAGMA recursive_triggers").fetchone()[0] == 1
    assert data_snapshot(connection) == before
    assert (
        connection.execute(
            "SELECT type, name, sql FROM sqlite_schema ORDER BY name"
        ).fetchall()
        == schema
    )
    assert not connection.in_transaction
    connection.close()


def test_upgrade_refuses_corrupt_v1_foreign_keys_atomically(tmp_path):
    connection = connect_database(tmp_path / "legacy.sqlite")
    seed_v1(connection)
    connection.execute("PRAGMA foreign_keys = OFF")
    with connection:
        connection.execute("DROP TRIGGER obligations_immutable_delete")
        connection.execute("DELETE FROM obligations")
    connection.execute("PRAGMA foreign_keys = ON")
    before = data_snapshot(connection)
    with pytest.raises(sqlite3.IntegrityError, match="foreign key"):
        migrations.apply_migrations(connection)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert data_snapshot(connection) == before
    connection.close()


def test_v1_migration_definition_remains_historically_identical():
    # Pinned from application commit 7079424, including append-only guards.
    assert (
        hashlib.sha256(migrations._SCHEMA_V1.encode()).hexdigest()
        == "c1be81a4acd8fc59077ed536be2b2fd4732ee2ae3dba117450e0dc08b6ea4178"
    )


def test_mapping_upgrade_preserves_populated_v2_and_rolls_back_on_conflict(tmp_path):
    connection = connect_database(tmp_path / "version2.sqlite")
    seed_v1(connection)
    connection.executescript(
        "PRAGMA foreign_keys = OFF;\n"
        + migrations._SCHEMA_V2
        + "\nPRAGMA user_version = 2; PRAGMA foreign_keys = ON;"
    )
    before = data_snapshot(connection)
    connection.execute("CREATE TABLE csv_mappings (legacy TEXT)")
    with pytest.raises(sqlite3.DatabaseError):
        migrations.apply_migrations(connection)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
    assert not connection.in_transaction
    connection.execute("DROP TABLE csv_mappings")
    migrations.apply_migrations(connection)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 5
    after = data_snapshot(connection)
    for table, rows in before.items():
        assert after[table] == rows
    assert after["csv_mappings"] == after["mapping_confirmations"] == []
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    connection.close()


def test_correction_upgrade_preserves_v3_mappings_and_rolls_back_on_conflict(tmp_path):
    connection = connect_database(tmp_path / "version3.sqlite")
    seed_v1(connection)
    connection.executescript(
        "PRAGMA foreign_keys = OFF;\n"
        + migrations._SCHEMA_V2
        + migrations._SCHEMA_V3
        + "\nPRAGMA user_version = 3; PRAGMA foreign_keys = ON;"
    )
    with connection:
        connection.execute(
            "INSERT INTO csv_mappings VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "LEGACY-MAP",
                "fictional.csv",
                b"Ref\nfictional\n",
                "[]",
                "{}",
                "2026-09-28",
                "2026-09-28T12:00:00+00:00",
            ),
        )
    before = data_snapshot(connection)
    connection.execute("CREATE TABLE entry_corrections (legacy TEXT)")
    with pytest.raises(sqlite3.DatabaseError):
        migrations.apply_migrations(connection)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
    connection.execute("DROP TABLE entry_corrections")
    migrations.apply_migrations(connection)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 5
    after = data_snapshot(connection)
    for table, rows in before.items():
        assert after[table] == rows
    assert after["entry_corrections"] == []
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    connection.close()


def seed_v4(connection):
    seed_v1(connection)
    connection.executescript(
        "PRAGMA foreign_keys = OFF;\n"
        + migrations._SCHEMA_V2
        + migrations._SCHEMA_V3
        + migrations._SCHEMA_V4
        + "\nPRAGMA user_version = 4; PRAGMA foreign_keys = ON;"
    )
    with connection:
        connection.execute(
            "INSERT INTO entry_voids VALUES (?, ?, ?, ?, ?, ?)",
            (
                "VOID-PAY",
                "PAY",
                "SOURCE-PAY",
                "merchant-undo",
                "synthetic correction",
                "2026-09-28T13:00:00+00:00",
            ),
        )


def test_precision_upgrade_preserves_v4_evidence_guards_and_replays(tmp_path):
    with connect_database(tmp_path / "version4.sqlite") as connection:
        seed_v4(connection)
        before = data_snapshot(connection)
        guards = connection.execute(
            "SELECT type, name, sql FROM sqlite_schema "
            "WHERE type IN ('trigger', 'index') AND sql IS NOT NULL ORDER BY name"
        ).fetchall()
        migrations.apply_migrations(connection)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 5
        assert data_snapshot(connection) == before
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA recursive_triggers").fetchone()[0] == 1
        assert (
            connection.execute(
                "SELECT type, name, sql FROM sqlite_schema "
                "WHERE type IN ('trigger', 'index') AND sql IS NOT NULL ORDER BY name"
            ).fetchall()
            == guards
        )
        schema = connection.execute(
            "SELECT type, name, sql FROM sqlite_schema ORDER BY name"
        ).fetchall()
        migrations.apply_migrations(connection)
        assert data_snapshot(connection) == before
        assert (
            connection.execute(
                "SELECT type, name, sql FROM sqlite_schema ORDER BY name"
            ).fetchall()
            == schema
        )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("DELETE FROM transactions WHERE transaction_id = 'PAY'")
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("DELETE FROM entry_voids")

        late = dict(
            connection.execute(
                "SELECT * FROM transactions WHERE transaction_id = 'PAY'"
            ).fetchone()
        )
        late.update(
            transaction_id="LATE",
            source_id="LATE",
            source_row=4,
            occurred_at="2026-09-28T20:59:59.999999+00:00",
            business_date="2026-09-28",
            type="CASH_SALE",
            counterparty_id=None,
            obligation_id=None,
            idempotency_key="late-entry",
            recorded_at="2026-09-29T00:00:00+00:00",
        )
        columns = ", ".join(late)
        values = ", ".join(f":{key}" for key in late)
        connection.execute(
            f"INSERT INTO transactions ({columns}) VALUES ({values})", late
        )
        assert tuple(
            connection.execute(
                "SELECT occurred_at, business_date FROM transactions "
                "WHERE transaction_id = 'LATE'"
            ).fetchone()
        ) == ("2026-09-28T20:59:59.999999+00:00", "2026-09-28")


def test_precision_upgrade_failure_rolls_back_v4_schema_data_and_version(tmp_path):
    with connect_database(tmp_path / "version4.sqlite") as connection:
        seed_v4(connection)
        connection.execute("CREATE TABLE transactions_new (legacy TEXT)")
        before = data_snapshot(connection)
        schema = connection.execute(
            "SELECT type, name, sql FROM sqlite_schema ORDER BY name"
        ).fetchall()
        with pytest.raises(sqlite3.DatabaseError):
            migrations.apply_migrations(connection)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 4
        assert data_snapshot(connection) == before
        assert (
            connection.execute(
                "SELECT type, name, sql FROM sqlite_schema ORDER BY name"
            ).fetchall()
            == schema
        )
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA recursive_triggers").fetchone()[0] == 1
        assert not connection.in_transaction
