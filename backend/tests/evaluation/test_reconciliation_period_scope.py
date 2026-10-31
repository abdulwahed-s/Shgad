"""D59 scope decision, 31 Oct 2026: explicit audits retain the frozen behavior."""

import asyncio
import json
from datetime import date, timedelta

import pytest
from scripts.evaluation_runtime import (
    observed_history,
    production_database,
    reference_parties,
)
from scripts.make_ground_truth import cutoff
from test_interpretation_pipeline import ROOT, Scripted, ask, understood

from app.agents import orchestrator, planner
from app.db.connection import connect_database
from app.db.migrations import apply_migrations
from app.schemas.chat import ChatRequest
from app.schemas.interpretation import Interpretation
from app.services.business_clock import BusinessClock
from app.services.demo_seed import restore_demo
from app.services.reconcile import reconciliation_report

pytestmark = pytest.mark.pipeline("interpretation")
BASELINE = ROOT / "backend/tests/fixtures/reconciliation_explicit_01ce749.json"


def plan_json(value):
    return {
        "intent": value.intent,
        "period": {"start": str(value.period.start), "end": str(value.period.end)},
        "parties": list(value.parties),
        "per_day": value.per_day,
        "calls": [
            {
                "name": call.name,
                "arguments": call.arguments,
                "clock": str(call.clock.today),
                "server_range": {
                    "start": str(call.server_range.start),
                    "end": str(call.server_range.end),
                }
                if call.server_range
                else None,
                "plan": call.plan,
                "party": call.party.model_dump(mode="json") if call.party else None,
            }
            for call in value.calls
        ],
    }


def test_explicit_period_plan_claims_and_template_equal_01ce749():
    baseline = json.loads(BASELINE.read_text("utf-8"))
    assert baseline["baseline_commit"] == "01ce749"
    as_of = date.fromisoformat(baseline["business_as_of"])
    history = observed_history("primary", as_of, ROOT / "data")
    with production_database(
        history, reference_parties(ROOT / "data"), as_of=as_of
    ) as db:
        decided = planner.plan(
            Interpretation.model_validate(baseline["interpretation"]),
            connection=db,
            clock=BusinessClock(as_of),
            known_at=cutoff(as_of),
        )
    assert plan_json(decided) == baseline["plan"]
    response = ask(
        baseline["question"], json.dumps(baseline["interpretation"]), as_of=as_of
    ).model_dump(mode="json")
    assert {key: response[key] for key in baseline["response"]} == baseline["response"]


@pytest.mark.parametrize(
    ("kind", "evidence", "start", "end"),
    [
        ("today", "اليوم", "2026-09-28", "2026-09-28"),
        ("yesterday", "امس", "2026-09-27", "2026-09-27"),
        ("this_week", "هالاسبوع", "2026-09-26", "2026-09-28"),
        ("last_month", "الشهر الماضي", "2026-08-01", "2026-08-31"),
    ],
)
def test_stated_periods_use_the_original_reconciliation_plan(
    kind, evidence, start, end
):
    as_of = date(2026, 9, 28)
    history = observed_history("primary", as_of, ROOT / "data")
    with production_database(
        history, reference_parties(ROOT / "data"), as_of=as_of
    ) as db:
        decided = planner.plan(
            Interpretation(
                behavior="answer",
                intent="reconciliation",
                time={"type": kind, "evidence": evidence},
            ),
            connection=db,
            clock=BusinessClock(as_of),
            known_at=cutoff(as_of),
        )
    assert decided.period.start.isoformat() == start
    assert decided.period.end.isoformat() == end
    assert decided.calls == (
        planner.Call(
            "reconcile",
            {"period": "explicit", "start_date": start, "end_date": end},
            BusinessClock(as_of),
            decided.period,
        ),
    )


@pytest.fixture
def sample_ledger():
    db = connect_database(":memory:")
    try:
        apply_migrations(db)
        restore_demo(db, clock=BusinessClock(date(2026, 9, 28)))
        yield db
    finally:
        db.close()


def test_no_period_drill_keeps_every_flag_and_daily_gap_with_sources(sample_ledger):
    ledger = sample_ledger
    as_of = date(2026, 9, 28)
    expected_flags = [
        flag.model_dump(mode="json")
        for flag in reconciliation_report(
            ledger, clock=BusinessClock(as_of), known_at=cutoff(as_of)
        ).flags
    ]
    selected = {
        row[0]
        for row in ledger.execute(
            "SELECT source_id FROM transactions WHERE business_date BETWEEN ? AND ?",
            ("2026-09-26", "2026-09-28"),
        )
    }
    expected_flags = [
        flag for flag in expected_flags if selected.intersection(flag["source_ids"])
    ]
    question = "اكو شي غريب بالحسابات لازم انتبهله؟"
    before = tuple(ledger.iterdump())
    response = asyncio.run(
        orchestrator.converse(
            ChatRequest(message=question, conversation_id="scope-drill"),
            client=Scripted(understood(intent="reconciliation")),
            connection=ledger,
            clock=BusinessClock(as_of),
            known_at=cutoff(as_of),
        )
    )
    assert tuple(ledger.iterdump()) == before
    assert response.status == "answered"
    assert response.interpretation.period.model_dump(mode="json") == {
        "start": "2026-09-26",
        "end": "2026-09-28",
    }
    figures = {figure.key: figure for figure in response.figures}
    assert len(expected_flags) == 2
    for index, flag in enumerate(expected_flags):
        figure = figures[f"tool_0.items.{index}.amount"]
        assert figure.amount_iqd == flag["amount"]["amount_iqd"]
        assert set(figure.source_ids) == set(flag["source_ids"])
        assert all(source in response.reply_ar for source in figure.source_ids)
    history = observed_history("primary", as_of, ROOT / "data")
    for index in range(3):
        expected = history.daily_close(
            date(2026, 9, 26) + timedelta(days=index), known_at=cutoff(as_of)
        )
        figure = figures[f"tool_0.cash_differences.{index}.amount"]
        assert figure.amount_iqd == expected["unexplained_difference_iqd"]
        assert set(figure.source_ids) == set(expected["source_ids"])
        assert all(source in response.reply_ar for source in figure.source_ids)
    assert len([key for key in figures if "cash_differences." in key]) == 3
    assert all(
        figure.source_ids or figure.query_evidence for figure in response.figures
    )
