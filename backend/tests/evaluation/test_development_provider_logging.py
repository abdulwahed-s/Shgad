"""Development transport metadata is isolated from grading and model inputs."""

import asyncio
import copy
import json
from pathlib import Path

import httpx
import pytest
from scripts import dev_eval_v3
from scripts.evaluation_clients import BudgetedClient
from scripts.evaluation_metrics import aggregate_questions

from app.agents.llm_client import LLMUnavailable
from app.config import Settings

ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.pipeline("interpretation")


def settings(*, fallback=True):
    return Settings(
        _env_file=None,
        llm_provider="gemini",
        llm_model_id="synthetic-primary",
        gemini_api_key="fictional-primary-secret",
        llm_fallback_provider="openai" if fallback else None,
        llm_fallback_model_id="synthetic-fallback" if fallback else None,
        openai_api_key="fictional-fallback-secret" if fallback else None,
    )


async def no_sleep(_):
    pass


def client_for(handler, *, fallback=True, max_requests=20):
    return BudgetedClient(
        settings(fallback=fallback),
        max_requests=max_requests,
        spacing_seconds=0,
        sleep=no_sleep,
        transport=httpx.MockTransport(handler),
    )


def test_each_actual_retry_and_fallback_has_provider_status_and_question_ordinal():
    statuses = iter((503, 402, 401))

    def respond(_):
        return httpx.Response(
            next(statuses),
            headers={"X-Private-Sentinel": "private-header"},
            text="private-error-body",
        )

    async def exercise():
        async with client_for(respond) as client:
            client.begin_question()
            with pytest.raises(LLMUnavailable):
                await client.complete([{"role": "user", "content": "private-prompt"}])
            receipt = client.question_receipt()
            assert receipt == {
                "attempt_count": 3,
                "attempts": [
                    {"attempt": 1, "provider": "gemini", "http_status": 503},
                    {"attempt": 2, "provider": "gemini", "http_status": 402},
                    {"attempt": 3, "provider": "openai", "http_status": 401},
                ],
            }
            assert client.receipt()["provider_requests"] == 3
            client.begin_question()
            assert client.question_receipt() == {"attempt_count": 0, "attempts": []}
            assert receipt["attempt_count"] == 3  # Detached from mutable state.
            encoded = json.dumps(receipt)
            assert "private" not in encoded and "secret" not in encoded

    asyncio.run(exercise())


@pytest.mark.parametrize(
    ("failure", "status"), [("before_headers", None), ("body", 200)]
)
def test_http_status_survives_body_failure_but_is_null_without_headers(failure, status):
    def respond(request):
        if failure == "before_headers":
            raise httpx.ReadTimeout("private-timeout", request=request)
        return httpx.Response(200, text="private-invalid-json-body")

    async def exercise():
        async with client_for(respond, fallback=False) as client:
            client.begin_question()
            with pytest.raises(LLMUnavailable):
                await client.complete([{"role": "user", "content": "sentinel"}])
            assert client.question_receipt() == {
                "attempt_count": 1,
                "attempts": [
                    {"attempt": 1, "provider": "gemini", "http_status": status}
                ],
            }

    asyncio.run(exercise())


def test_budget_block_is_not_logged_as_an_http_attempt_or_carried_to_next_question():
    async def exercise():
        async with client_for(lambda _: httpx.Response(503), max_requests=1) as client:
            client.begin_question()
            with pytest.raises(LLMUnavailable):
                await client.complete([{"role": "user", "content": "sentinel"}])
            assert client.question_receipt()["attempt_count"] == 1
            client.begin_question()
            with pytest.raises(LLMUnavailable):
                await client.complete([{"role": "user", "content": "sentinel"}])
            assert client.question_receipt() == {"attempt_count": 0, "attempts": []}
            assert client.receipt()["provider_requests"] == 1

    asyncio.run(exercise())


def question(identifier):
    # Builder-authored transport sentinel, never read from a sealed/check split.
    return {
        "id": identifier,
        "category": "cash_on_hand",
        "question_ar": "شكد عندي كاش اليوم؟",
        "business_as_of": "2026-09-28",
        "dataset": "primary",
        "spec": {
            "intent": "cash_on_hand",
            "expected_behavior": "answer",
            "expected_tools": ["get_sales"],
            "counterparty_ids": [],
            "resolved_period": {"start": "2026-09-28", "end": "2026-09-28"},
            "parameters": {},
            "calculation": "cash_on_hand",
        },
    }


def test_runner_logging_preserves_all_grades_inputs_and_aggregate_only_policy():
    async def exercise(logging):
        transmitted = []
        client = None

        def respond(request):
            transmitted.append(json.loads(request.content))
            if client.question_attempts == 1:
                return httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": (
                                        '{"behavior":"answer","intent":"cash_on_hand"}'
                                    ),
                                }
                            }
                        ]
                    },
                )
            return httpx.Response(401, text="private-error")

        client = client_for(respond, fallback=False)
        if not logging:
            client.question_receipt = None
        questions = [question("LOG-001"), question("LOG-002"), question("SEALED-001")]
        questions[1]["dataset"] = "nonexistent_synthetic_fixture"
        async with client:
            rows = await dev_eval_v3.run(
                questions,
                {q["id"]: ["cash_on_hand"] for q in questions},
                client,
                ROOT / "data",
                withheld="SEALED-",
            )
        return rows, transmitted, client.receipt()

    plain, plain_inputs, plain_counts = asyncio.run(exercise(False))
    logged, logged_inputs, logged_counts = asyncio.run(exercise(True))
    assert logged_inputs == plain_inputs and logged_counts == plain_counts
    assert logged[0]["joint_correct"] and logged[2]["joint_correct"]
    assert logged[0]["provider_log"]["attempt_count"] == 2
    assert logged[1]["provider_log"] == {"attempt_count": 0, "attempts": []}
    assert "provider_log" not in logged[2]
    without_metadata = copy.deepcopy(logged)
    for row in without_metadata:
        row.pop("provider_log", None)
    assert without_metadata == plain
    assert aggregate_questions(logged) == aggregate_questions(plain)
