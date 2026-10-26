"""D55 real ledger/services/provenance; fake provider, no credentials or answers."""

import asyncio
import json
from datetime import UTC, date, datetime

import httpx
import pytest

from app.agents import orchestrator
from app.agents.llm_client import LLMClient
from app.agents.messages_ar import text
from app.agents.renderer import render_draft, render_reply
from app.agents.tool_registry import invoke
from app.agents.verification import verify_tool_output
from app.config import Settings
from app.schemas.chat import ChatRequest
from app.schemas.tools import ToolEnvelope
from app.services.business_clock import BusinessClock
from app.services.errors import FinancialRuleError
from app.services.financial_queries import QuerySnapshot

CLOCK = BusinessClock(date(2026, 9, 28))
KNOWN = datetime.fromisoformat("2026-09-28T23:59:59+03:00")


def chat(ledger, message, *responses):
    sent, queue = [], list(responses)

    def respond(request):
        sent.append(json.loads(request.content))
        assert queue, "unexpected provider call"
        return httpx.Response(200, json={"choices": [{"message": queue.pop(0)}]})

    async def run():
        async with LLMClient(
            Settings(
                llm_provider="groq", groq_api_key="fictional", llm_model_id="fake"
            ),
            transport=httpx.MockTransport(respond),
        ) as client:
            return await orchestrator.converse(
                ChatRequest(message=message, conversation_id="final"),
                client=client,
                connection=ledger,
                clock=CLOCK,
                known_at=KNOWN,
            )

    return asyncio.run(run()), sent


def narration(value):
    return {"content": json.dumps({"status": "answered", "draft_ar": value})}


def sales_call(arguments):
    return {
        "tool_calls": [
            {
                "id": "sale",
                "type": "function",
                "function": {"name": "get_sales", "arguments": json.dumps(arguments)},
            }
        ]
    }


def test_named_month_overrides_model_period_and_preserves_range(ledger, insert_event):
    insert_event(
        source_id="AUG", occurred_at="2026-08-15T12:00:00+03:00", amount_iqd=17000
    )
    insert_event(source_id="SEP", amount_iqd=33000)
    ledger.commit()
    reply, sent = chat(
        ledger,
        "وريني مبيعات شهر اغسطس",
        sales_call({"period": "today"}),
        narration("{{fig:cash_sales}}"),
    )
    assert reply.status == "answered" and len(sent) == 2
    assert (str(reply.resolved_range.start), str(reply.resolved_range.end)) == (
        "2026-08-01",
        "2026-08-31",
    )
    assert reply.figures[0].amount_iqd == 17000
    assert reply.figures[0].source_ids == ("AUG",)
    wire = json.loads(sent[-1]["messages"][-1]["content"])
    assert "period_set_by_server" in wire["data"]["warnings"]


@pytest.mark.parametrize(
    "message,key",
    [
        ("مبيعات حزيران", "clarify_history"),
        ("هامشي حزيران", "clarify_history"),
        ("مبيعات آب 2026", "clarify_period"),
    ],
)
def test_unavailable_or_conflicting_month_needs_no_provider(ledger, message, key):
    reply, sent = chat(ledger, message)
    assert reply.status == "clarification" and reply.reply_ar == text(key)
    assert sent == [] and reply.figures == ()


def test_model_cannot_authorize_an_explicit_month(ledger):
    output = invoke(
        "get_sales",
        {"period": "explicit", "start_date": "2026-08-01", "end_date": "2026-08-31"},
        connection=ledger,
        clock=CLOCK,
        known_at=KNOWN,
        user_message="مبيعات آب",
    )
    assert not output.ok and output.error.code == "VALIDATION_ERROR"


@pytest.mark.parametrize("month,start", [(9, "2026-08-01"), (8, "2026-08-02")])
def test_trusted_month_context_must_match_user_and_entire_range(ledger, month, start):
    result = invoke(
        "get_sales",
        {"period": "explicit", "start_date": start, "end_date": "2026-08-31"},
        connection=ledger,
        clock=CLOCK,
        known_at=KNOWN,
        user_message="مبيعات آب",
        server_month=month,
    )
    assert not result.ok and result.error.code == "VALIDATION_ERROR"


def test_model_cannot_supply_a_query_evidence_tool_argument(ledger):
    result = invoke(
        "get_sales",
        {"period": "today", "query_evidence": {"matching_rows": 0}},
        connection=ledger,
        clock=CLOCK,
        known_at=KNOWN,
    )
    assert not result.ok and not result.figures


@pytest.fixture
def no_collections(ledger, insert_event):
    insert_event(source_id="SALE", amount_iqd=80000, category_id="CAT-01", quantity=16)
    ledger.commit()
    return ledger


def weekly(ledger):
    result = invoke(
        "get_sales",
        {"period": "this_week", "kind": "all"},
        connection=ledger,
        clock=CLOCK,
        known_at=KNOWN,
        server_plan="weekly_summary",
    )
    assert result.ok, result.error
    return result


def test_weekly_zero_collections_render_with_verified_query_evidence(no_collections):
    output = weekly(no_collections)
    rendered = render_draft("{{fig:weekly.collections}}", outputs=[output])
    zero = next(f for f in rendered.figures if f.key == "weekly.collections")
    assert zero.amount_iqd == 0 and zero.source_ids == ()
    assert zero.query_evidence.model_dump(mode="json") == {
        "tool": "get_sales",
        "period": {"start": "2026-09-26", "end": "2026-09-28"},
        "filters": {
            "event_types": ["CREDIT_COLLECTION"],
            "active_only": True,
            "known_at": KNOWN.astimezone(UTC).isoformat(),
        },
        "matching_rows": 0,
    }
    assert "٠" in rendered.reply_ar
    template = render_reply(None, outputs=[output])
    assert any(f.key.endswith("weekly.collections") for f in template.figures)


def test_zero_outside_observed_range_is_unavailable_not_a_proof(ledger):
    result = invoke(
        "get_sales",
        {"period": "explicit", "start_date": "2026-06-01", "end_date": "2026-06-30"},
        connection=ledger,
        clock=CLOCK,
        known_at=KNOWN,
        user_message="2026-06-01 2026-06-30",
    )
    assert not result.ok and result.error.details["reason"] == "OUTSIDE_OBSERVED_DATA"
    assert not result.figures


def test_missing_opening_cash_still_clarifies_with_no_zero(ledger):
    result = invoke(
        "forecast",
        {"until": "next_weekday:thu"},
        connection=ledger,
        clock=CLOCK,
        known_at=KNOWN,
    )
    assert not result.ok and result.error.code == "MISSING_OPENING_BALANCE"
    assert result.figures == ()


def test_zero_evidence_wire_copy_is_not_verified(no_collections):
    output = weekly(no_collections)
    copy = ToolEnvelope.model_validate(output.model_dump(mode="json"))
    with pytest.raises(FinancialRuleError, match="VALIDATION_ERROR"):
        render_draft("{{fig:weekly.collections}}", outputs=[copy])


@pytest.mark.parametrize(
    "field,value",
    [
        ("matching_rows", 1),
        ("tool", "forecast"),
        ("period", {"start": "2026-06-01", "end": "2026-06-30"}),
        (
            "filters",
            {
                "event_types": ["CASH_SALE"],
                "active_only": True,
                "known_at": KNOWN.isoformat(),
            },
        ),
    ],
)
def test_zero_query_mutation_invalidates_fingerprint(no_collections, field, value):
    output = weekly(no_collections)
    figure = next(f for f in output.figures if f.key == "weekly.collections")
    figure.query_evidence.__dict__[field] = value
    with pytest.raises(FinancialRuleError, match="VALIDATION_ERROR"):
        render_draft("{{fig:weekly.collections}}", outputs=[output])


def test_verifier_rejects_a_zero_proof_with_wrong_filters(no_collections):
    output = weekly(no_collections)
    figure = next(f for f in output.figures if f.key == "weekly.collections")
    figure.query_evidence.filters.__dict__["event_types"] = ("OWNER_DRAWING",)
    with pytest.raises(FinancialRuleError, match="VALIDATION_ERROR"):
        verify_tool_output(
            output,
            snapshot=QuerySnapshot(no_collections, clock=CLOCK, known_at=KNOWN),
            tool_name="get_sales",
            weekly_plan=True,
        )


def test_zero_proof_requires_actually_zero_matching_rows(no_collections, insert_event):
    output = weekly(no_collections)
    insert_event(
        source_id="COLLECTED",
        type="CREDIT_COLLECTION",
        amount_iqd=500,
        counterparty_id="CUST-01",
        status="flagged",
    )
    no_collections.commit()
    with pytest.raises(FinancialRuleError, match="VALIDATION_ERROR"):
        verify_tool_output(
            output,
            snapshot=QuerySnapshot(no_collections, clock=CLOCK, known_at=KNOWN),
            tool_name="get_sales",
            weekly_plan=True,
        )


def test_weekly_zero_reaches_chat_and_provider_as_verified_slot(no_collections):
    reply, sent = chat(
        no_collections, "ملخص هذا الاسبوع", narration("{{fig:weekly.collections}}")
    )
    assert reply.status == "answered" and len(sent) == 1
    assert any(f.amount_iqd == 0 and f.query_evidence for f in reply.figures)
    assert any(
        m["role"] == "tool" and "weekly.collections" in m["content"]
        for m in sent[0]["messages"]
    )
