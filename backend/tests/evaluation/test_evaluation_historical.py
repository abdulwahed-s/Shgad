"""Handmade financial fixtures for the approved historical registry amendment.

No sealed questions, annotation records, final outcomes or application services.
FINANCIAL_RULES §§2, 3, 5; historical economic time is distinct from knowledge.
"""

from datetime import date

import pytest
from scripts.evaluation_historical import historical_catalogue
from scripts.evaluation_metrics import compare_claim, proven_aliases
from scripts.evaluation_truth import claim_catalogue
from scripts.make_ground_truth import TruthLedger

DAY = date(2026, 9, 20)
KNOWN = date(2026, 9, 23)


def row(key, kind, amount, day="2026-09-20", hour=12, **extra):
    return (
        dict(
            transaction_id=key,
            source_id=key,
            type=kind,
            amount_iqd=amount,
            business_date=day,
            occurred_at=f"{day}T{hour:02}:00:00+03:00",
            recorded_at=f"{day}T{hour:02}:00:00+03:00",
            category_id=None,
            quantity=None,
            obligation_id=None,
            counterparty_id=None,
            due_date=None,
        )
        | extra
    )


def ledger(rows, *, opening=None, links=(), voids=(), complete=True, baseline=True):
    value = TruthLedger(rows, opening=opening, links=links, voids=voids)
    value.evaluation_coverage = (date(2026, 9, 18), KNOWN) if complete else None
    value.evaluation_opening_baseline = baseline
    return value


def facts(value, *, as_of=KNOWN, start=DAY, end=DAY, **kwargs):
    return historical_catalogue(value, as_of, start, end, **kwargs)


def test_t19_ten_historical_facts_have_independent_arithmetic_and_exact_scope():
    value = ledger(
        [
            row("prior", "DAILY_CASH_COUNT", 100, "2026-09-19", hour=20),
            row("sale", "CASH_SALE", 30),
            row("capital", "CAPITAL_INJECTION", 10),
            row("draw", "OWNER_DRAWING", 8),
            row("expense", "OPERATING_EXPENSE", 12),
            row("credit", "CREDIT_SALE", 70, obligation_id="R", counterparty_id="A"),
            row(
                "invoice",
                "SUPPLIER_INVOICE",
                90,
                obligation_id="P",
                counterparty_id="B",
            ),
            row("count", "DAILY_CASH_COUNT", 125, hour=20),
            row("later", "CASH_SALE", 999, "2026-09-21"),
        ]
    )
    result = facts(value)
    expected = {
        "period_end.cash_on_hand": 125,
        "period_end.receivables.total_outstanding": 70,
        "period_end.payables.total_outstanding": 90,
        "period.cash_inflows_iqd": 40,
        "period.cash_outflows_iqd": 20,
        "closing.expected_cash_iqd": 120,
        "closing.counted_cash_iqd": 125,
        "closing.unexplained_difference_iqd": 5,
        "closing.pre_count_book_cash_iqd": 120,
        "closing.book_to_count_difference_iqd": 5,
    }
    for key, amount in expected.items():
        fact = result[key]
        assert fact["value"] == amount and fact["unit"] == "IQD"
        assert fact["economic_period"] == {"start": str(DAY), "end": str(DAY)}
        assert fact["knowledge_cutoff"].startswith(str(KNOWN))
        assert fact["historical_reconstruction"] is True
        assert "known by the question cutoff" in fact["reconstruction_label"]
        assert "later" not in fact["source_ids"]
    expected_fact = result["closing.expected_cash_iqd"]
    assert set(expected_fact["source_ids"]) == {
        "prior",
        "sale",
        "capital",
        "draw",
        "expense",
    }
    assert expected_fact["prerequisite_source_ids"] == ["count"]
    assert claim_catalogue(value, KNOWN, DAY, DAY)["cash_on_hand"]["value"] == 1124


def test_missing_previous_calendar_count_allows_book_but_never_daily_residual():
    result = facts(
        ledger(
            [
                row("old", "DAILY_CASH_COUNT", 100, "2026-09-18", hour=20),
                row("sale", "CASH_SALE", 30),
                row("count", "DAILY_CASH_COUNT", 135, hour=20),
            ]
        )
    )
    assert result["closing.pre_count_book_cash_iqd"]["value"] == 130
    assert result["closing.book_to_count_difference_iqd"]["value"] == 5
    assert result["closing.counted_cash_iqd"]["value"] == 135
    assert "closing.expected_cash_iqd" not in result
    assert "closing.unexplained_difference_iqd" not in result
    assert (
        result["closing.book_to_count_difference_iqd"][
            "strict_daily_comparison_available"
        ]
        is False
    )


def test_target_count_cannot_supply_its_own_expected_or_book_baseline():
    result = facts(ledger([row("count", "DAILY_CASH_COUNT", 125, hour=20)]))
    assert result["period_end.cash_on_hand"]["value"] == 125
    assert result["closing.counted_cash_iqd"]["source_ids"] == ["count"]
    assert "closing.pre_count_book_cash_iqd" not in result
    assert "closing.expected_cash_iqd" not in result


def test_known_late_entry_and_void_reconstruct_economic_target_without_double_count():
    void = dict(
        void_id="V",
        transaction_id="wrong",
        source_id="wrong",
        voided_at="2026-09-22T12:00:00+03:00",
    )
    value = ledger(
        [
            row("prior", "DAILY_CASH_COUNT", 100, "2026-09-19", hour=20),
            row("wrong", "CASH_SALE", 40),
            row("correct", "CASH_SALE", 30, recorded_at="2026-09-22T12:01:00+03:00"),
            row("count", "DAILY_CASH_COUNT", 135, hour=20),
            row("unknown", "CASH_SALE", 888, recorded_at="2026-09-24T12:00:00+03:00"),
        ],
        voids=[void],
    )
    early = facts(value, as_of=date(2026, 9, 20))
    later = facts(value)
    assert early["closing.expected_cash_iqd"]["value"] == 140
    assert later["closing.expected_cash_iqd"]["value"] == 130
    assert later["period_end.cash_on_hand"]["value"] == 135
    assert later["period.cash_inflows_iqd"]["value"] == 30
    assert later["closing.expected_cash_iqd"]["void_provenance"] == [void]
    assert "unknown" not in later["closing.expected_cash_iqd"]["source_ids"]


def test_settlement_requires_verified_matching_link_economically_by_target():
    rows = [
        row(
            "origin",
            "CREDIT_SALE",
            100,
            obligation_id="R",
            counterparty_id="A",
            due_date="2026-09-19",
        ),
        row("paid", "CREDIT_COLLECTION", 20, obligation_id="R", counterparty_id="A"),
        row(
            "candidate", "CREDIT_COLLECTION", 7, obligation_id="R", counterparty_id="A"
        ),
        row(
            "later",
            "CREDIT_COLLECTION",
            30,
            "2026-09-21",
            obligation_id="R",
            counterparty_id="A",
        ),
    ]
    links = [
        dict(
            payment_link_id="L",
            payment_transaction_id="paid",
            obligation_id="R",
            amount_iqd=20,
            match_basis="confirmed",
            created_at="2026-09-22T12:00:00+03:00",
        ),
        dict(
            payment_link_id="L2",
            payment_transaction_id="later",
            obligation_id="R",
            amount_iqd=30,
            match_basis="confirmed",
            created_at="2026-09-22T12:00:00+03:00",
        ),
    ]
    result = facts(
        ledger(rows, links=links), parties=["A"], parameters={"overdue_only": True}
    )
    key = "period_end.receivables.total_outstanding"
    assert result[key]["value"] == 80
    assert result[key]["source_ids"] == ["origin", "paid"]
    assert result[key]["allocation_provenance"] == [links[0]]
    assert result["period.cash_inflows_iqd"]["value"] == 27  # Cash needs no allocation.
    assert facts(ledger(rows, links=links), as_of=DAY)[key]["value"] == 100


def test_unknown_due_date_filtered_balance_is_unavailable_not_zero():
    result = facts(
        ledger(
            [row("origin", "CREDIT_SALE", 100, obligation_id="R", counterparty_id="A")]
        ),
        parameters={"overdue_only": True},
    )
    assert "period_end.receivables.total_outstanding" not in result
    assert result["period_end.payables.total_outstanding"]["value"] == 0


@pytest.mark.parametrize("baseline", [False, True])
def test_opening_fallback_requires_bound_baseline_without_invented_record_time(
    baseline,
):
    opening = dict(business_date="2026-09-18", amount_iqd=100, source_id="OPEN")
    result = facts(
        ledger(
            [
                row("sale", "CASH_SALE", 30),
                row("count", "DAILY_CASH_COUNT", 140, hour=20),
            ],
            opening=opening,
            baseline=baseline,
        )
    )
    assert ("closing.pre_count_book_cash_iqd" in result) is baseline
    if baseline:
        assert result["closing.pre_count_book_cash_iqd"]["value"] == 130
        assert result["closing.pre_count_book_cash_iqd"]["opening_recorded_at"] is None
    assert "closing.expected_cash_iqd" not in result


def test_incomplete_records_never_establish_zero_or_new_historical_facts():
    result = facts(ledger([], complete=False))
    assert not any(
        key.startswith(("period.", "period_end.", "closing.")) for key in result
    )
    complete = facts(ledger([]))
    assert complete["period.cash_inflows_iqd"]["value"] == 0
    assert complete["period_end.receivables.total_outstanding"]["value"] == 0
    assert "period_end.cash_on_hand" not in complete


def test_duplicate_counts_and_overpayment_fail_closed_per_fact_family():
    rows = [
        row("one", "DAILY_CASH_COUNT", 10, hour=20),
        row("two", "DAILY_CASH_COUNT", 20, hour=20),
    ]
    result = facts(ledger(rows))
    assert "closing.counted_cash_iqd" not in result
    assert "period_end.cash_on_hand" not in result


def test_negative_expected_and_book_cash_keep_sign_and_outflows_stay_positive():
    result = facts(
        ledger(
            [
                row("prior", "DAILY_CASH_COUNT", 10, "2026-09-19", hour=20),
                row("expense", "OPERATING_EXPENSE", 30),
                row("count", "DAILY_CASH_COUNT", 5, hour=20),
            ]
        )
    )
    assert result["closing.expected_cash_iqd"]["value"] == -20
    assert result["closing.pre_count_book_cash_iqd"]["value"] == -20
    assert result["closing.unexplained_difference_iqd"]["value"] == 25
    assert result["period.cash_outflows_iqd"]["value"] == 30


def test_t31_future_or_outside_observed_target_never_gets_historical_alias():
    value = ledger([row("count", "DAILY_CASH_COUNT", 100, hour=20)])
    for start, end in [(DAY, date(2026, 9, 24)), (date(2026, 9, 17), DAY)]:
        result = facts(value, start=start, end=end)
        assert not any(
            key.startswith(("period.", "period_end.", "closing.")) for key in result
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("economic_period", {"start": "2026-09-21", "end": "2026-09-21"}),
        ("knowledge_cutoff", "2026-09-24T23:59:59+03:00"),
        ("historical_reconstruction", False),
        ("reconstruction_label", "current cash"),
    ],
)
def test_t31_historical_claim_requires_its_actual_target_knowledge_and_label(
    field, value
):
    expected = facts(ledger([row("count", "DAILY_CASH_COUNT", 125, hour=20)]))[
        "closing.counted_cash_iqd"
    ]
    claim = expected | dict(formula="physical count")
    assert compare_claim(expected, claim) == (True, True)
    assert compare_claim(expected, claim | {field: value}) == (False, False)
    aliases = proven_aliases(
        "closing.counted_cash_iqd",
        {"cash_on_hand": expected, "closing.counted_cash_iqd": expected},
        {},
    )
    assert aliases == {"closing.counted_cash_iqd"}


def test_historical_traceability_checks_comparison_prerequisites_and_audit_provenance():
    expected = facts(
        ledger(
            [
                row("prior", "DAILY_CASH_COUNT", 100, "2026-09-19", hour=20),
                row("sale", "CASH_SALE", 30),
                row("count", "DAILY_CASH_COUNT", 135, hour=20),
            ]
        )
    )["closing.expected_cash_iqd"]
    claim = expected | dict(formula="prior count plus movements")
    assert compare_claim(expected, claim) == (True, True)
    assert compare_claim(expected, claim | {"prerequisite_source_ids": []}) == (
        True,
        False,
    )


def test_review_correction_keeps_pre_count_economic_order_despite_later_recording():
    result = facts(
        ledger(
            [
                row("prior", "DAILY_CASH_COUNT", 100, "2026-09-19", hour=20),
                row("sale", "CASH_SALE", 30),
                row(
                    "review",
                    "CAPITAL_INJECTION",
                    10,
                    hour=20,
                    recorded_at="2026-09-22T12:00:00+03:00",
                    source="daily_close_review",
                ),
                row("count", "DAILY_CASH_COUNT", 140, hour=20),
            ]
        )
    )
    assert result["period_end.cash_on_hand"]["value"] == 140
    assert result["closing.expected_cash_iqd"]["value"] == 140
    assert result["closing.pre_count_book_cash_iqd"]["value"] == 140


@pytest.mark.parametrize("change", [{"amount_iqd": 101}, {"match_basis": "candidate"}])
def test_invalid_overpayment_or_candidate_allocation_never_reduces_a_debt(change):
    rows = [
        row("origin", "CREDIT_SALE", 100, obligation_id="R", counterparty_id="A"),
        row("paid", "CREDIT_COLLECTION", 101, obligation_id="R", counterparty_id="A"),
    ]
    link = (
        dict(
            payment_link_id="L",
            payment_transaction_id="paid",
            obligation_id="R",
            amount_iqd=20,
            match_basis="confirmed",
            created_at="2026-09-22T12:00:00+03:00",
        )
        | change
    )
    result = facts(ledger(rows, links=[link]))
    assert "period_end.receivables.total_outstanding" not in result
    assert result["period.cash_inflows_iqd"]["value"] == 101


def test_cash_audit_scope_starts_at_its_actual_baseline_and_ends_at_book_boundary():
    old = row("old", "CASH_SALE", 9, "2026-09-18")
    later = row("after", "CASH_SALE", 9, hour=21)
    voids = [
        dict(
            void_id="V-" + r["transaction_id"],
            transaction_id=r["transaction_id"],
            source_id=r["source_id"],
            voided_at="2026-09-22T12:00:00+03:00",
        )
        for r in (old, later)
    ]
    result = facts(
        ledger(
            [old, later, row("count", "DAILY_CASH_COUNT", 100, hour=20)],
            opening=dict(business_date="2026-09-19", amount_iqd=80, source_id="OPEN"),
            voids=voids,
        )
    )
    assert result["period_end.cash_on_hand"]["void_provenance"] == [voids[1]]
    assert result["closing.pre_count_book_cash_iqd"]["void_provenance"] == []


def test_trace_provenance_is_a_unique_record_set_independent_of_serialization_order():
    expected = facts(ledger([row("count", "DAILY_CASH_COUNT", 100, hour=20)]))[
        "closing.counted_cash_iqd"
    ]
    records = [
        dict(payment_link_id="L1", amount_iqd=20),
        dict(payment_link_id="L2", amount_iqd=30),
    ]
    expected["allocation_provenance"] = records
    claim = expected | dict(
        formula="count", allocation_provenance=list(reversed(records))
    )
    assert compare_claim(expected, claim) == (True, True)
    assert compare_claim(
        expected,
        claim | {"allocation_provenance": [records[0], records[0], records[1]]},
    ) == (True, False)


def test_book_difference_must_disclose_missing_strict_daily_comparison():
    expected = facts(
        ledger(
            [
                row("old", "DAILY_CASH_COUNT", 100, "2026-09-18", hour=20),
                row("count", "DAILY_CASH_COUNT", 110, hour=20),
            ]
        )
    )["closing.book_to_count_difference_iqd"]
    claim = expected | dict(formula="count minus book")
    assert compare_claim(expected, claim) == (True, True)
    claim.pop("strict_daily_comparison_available")
    assert compare_claim(expected, claim) == (False, False)


def test_book_comparison_retains_target_count_correction_as_prerequisite_provenance():
    void = dict(
        void_id="V-TARGET",
        transaction_id="old-target",
        source_id="old-target",
        voided_at="2026-09-22T12:00:00+03:00",
    )
    result = facts(
        ledger(
            [
                row("prior", "DAILY_CASH_COUNT", 100, "2026-09-19", hour=20),
                row("sale", "CASH_SALE", 30),
                row("old-target", "DAILY_CASH_COUNT", 125, hour=20),
                row(
                    "target",
                    "DAILY_CASH_COUNT",
                    135,
                    hour=20,
                    recorded_at="2026-09-22T12:01:00+03:00",
                ),
            ],
            voids=[void],
        )
    )
    assert result["closing.pre_count_book_cash_iqd"]["value"] == 130
    for key in (
        "closing.pre_count_book_cash_iqd",
        "closing.book_to_count_difference_iqd",
    ):
        assert result[key]["void_provenance"] == [void]
    assert "target" not in result["closing.pre_count_book_cash_iqd"]["source_ids"]


def test_independent_movement_survives_unrelated_ambiguous_legacy_cash():
    value = ledger(
        [
            row("one", "DAILY_CASH_COUNT", 10, hour=20),
            row("two", "DAILY_CASH_COUNT", 20, hour=20),
            row("sale", "CASH_SALE", 30),
        ]
    )
    result = claim_catalogue(value, KNOWN, DAY, DAY)
    assert result["period.cash_inflows_iqd"]["value"] == 30
    assert "period_end.cash_on_hand" not in result


def test_ambiguous_count_event_order_keeps_movement_but_withholds_cash_snapshot():
    result = facts(
        ledger(
            [
                row("count", "DAILY_CASH_COUNT", 100, hour=20),
                row("sale", "CASH_SALE", 30, hour=20),
            ]
        )
    )
    assert result["period.cash_inflows_iqd"]["value"] == 30
    assert "period_end.cash_on_hand" not in result


def test_opening_fallback_requires_complete_history_since_the_actual_baseline():
    result = facts(
        ledger(
            [row("sale", "CASH_SALE", 30)],
            opening=dict(business_date="2026-09-01", amount_iqd=100, source_id="OPEN"),
        )
    )
    assert result["period.cash_inflows_iqd"]["value"] == 30
    assert "period_end.cash_on_hand" not in result


def test_recorded_sales_and_margin_do_not_require_unambiguous_cash_counts():
    value = ledger(
        [
            row("one", "DAILY_CASH_COUNT", 10, hour=20),
            row("two", "DAILY_CASH_COUNT", 20, hour=20),
            row("sale", "CASH_SALE", 30, category_id="C", quantity=3),
        ]
    )
    value.categories = {"C": dict(buy_price_iqd=3)}
    result = claim_catalogue(value, KNOWN, DAY, DAY)
    assert result["cash_sales"]["value"] == 30
    assert result["gross_margin"]["value"] == 21
    assert "unexplained_cash_difference" not in result
    assert "cash_on_hand" not in result


def test_unavailable_debt_family_preserves_independent_sales_and_cash():
    value = ledger(
        [
            row("origin", "CREDIT_SALE", 100, obligation_id="R", counterparty_id="A"),
            row(
                "paid", "CREDIT_COLLECTION", 101, obligation_id="R", counterparty_id="A"
            ),
            row("sale", "CASH_SALE", 30),
            row("count", "DAILY_CASH_COUNT", 135, hour=20),
        ],
        links=[
            dict(
                payment_link_id="L",
                payment_transaction_id="paid",
                obligation_id="R",
                amount_iqd=101,
                match_basis="confirmed",
                created_at="2026-09-20T12:00:00+03:00",
            )
        ],
    )
    result = claim_catalogue(value, DAY, DAY, DAY)
    assert result["cash_sales"]["value"] == 30
    assert result["cash_on_hand"]["value"] == 135
    assert "receivables.total_outstanding" not in result
