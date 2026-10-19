"""Recorded compatible-provider transport: bounded retries and no credential leaks."""

import asyncio
import json

import httpx
import pytest

from app.agents.llm_client import LLMClient, LLMUnavailable
from app.agents.tool_registry import definitions
from app.config import Settings


def settings(**extra):
    return Settings(
        llm_provider="gemini",
        llm_model_id="recorded-primary",
        gemini_api_key="synthetic-primary-secret",
        **extra,
    )


def answer(content='{"status":"refused","message_key":"unsupported_write"}'):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def run(handler, config=None, tools=()):
    async def scenario():
        delays = []

        async def sleep(delay):
            delays.append(delay)

        async with LLMClient(
            config or settings(), transport=httpx.MockTransport(handler), sleep=sleep
        ) as client:
            reply = await client.complete(
                [{"role": "user", "content": "fictional"}], tools=tools
            )
            return reply, delays

    return asyncio.run(scenario())


def test_429_backoff_then_success_with_identical_schemas():
    sent = []

    def respond(request):
        sent.append(json.loads(request.content))
        if len(sent) == 1:
            return httpx.Response(
                429, headers={"Retry-After": "2"}, json={"private": "ignored"}
            )
        return httpx.Response(200, json=answer())

    reply, delays = run(respond, tools=definitions())
    assert reply.provider == "gemini" and len(sent) == 2
    assert delays == [2] and sent[0]["tools"] == sent[1]["tools"] == list(definitions())


@pytest.mark.parametrize(
    "retry_after",
    ["999999", "99999999999999999999", " 60 ", "Fri, 31 Dec 9999 23:59:59 GMT"],
)
def test_long_retry_after_defers_provider_instead_of_retrying_early(retry_after):
    hosts = []

    def respond(request):
        hosts.append(request.url.host)
        if request.url.host == "generativelanguage.googleapis.com":
            return httpx.Response(429, headers={"Retry-After": retry_after})
        return httpx.Response(200, json=answer())

    reply, delays = run(
        respond,
        settings(
            llm_fallback_provider="groq",
            llm_fallback_model_id="recorded-fallback",
            groq_api_key="synthetic-fallback-secret",
        ),
    )
    assert reply.provider == "groq" and delays == []
    assert hosts == ["generativelanguage.googleapis.com", "api.groq.com"]


def test_bounded_retries_then_other_provider_without_changing_schemas():
    hosts = []
    bodies = []

    def respond(request):
        hosts.append(request.url.host)
        bodies.append(json.loads(request.content))
        if request.url.host == "generativelanguage.googleapis.com":
            return httpx.Response(503, text="synthetic-primary-secret")
        assert request.headers["Authorization"] == "Bearer synthetic-fallback-secret"
        return httpx.Response(200, json=answer())

    reply, delays = run(
        respond,
        settings(
            llm_fallback_provider="groq",
            llm_fallback_model_id="recorded-fallback",
            groq_api_key="synthetic-fallback-secret",
        ),
        definitions(),
    )
    assert hosts == ["generativelanguage.googleapis.com"] * 2 + ["api.groq.com"]
    assert len(delays) == 1 and reply.provider == "groq"
    assert all(body["tools"] == list(definitions()) for body in bodies)


def test_timeouts_are_bounded_and_sanitized():
    attempts = []

    def respond(request):
        attempts.append(request)
        raise httpx.ReadTimeout("synthetic-primary-secret", request=request)

    with pytest.raises(LLMUnavailable) as caught:
        run(respond)
    assert len(attempts) == 2 and "synthetic-primary-secret" not in str(caught.value)


@pytest.mark.parametrize("status", [302, 400, 401, 403])
def test_nonretriable_errors_do_not_repeat_or_follow_redirects(status):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(
            status,
            text="synthetic-primary-secret",
            headers={"Location": "https://invalid.test"},
        )

    with pytest.raises(LLMUnavailable):
        run(respond)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "body",
    [
        {"choices": []},
        {"choices": [{"message": {"content": None, "tool_calls": 0}}]},
        answer("synthetic-primary-secret"),
    ],
)
def test_malformed_or_secret_echo_responses_fail_closed(body):
    with pytest.raises(LLMUnavailable):
        run(lambda request: httpx.Response(200, json=body))


def test_unconfigured_client_does_not_construct_network_requests():
    def forbidden(request):
        pytest.fail("unconfigured client sent a request")

    with pytest.raises(LLMUnavailable):
        run(forbidden, Settings())


def test_native_signature_and_calls_round_trip_as_data():
    call = {
        "id": "fake-call",
        "type": "function",
        "function": {"name": "get_sales", "arguments": '{"period":"today"}'},
        "extra_content": {"google": {"thought_signature": "synthetic-signature"}},
    }
    reply, _ = run(
        lambda request: httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [call],
                        }
                    }
                ]
            },
        )
    )
    assert reply.tool_calls[0].arguments == {"period": "today"}
    assert reply.message["tool_calls"] == [call]


def test_tool_arguments_reject_duplicate_json_keys():
    response = {
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "fake",
                            "type": "function",
                            "function": {
                                "name": "get_sales",
                                "arguments": '{"period":"today","period":"last_week"}',
                            },
                        }
                    ],
                }
            }
        ]
    }
    with pytest.raises(LLMUnavailable):
        run(lambda request: httpx.Response(200, json=response))


def test_total_timeout_bounds_a_provider_that_never_finishes_its_stream():
    attempts = []

    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.sleep(2)
            yield b"{}"

    def respond(request):
        attempts.append(request)
        return httpx.Response(200, stream=SlowStream())

    with pytest.raises(LLMUnavailable):
        run(respond, settings(llm_timeout_seconds=1))
    assert len(attempts) == 2


def test_fallback_stays_selected_for_the_rest_of_the_request():
    hosts = []

    def respond(request):
        hosts.append(request.url.host)
        return (
            httpx.Response(503)
            if request.url.host.startswith("generativelanguage")
            else httpx.Response(200, json=answer())
        )

    async def scenario():
        async def sleep(delay):
            pass

        async with LLMClient(
            settings(
                llm_fallback_provider="groq",
                llm_fallback_model_id="recorded-fallback",
                groq_api_key="synthetic-fallback-secret",
            ),
            transport=httpx.MockTransport(respond),
            sleep=sleep,
        ) as client:
            for _ in range(2):
                await client.complete([{"role": "user", "content": "fictional"}])

    asyncio.run(scenario())
    assert hosts == ["generativelanguage.googleapis.com"] * 2 + ["api.groq.com"] * 2
