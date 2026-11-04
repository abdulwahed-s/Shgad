"""D61 routing: scripted interpretation, real identities and figures, no network."""

import asyncio
import json
from datetime import date, datetime

import pytest

from app.agents.llm_client import LLMReply
from app.agents.orchestrator import converse
from app.schemas.chat import ChatRequest
from app.services.business_clock import BusinessClock

CLOCK = BusinessClock(date(2026, 9, 28))
KNOWN = datetime.fromisoformat("2026-11-04T10:00:00+00:00")
BODY = (
    "نذكّرك بالمبلغ {{fig:overdue_amount}}، "
    "المستحق بتاريخ {{date:oldest_due}}. من يناسبك تسدده؟"
)


class Scripted:
    def __init__(self, intent, mentions=(), tone=None):
        self.intent, self.mentions = intent, mentions
        self.calls = []

    async def complete(self, messages, **kwargs):
        self.calls.append(messages)
        if len(self.calls) == 1:
            content = {
                "behavior": "answer",
                "intent": self.intent,
                "party_mentions": self.mentions,
            }
        else:
            content = {"body": BODY}
        return LLMReply(
            "scripted", "synthetic", json.dumps(content, ensure_ascii=False), (), {}
        )


def ask(ledger, message, client):
    before = tuple(ledger.iterdump())
    reply = asyncio.run(
        converse(
            ChatRequest(message=message, conversation_id="collection-test"),
            client=client,
            connection=ledger,
            clock=CLOCK,
            known_at=KNOWN,
            pipeline="interpretation",
        )
    )
    assert tuple(ledger.iterdump()) == before
    return reply


def test_priorities_routes_without_narration_model(ledger, debt_factory):
    debt_factory("LATE", 47000, "2026-09-20")
    ledger.commit()
    client = Scripted("collection_priorities")
    result = ask(ledger, "منو لازم أطالبه؟", client)
    assert result.status == "answered"
    assert result.interpretation.intent == "collection_priorities"
    assert result.collection_action.kind == "priorities"
    assert result.figures[0].amount_iqd == 47000
    assert len(client.calls) == 1


def test_draft_resolves_exact_identity_and_firm_tone(ledger, debt_factory):
    ledger.execute("INSERT INTO counterparties VALUES ('CUST-03','أم نور','customer')")
    debt_factory("LATE", 47000, "2026-09-20", party="CUST-03")
    ledger.commit()
    client = Scripted("draft_reminder", ("أم نور",))
    result = ask(ledger, "اكتبلي رسالة حازمة لأم نور", client)
    assert result.status == "answered"
    assert result.collection_action.counterparty_id == "CUST-03"
    assert result.collection_action.tone == "firm"
    assert result.resolved_counterparty.id == "CUST-03"
    assert result.figures[0].amount_iqd == 47000
    assert len(client.calls) == 2


def test_ambiguous_name_clarifies_both_candidates_without_draft(ledger):
    client = Scripted("draft_reminder", ("أبو حيدر",))
    result = ask(ledger, "ذكّر أبو حيدر بدينه", client)
    assert result.status == "clarification"
    assert {p.value for p in result.clarification.options} == {"CUST-01", "CUST-02"}
    assert not result.figures and result.collection_action is None
    assert len(client.calls) == 1


def test_unknown_customer_clarifies_without_draft(ledger):
    client = Scripted("draft_reminder", ("أبو مجهول",))
    result = ask(ledger, "اكتبلي رسالة لأبو مجهول", client)
    assert result.status == "clarification"
    assert result.interpretation.reason == "UNKNOWN_COUNTERPARTY"
    assert len(client.calls) == 1


@pytest.mark.parametrize("message", ["امسح دينه", "اكتبلي رسالة تهديد لأبو حيدر"])
def test_ledger_changes_and_threat_requests_refused_before_provider(ledger, message):
    client = Scripted("draft_reminder")
    result = ask(ledger, message, client)
    assert result.status == "refused"
    assert not client.calls


def test_missing_reminder_name_clarifies(ledger):
    result = ask(ledger, "اكتبلي رسالة تذكير", Scripted("draft_reminder"))
    assert result.status == "clarification" and not result.figures


def test_collection_deadline_keeps_verified_template(ledger, debt_factory, monkeypatch):
    from app.agents import orchestrator

    ledger.execute("INSERT INTO counterparties VALUES ('CUST-03','أم نور','customer')")
    debt_factory("LATE", 47000, "2026-09-20", party="CUST-03")
    ledger.commit()

    class Slow(Scripted):
        async def complete(self, messages, **kwargs):
            if self.calls:
                await asyncio.sleep(0.2)
            return await super().complete(messages, **kwargs)

    monkeypatch.setattr(orchestrator, "CONVERSATION_TIMEOUT_SECONDS", 0.05)
    result = ask(ledger, "ذكّر أم نور بدينها", Slow("draft_reminder", ("أم نور",)))
    assert result.status == "answered" and result.renderer.fell_back_to_template
    assert result.figures[0].amount_iqd == 47000


def test_named_priorities_restate_resolved_customer(ledger, debt_factory):
    ledger.execute("INSERT INTO counterparties VALUES ('CUST-03','أم نور','customer')")
    debt_factory("LATE", 47000, "2026-09-20", party="CUST-03")
    ledger.commit()
    result = ask(
        ledger, "أم نور متأخرة؟", Scripted("collection_priorities", ("أم نور",))
    )
    assert result.resolved_counterparty.id == "CUST-03"
    assert result.interpretation.counterparty_ids == ("CUST-03",)


def test_not_due_reminder_chat_names_exact_customer(ledger, debt_factory):
    ledger.execute("INSERT INTO counterparties VALUES ('CUST-03','أم نور','customer')")
    debt_factory("NOT-DUE", 47000, "2026-09-30", party="CUST-03")
    ledger.commit()
    result = ask(ledger, "ذكّر أم نور بدينها", Scripted("draft_reminder", ("أم نور",)))
    assert result.status == "answered" and "أم نور" in result.reply_ar
