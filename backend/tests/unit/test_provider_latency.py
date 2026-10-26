"""D52 / roadmap §3.2a: bounded failover and sanitized attempt evidence."""

import asyncio
import json
import time
from datetime import UTC, datetime
from email.utils import format_datetime

import httpx
import pytest
from pydantic import ValidationError

from app.agents.llm_client import LLMClient
from app.agents.openai_protocol import request_payload
from app.config import Settings


def configuration(**updates):
    return Settings(
        llm_provider="gemini",
        llm_model_id="gemini-3.8-flash",
        llm_fallback_provider="openai",
        llm_fallback_model_id="gpt-6-luna",
        llm_timeout_seconds=30,
        gemini_api_key="fictional-gemini",
        openai_api_key="fictional-openai",
        **updates,
    )


def completion(provider):
    if provider == "gemini":
        return {"choices": [{"message": {"content": "OK"}}]}
    return {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "OK"}],
            }
        ],
    }


def scenario(handler, *, settings=None):
    async def run():
        delays, observed = [], []

        async def sleep(delay):
            delays.append(delay)

        async with LLMClient(
            settings or configuration(),
            transport=httpx.MockTransport(handler),
            sleep=sleep,
            attempt_observer=observed.append,
        ) as client:
            reply = await client.complete([{"role": "user", "content": "fictional"}])
            return reply, client.attempt_receipts, delays, observed

    return asyncio.run(run())


def test_primary_deadline_defaults_and_fallback_remains_thirty_seconds():
    settings = configuration()
    assert settings.llm_primary_timeout_seconds == 15
    assert settings.llm_timeout_seconds == 30
    deadlines = []

    def handler(request):
        deadlines.append(request.extensions["timeout"]["read"])
        if request.url.host == "generativelanguage.googleapis.com":
            return httpx.Response(401)
        return httpx.Response(200, json=completion("openai"))

    scenario(handler)
    assert deadlines == [15, 30]


@pytest.mark.parametrize("value", [4, 31])
def test_primary_deadline_rejects_out_of_range(value):
    with pytest.raises(ValidationError):
        configuration(llm_primary_timeout_seconds=value)


@pytest.mark.parametrize("value", [5, 30])
def test_primary_deadline_accepts_bounds(value):
    assert (
        configuration(llm_primary_timeout_seconds=value).llm_primary_timeout_seconds
        == value
    )


@pytest.mark.parametrize("kind", ["httpx", "deadline", "stream"])
def test_primary_timeout_immediately_falls_back_with_bounded_elapsed(kind):
    hosts = []

    class StalledStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.sleep(1)
            yield b"{}"

    async def handler(request):
        hosts.append(request.url.host)
        if request.url.host == "generativelanguage.googleapis.com":
            if kind == "httpx":
                raise httpx.ReadTimeout("fictional private detail")
            if kind == "stream":
                return httpx.Response(200, stream=StalledStream())
            await asyncio.sleep(1)
        await asyncio.sleep(0.01)
        return httpx.Response(200, json=completion("openai"))

    # Only the in-memory fake test uses a subsecond deadline; typed bounds stay 5–30.
    settings = configuration().model_copy(update={"llm_primary_timeout_seconds": 0.02})
    started = time.monotonic()
    reply, attempts, delays, observed = scenario(handler, settings=settings)
    assert time.monotonic() - started < 0.5
    assert hosts == ["generativelanguage.googleapis.com", "api.openai.com"]
    assert reply.provider == "openai" and delays == []
    assert [row["category"] for row in attempts] == ["timeout", "ok"]
    assert attempts == observed


@pytest.mark.parametrize("status", [401, 403])
def test_primary_auth_failure_immediately_falls_back(status):
    def handler(request):
        return (
            httpx.Response(status)
            if request.url.host == "generativelanguage.googleapis.com"
            else httpx.Response(200, json=completion("openai"))
        )

    reply, attempts, delays, _ = scenario(handler)
    assert reply.provider == "openai" and delays == []
    assert [row["category"] for row in attempts] == [f"http_{status}", "ok"]


@pytest.mark.parametrize("failure", [500, 502, 504, "transport"])
def test_other_retriable_failures_keep_one_retry_then_fallback(failure):
    def handler(request):
        if request.url.host == "generativelanguage.googleapis.com":
            if failure == "transport":
                raise httpx.ConnectError("fictional private detail")
            return httpx.Response(failure)
        return httpx.Response(200, json=completion("openai"))

    reply, attempts, delays, _ = scenario(handler)
    category = "transport" if failure == "transport" else f"http_{failure}"
    assert [row["category"] for row in attempts] == [category, category, "ok"]
    assert delays == [1] and reply.provider == "openai"


@pytest.mark.parametrize("header", [None, "invalid-date", "short-date"])
def test_missing_invalid_and_short_http_date_retry_after(header, monkeypatch):
    from app.agents import llm_client

    class FrozenDatetime:
        @staticmethod
        def now(zone):
            return datetime(2026, 10, 26, tzinfo=zone)

    monkeypatch.setattr(llm_client, "datetime", FrozenDatetime)
    if header == "short-date":
        header = format_datetime(datetime(2026, 10, 26, 0, 0, 2, tzinfo=UTC))
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(
                429, headers={} if header is None else {"Retry-After": header}
            )
        return httpx.Response(200, json=completion("gemini"))

    reply, attempts, delays, _ = scenario(handler)
    assert reply.provider == "gemini"
    assert delays == [2 if header and header != "invalid-date" else 1]
    assert [row["category"] for row in attempts] == ["http_429", "ok"]


def test_gemini_low_reasoning_and_openai_payload_unchanged():
    messages = [{"role": "user", "content": "fictional"}]
    payloads = []

    def handler(request):
        payloads.append(json.loads(request.content))
        if request.url.host == "generativelanguage.googleapis.com":
            return httpx.Response(401)
        return httpx.Response(200, json=completion("openai"))

    scenario(handler)
    assert payloads[0]["reasoning_effort"] == "low"
    assert payloads[1] == request_payload("gpt-6-luna", messages)
    assert payloads[1]["reasoning"] == {"effort": "medium"}


def test_malformed_attempt_receipt_is_sanitized_and_timed():
    def handler(request):
        if request.url.host == "generativelanguage.googleapis.com":
            return httpx.Response(200, content=b"fictional private provider body")
        return httpx.Response(200, json=completion("openai"))

    _, attempts, _, observed = scenario(handler)
    assert [row["category"] for row in attempts] == ["malformed", "ok"]
    for row in observed:
        assert set(row) == {"provider", "model", "status", "category", "elapsed_ms"}
        assert type(row["elapsed_ms"]) is int and row["elapsed_ms"] >= 0
    assert "fictional" not in json.dumps(attempts)


def test_conversation_cancellation_still_finalizes_attempt_receipt():
    async def handler(request):
        await asyncio.sleep(1)

    async def run():
        async with LLMClient(
            configuration(), transport=httpx.MockTransport(handler)
        ) as client:
            with pytest.raises(TimeoutError):
                async with asyncio.timeout(0.01):
                    await client.complete([{"role": "user", "content": "fictional"}])
            assert client.attempt_receipts[0]["category"] == "timeout"
            assert client.attempt_receipts[0]["elapsed_ms"] >= 0

    asyncio.run(run())
