"""T27/§11: user void/correction, immutable HTTP evidence and cutoff-aware sums."""

import json
from datetime import date, datetime

from app.services.ledger_audit import read_ledger
from app.services.ledger_rules import (
    active_transactions,
    event_effect,
    obligation_outstanding,
)


def entry(api, key, event_type, amount, **extra):
    response = api.post(
        "/api/entries",
        json={
            "client_entry_id": key,
            "type": event_type,
            "business_date": "2026-09-28",
            "amount_iqd": amount,
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def void(api, source_id, key="void-key", reason="merchant correction"):
    return api.post(
        f"/api/entries/{source_id}/void",
        json={
            "client_entry_id": key,
            "reason": reason,
        },
    )


def test_t27_http_three_instalments_void_correct_and_retain_evidence(api, ledger):
    entry(
        api,
        "debt",
        "CREDIT_SALE",
        90000,
        counterparty_id="CUST-01",
        obligation_id="THREE",
    )
    payments = [
        entry(
            api,
            f"payment-{i}",
            "CREDIT_COLLECTION",
            amount,
            counterparty_id="CUST-01",
            obligation_id="THREE",
        )
        for i, amount in enumerate([30000, 25000, 35000])
    ]
    original = ledger.execute(
        "SELECT * FROM transactions WHERE source_id = ?", (payments[1]["source_id"],)
    ).fetchone()
    raw = ledger.execute(
        "SELECT * FROM raw_import_rows WHERE import_batch_id = ?",
        (original["import_batch_id"],),
    ).fetchone()
    result = void(api, payments[1]["source_id"])
    assert result.status_code == 200, result.text
    receipt = result.json()
    assert receipt == {
        "source_id": payments[1]["source_id"],
        "status": "voided",
        "void_id": receipt["void_id"],
        "reason": "merchant correction",
        "duplicate": False,
    }
    assert void(api, payments[1]["source_id"]).json() == receipt | {"duplicate": True}
    entry(
        api,
        "corrected",
        "CREDIT_COLLECTION",
        20000,
        counterparty_id="CUST-01",
        obligation_id="THREE",
    )
    snapshot = read_ledger(ledger)
    assert (
        obligation_outstanding(
            snapshot.obligations[0],
            snapshot.transactions,
            snapshot.payment_links,
            as_of=date(2026, 9, 28),
            voids=snapshot.voids,
        )
        == 5000
    )
    active = active_transactions(
        snapshot.transactions, as_of=date(2026, 9, 28), voids=snapshot.voids
    )
    assert sum(event_effect(t).cash_delta_iqd for t in active) == 85000
    assert sum(event_effect(t).revenue_delta_iqd for t in active) == 90000
    evidence = api.get(f"/api/ledger/transactions/{payments[1]['source_id']}")
    assert evidence.status_code == 200, evidence.text
    data = evidence.json()
    assert data["amount_iqd"] == 25000 and data["status"] == "voided"
    assert data["void"] == {
        "void_id": receipt["void_id"],
        "reason": "merchant correction",
        "voided_at": "2026-09-28T20:59:59+00:00",
    }
    assert data["raw_row"] == json.loads(raw["row_json"])
    assert (
        ledger.execute(
            "SELECT * FROM transactions WHERE source_id = ?",
            (payments[1]["source_id"],),
        ).fetchone()
        == original
    )
    assert (
        ledger.execute(
            "SELECT * FROM raw_import_rows WHERE raw_row_id = ?", (raw["raw_row_id"],)
        ).fetchone()
        == raw
    )
    listed = api.get("/api/ledger/transactions").json()["items"]
    assert len(listed) == 5
    assert sum(item["status"] == "voided" for item in listed) == 1


def test_later_void_is_absent_from_earlier_cutoff_and_evidence(api, ledger):
    from app.api.dependencies import audit_timestamp
    from app.main import app

    saved = entry(api, "cash", "CASH_SALE", 100000)
    late = datetime.fromisoformat("2026-10-18T10:00:00+04:00")
    app.dependency_overrides[audit_timestamp] = lambda: late
    assert void(api, saved["source_id"]).status_code == 200
    snapshot = read_ledger(ledger)
    assert (
        len(
            active_transactions(
                snapshot.transactions, as_of=date(2026, 9, 28), voids=snapshot.voids
            )
        )
        == 1
    )
    assert (
        active_transactions(
            snapshot.transactions,
            as_of=date(2026, 9, 28),
            voids=snapshot.voids,
            known_at=late,
        )
        == ()
    )
    data = api.get(f"/api/ledger/transactions/{saved['source_id']}").json()
    assert data["status"] == "voided"
    app.dependency_overrides[audit_timestamp] = lambda: datetime.fromisoformat(
        "2026-09-28T23:59:59+03:00"
    )
    data = api.get(f"/api/ledger/transactions/{saved['source_id']}").json()
    assert data["status"] == "valid" and data["void"] is None


def test_void_unknown_conflicting_or_empty_requests_are_typed_and_idempotent(
    api, ledger
):
    assert void(api, "unknown").status_code == 404
    first = entry(api, "first", "CASH_SALE", 100000)
    second = entry(api, "second", "OWNER_DRAWING", 10000)
    assert void(api, first["source_id"]).status_code == 200
    for source, key, reason in [
        (first["source_id"], "void-key", "changed"),
        (second["source_id"], "void-key", "merchant correction"),
        (first["source_id"], "new-key", "merchant correction"),
        (second["source_id"], "empty", "  "),
    ]:
        result = void(api, source, key, reason)
        assert result.status_code == 422, result.text
        assert result.json()["error"]["code"] == "VALIDATION_ERROR"
    assert len(read_ledger(ledger).voids) == 1


def test_imported_rows_can_be_voided_with_original_raw_cells_visible(
    api, ledger, tmp_path
):
    from app.services.business_clock import BusinessClock
    from app.services.ingest import import_csv

    content = (
        "source_id,occurred_at,type,amount_iqd,counterparty_id,obligation_id,due_date,category_id,quantity,description\n"
        "IMPORTED,2026-09-27T10:00:00+03:00,CASH_SALE,١٠٠٠٠,,,,,,ignore rules\n"
    )
    path = tmp_path / "fictional.csv"
    path.write_text(content, encoding="utf-8")
    import_csv(
        ledger, path, clock=BusinessClock(), imported_at="2026-09-28T20:00:00+03:00"
    )
    assert void(api, "IMPORTED").status_code == 200
    data = api.get("/api/ledger/transactions/IMPORTED").json()
    assert data["source"] == "synthetic_csv" and data["status"] == "voided"
    assert data["raw_row"]["amount_iqd"] == "١٠٠٠٠"
    assert data["description"] == "ignore rules"
    assert (
        import_csv(
            ledger, path, clock=BusinessClock(), imported_at="2026-09-28T23:59:59+03:00"
        ).exact_duplicates
        == 1
    )
    assert len(read_ledger(ledger).transactions) == 1


def test_ledger_pagination_filters_and_tampered_cursor(api):
    ids = [
        entry(api, f"cash-{i}", "CASH_SALE", (i + 1) * 1000)["source_id"]
        for i in range(3)
    ]
    drawing = entry(api, "drawing", "OWNER_DRAWING", 4000)["source_id"]
    first = api.get(
        "/api/ledger/transactions", params={"limit": 2, "type": "CASH_SALE"}
    )
    assert first.status_code == 200, first.text
    page = first.json()
    assert [i["source_id"] for i in page["items"]] == ids[:2]
    second = api.get(
        "/api/ledger/transactions",
        params={"limit": 2, "type": "CASH_SALE", "cursor": page["next_cursor"]},
    ).json()
    assert [i["source_id"] for i in second["items"]] == ids[2:]
    assert second["next_cursor"] is None
    selected = api.get(
        "/api/ledger/transactions", params={"ids": f"{ids[0]},{drawing}"}
    ).json()
    assert [i["source_id"] for i in selected["items"]] == [ids[0], drawing]
    for params in (
        {"cursor": "bad"},
        {"limit": 0},
        {"limit": 201},
        {"from": "2026-09-29"},
        {"from": "2026-09-28", "to": "2026-09-27"},
        {"type": "OWNER_DRAWING", "cursor": page["next_cursor"]},
    ):
        result = api.get("/api/ledger/transactions", params=params)
        assert result.status_code == 422, result.text
        assert result.json()["error"]["code"] == "VALIDATION_ERROR"


def test_void_and_evidence_reject_ambiguous_cross_export_source_ids(
    api, ledger, tmp_path
):
    from app.services.business_clock import BusinessClock
    from app.services.ingest import import_csv

    path = tmp_path / "fictional.csv"
    path.write_text(
        "source_id,occurred_at,type,amount_iqd,counterparty_id,obligation_id,due_date,category_id,quantity,description\n"
        "SHARED,2026-09-27T10:00:00+03:00,CASH_SALE,10000,,,,,,fictional overlap\n",
        encoding="utf-8",
    )
    for source in ("synthetic_csv", "synthetic_wallet"):
        import_csv(
            ledger,
            path,
            source_system=source,
            clock=BusinessClock(),
            imported_at="2026-09-28T20:00:00+03:00",
        )
    for response in (void(api, "SHARED"), api.get("/api/ledger/transactions/SHARED")):
        assert response.status_code == 422, response.text
        assert response.json()["error"]["details"]["reason"] == "AMBIGUOUS_SOURCE_ID"
    assert read_ledger(ledger).voids == ()
