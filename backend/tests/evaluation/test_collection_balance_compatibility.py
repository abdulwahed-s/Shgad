"""A model's new intent must preserve the established overdue-balance answer."""

from datetime import date

import pytest
from test_interpretation_pipeline import ask, understood

pytestmark = pytest.mark.pipeline("interpretation")


def test_overdue_balance_with_amount_uses_original_plan_figures_and_sources():
    question = "اريد اشوف منو متأخر بتسديد دينه وشكد بقى عليه"
    baseline = ask(
        question, understood(intent="debts", overdue_only=True), as_of=date(2026, 8, 20)
    )
    candidate = ask(
        question, understood(intent="collection_priorities"), as_of=date(2026, 8, 20)
    )
    assert candidate.interpretation.intent == "debts"
    assert candidate.used_tools == baseline.used_tools == ("get_debts",)
    assert candidate.resolved_range == baseline.resolved_range
    assert candidate.figures == baseline.figures
    assert candidate.metrics == baseline.metrics
    assert candidate.collection_action is None


@pytest.mark.parametrize(
    ("question", "new_intent", "original"),
    [
        ("شكد عندي كاش اليوم؟", "daily_brief", {"intent": "cash_on_hand"}),
        ("اريد ملخص مبيعات اليوم", "daily_brief", {"intent": "sales"}),
        ("رتب مبيعات اليوم حسب الأصناف", "collection_priorities", {"intent": "sales"}),
        (
            "المجهز يطالبني بشكد باقي، شنو المتأخر؟",
            "collection_priorities",
            {"intent": "debts", "direction": "payable", "overdue_only": True},
        ),
        (
            "منو مو متأخر وشكد باقي عليه؟",
            "collection_priorities",
            {"intent": "debts", "overdue_only": False},
        ),
    ],
)
def test_mismatched_specialist_retries_to_existing_financial_route(
    question, new_intent, original
):
    baseline = ask(question, understood(**original))
    candidate = ask(question, understood(intent=new_intent), understood(**original))
    assert baseline.status == candidate.status == "answered"
    assert candidate.interpretation.intent == baseline.interpretation.intent
    assert candidate.used_tools == baseline.used_tools
    assert candidate.resolved_range == baseline.resolved_range
    assert candidate.figures == baseline.figures
    assert candidate.metrics == baseline.metrics
    assert candidate.collection_action is None
