"""D52 load driver: real app/ledger/renderer with fake providers and no scoring."""

import asyncio
import importlib.util
import json
from importlib import import_module
from pathlib import Path

import httpx
import pytest

from app.config import Settings


def module():
    path = Path(__file__).resolve().parents[3] / "scripts/provider_load_check.py"
    spec = importlib.util.spec_from_file_location("provider_load_check", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def fake_settings(check):
    return Settings(
        app_env="test",
        llm_provider="gemini",
        llm_model_id="gemini-3.8-flash",
        llm_fallback_provider="openai",
        llm_fallback_model_id="gpt-6-luna",
        gemini_api_key="fictional-gemini",
        openai_api_key="fictional-openai",
    )


def test_load_plan_never_loads_credentials_or_sends_requests(monkeypatch, capsys):
    check = module()

    def forbidden(*args, **kwargs):
        pytest.fail("plan accessed credentials or network")

    monkeypatch.setattr(check, "runtime_settings", forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
    assert check.main(["--plan", "--request-cap", "55", "--chat-turns", "20"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["requests"] == 0 and result["credentials_loaded"] is False
    assert result["chat_turns"] == 20 and result["request_cap"] == 55


def test_load_requires_authorization_before_settings(monkeypatch):
    check = module()
    monkeypatch.setattr(check, "runtime_settings", lambda: pytest.fail("loaded keys"))
    with pytest.raises(ValueError, match="authorization"):
        asyncio.run(check.run_check(request_cap=55))


def test_load_hard_cap_counts_failed_attempts_and_never_overruns():
    check = module()
    sent = []

    def respond(request):
        sent.append(request)
        return httpx.Response(503)

    async def no_sleep(delay):
        pass

    result = asyncio.run(
        check.run_check(
            request_cap=1,
            authorize_paid=True,
            settings=fake_settings(check),
            inner=httpx.MockTransport(respond),
            sleep=no_sleep,
        )
    )
    assert len(sent) == result["request_attempts"] == 1
    assert result["stopped_reason"] == "request_cap"
    assert result["provider_receipts"][0]["category"] == "http_503"


def test_load_uses_twenty_real_app_chats_with_pacing_and_sanitized_receipts(
    monkeypatch,
):
    check = module()
    delays = []
    from app.api import request_safety

    clock = [0]
    monkeypatch.setattr(request_safety, "monotonic", lambda: clock[0])

    async def sleep(delay):
        delays.append(delay)
        clock[0] += delay

    result = asyncio.run(
        check.run_check(
            request_cap=55,
            authorize_paid=True,
            settings=fake_settings(check),
            inner=httpx.MockTransport(import_module("demo_drill").RecordedWire()),
            sleep=sleep,
        )
    )
    assert result["completed_chats"] == 20
    assert result["outcomes"] == {"answered": 20}
    assert result["request_attempts"] == 40
    # Seven seconds exceeds the requested minimum and respects the local 10/min cap.
    assert delays == [7] * 19
    assert all(row["http_status"] == 200 for row in result["chat_receipts"])
    assert all(row["provenance_ok"] for row in result["chat_receipts"])
    assert all(row["category"] == "ok" for row in result["provider_receipts"])
    assert "reply_ar" not in json.dumps(result)
    assert "fictional-gemini" not in json.dumps(result)


def test_load_stops_after_two_consecutive_unsuccessful_chats():
    check = module()

    async def sleep(delay):
        pass

    result = asyncio.run(
        check.run_check(
            request_cap=55,
            authorize_paid=True,
            settings=fake_settings(check),
            inner=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, json={"choices": [{"message": {"content": "{}"}}]}
                )
            ),
            sleep=sleep,
        )
    )
    assert result["completed_chats"] == 2
    assert result["stopped_reason"] == "two_consecutive_failed_chats"


def test_load_owns_transport_until_all_chat_clients_finish(monkeypatch):
    check = module()
    from app.api import request_safety

    clock = [0]
    monkeypatch.setattr(request_safety, "monotonic", lambda: clock[0])

    class ClosingWire(httpx.MockTransport):
        closed = False
        closes = 0

        async def handle_async_request(self, request):
            assert not self.closed, "used closed provider pool"
            return await super().handle_async_request(request)

        async def aclose(self):
            self.closed = True
            self.closes += 1

    wire = ClosingWire(import_module("demo_drill").RecordedWire())

    async def sleep(delay):
        clock[0] += delay

    result = asyncio.run(
        check.run_check(
            request_cap=55,
            authorize_paid=True,
            settings=fake_settings(check),
            inner=wire,
            sleep=sleep,
        )
    )
    assert result["outcomes"] == {"answered": 20}
    assert wire.closed and wire.closes == 1


@pytest.mark.parametrize("cap", [0, 56])
def test_load_rejects_invalid_cap_before_credentials(cap, monkeypatch):
    check = module()
    monkeypatch.setattr(check, "runtime_settings", lambda: pytest.fail("loaded keys"))
    with pytest.raises(SystemExit):
        check.main(["--plan", "--request-cap", str(cap)])
