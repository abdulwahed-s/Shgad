"""Roadmap §12.2, T19/T31: hand-computed metrics, no model or ledger mocks."""

from copy import deepcopy

import pytest
from scripts.evaluation_metrics import (
    aggregate_questions,
    grade_question,
    integer_value,
    reconciliation_metrics,
)


def sample():
    spec = dict(
        expected_behavior="answer",
        intent="sales",
        expected_tools=["get_sales"],
        counterparty_ids=["CUST-01"],
        resolved_period={"start": "2026-09-26", "end": "2026-09-28"},
    )
    catalogue = {
        "cash_sales": dict(
            value=420000, unit="IQD", label="recorded_cash_sales", source_ids=["SALE"]
        ),
        "credit_sales": dict(
            value=90000, unit="IQD", label="credit_sales", source_ids=["CREDIT"]
        ),
    }
    observed = dict(
        behavior="answer",
        intent="sales",
        tools=["get_sales"],
        counterparty_ids=["CUST-01"],
        period=spec["resolved_period"],
        claims=[
            dict(field=key, **value, formula="sum active sales")
            for key, value in catalogue.items()
        ],
    )
    return spec, catalogue, observed


@pytest.mark.parametrize(
    "value,expected",
    [
        (420000, 420000),
        ("٤٢٠ ألف", 420000),
        ("420,000 IQD", 420000),
        ("−١٬٢٣٤ دينار", -1234),
        ("۹۰٬۰۰۰", 90000),
        ("٨٠٪", 80),
    ],
)
def test_exact_integer_normalizes_accepted_display_without_rounding(value, expected):
    assert integer_value(value) == expected


@pytest.mark.parametrize("value", [True, 1.0, "1.5", "1,00", "1e3", "NaN", "١٫٥"])
def test_integer_rejects_noninteger_or_ambiguous_format(value):
    with pytest.raises(ValueError):
        integer_value(value)


def test_t19_whole_question_all_required_amounts_and_labels_units():
    spec, catalogue, observed = sample()
    good = grade_question(spec, catalogue, set(catalogue), observed)
    assert good["numeric_correct"] and good["joint_correct"]
    assert good["traceability"] == {"numerator": 2, "denominator": 2, "rate": 1.0}
    for mutation in ("missing", "amount", "label", "unit", "conflicting_duplicate"):
        bad = deepcopy(observed)
        if mutation == "missing":
            bad["claims"].pop()
        elif mutation == "conflicting_duplicate":
            bad["claims"].append(bad["claims"][0] | {"value": 1})
        else:
            bad["claims"][1][{"amount": "value"}.get(mutation, mutation)] = "wrong"
        assert not grade_question(spec, catalogue, set(catalogue), bad)[
            "numeric_correct"
        ]


@pytest.mark.parametrize(
    "field,value",
    [
        ("counterparty_ids", ["CUST-02"]),
        ("period", {"start": "2026-09-19", "end": "2026-09-25"}),
    ],
)
def test_t31_right_amount_and_tool_wrong_customer_or_period_fails(field, value):
    spec, catalogue, observed = sample()
    observed[field] = value
    result = grade_question(spec, catalogue, set(catalogue), observed)
    assert not result["numeric_correct"] and not result["joint_correct"]


def test_documented_selected_sales_alias_satisfies_same_requested_category():
    spec, catalogue, observed = sample()
    spec |= dict(calculation="sales", parameters=dict(kind="cash"))
    catalogue["selected_sales"] = dict(catalogue["cash_sales"])
    observed["claims"] = [dict(observed["claims"][0], field="selected_sales")]
    result = grade_question(spec, catalogue, {"cash_sales"}, observed)
    assert result["numeric_correct"]
    observed["claims"][0]["label"] = "credit_sales"
    assert not grade_question(spec, catalogue, {"cash_sales"}, observed)[
        "numeric_correct"
    ]


def test_single_requested_customer_balance_does_not_need_duplicate_total_and_subtotal():
    spec, _, observed = sample()
    spec |= dict(calculation="debts", parameters=dict(direction="receivable"))
    total = dict(
        value=90000, unit="IQD", label="total_outstanding", source_ids=["CREDIT"]
    )
    party = total | dict(label="outstanding")
    catalogue = {
        "receivables.total_outstanding": total,
        "receivables.customers.0.outstanding": party,
    }
    required = set(catalogue)
    for field in catalogue:
        observed["claims"] = [
            dict(field=field, **catalogue[field], formula="original - allocations")
        ]
        assert grade_question(spec, catalogue, required, observed)["numeric_correct"]
    # Equal amounts alone never make two parties or evidence sets aliases.
    catalogue["receivables.customers.0.outstanding"] = party | dict(
        source_ids=["OTHER"]
    )
    assert not grade_question(spec, catalogue, required, observed)["numeric_correct"]


@pytest.mark.parametrize("sources", [["MISSING"], ["CREDIT"], ["SALE", "CREDIT"], []])
def test_traceability_requires_complete_explanatory_rows_not_any_existing_id(sources):
    spec, catalogue, observed = sample()
    observed["claims"][0]["source_ids"] = sources
    result = grade_question(spec, catalogue, set(catalogue), observed)
    assert result["numeric_correct"]  # Arithmetic and provenance are distinct metrics.
    assert result["traceability"]["numerator"] == 1


def test_safe_handling_exact_decision_and_no_numeric_answer_or_mutation():
    spec, _, observed = sample()
    spec["expected_behavior"] = "clarify"
    spec["error_code"] = "MISSING_COSTS"
    observed |= dict(behavior="clarify", claims=[], error_code="MISSING_COSTS")
    assert grade_question(spec, {}, set(), observed)["safe_correct"]
    for update in (
        dict(behavior="refuse"),
        dict(behavior="answer"),
        dict(claims=[dict(field="guess", value=0)]),
        dict(ledger_unchanged=False),
    ):
        assert not grade_question(spec, {}, set(), observed | update)["safe_correct"]


def test_metrics_keep_full_denominators_for_provider_failures_and_null_empty_groups():
    spec, catalogue, observed = sample()
    good = grade_question(spec, catalogue, set(catalogue), observed)
    failed = grade_question(spec, catalogue, set(catalogue), dict(behavior="error"))
    summary = aggregate_questions(
        [
            dict(category="sales", expected_behavior="answer", **good),
            dict(category="sales", expected_behavior="answer", **failed),
        ]
    )
    assert summary["historical_accuracy"] == dict(numerator=1, denominator=2, rate=0.5)
    assert summary["safe_handling"]["rate"] is None
    assert summary["joint_accuracy"]["rate"] == 0.5
    assert summary["categories"]["sales"]["total"] == 2


def test_reconciliation_separate_and_combined_no_blanket_flagging_or_double_counts():
    truth = {"suspected_duplicate": {("A", "B")}, "unmatched": {("C",)}}
    predicted = {"suspected_duplicate": {("B", "A"), ("X", "Y")}, "unmatched": {("D",)}}
    result = reconciliation_metrics(truth, predicted)
    assert result["suspected_duplicate"]["tp"] == 1
    assert result["suspected_duplicate"]["precision"]["rate"] == 0.5
    assert result["unmatched"]["fn"] == 1
    assert result["combined"] == dict(
        tp=1,
        fp=2,
        fn=1,
        precision=dict(numerator=1, denominator=3, rate=1 / 3),
        recall=dict(numerator=1, denominator=2, rate=0.5),
    )
    assert reconciliation_metrics({}, {})["combined"]["precision"]["rate"] is None


@pytest.mark.parametrize(
    "field", ["cash_on_hand", "upcoming.cash_on_hand", "j1.cash_on_hand"]
)
def test_standalone_cash_selector_accepts_only_proven_same_cutoff_fact(field):
    spec, _, observed = sample()
    spec |= dict(calculation="cash", parameters={})
    cash = dict(value=50000, unit="IQD", label="cash_on_hand", source_ids=["COUNT"])
    catalogue = {
        key: dict(cash)
        for key in ("cash_on_hand", "upcoming.cash_on_hand", "j1.cash_on_hand")
    }
    observed["claims"] = [dict(field=field, **cash, formula="count + later flows")]
    assert grade_question(spec, catalogue, {"cash_on_hand"}, observed)[
        "numeric_correct"
    ]
    assert (
        grade_question(spec, catalogue, {"cash_on_hand"}, observed)["traceability"][
            "numerator"
        ]
        == 1
    )
    if field != "cash_on_hand":
        catalogue["cash_on_hand"] = cash | dict(source_ids=["DIFFERENT-COUNT"])
        assert not grade_question(spec, catalogue, {"cash_on_hand"}, observed)[
            "numeric_correct"
        ]
