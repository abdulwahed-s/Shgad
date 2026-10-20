"""T11/T21/T23/T28: recorded-sales coverage and deterministic weekly figures."""

from datetime import date, datetime

import pytest

from app.agents.tool_registry import invoke
from app.services.business_clock import BusinessClock

CLOCK = BusinessClock(date(2026, 9, 28))
KNOWN = datetime.fromisoformat("2026-09-28T23:59:59+03:00")


@pytest.fixture
def priced_shop(ledger, insert_event, debt_factory):
    insert_event(
        source_id="CASH-PRICED", amount_iqd=80000, category_id="CAT-01", quantity=20
    )
    credit = debt_factory("CREDIT-UNPRICED", 10000, "2026-09-30")
    insert_event(source_id="CASH-UNPRICED", amount_iqd=10000)
    insert_event(source_id="EXPENSE", type="OPERATING_EXPENSE", amount_iqd=5000)
    insert_event(source_id="DRAWING", type="OWNER_DRAWING", amount_iqd=99000)
    insert_event(source_id="CAPITAL", type="CAPITAL_INJECTION", amount_iqd=100000)
    insert_event(
        source_id="PREVIOUS",
        type="DAILY_CASH_COUNT",
        amount_iqd=300000,
        occurred_at="2026-09-27T21:00:00+03:00",
    )
    insert_event(
        source_id="CLOSING",
        type="DAILY_CASH_COUNT",
        amount_iqd=411000,
        occurred_at="2026-09-28T21:00:00+03:00",
    )
    ledger.commit()
    return credit


def test_t23_margin_recorded_coverage_unpriced_credit_gap_drawings_and_capital(
    api, priced_shop
):
    response = api.get("/api/reports/margin?period=today")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["gross_margin"]["amount_iqd"] == 60000
    assert body["gross_margin"]["label_key"] == "estimated_gross_margin"
    assert body["coverage_pct"] == 80 and body["unpriced_sales_count"] == 2
    assert body["after_recorded_expenses"]["amount_iqd"] == 55000
    assert body["cost_of_goods"]["amount_iqd"] == 20000
    assert body["price_basis"][0]["buy_price"]["amount_iqd"] == 1000
    assert body["unexplained_difference_excluded"] is True
    assert body["note_key"] == "margin_excludes_unrecorded_costs"
    assert {"CASH-PRICED", "CAT-01"} <= set(body["gross_margin"]["source_ids"])
    assert "DRAWING" not in body["after_recorded_expenses"]["source_ids"]
    assert "CAPITAL" not in body["after_recorded_expenses"]["source_ids"]


def test_t11_weekly_known_totals_and_threshold(api, priced_shop):
    response = api.get("/api/reports/weekly?week=current")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["range"] == {
        "start": "2026-09-26",
        "end": "2026-09-28",
        "partial": True,
    }
    for key, value in {
        "cash_sales": 90000,
        "credit_sales": 10000,
        "collections": 0,
        "supplier_payments": 0,
        "operating_expenses": 5000,
        "owner_drawings": 99000,
        "capital_injections": 100000,
        "outstanding_receivables": 10000,
    }.items():
        assert body[key]["amount_iqd"] == value
    assert body["unexplained_cash_difference"]["kind"] == "missing"
    assert body["gross_margin"]["shown"] is True
    assert body["gross_margin"]["margin"]["amount_iqd"] == 60000


def test_t23_below_threshold_hides_weekly_margin_without_hiding_coverage(
    api, ledger, priced_shop, insert_event
):
    insert_event(source_id="MORE-UNPRICED", amount_iqd=1)
    ledger.commit()
    body = api.get("/api/reports/weekly").json()["gross_margin"]
    assert body["coverage_pct"] == 79
    assert body["shown"] is False and body["margin"]["kind"] == "missing"
    assert body["margin"]["amount_iqd"] is None
    assert (
        api.get("/api/reports/margin?period=today").json()["gross_margin"]["amount_iqd"]
        == 60000
    )


def test_t23_no_priced_sales_typed_failure_and_no_sales_coverage_unavailable(
    api, ledger, insert_event
):
    response = api.get("/api/reports/margin?period=today")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MISSING_COSTS"
    weekly = api.get("/api/reports/weekly").json()["gross_margin"]
    assert weekly["coverage_pct"] is None and weekly["margin"]["amount_iqd"] is None
    insert_event()
    ledger.commit()
    response = api.get("/api/reports/margin?period=today")
    assert response.status_code == 422
    result = invoke(
        "get_margin",
        {"period": "today"},
        connection=ledger,
        clock=CLOCK,
        known_at=KNOWN,
    )
    assert not result.ok and result.error.code == "MISSING_COSTS" and not result.figures


def test_t23_margin_tool_has_coverage_and_count_evidence(ledger, priced_shop):
    ledger.execute("PRAGMA query_only=ON")
    result = invoke(
        "get_margin",
        {"period": "today"},
        connection=ledger,
        clock=CLOCK,
        known_at=KNOWN,
    )
    assert result.ok
    assert result.result["gross_margin"]["amount_iqd"] == 60000
    metrics = {m.key: m for m in result.metrics}
    assert metrics["coverage_pct"].value == 80
    assert metrics["coverage_pct"].unit == "percent"
    assert set(metrics["coverage_pct"].source_ids) == {
        "CASH-PRICED",
        "CASH-UNPRICED",
        "CREDIT-UNPRICED",
    }
    assert metrics["unpriced_sales_count"].value == 2


def test_voided_sales_and_expenses_excluded_with_current_and_prior_knowledge(
    api, ledger, priced_shop
):
    assert (
        api.post(
            "/api/entries/EXPENSE/void",
            json={"client_entry_id": "ve", "reason": "fictional"},
        ).status_code
        == 200
    )
    assert (
        api.get("/api/reports/margin?period=today").json()["after_recorded_expenses"][
            "amount_iqd"
        ]
        == 60000
    )
    assert (
        api.post(
            "/api/entries/CASH-PRICED/void",
            json={"client_entry_id": "vs", "reason": "fictional"},
        ).status_code
        == 200
    )
    assert api.get("/api/reports/margin?period=today").status_code == 422
    prior = invoke(
        "get_margin",
        {"period": "today"},
        connection=ledger,
        clock=CLOCK,
        known_at=datetime.fromisoformat("2026-09-28T22:00:00+03:00"),
    )
    assert prior.ok and prior.result["after_recorded_expenses"]["amount_iqd"] == 55000


@pytest.mark.parametrize(
    "url",
    [
        "/api/reports/weekly?week=bad",
        "/api/reports/weekly?week=2026-10-10",
        "/api/reports/margin?period=next_n_days:7",
        "/api/reports/margin?from=2026-09-29&to=2026-09-30",
        "/api/reports/margin?from=2026-09-28",
    ],
)
def test_report_bad_or_unavailable_ranges_never_guess(api, url):
    response = api.get(url)
    assert response.status_code in (404, 422)
    assert response.json()["error"]["code"] in ("NOT_FOUND", "VALIDATION_ERROR")


def test_margin_loss_zero_buy_price_and_integer_percent(api, ledger, insert_event):
    ledger.execute(
        "INSERT INTO categories VALUES ('FREE', 'fictional free cost', 0, 1)"
    )
    insert_event(source_id="LOSS", amount_iqd=1, category_id="CAT-01", quantity=3)
    insert_event(source_id="FREE", amount_iqd=2, category_id="FREE", quantity=2)
    insert_event(source_id="UNPRICED", amount_iqd=1)
    ledger.commit()
    body = api.get("/api/reports/margin?period=today").json()
    assert body["gross_margin"]["amount_iqd"] == -2997
    assert body["coverage_pct"] == 75
    assert body["cost_of_goods"]["amount_iqd"] == 3000


def test_weekly_coverage_threshold_is_configurable(api, ledger, insert_event):
    from app.config import Settings, get_settings
    from app.main import app

    insert_event(amount_iqd=75000, category_id="CAT-01", quantity=10)
    insert_event(amount_iqd=25000)
    ledger.commit()
    assert not api.get("/api/reports/weekly").json()["gross_margin"]["shown"]
    app.dependency_overrides[get_settings] = lambda: Settings(
        margin_min_coverage_pct=75
    )
    assert api.get("/api/reports/weekly").json()["gross_margin"]["shown"]


def test_previous_week_and_date_selector_agree_with_sql(api, ledger, insert_event):
    insert_event(
        source_id="OLD",
        amount_iqd=123456,
        category_id="CAT-01",
        quantity=2,
        occurred_at="2026-09-20T12:00:00+03:00",
    )
    insert_event(source_id="NEW", amount_iqd=777777)
    ledger.commit()
    previous = api.get("/api/reports/weekly?week=previous").json()
    dated = api.get("/api/reports/weekly?week=2026-09-21").json()
    assert previous == dated
    expected = ledger.execute(
        "SELECT SUM(amount_iqd) FROM transactions WHERE type='CASH_SALE' "
        "AND business_date BETWEEN '2026-09-19' AND '2026-09-25'"
    ).fetchone()[0]
    assert previous["cash_sales"]["amount_iqd"] == expected == 123456
    assert previous["cash_sales"]["source_ids"] == ["OLD"]


def test_t11_weekly_warnings_include_the_actual_evidenced_flags(api, tool_history):
    before = tuple(tool_history.iterdump())
    weekly = api.get("/api/reports/weekly").json()
    flags = api.get("/api/flags").json()["items"]
    assert weekly["flags"] == flags
    assert weekly["flags_count"] == len(flags) > 0
    assert weekly["suggestion_key"] == "review_unmatched_payment"
    for flag in weekly["flags"]:
        assert flag["reason_key"] and flag["confidence_basis"]
        assert flag["next_step_key"] in {"review", "provide_details"}
        assert flag["amount"]["source_ids"] == flag["source_ids"]
        assert flag["amount"]["formula"]
        for source in flag["source_ids"]:
            assert api.get(f"/api/ledger/transactions/{source}").status_code == 200
    assert tuple(tool_history.iterdump()) == before


def test_t11_duplicate_only_week_never_suggests_no_action(api, ledger):
    content = (
        "source_id,occurred_at,type,amount_iqd,counterparty_id,obligation_id,"
        "due_date,category_id,quantity,description\n"
        "DUP-A,2026-09-28T10:00:00+03:00,CASH_SALE,1000,,,,,,fictional\n"
        "DUP-B,2026-09-28T11:00:00+03:00,CASH_SALE,1000,,,,,,fictional\n"
    )
    assert (
        api.post(
            "/api/imports/csv", files={"file": ("fictional.csv", content, "text/csv")}
        ).status_code
        == 200
    )
    weekly = api.get("/api/reports/weekly").json()
    assert weekly["suggestion_key"] == "review_duplicate_payment"
    assert weekly["cash_sales"]["amount_iqd"] == 2000
    assert weekly["flags"][0]["type"] == "suspected_duplicate"
    assert set(weekly["flags"][0]["source_ids"]) == {"DUP-A", "DUP-B"}
    assert (
        api.post(
            "/api/entries/DUP-B/void",
            json={"client_entry_id": "weekly-void", "reason": "fictional review"},
        ).status_code
        == 200
    )
    weekly = api.get("/api/reports/weekly").json()
    assert weekly["flags"] == [] and weekly["flags_count"] == 0
    assert weekly["cash_sales"]["amount_iqd"] == 1000


def test_t11_complete_weekly_lines_debt_aging_and_difference_evidence(
    api, ledger, priced_shop, insert_event, debt_factory
):
    for day in (25, 26):
        insert_event(
            source_id=f"COUNT-{day}",
            type="DAILY_CASH_COUNT",
            amount_iqd=300000,
            occurred_at=f"2026-09-{day}T21:00:00+03:00",
        )
    # Oldest debt takes precedence over a larger, newer debt; suppliers stay separate.
    debt_factory("OLDER", 1000, "2026-07-01", party="CUST-02")
    debt_factory("PAYABLE", 999999, "2026-07-01", kind="payable")
    ledger.commit()
    weekly = api.get("/api/reports/weekly").json()
    assert weekly["unexplained_cash_difference"]["amount_iqd"] == 25000
    assert weekly["unexplained_cash_difference"]["kind"] == "flagged"
    assert {"COUNT-25", "COUNT-26", "PREVIOUS", "CLOSING", "CAPITAL", "DRAWING"} <= set(
        weekly["unexplained_cash_difference"]["source_ids"]
    )
    assert weekly["outstanding_receivables"]["amount_iqd"] == 11000
    assert weekly["overdue_receivables"]["amount_iqd"] == 1000
    assert [p["counterparty_id"] for p in weekly["debt_aging_top"]] == [
        "CUST-02",
        "CUST-01",
    ]
    assert weekly["debt_aging_top"][0]["days_overdue"] == 89
    assert weekly["gross_margin"]["shown"] is False
    assert weekly["gross_margin"]["coverage_pct"] == 79
    assert weekly["gross_margin"]["note_key"] == "margin_insufficient_priced_sales"
    # Recorded money is independently derivable from active SQL rows.
    for key, kind in (
        ("cash_sales", "CASH_SALE"),
        ("credit_sales", "CREDIT_SALE"),
        ("collections", "CREDIT_COLLECTION"),
        ("supplier_payments", "SUPPLIER_PAYMENT"),
        ("operating_expenses", "OPERATING_EXPENSE"),
        ("owner_drawings", "OWNER_DRAWING"),
        ("capital_injections", "CAPITAL_INJECTION"),
    ):
        rows = ledger.execute(
            "SELECT source_id, amount_iqd FROM transactions WHERE type=? "
            "AND business_date BETWEEN '2026-09-26' AND '2026-09-28'",
            (kind,),
        ).fetchall()
        assert weekly[key]["amount_iqd"] == sum(r["amount_iqd"] for r in rows)
        assert set(weekly[key]["source_ids"]) == {r["source_id"] for r in rows}
