"""T04/T16/T20: real multipart uploads, receipts and deterministic ledger effects."""

import csv
import io
from datetime import datetime

import pytest

from app.services.ledger_audit import read_ledger
from app.services.ledger_rules import event_effect, obligation_outstanding

FIELDS = (
    "source_id,occurred_at,type,amount_iqd,counterparty_id,obligation_id,"
    "due_date,category_id,quantity,description"
).split(",")


def csv_bytes(rows, *, extra=()):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS + list(extra))
    writer.writeheader()
    for index, row in enumerate(rows, 1):
        writer.writerow(
            dict.fromkeys(FIELDS, "")
            | {
                "source_id": f"UPLOAD-{index}",
                "occurred_at": "2026-09-27T12:00:00+03:00",
                "type": "CASH_SALE",
                "amount_iqd": "100000",
                "description": "fictional upload",
            }
            | row
        )
    return stream.getvalue().encode("utf-8-sig")


def upload(api, rows, **kwargs):
    return api.post(
        "/api/imports/csv",
        files={"file": ("fictional.csv", csv_bytes(rows, **kwargs), "text/csv")},
    )


def test_t04_t20_http_import_receipt_replay_and_cash_credit_semantics(api, ledger):
    rows = [
        {},
        {
            "type": "CREDIT_SALE",
            "counterparty_id": "CUST-01",
            "obligation_id": "DEBT",
            "amount_iqd": "70000",
            "due_date": "2026-09-30",
        },
        {
            "type": "CREDIT_COLLECTION",
            "counterparty_id": "CUST-01",
            "obligation_id": "DEBT",
            "amount_iqd": "30000",
        },
        {"type": "OWNER_DRAWING", "amount_iqd": "5000"},
        {"type": "CAPITAL_INJECTION", "amount_iqd": "8000"},
    ]
    first = upload(api, rows)
    assert first.status_code == 200, first.text
    receipt = first.json()
    assert receipt == {
        "batch_id": receipt["batch_id"],
        "accepted": 5,
        "rejected": 0,
        "exact_duplicates": 0,
        "flagged_for_review": 0,
        "errors": [],
    }
    assert api.get(f"/api/imports/{receipt['batch_id']}").json() == receipt
    snapshot = read_ledger(ledger)
    effects = [event_effect(row) for row in snapshot.transactions]
    assert sum(e.cash_delta_iqd for e in effects) == 133000
    assert sum(e.revenue_delta_iqd for e in effects) == 170000
    assert (
        obligation_outstanding(
            snapshot.obligations[0],
            snapshot.transactions,
            snapshot.payment_links,
            as_of=datetime.fromisoformat("2026-09-28").date(),
        )
        == 40000
    )
    replay = upload(api, rows)
    assert replay.status_code == 200
    assert replay.json() == receipt | {"accepted": 0, "exact_duplicates": 5}
    assert read_ledger(ledger) == snapshot
    assert api.get(f"/api/imports/{receipt['batch_id']}").json() == receipt


def test_t16_http_quarantine_and_disjoint_batch_counts(api, ledger):
    result = upload(
        api,
        [
            {},
            {"source_id": "UPLOAD-1"},
            {"amount_iqd": "-1"},
            {"type": "CREDIT_COLLECTION", "counterparty_id": "CUST-01"},
        ],
    )
    assert result.status_code == 200, result.text
    receipt = result.json()
    assert [
        receipt[k]
        for k in ("accepted", "exact_duplicates", "rejected", "flagged_for_review")
    ] == [1, 1, 1, 1]
    assert receipt["errors"] == [
        {"row": 3, "code": "INVALID_AMOUNT", "message": "INVALID_AMOUNT"}
    ]
    assert api.get(f"/api/imports/{receipt['batch_id']}").json() == receipt
    assert ledger.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 2


@pytest.mark.parametrize(
    "filename,content,reason",
    [
        ("bad.txt", b"bad", "FILE_TYPE"),
        ("bad.csv", b"\xff", "INVALID_FILE"),
        ("bad.csv", b"source_id,source_id\na,a\n", "CSV_COLUMNS"),
        ("large.csv", b"x" * (5 * 1024 * 1024 + 1), "FILE_SIZE"),
    ],
    ids=["extension", "encoding", "columns", "size"],
)
def test_invalid_upload_is_typed_without_writes(api, ledger, filename, content, reason):
    result = api.post(
        "/api/imports/csv", files={"file": (filename, content, "text/csv")}
    )
    assert result.status_code == 422, result.text
    assert result.json() == {
        "error": {
            "code": "IMPORT_REJECTED",
            "message_key": "error_import_rejected",
            "details": {"reason": reason},
        }
    }
    assert ledger.execute("SELECT COUNT(*) FROM raw_import_rows").fetchone()[0] == 0


def test_unknown_batch_and_missing_file_use_contract_errors(api):
    result = api.get("/api/imports/unknown")
    assert result.status_code == 404
    assert result.json()["error"]["code"] == "NOT_FOUND"
    result = api.post("/api/imports/csv")
    assert result.status_code == 422
    assert result.json()["error"]["code"] == "VALIDATION_ERROR"


def test_http_failure_rolls_back_and_hides_database_details(api, ledger):
    ledger.execute("""CREATE TRIGGER synthetic_failure BEFORE INSERT ON transactions
        WHEN NEW.source_id = 'FAIL'
        BEGIN SELECT RAISE(ABORT, 'private synthetic failure'); END""")
    ledger.commit()
    result = upload(api, [{}, {"source_id": "FAIL"}])
    assert result.status_code == 500
    assert result.json() == {
        "error": {"code": "INTERNAL", "message_key": "error_internal", "details": {}}
    }
    assert ledger.execute("SELECT COUNT(*) FROM raw_import_rows").fetchone()[0] == 0
    assert ledger.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0


def test_late_upload_audit_does_not_fabricate_historical_knowledge(api, ledger):
    from app.api.dependencies import audit_timestamp
    from app.db.forecast_repository import read_forecast_snapshot
    from app.main import app
    from app.services.business_clock import BusinessClock

    audit = datetime.fromisoformat("2026-10-18T10:00:00+04:00")
    app.dependency_overrides[audit_timestamp] = lambda: audit
    result = upload(api, [{}])
    assert result.status_code == 200, result.text
    assert result.json()["accepted"] == 1
    row = read_ledger(ledger).transactions[0]
    assert row.recorded_at == audit
    assert row.business_date.isoformat() == "2026-09-27"
    assert read_forecast_snapshot(ledger, clock=BusinessClock()).transactions == ()
