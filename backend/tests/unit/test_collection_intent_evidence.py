"""New specialist intents cannot take over ordinary financial questions (D61)."""

import pytest

from app.agents.interpreter import parse


@pytest.mark.parametrize(
    "question",
    [
        "اريد اشوف منو متأخر بتسديد دينه وشكد بقى عليه",
        "منو متأخر وكم المبلغ الباقي؟",
        "أم نور متأخرة، شكد رصيدها؟",
        "Who is overdue and how much do they still owe?",
    ],
)
def test_overdue_balance_request_keeps_debts_even_if_model_selects_priorities(question):
    value = parse('{"behavior":"answer","intent":"collection_priorities"}', question)
    assert value is not None
    assert value.intent == "debts"
    assert value.overdue_only is True


@pytest.mark.parametrize(
    "question",
    [
        "منو لازم أطالبه؟",
        "منو متأخر بالدفع؟",
        "رتبلي المتأخرين وشكد بقى عليهم حتى أتابعهم",
        "Who should I follow up with and how much do they owe?",
    ],
)
def test_explicit_followup_or_priorities_request_can_use_collection_specialist(
    question,
):
    value = parse('{"behavior":"answer","intent":"collection_priorities"}', question)
    assert value is not None and value.intent == "collection_priorities"


@pytest.mark.parametrize(
    "intent", ["collection_priorities", "draft_reminder", "daily_brief"]
)
def test_new_intent_without_its_request_evidence_is_rejected(intent):
    value = parse(
        '{"behavior":"answer","intent":"' + intent + '"}', "شكد بعنا كاش اليوم؟"
    )
    assert value is None


@pytest.mark.parametrize(
    ("intent", "question"),
    [
        ("draft_reminder", "اكتبلي رسالة تذكير لأم نور"),
        ("draft_reminder", "ذكّر أبو حيدر بدينه"),
        ("daily_brief", "شنو عندي اليوم؟"),
        ("daily_brief", "شلون الوضع اليوم؟"),
        ("daily_brief", "اعرض ملخص الصبح"),
    ],
)
def test_new_request_evidence_is_sufficient_without_changing_old_intents(
    intent, question
):
    value = parse('{"behavior":"answer","intent":"' + intent + '"}', question)
    assert value is not None and value.intent == intent


def test_plain_debts_interpretation_is_unchanged():
    value = parse(
        '{"behavior":"answer","intent":"debts","overdue_only":true}',
        "منو متأخر وكم بقى عليه؟",
    )
    assert value is not None and value.intent == "debts" and value.overdue_only


@pytest.mark.parametrize(
    ("intent", "question"),
    [
        ("daily_brief", "شكد عندي كاش اليوم؟"),
        ("daily_brief", "اريد ملخص مبيعات اليوم"),
        ("daily_brief", "What is my cash balance today?"),
        ("collection_priorities", "رتب مبيعات اليوم حسب الأصناف"),
        ("collection_priorities", "Rank today's sales by product"),
        ("collection_priorities", "المجهز يطالبني بشكد باقي، شنو المتأخر؟"),
        ("collection_priorities", "منو مو متأخر وشكد باقي عليه؟"),
        ("collection_priorities", "Who is not overdue and how much do they owe?"),
    ],
)
def test_specialists_reject_specific_other_metrics_creditors_and_negated_overdue(
    intent, question
):
    assert parse('{"behavior":"answer","intent":"' + intent + '"}', question) is None
