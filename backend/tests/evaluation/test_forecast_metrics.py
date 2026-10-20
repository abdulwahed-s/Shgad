"""Hand-computed financial benchmark regressions, FINANCIAL_RULES §6/§7b.

All inputs are tiny fictional records; no packaged final outcomes are opened.
"""

from datetime import date

import pytest
from scripts.make_ground_truth import TruthError, TruthLedger


def test_t32_invoice_safety_uses_realized_shortfall_denominator():
    from scripts.forecast_metrics import false_ok

    result = false_ok(
        [
            dict(
                amount_due_iqd=100000,
                predicted_closing_iqd=20000,
                predicted_payment_iqd=100000,
                realized_closing_iqd=-10000,
                realized_payment_iqd=100000,
            ),
            # Realized-solvent invoices are not part of the denominator.
            dict(
                amount_due_iqd=50000,
                predicted_closing_iqd=0,
                predicted_payment_iqd=50000,
                realized_closing_iqd=50000,
                realized_payment_iqd=0,
            ),
        ]
    )
    assert result == {
        "numerator": 1,
        "denominator": 1,
        "rate": 1.0,
        "eligible_invoices": 2,
    }


def test_false_ok_adds_only_that_invoices_payment_and_uses_zero_denominator_null():
    from scripts.forecast_metrics import false_ok

    # Another invoice's payment cannot turn this one into a predicted OK.
    cases = [
        dict(
            amount_due_iqd=100,
            predicted_closing_iqd=-20,
            predicted_payment_iqd=100,
            realized_closing_iqd=90,
            realized_payment_iqd=0,
        )
    ]
    assert false_ok(cases)["numerator"] == 0
    assert false_ok(cases)["denominator"] == 1
    assert false_ok(cases)["rate"] == 0.0
    assert false_ok([]) == {
        "numerator": 0,
        "denominator": 0,
        "rate": None,
        "eligible_invoices": 0,
    }
    cases[0]["realized_payment_iqd"] = 10
    assert false_ok(cases)["rate"] is None


def test_mae_and_worst_error_are_exact_iqd_and_retain_aggregate_denominator():
    from scripts.forecast_metrics import balance_errors

    assert balance_errors([100, 98, 101], [100, 100, 100]) == {
        "scored_days": 3,
        "absolute_error_sum_iqd": 3,
        "mae_iqd": 1,
        "worst_day_error_iqd": 2,
    }
    assert balance_errors([0, 1], [0, 0])["mae_iqd"] == 1
    with pytest.raises(ValueError):
        balance_errors([100.0], [100])
    with pytest.raises(ValueError):
        balance_errors([100], [100, 101])


def test_shortfall_timing_uses_next_day_known_due_and_two_day_hit_window():
    from scripts.forecast_metrics import first_shortfall, shortfall_timing

    days = [
        {"date": "2026-08-30", "closing_iqd": 120},
        {"date": "2026-08-31", "closing_iqd": 90},
    ]
    assert first_shortfall(days, {"2026-09-01": 100}) == "2026-08-31"
    assert shortfall_timing("2026-08-29", "2026-08-31") == {
        "predicted_date": "2026-08-29",
        "realized_date": "2026-08-31",
        "absolute_error_days": 2,
        "numerator": 1,
        "denominator": 1,
        "rate": 1.0,
    }
    assert shortfall_timing(None, "2026-08-31")["rate"] == 0.0
    assert shortfall_timing("2026-08-28", "2026-08-31")["rate"] == 0.0
    assert shortfall_timing(None, None)["rate"] is None


def test_seven_day_baseline_uses_counts_but_starts_from_count_plus_later_flows():
    def row(key, kind, amount, day, hour="21:00"):
        return dict(
            transaction_id=key,
            source_id=key,
            type=kind,
            amount_iqd=amount,
            business_date=day,
            occurred_at=f"{day}T{hour}:00+03:00",
            recorded_at=f"{day}T{hour}:00+03:00",
        )

    truth = TruthLedger(
        [
            row("old", "DAILY_CASH_COUNT", 1000, "2026-08-22"),
            row("now", "DAILY_CASH_COUNT", 993, "2026-08-29"),
            row("late", "CASH_SALE", 100, "2026-08-29", "22:00"),
        ]
    )
    result = truth.baseline(date(2026, 8, 29))
    assert result["daily_change_iqd"] == -1
    assert len(result["days"]) == 30
    assert result["days"][0]["closing_iqd"] == 1092
    assert result["days"][-1]["closing_iqd"] == 1063
    assert set(result["source_ids"]) == {"old", "now", "late"}
    with pytest.raises(TruthError, match="MISSING_COUNT"):
        truth.baseline(date(2026, 8, 28))
    truth.rows.append(row("old-conflict", "DAILY_CASH_COUNT", 1001, "2026-08-22"))
    with pytest.raises(TruthError, match="AMBIGUOUS_CASH_COUNT"):
        truth.baseline(date(2026, 8, 29))
