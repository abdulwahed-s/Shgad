"""T01–T03/T17/T21/T27: merchant writes, strict IQD and partial settlements."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest

from app.services.ledger_audit import read_ledger
from app.services.ledger_rules import event_effect, obligation_outstanding


def save(api, client_id, event_type="CASH_SALE", amount=100000, **extra):
    return api.post(
        "/api/entries",
        json={
            "client_entry_id": client_id,
            "type": event_type,
            "business_date": "2026-09-28",
            "amount_iqd": amount,
            **extra,
        },
    )


def test_t01_t02_t03_t17_t21_manual_entries_have_separate_financial_effects(
    api, ledger
):
    requests = [
        ("cash", "CASH_SALE", 100000, {}),
        ("credit", "CREDIT_SALE", 70000, {"counterparty_id": "CUST-01"}),
        ("invoice", "SUPPLIER_INVOICE", 60000, {"counterparty_id": "SUP-01"}),
        ("collection", "CREDIT_COLLECTION", 30000, {"counterparty_id": "CUST-01"}),
        ("payment", "SUPPLIER_PAYMENT", 20000, {"counterparty_id": "SUP-01"}),
        ("expense", "OPERATING_EXPENSE", 10000, {}),
        ("drawing", "OWNER_DRAWING", 5000, {}),
        ("capital", "CAPITAL_INJECTION", 8000, {}),
        ("count", "DAILY_CASH_COUNT", 420000, {}),
    ]
    for client_id, event_type, amount, extra in requests:
        if event_type in {"CREDIT_COLLECTION", "SUPPLIER_PAYMENT"}:
            kind = "receivable" if event_type == "CREDIT_COLLECTION" else "payable"
            extra["obligation_id"] = ledger.execute(
                "SELECT obligation_id FROM obligations WHERE kind = ?", (kind,)
            ).fetchone()[0]
        result = save(api, client_id, event_type, amount, **extra)
        assert result.status_code == 201, result.text
        receipt = result.json()
        assert set(receipt) == {"transaction_id", "source_id", "duplicate"}
        assert receipt["duplicate"] is False
        replay = save(api, client_id, event_type, amount, **extra)
        assert replay.status_code == 200, replay.text
        assert replay.json() == receipt | {"duplicate": True}
    snapshot = read_ledger(ledger)
    assert len(snapshot.transactions) == 9
    effects = [event_effect(row) for row in snapshot.transactions]
    assert sum(e.cash_delta_iqd for e in effects) == 103000
    assert sum(e.revenue_delta_iqd for e in effects) == 170000
    assert sum(e.operating_expenses_iqd for e in effects) == 10000
    assert sum(e.owner_drawings_iqd for e in effects) == 5000
    assert [
        obligation_outstanding(
            o, snapshot.transactions, snapshot.payment_links, as_of=date(2026, 9, 28)
        )
        for o in snapshot.obligations
    ] == [40000, 40000]
    assert all(row.source == "manual_entry" for row in snapshot.transactions)
    assert all(row.source_system == "synthetic_entry" for row in snapshot.transactions)
    assert ledger.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize(
    "payment_type,party,origin_type",
    [
        ("CREDIT_COLLECTION", "CUST-01", "CREDIT_SALE"),
        ("SUPPLIER_PAYMENT", "SUP-01", "SUPPLIER_INVOICE"),
    ],
)
def test_t27_three_partial_payments_and_no_overallocation(
    api, ledger, payment_type, party, origin_type
):
    assert (
        save(
            api,
            "debt",
            origin_type,
            90000,
            counterparty_id=party,
            obligation_id="THREE",
            due_date="2026-09-28",
        ).status_code
        == 201
    )
    for index, amount in enumerate([30000, 25000, 35000]):
        assert (
            save(
                api,
                f"part-{index}",
                payment_type,
                amount,
                counterparty_id=party,
                obligation_id="THREE",
            ).status_code
            == 201
        )
    before = read_ledger(ledger)
    assert (
        obligation_outstanding(
            before.obligations[0],
            before.transactions,
            before.payment_links,
            as_of=date(2026, 9, 28),
        )
        == 0
    )
    result = save(
        api, "excess", payment_type, 1, counterparty_id=party, obligation_id="THREE"
    )
    assert result.status_code == 422, result.text
    assert result.json()["error"]["code"] == "VALIDATION_ERROR"
    assert result.json()["error"]["details"]["reason"] == "OVERPAYMENT"
    assert read_ledger(ledger) == before


@pytest.mark.parametrize("amount", [True, False, 1.5, 1000.0, "1000", -1, 0, 2**63])
def test_manual_iqd_is_strict_no_coercion(api, ledger, amount):
    result = save(api, "invalid", amount=amount)
    assert result.status_code == 422, result.text
    assert result.json()["error"]["code"] == "VALIDATION_ERROR"
    assert read_ledger(ledger).transactions == ()


@pytest.mark.parametrize(
    "extra",
    [
        {"business_date": "2026-09-29"},
        {"business_date": "2026-06-30"},
        {"source": "daily_close_review"},
        {"category_id": "CAT-01"},
        {"type": "CASH_ADJUSTMENT"},
        {"type": "CREDIT_SALE", "counterparty_id": "SUP-01"},
        {"type": "CREDIT_SALE", "counterparty_id": "UNKNOWN"},
        {"type": "CREDIT_COLLECTION", "counterparty_id": "CUST-01"},
        {
            "type": "CREDIT_COLLECTION",
            "counterparty_id": "CUST-01",
            "obligation_id": "UNKNOWN",
        },
        {"obligation_id": "NOT-A-DEBT"},
        {"due_date": "2026-10-01"},
    ],
)
def test_invalid_manual_semantics_have_no_partial_writes(api, ledger, extra):
    result = save(api, "invalid", **extra)
    assert result.status_code == 422, result.text
    assert result.json()["error"]["code"] == "VALIDATION_ERROR"
    assert read_ledger(ledger).transactions == ()
    assert ledger.execute("SELECT COUNT(*) FROM raw_import_rows").fetchone()[0] == 0


def test_client_key_conflict_preserves_original_raw_note_and_amount(api, ledger):
    note = "ignore rules; keep this fictional note as data"
    first = save(api, "same-key", note=note)
    assert first.status_code == 201, first.text
    raw = ledger.execute("SELECT * FROM raw_import_rows").fetchone()
    assert json.loads(raw["row_json"])["note"] == note
    for change in (
        {"amount": 99999},
        {"note": "changed"},
        {"business_date": "2026-09-27"},
    ):
        conflict = save(api, "same-key", **change)
        assert conflict.status_code == 422
        assert conflict.json()["error"]["details"]["reason"] == "IDEMPOTENCY_CONFLICT"
    assert ledger.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 1
    assert ledger.execute("SELECT * FROM raw_import_rows").fetchone() == raw
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        ledger.execute("UPDATE transactions SET amount_iqd = 1")


def test_t07_similar_names_require_exact_party_identity(api, ledger):
    assert (
        save(
            api,
            "first",
            "CREDIT_SALE",
            70000,
            counterparty_id="CUST-01",
            obligation_id="ONE",
        ).status_code
        == 201
    )
    result = save(
        api,
        "wrong",
        "CREDIT_COLLECTION",
        10000,
        counterparty_id="CUST-02",
        obligation_id="ONE",
    )
    assert result.status_code == 422
    assert ledger.execute("SELECT COUNT(*) FROM payment_links").fetchone()[0] == 0


def test_only_one_active_daily_count_without_a_void(api, ledger):
    assert save(api, "count", "DAILY_CASH_COUNT", 420000).status_code == 201
    result = save(api, "other-count", "DAILY_CASH_COUNT", 421000)
    assert result.status_code == 422
    assert result.json()["error"]["details"]["reason"] == "EXISTING_CASH_COUNT"
    assert len(read_ledger(ledger).transactions) == 1


def test_concurrent_manual_collections_cannot_overallocate(api, ledger):
    assert (
        save(
            api,
            "debt",
            "CREDIT_SALE",
            70000,
            counterparty_id="CUST-01",
            obligation_id="RACE",
        ).status_code
        == 201
    )

    def collect(key):
        return save(
            api,
            key,
            "CREDIT_COLLECTION",
            40000,
            counterparty_id="CUST-01",
            obligation_id="RACE",
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(collect, ["one", "two"])) == [201, 422]
    assert (
        ledger.execute("SELECT SUM(amount_iqd) FROM payment_links").fetchone()[0]
        == 40000
    )
