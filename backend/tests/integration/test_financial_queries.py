"""FINANCIAL_RULES §§2/3/5/7/7a/11: T06/T07/T10/T22/T30/T31.

Every figure is calculated by the real service over inline fictional SQLite rows.
"""

from datetime import date, datetime

import pytest

from app.agents.tool_registry import invoke
from app.services.business_clock import BusinessClock

CLOCK = BusinessClock(date(2026, 9, 28))
KNOWN = datetime.fromisoformat("2026-09-28T23:59:59+03:00")


def call(ledger, name, args, **kwargs):
    return invoke(name, args, connection=ledger, clock=CLOCK, known_at=KNOWN, **kwargs)


def test_t30_upcoming_exact_positions_and_day_timing(api, j1_shop):
    response = api.get("/api/obligations/upcoming?days=7")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["range"] == {"start": "2026-09-28", "end": "2026-10-04"}
    for key, value in {
        "cash_on_hand": 420000,
        "dues_total": 650000,
        "expected_total": 150000,
        "position_confirmed": -230000,
        "position_with_expected": -80000,
    }.items():
        assert body[key]["amount_iqd"] == value
        assert body[key]["source_ids"] and body[key]["formula"]
    assert body["days"][2]["running_with_expected_iqd"] == 570000
    assert body["days"][3]["running_with_expected_iqd"] == -80000
    assert body["first_short_date_confirmed"] == "2026-10-01"
    assert body["first_short_date_with_expected"] == "2026-10-01"
    assert body["counted_at"] and body["last_synced_at"]


def test_t30_overdue_variant_is_separate_and_payables_due_now(
    api, j1_shop, debt_factory
):
    debt_factory("OVERDUE-R", 90000, "2026-09-27")
    debt_factory("OVERDUE-P", 50000, "2026-09-27", kind="payable")
    j1_shop.commit()
    body = api.get("/api/obligations/upcoming").json()
    assert body["expected_total"]["amount_iqd"] == 150000
    assert body["dues_total"]["amount_iqd"] == 700000
    assert body["overdue_receivables"][0]["timing"] == "unknown"
    assert body["days"][0]["dues_iqd"] == 50000
    assert body["days"][0]["running_confirmed_iqd"] == 370000
    assert next(d for d in body["dues"] if d["due_now"])["due_date"] == "2026-09-27"


def test_t06_missing_cash_keeps_obligations_without_fabricating_positions(
    api, ledger, debt_factory
):
    debt_factory("P", 650000, "2026-10-01", kind="payable")
    ledger.commit()
    body = api.get("/api/obligations/upcoming").json()
    assert body["dues_total"]["amount_iqd"] == 650000
    for key in ("cash_on_hand", "position_confirmed", "position_with_expected"):
        assert body[key]["kind"] == "missing" and body[key]["amount_iqd"] is None
    assert all(d["running_confirmed_iqd"] is None for d in body["days"])
    assert body["first_short_date_confirmed"] is None


@pytest.mark.parametrize("days", [0, 31, "1.5", "nan", "x"])
def test_upcoming_rejects_invalid_window(api, days):
    response = api.get(f"/api/obligations/upcoming?days={days}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_t22_sales_tool_recorded_sales_separate_signed_difference(ledger, insert_event):
    insert_event(
        source_id="PREV",
        type="DAILY_CASH_COUNT",
        amount_iqd=300000,
        occurred_at="2026-09-27T21:00:00+03:00",
    )
    for key, event, amount, extra in [
        ("SALE", "CASH_SALE", 120000, {}),
        (
            "COL",
            "CREDIT_COLLECTION",
            30000,
            {"counterparty_id": "CUST-01", "status": "flagged"},
        ),
        ("EXP", "OPERATING_EXPENSE", 20000, {}),
        ("DRAW", "OWNER_DRAWING", 10000, {}),
        ("COUNT", "DAILY_CASH_COUNT", 445000, {}),
    ]:
        insert_event(source_id=key, type=event, amount_iqd=amount, **extra)
    ledger.commit()
    ledger.execute("PRAGMA query_only=ON")
    result = call(ledger, "get_sales", {"period": "today"})
    assert result.ok
    assert result.result["cash_sales"]["amount_iqd"] == 120000
    assert result.result["total_sales"]["amount_iqd"] == 120000
    assert result.result["unexplained_cash_difference"]["amount_iqd"] == 25000
    cash = next(f for f in result.figures if f.key == "cash_sales")
    assert cash.source_ids == ("SALE",) and cash.formula
    assert result.currency == "IQD" and result.resolved_range.start == CLOCK.today


def test_missing_consecutive_counts_are_missing_not_zero(ledger, insert_event):
    insert_event()
    result = call(ledger, "get_sales", {"period": "today"})
    assert result.ok
    assert result.result["unexplained_cash_difference"]["amount_iqd"] is None


def test_t07_names_are_not_merged_and_arguments_cannot_write(ledger, j1_shop):
    ambiguous = call(ledger, "get_debts", {"counterparty_query": "أبو حيدر"})
    assert not ambiguous.ok and ambiguous.error.code == "AMBIGUOUS_COUNTERPARTY"
    assert ambiguous.result is None and not ambiguous.figures
    before = ledger.total_changes
    for name, args in [
        ("void", {}),
        ("get_sales", {"period": "today", "sql": "DELETE FROM transactions"}),
        ("get_debts", {"overdue_only": 1}),
    ]:
        result = call(ledger, name, args)
        assert not result.ok and result.error.code == "VALIDATION_ERROR"
    assert ledger.total_changes == before


def test_t30_debts_both_and_next_n_days_use_same_obligations_view(ledger, j1_shop):
    ledger.execute("PRAGMA query_only=ON")
    result = call(
        ledger, "get_debts", {"direction": "both", "due_period": "next_n_days:7"}
    )
    assert result.ok
    assert result.result["receivables"]["total_outstanding"]["amount_iqd"] == 150000
    assert result.result["payables"]["total_outstanding"]["amount_iqd"] == 650000
    assert result.result["upcoming"]["position_with_expected"]["amount_iqd"] == -80000


def test_debt_aging_exact_allocations_and_void_cutoff(api, ledger, debt_factory):
    origin = debt_factory("DEBT", 90000, "2026-09-20")
    ledger.commit()
    saved = api.post(
        "/api/entries",
        json={
            "client_entry_id": "pay",
            "type": "CREDIT_COLLECTION",
            "business_date": "2026-09-28",
            "amount_iqd": 30000,
            "counterparty_id": origin.counterparty_id,
            "obligation_id": origin.obligation_id,
        },
    ).json()
    body = api.get("/api/debts?overdue_only=true").json()
    assert body["total_outstanding"]["amount_iqd"] == 60000
    assert body["aging"]["d8_30"]["amount_iqd"] == 60000
    assert saved["source_id"] in body["total_outstanding"]["source_ids"]
    assert (
        api.post(
            f"/api/entries/{saved['source_id']}/void",
            json={"client_entry_id": "v", "reason": "fictional correction"},
        ).status_code
        == 200
    )
    assert api.get("/api/debts").json()["total_outstanding"]["amount_iqd"] == 90000


def test_explicit_dates_require_trusted_user_text_and_future_sales_fail(ledger):
    args = {"period": "explicit", "start_date": "2026-09-28", "end_date": "2026-09-28"}
    assert not call(ledger, "get_sales", args).ok
    assert call(ledger, "get_sales", args, user_message="عن 2026-09-28").ok
    future = call(ledger, "get_sales", {"period": "next_n_days:7"})
    assert not future.ok and future.error.code == "NOT_FOUND"


def test_missing_due_date_is_typed_not_silently_excluded(api, ledger, debt_factory):
    debt_factory("UNDATED", 10000, None)
    ledger.commit()
    response = api.get("/api/obligations/upcoming")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MISSING_DUE_DATE"


@pytest.mark.parametrize(
    "kind,expected", [("cash", 100000), ("credit", 70000), ("all", 170000)]
)
def test_sales_kind_selects_without_relabelling_total(
    ledger, insert_event, debt_factory, kind, expected
):
    insert_event()
    debt_factory("CREDIT", 70000, "2026-09-30")
    result = call(ledger, "get_sales", {"period": "today", "kind": kind})
    assert result.result["selected_sales"]["amount_iqd"] == expected
    assert result.result["total_sales"]["amount_iqd"] == 170000


def test_counterparty_text_is_not_a_server_date_slot(ledger, debt_factory):
    ledger.execute(
        "INSERT INTO counterparties VALUES ('DATE-NAME', '2026-09-28', 'customer')"
    )
    debt_factory("DATE-NAME-DEBT", 10000, "2026-09-30", party="DATE-NAME")
    result = call(ledger, "get_debts", {"counterparty_query": "2026-09-28"})
    assert result.ok
    assert "receivables.customers.0.display_name" not in result.dates
