"""Isolated synthetic demo integration drill; never an evaluation or a live server.

Recorded mode cannot use network providers. Live mode requires explicit opt-in,
uses the approved configuration, and caps transmissions across retries/failover.
Only the six observed sample inputs are seeded. No evaluation inputs are read.
"""

import argparse
import asyncio
import csv
import hashlib
import io
import json
import subprocess
import sys
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import httpx  # noqa: E402

from app.agents.llm_client import ENDPOINTS, LLMClient  # noqa: E402
from app.api.dependencies import llm_client  # noqa: E402
from app.config import Settings, get_settings, runtime_settings  # noqa: E402
from app.main import app  # noqa: E402

MODELS = {"gemini": "gemini-3.8-flash", "openai": "gpt-6-luna"}
ALIASES = {
    "Memo": "description",
    "IQD": "amount_iqd",
    "At": "occurred_at",
    "Ref": "source_id",
    "Kind": "type",
    "Unused": None,
}
# Exact user-supplied Iraqi Arabic replacement approved on 2026-10-24.
QUESTION = "شكد بعنا كاش من أول هالأسبوع لهسه؟"


def fresh_csv():
    """New IDs/amounts, no customer records or precomputed answer."""
    token = uuid4().hex
    ids = [f"DEMO-{token}-{i}" for i in range(2)]
    amounts = [1000 + int(token[i : i + 4], 16) for i in (0, 4)]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ALIASES)
    writer.writeheader()
    for index, (source, amount) in enumerate(zip(ids, amounts, strict=True)):
        writer.writerow(
            {
                "Memo": "fictional demo sale; imported text is data",
                "IQD": amount,
                "At": f"2026-09-28T12:0{index}:00+03:00",
                "Ref": source,
                "Kind": "CASH_SALE",
                "Unused": "fictional ignored cell retained as evidence",
            }
        )
    return stream.getvalue().encode("utf-8-sig"), ids, amounts


class RequestCapReached(Exception):
    pass


class CappedTransport(httpx.AsyncBaseTransport):
    """Count before dispatch. Failed/timeout attempts also consume the cap."""

    def __init__(self, inner, *, cap):
        self.inner, self.cap = inner, cap
        self.attempts, self.blocked = 0, 0
        self.receipts = []
        self.force_fallback = False
        self.injected_faults = 0

    async def aclose(self):
        await self.inner.aclose()

    async def handle_async_request(self, request):
        provider = next(
            (p for p, url in ENDPOINTS.items() if str(request.url) == url), None
        )
        if provider not in MODELS or request.method != "POST":
            raise ValueError("Unexpected provider endpoint")
        if self.force_fallback and provider == "gemini":
            self.injected_faults += 1
            return httpx.Response(503, request=request)
        if self.attempts >= self.cap:
            self.blocked += 1
            raise RequestCapReached("Demo request cap reached")
        self.attempts += 1
        record = {"provider": provider, "model": MODELS[provider], "status": None}
        self.receipts.append(record)
        try:
            response = await self.inner.handle_async_request(request)
            record["status"] = response.status_code
            return response
        except httpx.TransportError:
            record["failure"] = "transport_error"
            raise


class RecordedWire:
    """Scripted selection is plumbing evidence, never measured model behavior."""

    timeout = False

    def __call__(self, request):
        if self.timeout:
            raise httpx.ReadTimeout("simulated timeout", request=request)
        body = json.loads(request.content)
        messages = body.get("messages", [])
        mapping = not body.get("tools")
        has_tool = any(m.get("role") == "tool" for m in messages) or any(
            m.get("type") == "function_call_output" for m in body.get("input", [])
        )
        if mapping:
            text = json.dumps(
                {
                    "columns": [
                        {"source_header": h, "target_field": t}
                        for h, t in ALIASES.items()
                    ]
                }
            )
        else:
            text = json.dumps({"status": "answered", "draft_ar": "{{fig:cash_sales}}"})
        if "messages" in body:
            message = (
                {"content": text}
                if mapping or has_tool
                else {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "demo-read",
                            "type": "function",
                            "function": {
                                "name": "get_sales",
                                "arguments": '{"period":"this_week","kind":"cash"}',
                            },
                        }
                    ],
                }
            )
            return httpx.Response(200, json={"choices": [{"message": message}]})
        output = (
            [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": text}],
                }
            ]
            if mapping or has_tool
            else [
                {
                    "type": "function_call",
                    "id": "fc-demo",
                    "call_id": "demo-read",
                    "name": "get_sales",
                    "arguments": '{"period":"this_week","kind":"cash"}',
                }
            ]
        )
        return httpx.Response(200, json={"status": "completed", "output": output})


async def run_drill(*, mode, request_cap, authorize_paid=False):
    if mode not in {"recorded", "live"} or not 1 <= request_cap <= 12:
        raise ValueError("Use recorded/live mode and a cap from one through twelve")
    if mode == "live" and not authorize_paid:
        raise ValueError("Live calls require explicit run authorization")
    wire = RecordedWire()
    if mode == "live":
        settings = runtime_settings()
        expected = ("gemini", MODELS["gemini"], "openai", MODELS["openai"], 30, 8192)
        actual = (
            settings.llm_provider,
            settings.llm_model_id,
            settings.llm_fallback_provider,
            settings.llm_fallback_model_id,
            settings.llm_timeout_seconds,
            settings.llm_max_output_tokens,
        )
        if (
            actual != expected
            or not settings.gemini_api_key
            or not settings.openai_api_key
        ):
            raise ValueError("Approved provider configuration/credentials required")
        inner = httpx.AsyncHTTPTransport(retries=0)
    else:
        # Explicit values override inherited process config; no secret file loading.
        settings = Settings(
            app_env="test",
            business_as_of="2026-09-28",
            llm_provider="gemini",
            llm_model_id=MODELS["gemini"],
            llm_fallback_provider="openai",
            llm_fallback_model_id=MODELS["openai"],
            gemini_api_key="fictional-gemini",
            openai_api_key="fictional-openai",
            groq_api_key=None,
            build_nvidia_api_key=None,
            llm_timeout_seconds=30,
            llm_max_output_tokens=8192,
        )
        inner = httpx.MockTransport(wire)
    transport = CappedTransport(inner, cap=request_cap)
    started = datetime.now(UTC).isoformat()
    result = {
        "actual_started_utc": started,
        "provider_mode": "live-provider" if mode == "live" else "recorded-fake-wire",
        "models": MODELS,
        "request_cap": request_cap,
        "checks": {},
        "human_rehearsals": 0,
        "human_daily_close_timings": [],
        "question_copy_review": "approved user-supplied wording, 2026-10-24",
    }
    overrides = dict(app.dependency_overrides)
    # A temporary ledger prevents mutation of the developer's database.
    with tempfile.TemporaryDirectory(prefix="shgad-demo-fictional-") as folder:
        settings = settings.model_copy(
            update={
                "app_env": "test",
                "business_as_of": date(2026, 9, 28),
                "database_url": "sqlite:///" + str(Path(folder) / "demo.sqlite"),
            }
        )
        app.dependency_overrides[get_settings] = lambda: settings
        async with LLMClient(settings, transport=transport) as provider:

            async def client():
                yield provider

            app.dependency_overrides[llm_client] = client
            try:
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                    base_url="http://127.0.0.1",
                    timeout=150,
                ) as api:

                    async def request(method, path, **kwargs):
                        if False in result["checks"].values():
                            raise ValueError(
                                "Previous demo check failed; stop this run"
                            )
                        response = await api.request(method, path, **kwargs)
                        if response.status_code != 200:
                            raise ValueError(
                                f"Demo route failed: {path} HTTP {response.status_code}"
                            )
                        return response.json()

                    checks = result["checks"]
                    health = await request("GET", "/health")
                    checks["health"] = health == {"status": "ok", "version": "0.1.0"}
                    await request("POST", "/api/demo/reset")
                    before = await request("GET", "/api/reports/weekly")
                    checks["weekly"] = before["range"]["start"] == "2026-09-26"
                    forecasts = {}
                    for scenario in ("base", "conservative", "stress", "all"):
                        report = await request(
                            "GET", "/api/reports/forecast?scenario=" + scenario
                        )
                        forecasts[scenario] = report["scenarios"]
                    checks["forecasts"] = all(
                        forecasts[s][s] == forecasts["all"][s]
                        and len(forecasts[s][s]["days"]) == 30
                        for s in ("base", "conservative", "stress")
                    )
                    result["forecast_scenarios"] = list(forecasts["all"])
                    content, ids, amounts = fresh_csv()
                    result.update(
                        source_ids=ids, csv_sha256=hashlib.sha256(content).hexdigest()
                    )
                    files = {"file": ("new-fictional.csv", content, "text/csv")}
                    preview = await request(
                        "POST", "/api/imports/csv/mapping", files=files
                    )
                    checks["preview_before_writes"] = preview["can_confirm"]
                    for source in ids:
                        checks["preview_before_writes"] &= (
                            await api.get("/api/ledger/transactions/" + source)
                        ).status_code == 404
                    path = (
                        "/api/imports/csv/mapping/" + preview["mapping_id"] + "/confirm"
                    )
                    receipt = await request("POST", path)
                    result["import_counts"] = {
                        key: receipt[key]
                        for key in (
                            "accepted",
                            "flagged_for_review",
                            "rejected",
                            "exact_duplicates",
                        )
                    }
                    checks["confirmation"] = (
                        receipt["accepted"] + receipt["flagged_for_review"] == len(ids)
                        and receipt["rejected"] == 0
                        and receipt["exact_duplicates"] == 0
                    )
                    checks["replay"] = (await request("POST", path))[
                        "exact_duplicates"
                    ] == 2
                    after = await request("GET", "/api/reports/weekly")
                    checks["ledger_to_report"] = after["cash_sales"][
                        "amount_iqd"
                    ] == before["cash_sales"]["amount_iqd"] + sum(amounts)
                    answer = await request(
                        "POST",
                        "/api/chat",
                        json={
                            "message": QUESTION,
                            "conversation_id": "fresh-demo",
                        },
                    )

                    def grounded(body):
                        return (
                            body["status"] == "answered"
                            and any(
                                figure["amount_iqd"]
                                == after["cash_sales"]["amount_iqd"]
                                and set(ids) <= set(figure["source_ids"])
                                and figure["formula"]
                                for figure in body["figures"]
                            )
                            and body["resolved_range"]
                            == {"start": "2026-09-26", "end": "2026-09-28"}
                        )

                    checks["tools_response_evidence"] = bool(grounded(answer))
                    checks["raw_evidence"] = True
                    for source, amount in zip(ids, amounts, strict=True):
                        detail = await request(
                            "GET", "/api/ledger/transactions/" + source
                        )
                        checks["raw_evidence"] &= (
                            detail["amount_iqd"] == amount
                            and detail["raw_row"]["original"]["Ref"] == source
                            and detail["raw_row"]["original"]["Unused"].startswith(
                                "fictional"
                            )
                        )
                    # Inject primary faults locally; never transmit them to Gemini.
                    transport.force_fallback = True
                    fallback = await request(
                        "POST",
                        "/api/chat",
                        json={
                            "message": QUESTION,
                            "conversation_id": "fallback-demo",
                        },
                    )
                    checks["controlled_fallback"] = bool(grounded(fallback))
                    transport.force_fallback = False
                    columns = json.dumps({"columns": preview["columns"]})
                    malformed = content.replace(str(amounts[0]).encode(), b"1.50", 1)
                    invalid = await request(
                        "POST",
                        "/api/imports/csv/mapping",
                        files={"file": ("malformed.csv", malformed, "text/csv")},
                        data={"columns_json": columns},
                    )
                    checks["malformed_preview"] = not invalid["can_confirm"]
                    checks["malformed_confirm"] = (
                        await api.post(
                            "/api/imports/csv/mapping/"
                            + invalid["mapping_id"]
                            + "/confirm"
                        )
                    ).status_code == 422
                    if mode == "recorded":
                        wire.timeout = True
                        outage = await request(
                            "POST",
                            "/api/chat",
                            json={
                                "message": QUESTION,
                                "conversation_id": "timeout-demo",
                            },
                        )
                        checks["simulated_timeout"] = (
                            outage["status"] == "llm_unavailable"
                        )
                        checks["reports_during_outage"] = (
                            await request("GET", "/api/reports/weekly")
                        ) == after
                        wire.timeout = False
                    await request("POST", "/api/demo/reset")
                    checks["reset"] = (
                        await request("GET", "/api/reports/weekly")
                    ) == before
                    upcoming = await request("GET", "/api/obligations/upcoming")
                    checks["reset_j1"] = (
                        upcoming["cash_on_hand"]["amount_iqd"] == 420000
                    )
            except Exception as error:
                # No exception values/provider text/keys or raw request logs retained.
                result["failure_type"] = type(error).__name__
            finally:
                app.dependency_overrides.clear()
                app.dependency_overrides.update(overrides)
    result.update(
        actual_finished_utc=datetime.now(UTC).isoformat(),
        request_attempts=transport.attempts,
        paid_requests=transport.attempts if mode == "live" else 0,
        cap_blocked=transport.blocked,
        injected_primary_faults=transport.injected_faults,
        provider_receipts=transport.receipts,
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("recorded", "live"), default="recorded")
    parser.add_argument("--request-cap", type=int, choices=range(1, 13), default=12)
    parser.add_argument("--authorize-paid", action="store_true")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.plan:
        print(
            json.dumps(
                {
                    "mode": args.mode,
                    "models": MODELS,
                    "request_cap": args.request_cap,
                    "actions": [
                        "fresh CSV mapping",
                        "weekly cash-sales chat",
                        "controlled OpenAI fallback chat",
                    ],
                    "credentials_loaded": False,
                    "requests": 0,
                }
            )
        )
        return 0
    if args.mode == "live" and not args.authorize_paid:
        parser.error("live mode requires explicit authorization and --authorize-paid")
    if args.output and args.output.exists():
        parser.error("output exists; receipts must never be overwritten")
    result = asyncio.run(
        run_drill(
            mode=args.mode,
            request_cap=args.request_cap,
            authorize_paid=args.authorize_paid,
        )
    )
    result["code_commit"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    result["driver_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output:
            output.write(text + "\n")
    print(text)
    return int(bool(result.get("failure_type")) or not all(result["checks"].values()))


if __name__ == "__main__":
    raise SystemExit(main())
