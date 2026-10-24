"""§14: fresh synthetic input reaches real ledger/tools/rendering, with no network."""

import asyncio
import csv
import importlib.util
import io
from pathlib import Path

import httpx
import pytest


def module():
    path = Path(__file__).resolve().parents[3] / "scripts" / "demo_drill.py"
    spec = importlib.util.spec_from_file_location("demo_drill", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_recorded_drill_uses_new_input_real_services_and_restores_sample():
    drill = module()
    result = asyncio.run(drill.run_drill(mode="recorded", request_cap=12))
    assert "failure_type" not in result, result
    assert set(result["checks"]) == {
        "health",
        "weekly",
        "forecasts",
        "preview_before_writes",
        "confirmation",
        "replay",
        "ledger_to_report",
        "tools_response_evidence",
        "raw_evidence",
        "controlled_fallback",
        "malformed_preview",
        "malformed_confirm",
        "simulated_timeout",
        "reports_during_outage",
        "reset",
        "reset_j1",
    }
    assert result["provider_mode"] == "recorded-fake-wire"
    assert result["paid_requests"] == 0
    assert result["checks"] and all(result["checks"].values())
    assert result["forecast_scenarios"] == ["base", "conservative", "stress"]
    assert result["request_attempts"] <= 12
    assert result["source_ids"] and result["csv_sha256"]
    assert result["human_rehearsals"] == 0
    assert result["human_daily_close_timings"] == []


def test_cap_counts_every_attempt_and_blocks_before_transmission():
    drill = module()
    sent = []

    async def send(request):
        sent.append(request.url.host)
        return httpx.Response(429)

    async def run():
        transport = drill.CappedTransport(httpx.MockTransport(send), cap=2)
        async with httpx.AsyncClient(transport=transport) as client:
            for _ in range(2):
                assert (await client.post(drill.ENDPOINTS["gemini"])).status_code == 429
            with pytest.raises(drill.RequestCapReached):
                await client.post(drill.ENDPOINTS["gemini"])
        return transport

    transport = asyncio.run(run())
    assert len(sent) == transport.attempts == 2
    assert transport.blocked == 1


def test_live_requires_authorization_before_settings_or_network(monkeypatch):
    drill = module()

    def forbidden():
        pytest.fail("unauthorized run loaded runtime credentials")

    monkeypatch.setattr(drill, "runtime_settings", forbidden)
    with pytest.raises(ValueError, match="explicit"):
        asyncio.run(drill.run_drill(mode="live", request_cap=12))


def test_fresh_csv_is_different_each_time_and_has_unfamiliar_order():
    drill = module()
    first, second = drill.fresh_csv(), drill.fresh_csv()
    assert first[0] != second[0]
    assert first[1] != second[1]
    assert (
        first[0].decode("utf-8-sig").splitlines()[0].startswith("Memo,IQD,At,Ref,Kind")
    )


def test_valid_new_rows_flagged_as_similar_are_still_preserved(monkeypatch):
    """A valid random amount can coincide; flagged is distinct from rejected."""
    drill = module()
    content, ids, _ = drill.fresh_csv()
    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=drill.ALIASES)
    writer.writeheader()
    for row in rows:
        writer.writerow(row | {"IQD": "1237"})
    monkeypatch.setattr(
        drill, "fresh_csv", lambda: (stream.getvalue().encode(), ids, [1237, 1237])
    )
    result = asyncio.run(drill.run_drill(mode="recorded", request_cap=12))
    assert "failure_type" not in result, result
    assert all(result["checks"].values())
    assert result["import_counts"] == {
        "accepted": 1,
        "flagged_for_review": 1,
        "rejected": 0,
        "exact_duplicates": 0,
    }
