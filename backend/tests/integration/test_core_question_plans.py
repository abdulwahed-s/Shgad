"""FINANCIAL_RULES sections5/7: real tools/SQLite, fake provider only."""

import asyncio
import json
from datetime import date, datetime

import httpx
import pytest

from app.agents import orchestrator
from app.agents.llm_client import LLMClient
from app.agents.tool_registry import invoke
from app.config import Settings
from app.schemas.chat import ChatRequest
from app.services.business_clock import BusinessClock
from app.services.period_phrases import resolve_period

CLOCK = BusinessClock(date(2026, 9, 28))
KNOWN = datetime.fromisoformat("2026-09-28T23:59:59+03:00")


def draft(value):
    return {"content": json.dumps({"status": "answered", "draft_ar": value})}


def calls(*items):
    return {
        "tool_calls": [
            {
                "id": f"core-{i}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(arguments),
                },
            }
            for i, (name, arguments) in enumerate(items)
        ]
    }


def converse(connection, message, *replies, clock=CLOCK):
    sent = []
    queue = list(replies)

    def respond(request):
        sent.append(json.loads(request.content))
        assert queue, "unexpected provider request"
        return httpx.Response(200, json={"choices": [{"message": queue.pop(0)}]})

    async def run():
        async with LLMClient(
            Settings(
                llm_provider="groq",
                llm_model_id="fake-core",
                groq_api_key="fictional",
            ),
            transport=httpx.MockTransport(respond),
        ) as client:
            return await orchestrator.converse(
                ChatRequest(message=message, conversation_id="core"),
                client=client,
                connection=connection,
                clock=clock,
                known_at=KNOWN,
            )

    return asyncio.run(run()), sent


@pytest.fixture
def receivables(ledger, debt_factory, insert_event):
    first = debt_factory("PART-PAID", 90000, "2026-09-20", party="CUST-01")
    debt_factory("FUTURE-DUE", 40000, "2026-10-15", party="CUST-02")
    for index, amount in enumerate((30000, 25000)):
        payment = insert_event(
            source_id=f"VERIFIED-{index}",
            type="CREDIT_COLLECTION",
            amount_iqd=amount,
            counterparty_id="CUST-01",
            obligation_id=first.obligation_id,
        )
        ledger.execute(
            "INSERT INTO payment_links VALUES (?, ?, ?, ?, ?, ?)",
            (
                f"LINK-{index}",
                payment.transaction_id,
                first.obligation_id,
                amount,
                "definite",
                "2026-09-28T10:00:00+00:00",
            ),
        )
    insert_event(
        source_id="UNALLOCATED",
        type="CREDIT_COLLECTION",
        amount_iqd=1000,
        counterparty_id="CUST-02",
        status="flagged",
    )
    ledger.commit()
    return ledger


def test_debtor_list_preserves_unfiltered_as_of_and_verified_outstanding(receivables):
    output = invoke(
        "get_debts",
        {"direction": "receivable"},
        connection=receivables,
        clock=CLOCK,
        known_at=KNOWN,
    )
    assert output.ok
    report = output.result["receivables"]
    assert report["total_outstanding"]["amount_iqd"] == 75000
    assert {
        p["counterparty_id"]: p["outstanding"]["amount_iqd"]
        for p in report["customers"]
    } == {
        "CUST-01": 35000,
        "CUST-02": 40000,
    }
    assert resolve_period("منو الزباين المديونين؟", weekday=0).status == "none_found"
    assert (
        str(output.resolved_range.start)
        == str(output.resolved_range.end)
        == "2026-09-28"
    )


def test_total_only_debtor_narration_still_lists_each_verified_customer(receivables):
    before = tuple(receivables.iterdump())
    result, sent = converse(
        receivables,
        "منو الزباين المديونين؟",
        calls(("get_debts", {"direction": "receivable"})),
        draft("{{fig:receivables.total_outstanding}}"),
    )
    assert result.status == "answered" and result.used_tools == ("get_debts",)
    assert len(sent) == 2
    assert {f.amount_iqd for f in result.figures} >= {35000, 40000}
    assert all(f.source_ids for f in result.figures)
    assert tuple(receivables.iterdump()) == before


def test_invalid_debtor_draft_fallback_keeps_customer_list(receivables):
    result, _ = converse(
        receivables,
        "منو الزباين المديونين؟",
        calls(("get_debts", {"direction": "receivable"})),
        draft("a raw 123"),
        draft("a raw 456"),
    )
    assert result.renderer.fell_back_to_template
    assert {f.amount_iqd for f in result.figures} >= {35000, 40000}
