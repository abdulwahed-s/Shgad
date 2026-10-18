"""Revised T22/T28/T34: consecutive counts and merchant-only signed review."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

import pytest

from app.services.ledger_audit import read_ledger
from app.services.ledger_rules import daily_close, event_effect, recorded_cash_sales


def setup_t22(api, *, closing=445000):
    source_ids = []
    for key, event, amount, extra in [
        ("previous", "DAILY_CASH_COUNT", 300000, {"business_date": "2026-09-27"}),
        (
            "debt",
            "CREDIT_SALE",
            70000,
            {"counterparty_id": "CUST-01", "obligation_id": "R"},
        ),
        ("cash", "CASH_SALE", 120000, {}),
        (
            "collection",
            "CREDIT_COLLECTION",
            30000,
            {"counterparty_id": "CUST-01", "obligation_id": "R"},
        ),
        ("expense", "OPERATING_EXPENSE", 20000, {}),
        ("drawing", "OWNER_DRAWING", 10000, {}),
        ("closing", "DAILY_CASH_COUNT", closing, {}),
    ]:
        response = api.post(
            "/api/entries",
            json={
                "client_entry_id": key,
                "type": event,
                "amount_iqd": amount,
                "business_date": "2026-09-28",
                **extra,
            },
        )
        assert response.status_code == 201, response.text
        source_ids.append(response.json()["source_id"])
    return source_ids


def resolve(api, key="review", resolution="capital_injection", amount=25000):
    return api.post(
        "/api/daily-close/2026-09-28/resolve",
        json={
            "client_entry_id": key,
            "resolution": resolution,
            "amount_iqd": amount,
            "note": "fictional merchant review",
        },
    )


def test_t22_t28_daily_close_capital_review_is_not_sales_or_double_subtracted(
    api, ledger
):
    sources = setup_t22(api)
    result = api.get("/api/daily-close/2026-09-28")
    assert result.status_code == 200, result.text
    before = result.json()
    assert before["date"] == "2026-09-28"
    for key, amount in {
        "count": 445000,
        "previous_count": 300000,
        "expected_close": 420000,
        "unexplained_difference": 25000,
        "remaining_difference": 25000,
    }.items():
        assert before[key]["amount_iqd"] == amount
        assert before[key]["source_ids"] and before[key]["formula"]
    assert before["unexplained_difference"]["kind"] == "flagged"
    assert before["resolved"] == []
    assert set(before["rows"]) == set(sources) - {sources[1]}
    response = resolve(api)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["duplicate"] is False
    assert body["daily_close"]["remaining_difference"]["amount_iqd"] == 0
    assert body["daily_close"]["unexplained_difference"]["amount_iqd"] == 0
    assert body["daily_close"]["expected_close"]["amount_iqd"] == 445000
    assert len(body["daily_close"]["resolved"]) == 1
    row = api.get(f"/api/ledger/transactions/{body['entry']['source_id']}").json()
    assert row["source"] == "daily_close_review" and row["type"] == "CAPITAL_INJECTION"
    assert row["category_id"] is None and row["quantity"] is None
    snapshot = read_ledger(ledger)
    assert recorded_cash_sales(snapshot.transactions, as_of=date(2026, 9, 28)) == 120000
    assert (
        sum(event_effect(t).revenue_delta_iqd for t in snapshot.transactions) == 190000
    )
    assert (
        sum(event_effect(t).operating_expenses_iqd for t in snapshot.transactions)
        == 20000
    )
    again = resolve(api).json()
    assert (
        again["duplicate"] is True and again["entry"]["source_id"] == row["source_id"]
    )
    assert again["daily_close"] == body["daily_close"]
    assert len(read_ledger(ledger).transactions) == 8


@pytest.mark.parametrize(
    "resolution,amount,code",
    [
        ("expense_unrecorded", 25000, "DIFFERENCE_SIGN_MISMATCH"),
        ("owner_drawing_unrecorded", 1, "DIFFERENCE_SIGN_MISMATCH"),
        ("capital_injection", 25001, "DIFFERENCE_EXCEEDED"),
        ("capital_injection", None, "VALIDATION_ERROR"),
        ("cash_sale_unitemized", 1.5, "VALIDATION_ERROR"),
        ("leave_unexplained", 0, "VALIDATION_ERROR"),
    ],
)
def test_t34_invalid_review_never_changes_financial_rows(
    api, ledger, resolution, amount, code
):
    setup_t22(api)
    before = read_ledger(ledger)
    response = resolve(api, resolution=resolution, amount=amount)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == code
    assert read_ledger(ledger) == before


def test_partial_negative_resolutions_and_leave_unexplained(api, ledger):
    setup_t22(api, closing=400000)
    response = resolve(api, resolution="leave_unexplained", amount=None)
    assert response.status_code == 200, response.text
    assert response.json()["entry"] is None
    assert (
        response.json()["daily_close"]["remaining_difference"]["amount_iqd"] == -20000
    )
    assert len(read_ledger(ledger).transactions) == 7
    assert (
        resolve(api, resolution="leave_unexplained", amount=None).json()["duplicate"]
        is True
    )
    assert (
        resolve(
            api, key="draw", resolution="owner_drawing_unrecorded", amount=8000
        ).json()["daily_close"]["remaining_difference"]["amount_iqd"]
        == -12000
    )
    assert (
        resolve(api, key="cost", resolution="expense_unrecorded", amount=12000).json()[
            "daily_close"
        ]["remaining_difference"]["amount_iqd"]
        == 0
    )
    snapshot = read_ledger(ledger)
    assert (
        sum(event_effect(t).operating_expenses_iqd for t in snapshot.transactions)
        == 32000
    )
    assert (
        sum(event_effect(t).owner_drawings_iqd for t in snapshot.transactions) == 18000
    )


def test_missing_counts_are_missing_and_review_requires_consecutive_days(api, ledger):
    response = api.get("/api/daily-close/2026-09-28")
    assert response.status_code == 200, response.text
    for key in (
        "count",
        "previous_count",
        "expected_close",
        "unexplained_difference",
        "remaining_difference",
    ):
        assert response.json()[key]["amount_iqd"] is None
        assert response.json()[key]["kind"] == "missing"
    assert resolve(api).json()["error"]["code"] == "MISSING_COUNT"
    for day in ("2026-09-26", "2026-09-28"):
        assert (
            api.post(
                "/api/entries",
                json={
                    "client_entry_id": day,
                    "type": "DAILY_CASH_COUNT",
                    "business_date": day,
                    "amount_iqd": 300000,
                },
            ).status_code
            == 201
        )
    body = api.get("/api/daily-close/2026-09-28").json()
    assert body["count"]["amount_iqd"] == 300000
    assert body["previous_count"]["kind"] == "missing"
    assert body["remaining_difference"]["amount_iqd"] is None
    assert resolve(api).json()["error"]["code"] == "MISSING_COUNT"
    assert read_ledger(ledger).reviews == ()


def test_review_void_restores_difference_without_erasing_history(api, ledger):
    setup_t22(api)
    created = resolve(api).json()["entry"]
    response = api.post(
        f"/api/entries/{created['source_id']}/void",
        json={
            "client_entry_id": "undo-review",
            "reason": "merchant changed explanation",
        },
    )
    assert response.status_code == 200, response.text
    body = api.get("/api/daily-close/2026-09-28").json()
    assert body["remaining_difference"]["amount_iqd"] == 25000
    assert body["resolved"][0]["entry"]["status"] == "voided"
    assert (
        resolve(api, key="replacement", resolution="cash_sale_unitemized").json()[
            "daily_close"
        ]["remaining_difference"]["amount_iqd"]
        == 0
    )
    snapshot = read_ledger(ledger)
    assert (
        recorded_cash_sales(
            snapshot.transactions, as_of=date(2026, 9, 28), voids=snapshot.voids
        )
        == 145000
    )


def test_late_review_preserves_earlier_cutoff(api, ledger):
    from app.api.dependencies import audit_timestamp
    from app.main import app

    setup_t22(api)
    later = datetime.fromisoformat("2026-10-18T10:00:00+04:00")
    app.dependency_overrides[audit_timestamp] = lambda: later
    assert resolve(api).status_code == 200
    snapshot = read_ledger(ledger)
    assert (
        daily_close(
            snapshot.transactions, business_date=date(2026, 9, 28)
        ).unexplained_difference_iqd
        == 25000
    )
    assert (
        api.get("/api/daily-close/2026-09-28").json()["remaining_difference"][
            "amount_iqd"
        ]
        == 0
    )


def test_concurrent_reviews_and_conflicting_keys_cannot_explain_twice(api, ledger):
    setup_t22(api)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda key: resolve(api, key=key), ["one", "two"]))
    assert sorted(r.status_code for r in responses) == [200, 422]
    assert len(read_ledger(ledger).reviews) == 1
    key = "one" if responses[0].status_code == 200 else "two"
    response = resolve(api, key=key, amount=1)
    assert response.status_code == 422
    assert response.json()["error"]["details"]["reason"] == "IDEMPOTENCY_CONFLICT"


def test_daily_close_rejects_unobserved_dates(api):
    for day in ("2026-06-30", "2026-09-29", "bad-date"):
        response = api.get(f"/api/daily-close/{day}")
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_client_key_collision_across_entry_and_review_is_typed(api, ledger):
    setup_t22(api)
    before = read_ledger(ledger)
    response = resolve(api, key="cash")
    assert response.status_code == 422, response.text
    assert response.json()["error"]["details"]["reason"] == "IDEMPOTENCY_CONFLICT"
    assert read_ledger(ledger) == before
    assert (
        resolve(
            api, key="leave", resolution="leave_unexplained", amount=None
        ).status_code
        == 200
    )
    response = api.post(
        "/api/entries",
        json={
            "client_entry_id": "leave",
            "type": "CASH_SALE",
            "amount_iqd": 1000,
            "business_date": "2026-09-28",
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["details"]["reason"] == "IDEMPOTENCY_CONFLICT"


def test_daily_close_sql_snapshot_excludes_future_and_later_knowledge(
    api, ledger, insert_event
):
    setup_t22(api)
    insert_event(
        source_id="FUTURE-POISON",
        occurred_at="2026-09-29T10:00:00+03:00",
        amount_iqd=999999,
    )
    ledger.commit()
    snapshot = read_ledger(ledger, as_of=date(2026, 9, 28))
    assert len(snapshot.transactions) == 7
    assert all(t.business_date <= date(2026, 9, 28) for t in snapshot.transactions)
    body = api.get("/api/daily-close/2026-09-28").json()
    assert body["remaining_difference"]["amount_iqd"] == 25000
