"""D28/FINANCIAL_RULES §2/§11: correction time and immutable source lineage."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

import pytest

from app.services.ledger_audit import read_ledger
from app.services.ledger_rules import cash_on_hand, obligation_outstanding


def current_audit():
    from app.api.dependencies import audit_timestamp
    from app.main import app

    now = datetime.fromisoformat("2026-10-18T10:00:00+04:00")
    app.dependency_overrides[audit_timestamp] = lambda: now
    return now


def seed_precount_collection(ledger, insert_event, *, count_time="21:00:00"):
    origin = insert_event(
        source_id="SALE",
        type="CREDIT_SALE",
        amount_iqd=90000,
        counterparty_id="CUST-01",
        obligation_id="R",
        occurred_at="2026-09-26T12:00:00+03:00",
    )
    ledger.execute(
        "INSERT INTO obligations VALUES (?, ?, ?, ?, ?, ?)",
        ("R", "receivable", origin.transaction_id, "CUST-01", 90000, None),
    )
    payment = insert_event(
        source_id="COLLECTION",
        type="CREDIT_COLLECTION",
        amount_iqd=25000,
        counterparty_id="CUST-01",
        obligation_id="R",
        occurred_at="2026-09-28T12:00:00+03:00",
    )
    ledger.execute(
        "INSERT INTO payment_links VALUES (?, ?, ?, ?, ?, ?)",
        (
            "LINK",
            payment.transaction_id,
            "R",
            25000,
            "definite",
            "2026-09-28T12:00:00+00:00",
        ),
    )
    insert_event(
        source_id="COUNT",
        type="DAILY_CASH_COUNT",
        amount_iqd=420000,
        occurred_at=f"2026-09-28T{count_time}+03:00",
    )
    ledger.commit()
    return payment


def correct(api, key="replacement", **extra):
    return api.post(
        "/api/entries",
        json={
            "client_entry_id": key,
            "type": "CREDIT_COLLECTION",
            "business_date": "2026-09-28",
            "amount_iqd": 20000,
            "counterparty_id": "CUST-01",
            "obligation_id": "R",
            "correction_of_source_id": "COLLECTION",
            **extra,
        },
    )


def test_correction_of_precount_collection_restores_debt_without_adding_cash_twice(
    api, ledger, insert_event
):
    original = seed_precount_collection(ledger, insert_event)
    now = current_audit()
    assert (
        api.post(
            "/api/entries/COLLECTION/void",
            json={
                "client_entry_id": "undo",
                "reason": "merchant correction",
            },
        ).status_code
        == 200
    )
    result = correct(api)
    assert result.status_code == 201, result.text
    snapshot = read_ledger(ledger)
    replacement = next(
        t for t in snapshot.transactions if t.source_id == result.json()["source_id"]
    )
    assert replacement.occurred_at == original.occurred_at
    assert replacement.recorded_at == now
    assert (
        cash_on_hand(
            snapshot.transactions,
            as_of=date(2026, 9, 28),
            voids=snapshot.voids,
            known_at=now,
        ).amount_iqd
        == 420000
    )
    assert (
        obligation_outstanding(
            snapshot.obligations[0],
            snapshot.transactions,
            snapshot.payment_links,
            as_of=date(2026, 9, 28),
            voids=snapshot.voids,
            known_at=now,
        )
        == 70000
    )
    assert (
        obligation_outstanding(
            snapshot.obligations[0],
            snapshot.transactions,
            snapshot.payment_links,
            as_of=date(2026, 9, 28),
            voids=snapshot.voids,
        )
        == 65000
    )
    detail = api.get(f"/api/ledger/transactions/{replacement.source_id}").json()
    assert detail["correction_of_source_id"] == "COLLECTION"
    assert detail["raw_row"]["correction_of_source_id"] == "COLLECTION"
    assert correct(api).json() == result.json() | {"duplicate": True}
    assert ledger.execute("SELECT COUNT(*) FROM entry_corrections").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        ledger.execute("DELETE FROM entry_corrections")


def test_correction_requires_voided_original_same_date_and_one_replacement(
    api, ledger, insert_event
):
    seed_precount_collection(ledger, insert_event)
    current_audit()
    assert correct(api).status_code == 422
    assert (
        api.post(
            "/api/entries/COLLECTION/void",
            json={
                "client_entry_id": "undo",
                "reason": "merchant correction",
            },
        ).status_code
        == 200
    )
    assert correct(api, business_date="2026-09-27").status_code == 422
    assert correct(api, correction_of_source_id="UNKNOWN").status_code == 404
    first = correct(api)
    assert first.status_code == 201, first.text
    duplicate_parent = correct(api, key="another-replacement")
    assert duplicate_parent.status_code == 422, duplicate_parent.text
    assert duplicate_parent.json()["error"]["details"]["reason"] == "ALREADY_CORRECTED"
    assert len(read_ledger(ledger).transactions) == 4


def test_concurrent_corrections_cannot_replace_original_twice(
    api, ledger, insert_event
):
    seed_precount_collection(ledger, insert_event)
    current_audit()
    api.post(
        "/api/entries/COLLECTION/void",
        json={"client_entry_id": "undo", "reason": "correction"},
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda key: correct(api, key=key), ["one", "two"]))
    assert sorted(r.status_code for r in responses) == [201, 422]
    assert ledger.execute("SELECT COUNT(*) FROM entry_corrections").fetchone()[0] == 1


def test_missing_optional_correction_reference_keeps_legacy_client_idempotency(
    api, ledger
):
    request = {
        "client_entry_id": "legacy",
        "type": "CASH_SALE",
        "business_date": "2026-09-28",
        "amount_iqd": 1000,
    }
    from app.db.records import insert_record
    from app.schemas.ledger import ImportBatch, RawImportRow, Transaction

    old = request | {
        "counterparty_id": None,
        "obligation_id": None,
        "due_date": None,
        "note": None,
    }
    with ledger:
        insert_record(
            ledger,
            ImportBatch(
                import_batch_id="LEGACY",
                source_system="synthetic_entry",
                file_sha256="a" * 64,
                imported_at="2026-09-28T23:59:59+03:00",
                row_count=1,
                accepted_count=1,
                status="completed",
            ),
        )
        insert_record(
            ledger,
            RawImportRow(
                raw_row_id="LEGACY-RAW",
                import_batch_id="LEGACY",
                source_row=1,
                row_json=json.dumps(old, ensure_ascii=False, sort_keys=True),
                status="accepted",
            ),
        )
        insert_record(
            ledger,
            Transaction(
                transaction_id="LEGACY",
                source_id="LEGACY",
                source_system="synthetic_entry",
                source="manual_entry",
                client_entry_id="legacy",
                source_row=1,
                import_batch_id="LEGACY",
                occurred_at="2026-09-28T23:59:59+03:00",
                type="CASH_SALE",
                amount_iqd=1000,
                idempotency_key="manual_entry:legacy",
            ),
        )
    again = api.post("/api/entries", json=request)
    assert again.status_code == 200, again.text
    assert again.json() == {
        "transaction_id": "LEGACY",
        "source_id": "LEGACY",
        "duplicate": True,
    }


def test_correction_keeps_original_time_even_after_end_of_day_count(
    api, ledger, insert_event
):
    original = seed_precount_collection(
        ledger, insert_event, count_time="23:59:59.999999"
    )
    current_audit()
    assert (
        api.post(
            "/api/entries/COLLECTION/void",
            json={
                "client_entry_id": "undo",
                "reason": "merchant correction",
            },
        ).status_code
        == 200
    )
    response = correct(api)
    assert response.status_code == 201, response.text
    row = next(
        t
        for t in read_ledger(ledger).transactions
        if t.source_id == response.json()["source_id"]
    )
    assert row.occurred_at == original.occurred_at
