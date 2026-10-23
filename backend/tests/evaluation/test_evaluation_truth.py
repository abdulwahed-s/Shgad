"""Independent historical claim/evidence calculations (FINANCIAL_RULES §§2–7a)."""

from datetime import date

from scripts.evaluation_truth import claim_catalogue, required_fields
from scripts.make_ground_truth import TruthLedger


def row(key, kind, amount, day="2026-09-28", **extra):
    return (
        dict(
            transaction_id=key,
            source_id=key,
            type=kind,
            amount_iqd=amount,
            business_date=day,
            occurred_at=f"{day}T12:00:00+03:00",
            recorded_at=f"{day}T12:00:00+03:00",
            category_id=None,
            quantity=None,
            obligation_id=None,
            counterparty_id=None,
            due_date=None,
        )
        | extra
    )


def test_independent_claims_exclude_capital_drawings_from_sales_and_use_exact_rows():
    ledger = TruthLedger(
        [
            row("cash", "CASH_SALE", 80000, category_id="CAT", quantity=40),
            row(
                "credit",
                "CREDIT_SALE",
                20000,
                obligation_id="OB",
                counterparty_id="CUST-01",
            ),
            row("draw", "OWNER_DRAWING", 3000),
            row("capital", "CAPITAL_INJECTION", 7000),
            row("expense", "OPERATING_EXPENSE", 5000),
        ],
        categories=[dict(category_id="CAT", buy_price_iqd=1000)],
    )
    catalogue = claim_catalogue(
        ledger, date(2026, 9, 28), date(2026, 9, 28), date(2026, 9, 28)
    )
    assert catalogue["cash_sales"]["value"] == 80000
    assert catalogue["cash_sales"]["source_ids"] == ["cash"]
    assert catalogue["total_sales"]["value"] == 100000
    assert set(catalogue["gross_margin"]["source_ids"]) == {"cash", "CAT"}
    assert catalogue["gross_margin"]["value"] == 40000
    assert catalogue["after_recorded_expenses"]["value"] == 35000
    assert catalogue["coverage_pct"]["value"] == 80
    assert catalogue["weekly.owner_drawings"]["value"] == 3000
    assert "unexplained_cash_difference" not in catalogue  # Missing counts, not zero.


def test_j1_and_seven_day_catalogue_evidence_includes_cash_and_active_allocations():
    ledger = TruthLedger(
        [
            row("count", "DAILY_CASH_COUNT", 420000),
            row(
                "invoice",
                "SUPPLIER_INVOICE",
                650000,
                obligation_id="P",
                counterparty_id="SUP-01",
                due_date="2026-10-01",
            ),
            row(
                "sale",
                "CREDIT_SALE",
                150000,
                obligation_id="R",
                counterparty_id="CUST-01",
                due_date="2026-09-30",
            ),
            row(
                "late",
                "CREDIT_SALE",
                99000,
                obligation_id="L",
                counterparty_id="CUST-02",
                due_date="2026-09-27",
            ),
        ]
    )
    catalogue = claim_catalogue(
        ledger, date(2026, 9, 28), date(2026, 9, 28), date(2026, 10, 1)
    )
    assert catalogue["j1.shortfall_with_collection"]["value"] == 80000
    assert set(catalogue["j1.shortfall_with_collection"]["source_ids"]) == {
        "count",
        "invoice",
        "sale",
    }
    assert catalogue["upcoming.position_with_expected"]["value"] == -80000
    assert "late" not in catalogue["upcoming.expected_total"]["source_ids"]


def test_required_multi_figure_categories_are_explicit_and_not_model_selected():
    spec = dict(
        calculation="sales", parameters=dict(kind="all"), expected_behavior="answer"
    )
    keys = {"cash_sales", "credit_sales", "total_sales", "unexplained_cash_difference"}
    assert required_fields(spec, dict.fromkeys(keys)) == keys
    spec["parameters"]["kind"] = "credit"
    assert required_fields(spec, dict.fromkeys(keys)) == {"credit_sales"}
    spec["expected_behavior"] = "clarify"
    assert required_fields(spec, dict.fromkeys(keys)) == set()


def test_margin_requires_margin_and_coverage_not_unrequested_unpriced_count():
    spec = dict(calculation="margin", expected_behavior="answer", parameters={})
    assert required_fields(spec, {}) == {"gross_margin", "coverage_pct"}


def test_standalone_cash_on_hand_is_cutoff_cash_with_exact_evidence():
    """FINANCIAL_RULES §2: count + later inflows - later outflows, not sales."""
    ledger = TruthLedger(
        [
            row("count", "DAILY_CASH_COUNT", 100000, day="2026-09-27"),
            row("sale", "CASH_SALE", 20000),
            row("draw", "OWNER_DRAWING", 8000),
            row("capital", "CAPITAL_INJECTION", 7000),
            row("expense", "OPERATING_EXPENSE", 3000),
        ]
    )
    catalogue = claim_catalogue(
        ledger, date(2026, 9, 28), date(2026, 9, 28), date(2026, 9, 28)
    )
    assert catalogue["cash_on_hand"] == dict(
        value=116000,
        unit="IQD",
        label="cash_on_hand",
        source_ids=["capital", "count", "draw", "expense", "sale"],
    )
    assert catalogue["cash_on_hand"] == catalogue["upcoming.cash_on_hand"]
    earlier = claim_catalogue(
        ledger, date(2026, 9, 27), date(2026, 9, 27), date(2026, 9, 27)
    )
    assert earlier["cash_on_hand"]["value"] == 100000
    assert earlier["cash_on_hand"]["source_ids"] == ["count"]


def test_standalone_cash_on_hand_missing_balance_has_no_zero_claim():
    catalogue = claim_catalogue(
        TruthLedger([]), date(2026, 9, 28), date(2026, 9, 28), date(2026, 9, 28)
    )
    assert "cash_on_hand" not in catalogue
