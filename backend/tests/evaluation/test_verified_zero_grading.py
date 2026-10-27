"""D56/roadmap §12.2: evaluator queries, never application attestations."""

from copy import deepcopy
from datetime import UTC, date

import pytest
from scripts.evaluation_evidence import METHOD_V2
from scripts.evaluation_metrics import compare_claim
from scripts.evaluation_truth import claim_catalogue
from scripts.make_ground_truth import TruthLedger, cutoff

DAY = date(2026, 9, 28)


def ledger(rows=()):
    result = TruthLedger(list(rows))
    result.evaluation_zero_coverage = (date(2026, 7, 1), DAY)
    return result


def claim():
    return dict(
        field="credit_sales",
        value=0,
        unit="IQD",
        label="credit_sales",
        source_ids=[],
        formula="sum of active credit sales in the resolved range",
        query_evidence=dict(
            tool="get_sales",
            period=dict(start=str(DAY), end=str(DAY)),
            filters=dict(
                event_types=["CREDIT_SALE"],
                active_only=True,
                known_at=cutoff(DAY).astimezone(UTC).isoformat(),
            ),
            matching_rows=0,
        ),
    )


def expected(history=None, start=DAY, end=DAY):
    return claim_catalogue(history or ledger(), DAY, start, end, method=METHOD_V2)[
        "credit_sales"
    ]


def test_independently_recomputed_empty_observed_selection_is_supported():
    assert compare_claim(expected(), claim(), method=METHOD_V2) == (True, True)


@pytest.mark.parametrize(
    "mutation",
    ["events", "active", "known", "period", "tool", "rows", "extra", "bool_rows"],
)
def test_wrong_closed_query_scope_is_unsupported(mutation):
    observed = claim()
    proof = observed["query_evidence"]
    if mutation == "events":
        proof["filters"]["event_types"] = ["CASH_SALE"]
    elif mutation == "active":
        proof["filters"]["active_only"] = False
    elif mutation == "known":
        proof["filters"]["known_at"] = "2026-09-27T20:59:59+00:00"
    elif mutation == "period":
        proof["period"]["start"] = "2026-09-27"
    elif mutation == "tool":
        proof["tool"] = "get_debts"
    elif mutation == "rows":
        proof["matching_rows"] = 1
    elif mutation == "bool_rows":
        proof["matching_rows"] = False
    else:
        proof["filters"]["counterparty_id"] = "FORGED"
    assert compare_claim(expected(), observed, method=METHOD_V2) == (True, False)


@pytest.mark.parametrize(
    "start,end", [(date(2026, 6, 30), DAY), (DAY, date(2026, 9, 29))]
)
def test_zero_outside_observed_coverage_is_unsupported(start, end):
    observed = claim()
    observed["query_evidence"]["period"] = dict(start=str(start), end=str(end))
    assert (
        compare_claim(expected(start=start, end=end), observed, method=METHOD_V2)[1]
        is False
    )


def test_app_proof_without_independent_query_never_receives_credit():
    forged = dict(value=0, unit="IQD", label="credit_sales", source_ids=[])
    forged["independent_zero"] = deepcopy(claim()["query_evidence"])
    assert compare_claim(forged, claim(), method=METHOD_V2) == (True, False)


def test_missing_observed_coverage_is_not_an_empty_query():
    assert (
        compare_claim(expected(TruthLedger([])), claim(), method=METHOD_V2)[1] is False
    )


@pytest.mark.parametrize("amount", [0, 7])
def test_nonempty_rows_are_not_an_empty_query(amount):
    history = ledger(
        [
            dict(
                transaction_id="ROW",
                source_id="SOURCE",
                type="CREDIT_SALE",
                business_date=str(DAY),
                amount_iqd=amount,
                occurred_at=cutoff(DAY).isoformat(),
                recorded_at=cutoff(DAY).isoformat(),
                category_id=None,
                obligation_id="O",
                counterparty_id="PARTY",
                due_date=None,
            )
        ]
    )
    assert compare_claim(expected(history), claim(), method=METHOD_V2)[1] is False


def test_v1_grading_still_requires_nonempty_row_ids():
    assert compare_claim(expected(), claim()) == (True, False)
    assert compare_claim(
        dict(value=8, unit="IQD", label="sales", source_ids=["ROW"]),
        dict(value=8, unit="IQD", label="sales", source_ids=["ROW"], formula="sum"),
    ) == (True, True)


def test_reconciliation_mapping_recomputes_amount_and_exact_row_provenance():
    from pathlib import Path

    from scripts.evaluation_runtime import observed_history

    root = Path(__file__).resolve().parents[3]
    history = observed_history("primary", DAY, root / "data")
    start, end = date(2026, 9, 19), date(2026, 9, 25)
    old = claim_catalogue(history, DAY, start, end)
    new = claim_catalogue(history, DAY, start, end, method=METHOD_V2)
    assert "items.0.amount" not in old
    fact = new["items.0.amount"]
    assert fact["value"] == 180000 - 30000
    assert set(fact["source_ids"]) == {"DEMO-01-J1-CREDIT", "DEMO-01-00706"}
    observed = fact | dict(formula="original amount - active verified allocations")
    assert compare_claim(fact, observed, method=METHOD_V2) == (True, True)
    observed["source_ids"] = ["DEMO-01-J1-CREDIT"]
    assert compare_claim(fact, observed, method=METHOD_V2) == (True, False)
    observed = fact | dict(formula="sum", reconciliation_flag_id="FORGED")
    assert compare_claim(fact, observed, method=METHOD_V2) == (False, False)
