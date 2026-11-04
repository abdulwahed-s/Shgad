"""D61 / FINANCIAL_RULES §12: real ledger queries, isolated reminder memory."""

import sqlite3
from datetime import date, datetime

import pytest

from app.db import migrations
from app.services.business_clock import BusinessClock
from app.services.demo_seed import restore_demo

CLOCK = BusinessClock(date(2026, 9, 28))
AUDIT = datetime.fromisoformat("2026-11-04T10:00:00+00:00")


def table_snapshot(db):
    tables = [
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name"
        )
    ]
    return {
        table: (
            db.execute(
                "SELECT sql FROM sqlite_schema WHERE name=?", (table,)
            ).fetchone()[0],
            sorted(tuple(row) for row in db.execute(f'SELECT * FROM "{table}"')),
        )
        for table in tables
    }


def test_v5_sample_upgrade_adds_only_empty_reminder_table(ledger, monkeypatch):
    """User-approved4Nov: every populated v5 table/schema/row must survive."""
    all_versions = migrations._MIGRATIONS
    with monkeypatch.context() as patch:
        patch.setattr(migrations, "_MIGRATIONS", all_versions[:5])
        # restore_demo builds a new v5 sample and atomically replaces the fixture.
        restore_demo(ledger, clock=CLOCK)
    assert ledger.execute("PRAGMA user_version").fetchone()[0] == 5
    before = table_snapshot(ledger)
    old_schema = {
        tuple(row)
        for row in ledger.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema")
    }
    assert len(before["transactions"][1]) > 100
    migrations.apply_migrations(ledger)
    after = table_snapshot(ledger)
    assert ledger.execute("PRAGMA user_version").fetchone()[0] == 6
    assert set(after) - set(before) == {"reminders"}
    assert after["reminders"][1] == []
    assert {name: after[name] for name in before} == before
    new_schema = {
        tuple(row)
        for row in ledger.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema")
    }
    assert old_schema <= new_schema
    assert all(row[2] == "reminders" for row in new_schema - old_schema)
    assert ledger.execute("PRAGMA foreign_key_check").fetchall() == []
    migrations.apply_migrations(ledger)
    assert table_snapshot(ledger) == after


def test_collection_ranking_exact_overdue_only_and_stable_ties(
    api, ledger, debt_factory
):
    ledger.execute(
        "INSERT INTO counterparties VALUES ('CUST-03','زبون تجريبي','customer')"
    )
    debt_factory("OLDER", 80000, "2026-09-10", party="CUST-01")
    debt_factory("LARGER", 90000, "2026-09-25", party="CUST-02")
    debt_factory("TIE", 90000, "2026-09-25", party="CUST-03")
    debt_factory("FUTURE", 990000, "2026-09-30", party="CUST-01")
    ledger.commit()
    before = tuple(ledger.iterdump())
    result = api.get("/api/collections")
    assert result.status_code == 200, result.text
    body = result.json()
    assert [p["counterparty_id"] for p in body["items"]] == [
        "CUST-02",
        "CUST-03",
        "CUST-01",
    ]
    debts = api.get("/api/debts?overdue_only=true").json()
    by_id = {p["counterparty_id"]: p for p in debts["customers"]}
    for item in body["items"]:
        original = by_id[item["counterparty_id"]]
        assert (
            item["overdue_amount"]["amount_iqd"]
            == original["outstanding"]["amount_iqd"]
        )
        assert item["source_ids"] == original["outstanding"]["source_ids"]
        assert item["oldest_due_date"] == original["oldest_due_date"]
        assert item["days_overdue"] == original["days_overdue"]
        assert item["reminder_count"] == 0
        assert item["last_reminder_business_date"] is None
        assert item["days_since_last_reminder"] is None
    assert body["total_overdue"]["amount_iqd"] == 260000
    assert body["customer_count"]["value"] == 3
    assert tuple(ledger.iterdump()) == before


def test_collection_same_amount_older_first(api, ledger, debt_factory):
    debt_factory("A", 90000, "2026-09-25", party="CUST-01")
    debt_factory("B", 90000, "2026-09-10", party="CUST-02")
    ledger.commit()
    assert [
        p["counterparty_id"] for p in api.get("/api/collections").json()["items"]
    ] == ["CUST-02", "CUST-01"]


def test_primary_sample_has_proven_empty_overdue_list(api):
    assert api.post("/api/demo/reset").status_code == 200
    body = api.get("/api/collections").json()
    assert body["items"] == []
    for key in ("total_overdue", "customer_count"):
        proof = body[key]["query_evidence"]
        assert proof["tool"] == "get_debts" and proof["matching_obligations"] == 0
        assert proof["filters"]["overdue_only"] is True


def test_reminder_log_amount_from_server_and_no_financial_changes(
    api, ledger, debt_factory, j1_shop
):
    debt_factory("LATE", 47000, "2026-09-20", party="CUST-02")
    ledger.commit()
    financial = {
        path: api.get(path).json()
        for path in ("/api/debts", "/api/obligations/upcoming", "/api/flags")
    }
    before = table_snapshot(ledger)
    request = {
        "counterparty_id": "CUST-02",
        "tone": "normal",
        "channel": "copy",
        "edited": True,
    }
    first = api.post("/api/reminders", json=request)
    assert first.status_code == 201, first.text
    result = first.json()
    assert result["overdue_amount"]["amount_iqd"] == 47000
    assert result["overdue_amount"]["source_ids"] == ["LATE"]
    assert result["business_date"] == "2026-09-28"
    assert result["recorded_at"].endswith(("Z", "+00:00"))
    assert result["edited"] is True
    assert api.post("/api/reminders", json=request).status_code == 201
    item = api.get("/api/collections").json()["items"][0]
    assert item["reminder_count"] == 2
    assert item["last_reminder_business_date"] == "2026-09-28"
    assert item["days_since_last_reminder"] == 0
    for path, expected in financial.items():
        assert api.get(path).json() == expected
    after = table_snapshot(ledger)
    assert {key: after[key] for key in before if key != "reminders"} == {
        key: value for key, value in before.items() if key != "reminders"
    }
    for sql in ("DELETE FROM reminders", "UPDATE reminders SET edited=0"):
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            ledger.execute(sql)
    ledger.rollback()
    assert api.post("/api/demo/reset").status_code == 200
    assert ledger.execute("SELECT count(*) FROM reminders").fetchone()[0] == 0


@pytest.mark.parametrize(
    "extra",
    [
        {"amount_iqd": 1},
        {"business_date": "2026-09-01"},
        {"edited": "false"},
        {"phone": "synthetic"},
        {"tone": "threat"},
        {"channel": "email"},
    ],
)
def test_reminder_closed_request_rejects_untrusted_values(
    api, ledger, debt_factory, extra
):
    debt_factory("LATE", 30000, "2026-09-20")
    ledger.commit()
    request = {
        "counterparty_id": "CUST-01",
        "tone": "gentle",
        "channel": "copy",
        "edited": False,
    }
    response = api.post("/api/reminders", json=request | extra)
    assert response.status_code == 422
    assert ledger.execute("SELECT count(*) FROM reminders").fetchone()[0] == 0


def test_not_due_or_paid_customer_never_gets_log(api, j1_shop):
    for party in ("CUST-01", "CUST-02"):
        response = api.post(
            "/api/reminders",
            json={
                "counterparty_id": party,
                "tone": "gentle",
                "channel": "whatsapp",
                "edited": False,
            },
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "NO_OVERDUE_DEBT"


def test_reminders_use_actual_audit_cutoff_not_financial_day_end(ledger, debt_factory):
    from app.schemas.collections import ReminderRequest
    from app.services.collections import get_reminders, log_reminder

    debt_factory("LATE", 30000, "2026-09-20")
    ledger.commit()
    request = ReminderRequest(
        counterparty_id="CUST-01", tone="gentle", channel="copy", edited=False
    )
    log_reminder(ledger, request, clock=CLOCK, now=AUDIT)
    assert (
        get_reminders(ledger, ("CUST-01",), clock=CLOCK, known_at=AUDIT).items[0].count
        == 1
    )
    before = datetime.fromisoformat("2026-11-04T09:59:59+00:00")
    assert (
        get_reminders(ledger, ("CUST-01",), clock=CLOCK, known_at=before).items[0].count
        == 0
    )


def test_missing_due_date_is_not_assumed_no_overdue(api, ledger, debt_factory):
    debt_factory("UNKNOWN-DUE", 30000, None)
    ledger.commit()
    response = api.get("/api/collections")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MISSING_DUE_DATE"


def test_more_than_two_hundred_customers_are_ranked_with_batched_memory(
    ledger, debt_factory
):
    from app.services.collections import collection_report

    for index in range(201):
        key = f"EXTRA-{index:03}"
        ledger.execute(
            "INSERT INTO counterparties VALUES (?,?,?)",
            (key, f"زبون {index}", "customer"),
        )
        debt_factory(f"D-{index}", 10000, "2026-09-20", party=key)
    ledger.commit()
    result = collection_report(ledger, clock=CLOCK, known_at=AUDIT)
    assert len(result.items) == 201
    assert all(item.reminder_count == 0 for item in result.items)


def test_empty_overdue_proof_supports_actual_audit_after_business_date(api):
    from app.api.dependencies import audit_timestamp
    from app.main import app

    app.dependency_overrides[audit_timestamp] = lambda: AUDIT
    assert api.post("/api/demo/reset").status_code == 200
    response = api.get("/api/collections")
    assert response.status_code == 200, response.text
    assert (
        response.json()["total_overdue"]["query_evidence"]["matching_obligations"] == 0
    )
