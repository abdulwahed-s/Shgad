"""The opt-in drill is isolated and does not need credentials for its plan."""

import asyncio
import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.agents.llm_client import LLMReply, LLMUnavailable
from app.config import Settings


def test_collection_drill_plan_is_builder_only_and_ten_documented_demo_checks():
    from scripts.collection_drill import plan

    smoke, demo = plan()
    assert len(smoke) == 20 and len(demo) == 10
    assert all(q["authorship"] == "builder-written, not independent" for q in smoke)
    assert {q["surface"] for q in smoke} == {
        "chat",
        "draft",
        "brief",
        "collections",
        "reminder",
    }


def test_drill_outage_still_checks_j1_ledger_isolation_memory_and_missing_cash(
    tmp_path,
):
    from scripts.collection_drill import drill

    class Outage:
        def begin_question(self):
            pass

        async def complete(self, *args, **kwargs):
            raise LLMUnavailable("scripted_offline")

        def receipt(self):
            return {"provider_requests": 0}

    async def no_wait(*args):
        pass

    from app.api.request_safety import LIMITS

    # Only this no-wait outage test lifts the real HTTP limit; production uses
    # 6.1 seconds between chat starts and keeps the real middleware unchanged.
    with (
        patch("scripts.collection_drill.asyncio.sleep", no_wait),
        patch.dict(LIMITS, chat=100),
    ):
        report = asyncio.run(drill(tmp_path, Outage(), Settings(_env_file=None)))
    rows = json.loads((tmp_path / "responses.json").read_text("utf-8"))
    assert len(rows) == 30
    assert report["all_financial_tables_unchanged"]
    assert (
        report["j1_before"]
        == report["j1_after"]
        == [420000, 650000, 150000, -230000, -80000]
    )
    # Offline templates are not counted as live model success.
    assert report["builder_smoke_passed"] < 20
    assert next(r for r in rows if r["id"] == "CS-19")["passed"]
    assert next(r for r in rows if r["id"] == "CS-20")["passed"]
    assert all(Path(p).parent == tmp_path for p in tmp_path.glob("*.sqlite"))


@pytest.fixture(scope="module")
def scripted_smoke(tmp_path_factory):
    from scripts.collection_drill import drill, plan

    from app.api.request_safety import LIMITS, _windows

    class Scripted:
        index = 0
        call = 0

        def begin_question(self):
            self.index += 1
            self.call = 0

        async def complete(self, *args, **kwargs):
            self.call += 1
            intents = {
                1: ("collection_priorities", []),
                2: ("draft_reminder", ["أم نور"]),
                3: ("draft_reminder", ["أبو علي"]),
                4: ("draft_reminder", ["أبو مجهول"]),
                5: ("draft_reminder", ["أبو حيدر"]),
                6: ("draft_reminder", ["أم صفاء"]),
                7: ("draft_reminder", ["أم نور"]),
                9: ("daily_brief", []),
                10: ("daily_brief", []),
            }
            if self.index > 20:
                raise LLMUnavailable("scripted_demo_outage")
            if self.index in intents and self.call == 1:
                intent, mentions = intents[self.index]
                value = {
                    "behavior": "answer",
                    "intent": intent,
                    "party_mentions": mentions,
                }
            else:
                value = {
                    "body": "نذكّرك بالمبلغ {{fig:overdue_amount}}، "
                    "المستحق بتاريخ {{date:oldest_due}}."
                }
            return LLMReply(
                "scripted", "synthetic", json.dumps(value, ensure_ascii=False), (), {}
            )

        def receipt(self):
            return {"provider_requests": 0}

    async def no_wait(*args):
        pass

    output = tmp_path_factory.mktemp("scripted_collection_smoke")
    _windows.clear()
    with (
        patch("scripts.collection_drill.asyncio.sleep", no_wait),
        patch.dict(LIMITS, chat=100),
        patch("app.agents.orchestrator.DEFAULT_PIPELINE", "interpretation"),
    ):
        report = asyncio.run(drill(output, Scripted(), Settings(_env_file=None)))
    rows = json.loads((output / "responses.json").read_text("utf-8"))
    return plan()[0], rows, report


def test_smoke_grader_accepts_real_verified_scripted_responses(scripted_smoke):
    _, rows, report = scripted_smoke
    assert report["builder_smoke_passed"] == 20, [
        r["id"] for r in rows[:20] if not r["passed"]
    ]


@pytest.mark.parametrize(
    "case_id,mutation",
    [
        ("CS-01", "figures"),
        ("CS-02", "source"),
        ("CS-02", "due"),
        ("CS-02", "customer"),
        ("CS-02", "period"),
        ("CS-09", "brief"),
    ],
)
def test_smoke_grader_rejects_missing_or_wrong_evidence(
    scripted_smoke, case_id, mutation
):
    from scripts.collection_drill import check_smoke

    cases, rows, _ = scripted_smoke
    case = next(c for c in cases if c["id"] == case_id)
    row = next(r for r in rows if r["id"] == case_id)
    body = copy.deepcopy(row["response"])
    if mutation == "figures":
        body["figures"] = []
    elif mutation == "source":
        body["figures"][0]["source_ids"] = []
    elif mutation == "due":
        body["dates"].pop("oldest_due")
    elif mutation == "customer":
        body["resolved_counterparty"]["id"] = "CUST-05"
    elif mutation == "period":
        body["resolved_range"]["start"] = "2026-09-27"
    else:
        body["brief"]["dues_today"]["amount_iqd"] = 123
    assert not check_smoke(case, row["http_status"], body, row["endpoint_projection"])
