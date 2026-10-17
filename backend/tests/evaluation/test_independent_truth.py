"""Hand-computed tests of the independent evaluator, never backend services."""

from datetime import date, timedelta

import pytest
from scripts.make_ground_truth import (
    TruthError,
    TruthLedger,
    median_days,
    round_half_up,
)


def row(source, kind, amount, day="2026-09-28", hour="12:00", **extra):
    return (
        dict(
            transaction_id=source,
            source_id=source,
            type=kind,
            amount_iqd=amount,
            business_date=day,
            occurred_at=f"{day}T{hour}:00+03:00",
            recorded_at=f"{day}T{hour}:00+03:00",
            category_id=None,
            quantity=None,
            obligation_id=None,
            counterparty_id=None,
            due_date=None,
            status="valid",
        )
        | extra
    )


def test_t22_signed_difference_and_t28_capital_is_not_sales():
    rows = [
        row("prev", "DAILY_CASH_COUNT", 300000, "2026-09-27"),
        row("sale", "CASH_SALE", 120000),
        row("collect", "CREDIT_COLLECTION", 30000),
        row("expense", "OPERATING_EXPENSE", 20000),
        row("draw", "OWNER_DRAWING", 10000),
        row("count", "DAILY_CASH_COUNT", 445000, hour="20:00"),
    ]
    ledger = TruthLedger(rows)
    result = ledger.daily_close(date(2026, 9, 28))
    assert (
        result["expected_close_iqd"],
        result["unexplained_difference_iqd"],
        result["recorded_cash_sales_iqd"],
    ) == (420000, 25000, 120000)
    rows.append(row("cap", "CAPITAL_INJECTION", 25000, hour="19:00"))
    assert (
        TruthLedger(rows).daily_close(date(2026, 9, 28))["unexplained_difference_iqd"]
        == 0
    )
    assert (
        TruthLedger(rows).sales(date(2026, 9, 28), date(2026, 9, 28))[
            "total_recorded_sales_iqd"
        ]
        == 120000
    )
    rows[-1] = row("cap", "CAPITAL_INJECTION", 50000, hour="19:00")
    assert (
        TruthLedger(rows).daily_close(date(2026, 9, 28))["unexplained_difference_iqd"]
        == -25000
    )


def test_missing_consecutive_counts_and_unknown_cash_are_not_zero():
    ledger = TruthLedger(
        [
            row("old", "DAILY_CASH_COUNT", 300000, "2026-09-26"),
            row("count", "DAILY_CASH_COUNT", 400000),
        ]
    )
    assert ledger.daily_close(date(2026, 9, 28))["unexplained_difference_iqd"] is None
    assert (
        ledger.sales(date(2026, 9, 27), date(2026, 9, 28))["unexplained_difference_iqd"]
        is None
    )
    with pytest.raises(TruthError, match="MISSING_OPENING_BALANCE"):
        TruthLedger([]).cash(date(2026, 9, 28))
    upcoming = TruthLedger([]).upcoming(date(2026, 9, 28))
    assert upcoming["position_confirmed_iqd"] is None
    assert upcoming["days"][0]["running_with_expected_iqd"] is None


def test_t27_late_entry_link_and_void_visibility():
    origin = row(
        "debt",
        "CREDIT_SALE",
        90000,
        "2026-09-20",
        obligation_id="OB",
        counterparty_id="C",
        due_date="2026-09-28",
    )
    payment = row(
        "payment",
        "CREDIT_COLLECTION",
        30000,
        obligation_id="OB",
        counterparty_id="C",
        recorded_at="2026-09-28T14:00:00+03:00",
    )
    link = dict(
        payment_transaction_id="payment",
        obligation_id="OB",
        amount_iqd=30000,
        created_at="2026-09-28T15:00:00+03:00",
    )
    void = dict(
        transaction_id="payment",
        source_id="payment",
        voided_at="2026-09-28T16:00:00+03:00",
    )
    ledger = TruthLedger(
        [origin, payment],
        links=[link],
        voids=[void],
        opening={
            "amount_iqd": 200000,
            "business_date": "2026-07-01",
            "source_id": "OPEN",
        },
    )
    for hour, cash, debt in [
        (13, 200000, 90000),
        (14, 230000, 90000),
        (15, 230000, 60000),
        (16, 200000, 90000),
    ]:
        known = f"2026-09-28T{hour}:30:00+03:00"
        assert ledger.cash(date(2026, 9, 28), known_at=known)["amount_iqd"] == cash
        assert (
            ledger.debts(date(2026, 9, 28), known_at=known)[0]["outstanding_iqd"]
            == debt
        )


def test_t23_recorded_coverage_excludes_drawing_capital_gap_and_unpriced_costs():
    rows = [
        row("priced", "CASH_SALE", 80000, category_id="CAT", quantity=40),
        row("unpriced", "CREDIT_SALE", 20000),
        row("draw", "OWNER_DRAWING", 10000),
        row("capital", "CAPITAL_INJECTION", 70000),
        row("expense", "OPERATING_EXPENSE", 5000),
    ]
    ledger = TruthLedger(rows, categories=[dict(category_id="CAT", buy_price_iqd=1000)])
    result = ledger.margin(date(2026, 9, 28), date(2026, 9, 28))
    assert result["estimated_gross_margin_iqd"] == 40000
    assert result["coverage_pct"] == 80
    assert result["weekly_margin_shown"] is True
    assert result["after_recorded_expenses_iqd"] == 35000
    assert result["unpriced_sales_count"] == 1
    with pytest.raises(TruthError, match="MISSING_COSTS"):
        TruthLedger(rows).margin(date(2026, 9, 28), date(2026, 9, 28))
    assert (
        TruthLedger([]).margin(date(2026, 9, 28), date(2026, 9, 28))["coverage_pct"]
        is None
    )


def test_t30_overdue_payable_today_receivable_excluded():
    rows = [
        row("cash", "DAILY_CASH_COUNT", 420000),
        row(
            "invoice",
            "SUPPLIER_INVOICE",
            650000,
            obligation_id="P",
            counterparty_id="S",
            due_date="2026-09-27",
        ),
        row(
            "expected",
            "CREDIT_SALE",
            150000,
            obligation_id="R",
            counterparty_id="C",
            due_date="2026-09-30",
        ),
        row(
            "late",
            "CREDIT_SALE",
            40000,
            obligation_id="L",
            counterparty_id="C",
            due_date="2026-09-27",
        ),
    ]
    result = TruthLedger(rows).upcoming(date(2026, 9, 28))
    assert result["dues_total_iqd"] == 650000
    assert result["expected_total_iqd"] == 150000
    assert result["days"][0]["running_confirmed_iqd"] == -230000
    assert result["first_short_date_with_expected"] == "2026-09-28"
    assert result["overdue_receivables"][0]["outstanding_iqd"] == 40000


def forecast_ledger():
    # Exactly 56 observed days: daily recorded sales 10, gap 2, expense 3,
    # drawing 1. Counts increase by 8/day. No hidden future input.
    start = date(2026, 8, 3)
    rows = [
        row("anchor", "DAILY_CASH_COUNT", 1000, str(start - timedelta(days=1)), "20:00")
    ]
    for i in range(56):
        day = str(start + timedelta(days=i))
        rows += [
            row(f"s{i}", "CASH_SALE", 10, day),
            row(f"e{i}", "OPERATING_EXPENSE", 3, day),
            row(f"d{i}", "OWNER_DRAWING", 1, day),
            row(f"c{i}", "DAILY_CASH_COUNT", 1000 + 8 * (i + 1), day, "20:00"),
        ]
    rows += [
        row(
            "R",
            "CREDIT_SALE",
            100,
            "2026-09-27",
            obligation_id="R",
            counterparty_id="C",
            due_date="2026-09-28",
        ),
        row(
            "P",
            "SUPPLIER_INVOICE",
            200,
            "2026-09-27",
            obligation_id="P",
            counterparty_id="S",
            due_date="2026-09-29",
        ),
        row(
            "overdue",
            "CREDIT_SALE",
            700,
            "2026-09-26",
            obligation_id="L",
            counterparty_id="C",
            due_date="2026-09-26",
        ),
    ]
    return TruthLedger(rows)


def test_t29_forecast_stress_all_drivers_and_thirty_rows():
    ledger = forecast_ledger()
    cutoff = date(2026, 9, 27)
    base, stress = ledger.forecast(cutoff, "base"), ledger.forecast(cutoff, "stress")
    assert len(base["days"]) == len(stress["days"]) == 30
    assert base["days"][0]["opening_iqd"] == 1448
    assert base["days"][0]["closing_iqd"] == 1556
    assert stress["days"][0]["closing_iqd"] == 1456
    assert stress["days"][1]["closing_iqd"] == 1264
    for b, s in zip(base["days"], stress["days"], strict=True):
        assert s["collections_iqd"] == 0
        assert s["closing_iqd"] <= b["closing_iqd"]
        assert (
            s["cash_sales_iqd"],
            s["unlinked_cash_iqd"],
            s["expenses_iqd"],
            s["owner_drawings_iqd"],
        ) == (10, 2, 3, 1)


def test_t26_median_is_settled_obligations_not_profile_or_partial_payment():
    ledger = forecast_ledger()
    # Two settled debts: +2, +4 late; customer median 3 days.
    for i, delay in enumerate((2, 4)):
        day = date(2026, 9, 10) + timedelta(days=delay)
        ledger.rows += [
            row(
                f"old{i}",
                "CREDIT_SALE",
                50,
                "2026-09-01",
                obligation_id=f"OLD{i}",
                counterparty_id="C",
                due_date="2026-09-10",
            ),
            row(
                f"part{i}",
                "CREDIT_COLLECTION",
                20,
                "2026-09-10",
                obligation_id=f"OLD{i}",
                counterparty_id="C",
            ),
            row(
                f"paid{i}",
                "CREDIT_COLLECTION",
                30,
                str(day),
                obligation_id=f"OLD{i}",
                counterparty_id="C",
            ),
        ]
        ledger.links += [
            dict(
                payment_transaction_id=f"part{i}",
                obligation_id=f"OLD{i}",
                amount_iqd=20,
                created_at="2026-09-10T12:00:00+03:00",
            ),
            dict(
                payment_transaction_id=f"paid{i}",
                obligation_id=f"OLD{i}",
                amount_iqd=30,
                created_at=f"{day}T12:00:00+03:00",
            ),
        ]
    result = ledger.forecast(date(2026, 9, 27), "conservative")
    assert [r["date"] for r in result["days"] if r["collections_iqd"]] == ["2026-10-01"]
    assert sum(r["collections_iqd"] for r in result["days"]) == 100


@pytest.mark.parametrize(
    ("values", "expected"), [([1, 2], 2), ([-1, -2], -2), ([2, 2, 3], 2), ([-1, 0], -1)]
)
def test_half_up_means_without_money_floats(values, expected):
    assert round_half_up(sum(values), len(values)) == expected


def test_t12_later_entries_and_voids_cannot_change_earlier_forecasts():
    ledger = forecast_ledger()
    expected = ledger.forecast(date(2026, 9, 27), "base")
    ledger.rows += [
        row("later", "CASH_SALE", 10**9, "2026-09-28"),
        row(
            "backfill",
            "CASH_SALE",
            10**9,
            "2026-09-20",
            recorded_at="2026-09-28T12:00:00+03:00",
        ),
    ]
    ledger.voids.append(
        dict(
            transaction_id="s20", source_id="s20", voided_at="2026-09-28T12:00:00+03:00"
        )
    )
    assert ledger.forecast(date(2026, 9, 27), "base") == expected


def test_prior_period_uses_explicit_knowledge_cutoff_for_sales_and_margin():
    sale = row("sale", "CASH_SALE", 10000, "2026-09-20", category_id="CAT", quantity=2)
    void = dict(
        transaction_id="sale", source_id="sale", voided_at="2026-09-28T12:00:00+03:00"
    )
    ledger = TruthLedger(
        [sale], categories=[dict(category_id="CAT", buy_price_iqd=1000)], voids=[void]
    )
    start, end = date(2026, 9, 19), date(2026, 9, 25)
    assert ledger.sales(start, end)["recorded_cash_sales_iqd"] == 10000
    assert ledger.margin(start, end)["estimated_gross_margin_iqd"] == 8000
    known = "2026-09-28T18:00:00+03:00"
    assert ledger.sales(start, end, known_at=known)["recorded_cash_sales_iqd"] == 0
    assert (
        ledger.margin(start, end, known_at=known)["estimated_gross_margin_iqd"] is None
    )


def test_baseline_uses_only_cutoff_and_seven_days_before():
    result = forecast_ledger().baseline(date(2026, 9, 27))
    assert len(result["days"]) == 30
    assert result["daily_change_iqd"] == 8
    assert result["days"][0] == {"date": "2026-09-28", "closing_iqd": 1456}
    assert result["days"][-1] == {"date": "2026-10-27", "closing_iqd": 1688}


def test_lateness_median_keeps_exact_half_day_and_missing_is_typed():
    assert median_days([2, 3]) * 2 == 5
    with pytest.raises(TruthError, match="MISSING_LATENESS_HISTORY"):
        median_days([])
