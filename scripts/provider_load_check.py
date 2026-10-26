"""Opt-in provider reliability load check, without scoring or retained answer text.

One already approved public synthetic demo question is repeated through the real
app route on a temporary demo ledger. Default pacing is seven seconds between
turns, exceeding the five-second minimum and respecting the local ten/min limit.
No evaluation data, labels, expected answers, or forecast outcomes are loaded.
"""

import argparse
import asyncio
import json
import math
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]

import httpx  # noqa: E402
from demo_drill import QUESTION, CappedTransport  # noqa: E402

from app.agents.llm_client import LLMClient  # noqa: E402
from app.agents.messages_ar import text  # noqa: E402
from app.api.dependencies import llm_client  # noqa: E402
from app.config import get_settings, runtime_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas.chat import ChatResponse  # noqa: E402

MAX_REQUESTS = 55
QUESTIONS = (QUESTION,)


class SessionTransport(CappedTransport):
    """Request-scoped clients share a pool whose lifetime belongs to this driver."""

    async def aclose(self):
        pass


def latency_summary(rows):
    values = sorted(row["elapsed_ms"] for row in rows)
    if not values:
        return {"p50_ms": None, "p95_ms": None, "max_ms": None}
    return {
        "p50_ms": statistics.median(values),
        "p95_ms": values[math.ceil(len(values) * 0.95) - 1],
        "max_ms": values[-1],
    }


def outcome(response):
    if response.status_code != 200:
        return "raw_error", False
    try:
        body = ChatResponse.model_validate_json(response.content)
    except ValueError:
        return "raw_error", False
    if body.status == "answered":
        # The application verifier/renderer owns figure computation. Check its
        # public provenance envelope, without labels or expected numeric answers.
        provenance = bool(body.figures) and all(
            figure.source_ids and figure.formula for figure in body.figures
        )
        return ("answered" if provenance else "raw_error"), provenance
    if body.status == "llm_unavailable" and not body.figures and not body.metrics:
        for key in ("busy", "needs_internet"):
            if body.reply_ar == text(key):
                return key, True
    return "unexpected_outcome", False


async def run_check(
    *,
    request_cap,
    chat_turns=20,
    authorize_paid=False,
    minimum_interval_seconds=7,
    settings=None,
    inner=None,
    sleep=asyncio.sleep,
    progress=None,
):
    if not 1 <= request_cap <= MAX_REQUESTS or not 20 <= chat_turns <= 100:
        raise ValueError("Invalid load check bounds")
    if not 5 <= minimum_interval_seconds <= 60:
        raise ValueError("Invalid pacing")
    if not authorize_paid:
        raise ValueError("Explicit paid authorization required")
    settings = settings or runtime_settings()
    if (
        settings.llm_provider,
        settings.llm_model_id,
        settings.llm_fallback_provider,
        settings.llm_fallback_model_id,
    ) != ("gemini", "gemini-3.8-flash", "openai", "gpt-6-luna"):
        raise ValueError("Approved configured pair required")
    fake = isinstance(inner, httpx.MockTransport)
    transport = SessionTransport(
        inner or httpx.AsyncHTTPTransport(retries=0), cap=request_cap
    )
    result = {
        "actual_started_utc": datetime.now(UTC).isoformat(),
        "provider_mode": "recorded-fake-wire" if fake else "live-provider",
        "request_cap": request_cap,
        "requested_chats": chat_turns,
        "question_count": len(QUESTIONS),
        "minimum_interval_seconds": minimum_interval_seconds,
        "chat_receipts": [],
        "stopped_reason": None,
    }
    overrides = dict(app.dependency_overrides)
    try:
        with tempfile.TemporaryDirectory(
            prefix="shgad-provider-load-fictional-"
        ) as folder:
            settings = settings.model_copy(
                update={
                    "app_env": "test",
                    "business_as_of": date(2026, 9, 28),
                    "database_url": "sqlite:///"
                    + str(Path(folder) / "synthetic.sqlite"),
                }
            )
            app.dependency_overrides[get_settings] = lambda: settings

            async def client():
                async with LLMClient(
                    settings,
                    transport=transport,
                    attempt_observer=transport.record_attempt,
                ) as provider:
                    yield provider

            app.dependency_overrides[llm_client] = client
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://127.0.0.1",
                timeout=150,
            ) as api:
                reset = await api.post("/api/demo/reset")
                if reset.status_code != 200:
                    raise ValueError("Synthetic setup failed")
                consecutive_failures = 0
                for turn in range(chat_turns):
                    if transport.attempts >= request_cap:
                        result["stopped_reason"] = "request_cap"
                        break
                    if turn:
                        await sleep(minimum_interval_seconds)
                    first_attempt = len(transport.receipts)
                    started = time.monotonic()
                    response = await api.post(
                        "/api/chat",
                        json={
                            "message": QUESTIONS[turn % len(QUESTIONS)],
                            "conversation_id": f"provider-load-{turn}",
                        },
                    )
                    elapsed = max(0, round((time.monotonic() - started) * 1000))
                    kind, provenance = outcome(response)
                    row = {
                        "turn": turn + 1,
                        "http_status": response.status_code,
                        "outcome": kind,
                        "elapsed_ms": elapsed,
                        "provenance_ok": provenance,
                        "fallback_used": any(
                            item["provider"] == settings.llm_fallback_provider
                            for item in transport.receipts[first_attempt:]
                        ),
                    }
                    result["chat_receipts"].append(row)
                    if progress is not None:
                        progress(dict(row))
                    consecutive_failures = (
                        0 if kind == "answered" else consecutive_failures + 1
                    )
                    if transport.blocked:
                        result["stopped_reason"] = "request_cap"
                        break
                    if consecutive_failures == 2:
                        result["stopped_reason"] = "two_consecutive_failed_chats"
                        break
    except Exception as error:
        result["failure_type"] = type(error).__name__
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides)
        await transport.inner.aclose()
    result.update(
        actual_finished_utc=datetime.now(UTC).isoformat(),
        completed_chats=len(result["chat_receipts"]),
        request_attempts=transport.attempts,
        paid_requests=0 if fake else transport.attempts,
        provider_receipts=transport.receipts,
        outcomes=dict(Counter(row["outcome"] for row in result["chat_receipts"])),
        latency=latency_summary(result["chat_receipts"]),
        fallback_chats=sum(row["fallback_used"] for row in result["chat_receipts"]),
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--authorize-paid", action="store_true")
    parser.add_argument(
        "--request-cap",
        type=int,
        choices=range(1, MAX_REQUESTS + 1),
        default=MAX_REQUESTS,
    )
    parser.add_argument("--chat-turns", type=int, choices=range(20, 101), default=20)
    parser.add_argument(
        "--minimum-interval-seconds", type=int, choices=range(5, 61), default=7
    )
    parser.add_argument("--progress", action="store_true")
    args = parser.parse_args(argv)
    if args.plan:
        print(
            json.dumps(
                {
                    "requests": 0,
                    "credentials_loaded": False,
                    "request_cap": args.request_cap,
                    "chat_turns": args.chat_turns,
                    "question_count": len(QUESTIONS),
                    "minimum_interval_seconds": args.minimum_interval_seconds,
                    "scope": "repeated approved demo question; no scoring",
                }
            )
        )
        return 0
    if not args.authorize_paid:
        parser.error("live checks require --authorize-paid")
    result = asyncio.run(
        run_check(
            request_cap=args.request_cap,
            chat_turns=args.chat_turns,
            authorize_paid=args.authorize_paid,
            minimum_interval_seconds=args.minimum_interval_seconds,
            progress=(lambda row: print(json.dumps(row), file=sys.stderr, flush=True))
            if args.progress
            else None,
        )
    )
    result["code_commit"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    print(json.dumps(result, indent=2))
    return int(
        bool(result.get("failure_type"))
        or result["completed_chats"] != args.chat_turns
        or any(
            row["outcome"] not in {"answered", "busy", "needs_internet"}
            for row in result["chat_receipts"]
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
