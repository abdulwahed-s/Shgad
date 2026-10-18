"""All five tools, production forecast reuse and per-figure verification (§8)."""

from datetime import date, datetime

import pytest

from app.agents.tool_registry import definitions, invoke
from app.services.business_clock import BusinessClock

CLOCK = BusinessClock(date(2026, 9, 28))
KNOWN = datetime.fromisoformat("2026-09-28T23:59:59+03:00")


def call(ledger, name, arguments):
    return invoke(name, arguments, connection=ledger, clock=CLOCK, known_at=KNOWN)


def test_exactly_five_allowlisted_strict_tool_definitions():
    tools = {d["function"]["name"]: d["function"]["parameters"] for d in definitions()}
    assert set(tools) == {
        "get_sales",
        "get_debts",
        "reconcile",
        "forecast",
        "get_margin",
    }
    assert all(d["additionalProperties"] is False for d in tools.values())


@pytest.mark.parametrize(
    "name,args",
    [
        ("get_sales", {"period": "this_week"}),
        ("get_debts", {}),
        ("reconcile", {"period": "this_week"}),
        ("forecast", {"scenario": "stress"}),
        ("get_margin", {"period": "this_week"}),
    ],
)
def test_all_five_on_seeded_query_only_ledger(tool_history, name, args):
    before = tool_history.total_changes
    tool_history.execute("PRAGMA query_only=ON")
    result = call(tool_history, name, args)
    assert result.ok, result.error
    assert result.data_version == "synthetic-ledger-v1" and result.currency == "IQD"
    assert result.resolved_range is not None
    assert tool_history.total_changes == before
    assert result.figures
    assert all(
        f.formula and (f.source_ids or f.amount_iqd in (None, 0))
        for f in result.figures
    )


def test_t10_forecast_weekday_adds_primary_capacity_without_projected_sales(
    tool_history,
):
    result = call(
        tool_history, "forecast", {"scenario": "base", "until": "next_weekday:thu"}
    )
    assert result.ok, result.error
    j1 = result.result["j1"]
    assert j1["cash_on_hand"]["amount_iqd"] == 420000
    assert j1["supplier_due"]["amount_iqd"] == 650000
    assert j1["expected_collection"]["amount_iqd"] == 150000
    assert j1["shortfall_with_collection"]["amount_iqd"] == 80000
    assert j1["shortfall_without_collection"]["amount_iqd"] == 230000
    assert len(result.result["scenarios"]["base"]["days"]) == 30
    assert result.resolved_range.end == date(2026, 10, 1)
    assert "collections_expected_not_guaranteed" in result.assumptions
    figure = next(
        f for f in result.figures if f.key == "scenarios.base.days.2.closing_iqd"
    )
    assert {"CNT-8", "J1-R", "J1-P"} <= set(figure.source_ids)


def test_forecast_http_and_late_void_cannot_change_cutoff(tool_history, api):
    response = api.get("/api/reports/forecast?scenario=base")
    assert response.status_code == 200, response.text
    before = response.json()
    from app.api.dependencies import audit_timestamp
    from app.main import app

    app.dependency_overrides[audit_timestamp] = lambda: datetime.fromisoformat(
        "2026-10-18T12:00:00+04:00"
    )
    assert (
        api.post(
            "/api/entries/J1-P/void",
            json={"client_entry_id": "late-v", "reason": "fictional later knowledge"},
        ).status_code
        == 200
    )
    assert api.get("/api/reports/forecast?scenario=base").json() == before
    assert api.get("/api/obligations/upcoming").json()["dues_total"]["amount_iqd"] == 0


def test_t06_forecast_missing_cash_and_history_typed(ledger, api, insert_event):
    result = call(ledger, "forecast", {"scenario": "base"})
    assert not result.ok and result.error.code == "MISSING_OPENING_BALANCE"
    assert result.result is None and not result.figures
    response = api.get("/api/reports/forecast?scenario=base")
    assert (
        response.status_code == 422
        and response.json()["error"]["code"] == "MISSING_OPENING_BALANCE"
    )
    insert_event(type="DAILY_CASH_COUNT")
    ledger.commit()
    assert (
        call(ledger, "forecast", {"scenario": "base"}).error.code
        == "MISSING_FORECAST_HISTORY"
    )


def test_reconcile_period_type_filters_and_flags_http(api, ledger, insert_event):
    insert_event(
        source_id="NOW",
        type="CREDIT_COLLECTION",
        amount_iqd=11111,
        counterparty_id="CUST-01",
        status="flagged",
    )
    insert_event(
        source_id="OLD",
        type="CREDIT_COLLECTION",
        amount_iqd=22222,
        counterparty_id="CUST-01",
        status="flagged",
        occurred_at="2026-08-20T12:00:00+03:00",
    )
    ledger.commit()
    body = api.get("/api/flags").json()
    assert {i["amount"]["amount_iqd"] for i in body["items"]} == {11111, 22222}
    filtered = call(ledger, "reconcile", {"period": "today", "types": ["unmatched"]})
    assert filtered.ok
    assert len(filtered.result["items"]) == 1
    assert filtered.result["items"][0]["source_ids"] == ["NOW"]
    assert filtered.figures[0].formula and filtered.figures[0].source_ids == ("NOW",)


def test_upcoming_scalar_day_figures_have_running_evidence(j1_shop):
    result = call(
        j1_shop, "get_debts", {"direction": "both", "due_period": "next_n_days:7"}
    )
    day = next(
        f
        for f in result.figures
        if f.key == "upcoming.days.3.running_with_expected_iqd"
    )
    assert day.amount_iqd == -80000
    assert set(day.source_ids) == {"CNT-090", "J1-P", "J1-R"}


def test_meta_is_honest_and_contains_no_configuration(api):
    response = api.get("/api/meta")
    assert response.status_code == 200
    assert response.json() == {
        "business_as_of": "2026-09-28",
        "week_start": "saturday",
        "data_version": "synthetic-ledger-v1",
        "llm_available": False,
        "merchant": {"id": "DEMO-01", "display_name_key": "demo_shop_name"},
    }


def test_reconcile_empty_ledger_does_not_invent_flag_figures(ledger):
    result = call(ledger, "reconcile", {"period": "today"})
    assert result.ok and result.result == {"items": []} and not result.figures
