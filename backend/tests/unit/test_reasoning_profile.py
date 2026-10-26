"""D53 comparison profiles change only the Gemini reasoning parameter."""

import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from app.agents.llm_client import LLMClient
from app.config import Settings


def test_reasoning_profile_defaults_to_low():
    assert Settings().gemini_reasoning_effort == "low"


@pytest.mark.parametrize("value", ["high", "medium", "none", "", 0])
def test_reasoning_profile_rejects_unsupported_values(value):
    with pytest.raises(ValidationError):
        Settings(gemini_reasoning_effort=value)


def test_process_reasoning_override_is_typed_and_file_free(monkeypatch):
    monkeypatch.setenv("GEMINI_REASONING_EFFORT", "default")
    assert Settings().gemini_reasoning_effort == "default"


@pytest.mark.parametrize("profile", ["low", "default"])
def test_gemini_profile_changes_only_reasoning_field(profile):
    sent = []

    def respond(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    async def run():
        async with LLMClient(
            Settings(
                llm_provider="gemini",
                llm_model_id="gemini-3.8-flash",
                gemini_api_key="fictional",
                gemini_reasoning_effort=profile,
            ),
            transport=httpx.MockTransport(respond),
        ) as client:
            await client.complete([{"role": "user", "content": "fictional"}])

    asyncio.run(run())
    assert (sent[0].get("reasoning_effort")) == ("low" if profile == "low" else None)
    assert sent[0]["model"] == "gemini-3.8-flash"
    assert sent[0]["messages"] == [{"role": "user", "content": "fictional"}]


def test_gemini_reasoning_profiles_leave_openai_wire_identical():
    sent = []

    def respond(request):
        sent.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": "OK"}],
                    }
                ],
            },
        )

    async def run():
        for profile in ("low", "default"):
            async with LLMClient(
                Settings(
                    llm_provider="openai",
                    llm_model_id="gpt-6-luna",
                    openai_api_key="fictional",
                    gemini_reasoning_effort=profile,
                ),
                transport=httpx.MockTransport(respond),
            ) as client:
                await client.complete([{"role": "user", "content": "fictional"}])

    asyncio.run(run())
    assert sent[0] == sent[1]
    assert sent[0]["reasoning"] == {"effort": "medium"}
    assert "reasoning_effort" not in sent[0]
