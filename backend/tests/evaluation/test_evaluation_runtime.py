"""Real production tools/renderer against observed dev data, synthetic wire only."""

import asyncio
import json
from dataclasses import fields
from datetime import date
from pathlib import Path

import httpx
import pytest
from scripts.evaluation_clients import BudgetedClient, ReplayClient
from scripts.evaluation_metrics import grade_question
from scripts.evaluation_runtime import (
    PromptInput,
    observe,
    observed_history,
    production_database,
    reference_parties,
)
from scripts.evaluation_truth import claim_catalogue, required_fields

from app.config import Settings

ROOT = Path(__file__).resolve().parents[3]


def test_blind_runtime_has_no_spec_answer_or_expected_context_channel():
    assert {f.name for f in fields(PromptInput)} == {"question", "business_as_of"}


def test_development_replay_uses_real_tools_independent_truth_and_no_gold_in_messages():
    replay = json.loads(
        (Path(__file__).parent / "fixtures/evaluation_replay.json").read_text(
            encoding="utf-8"
        )
    )
    questions = [
        json.loads(line)
        for line in (ROOT / "data/evaluation/development_questions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    client = ReplayClient()
    for question in questions:
        if question["id"] not in replay["cases"]:
            continue
        client.begin_question(replay["cases"][question["id"]])
        as_of = date.fromisoformat(question["business_as_of"])
        history = observed_history(question["dataset"], as_of, ROOT / "data")
        with production_database(
            history, reference_parties(ROOT / "data"), as_of=as_of
        ) as db:
            observed = asyncio.run(
                observe(
                    PromptInput(question["question_ar"], str(as_of)),
                    client=client,
                    connection=db,
                )
            )
        spec = question["spec"]
        period = spec["resolved_period"] or dict(start=str(as_of), end=str(as_of))
        catalogue = claim_catalogue(
            history,
            as_of,
            date.fromisoformat(period["start"]),
            date.fromisoformat(period["end"]),
            parties=spec["counterparty_ids"],
            parameters=spec["parameters"],
        )
        result = grade_question(
            spec, catalogue, required_fields(spec, catalogue), observed
        )
        assert (
            result["numeric_correct"]
            if spec["expected_behavior"] == "answer"
            else result["safe_correct"]
        )
        assert result["joint_correct"] and observed["ledger_unchanged"]
        assert (
            result["traceability"]["numerator"] == result["traceability"]["denominator"]
        )
    encoded = json.dumps(client.messages)
    for private in (
        "expected_behavior",
        "counterparty_ids",
        "calculation",
        "parameters",
        "resolved_period",
        "arabic_review",
        "DEV-001",
    ):
        assert private not in encoded
    assert client.receipt()["provider_requests"] == 0


def test_actual_retry_and_fallback_attempts_share_hard_global_and_question_limits():
    attempts = []

    def respond(request):
        attempts.append(request)
        return httpx.Response(429)

    async def no_sleep(_):
        pass

    async def exercise():
        async with BudgetedClient(
            Settings(
                llm_provider="gemini",
                llm_model_id="synthetic-primary",
                gemini_api_key="fake",
                llm_fallback_provider="openai",
                llm_fallback_model_id="synthetic-fallback",
                openai_api_key="fake",
            ),
            max_requests=3,
            per_question=2,
            spacing_seconds=0,
            sleep=no_sleep,
            transport=httpx.MockTransport(respond),
        ) as client:
            from app.agents.llm_client import LLMUnavailable

            for _ in range(2):
                client.begin_question()
                with pytest.raises(LLMUnavailable):
                    await client.complete(
                        [dict(role="user", content="format sentinel")]
                    )
            assert client.receipt()["provider_requests"] == 3
            assert client.receipt()["http_status_counts"] == {"429": 3}

    asyncio.run(exercise())
    assert len(attempts) == 3


def test_earlier_business_cutoff_keeps_opening_balance_known_at_that_cutoff():
    from scripts.make_ground_truth import TruthLedger, cutoff

    from app.services.business_clock import BusinessClock
    from app.services.financial_queries import QuerySnapshot

    as_of = date(2026, 7, 1)
    history = observed_history("small_happy_path", as_of, ROOT / "data")
    history = TruthLedger(
        [], opening=history.opening, categories=history.categories.values()
    )
    expected = history.cash(as_of)["amount_iqd"]
    with production_database(
        history, reference_parties(ROOT / "data"), as_of=as_of
    ) as db:
        snapshot = QuerySnapshot(db, clock=BusinessClock(as_of), known_at=cutoff(as_of))
        cash, _ = snapshot.cash()
        assert cash.amount_iqd == expected and expected > 0


def test_each_question_starts_primary_like_fresh_production_chat_client():
    sent = []

    def respond(request):
        sent.append(request.url.host)
        if len(sent) <= 2:
            return httpx.Response(429)
        content = '{"intent":"sales"}'
        if request.url.host == "api.openai.com":
            return httpx.Response(
                200,
                json=dict(
                    status="completed",
                    output=[
                        dict(
                            type="message",
                            role="assistant",
                            id="msg-sentinel",
                            status="completed",
                            content=[
                                dict(type="output_text", text=content, annotations=[])
                            ],
                        )
                    ],
                ),
            )
        return httpx.Response(
            200,
            json=dict(choices=[dict(message=dict(role="assistant", content=content))]),
        )

    async def no_sleep(_):
        pass

    async def exercise():
        async with BudgetedClient(
            Settings(
                llm_provider="gemini",
                llm_model_id="synthetic-primary",
                gemini_api_key="fictional-gemini-key",
                llm_fallback_provider="openai",
                llm_fallback_model_id="synthetic-fallback",
                openai_api_key="fictional-openai-key",
            ),
            max_requests=6,
            spacing_seconds=0,
            sleep=no_sleep,
            transport=httpx.MockTransport(respond),
        ) as client:
            client.begin_question()
            first = await client.complete(
                [dict(role="user", content="format sentinel")]
            )
            assert first.provider == "openai"
            client.begin_question()
            second = await client.complete(
                [dict(role="user", content="format sentinel")]
            )
            assert second.provider == "gemini"
            assert client.attempts == 4 and client.question_attempts == 1

    asyncio.run(exercise())


def test_probe_fallback_does_not_change_production_routing_or_reset_request_budget():
    sent = []

    def respond(request):
        sent.append(request.url.host)
        if len(sent) <= 2:
            return httpx.Response(429)
        if len(sent) == 3:
            return httpx.Response(
                200,
                json=dict(
                    status="completed",
                    output=[
                        dict(
                            type="message",
                            role="assistant",
                            id="msg-probe",
                            status="completed",
                            content=[
                                dict(
                                    type="output_text",
                                    text='{"intent":"sales"}',
                                    annotations=[],
                                )
                            ],
                        )
                    ],
                ),
            )
        if len(sent) == 4:
            message = dict(
                role="assistant",
                content=None,
                tool_calls=[
                    dict(
                        id="call-sentinel",
                        type="function",
                        function=dict(
                            name="get_sales",
                            arguments=json.dumps(dict(period="this_week", kind="cash")),
                        ),
                    )
                ],
            )
        else:
            message = dict(
                role="assistant",
                content=json.dumps(
                    dict(
                        status="answered",
                        draft_ar=(
                            "{{fig:cash_sales}} {{fig:unexplained_cash_difference}}"
                        ),
                    )
                ),
            )
        return httpx.Response(200, json=dict(choices=[dict(message=message)]))

    async def no_sleep(_):
        pass

    async def exercise():
        history = observed_history("primary", date(2026, 9, 28), ROOT / "data")
        with production_database(
            history, reference_parties(ROOT / "data"), as_of=date(2026, 9, 28)
        ) as db:
            async with BudgetedClient(
                Settings(
                    llm_provider="gemini",
                    llm_model_id="synthetic-primary",
                    gemini_api_key="fictional-gemini-key",
                    llm_fallback_provider="openai",
                    llm_fallback_model_id="synthetic-fallback",
                    openai_api_key="fictional-openai-key",
                ),
                max_requests=6,
                spacing_seconds=0,
                sleep=no_sleep,
                transport=httpx.MockTransport(respond),
            ) as client:
                client.begin_question()
                result = await observe(
                    PromptInput("شكد بعنا كاش هالأسبوع؟", "2026-09-28"),
                    client=client,
                    connection=db,
                )
                assert result["behavior"] == "answer" and result["tools"] == [
                    "get_sales"
                ]
                assert client.attempts == client.question_attempts == 5

    asyncio.run(exercise())
    assert (
        sent
        == ["generativelanguage.googleapis.com"] * 2
        + ["api.openai.com"]
        + ["generativelanguage.googleapis.com"] * 2
    )
