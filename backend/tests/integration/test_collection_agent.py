"""D61 collection drafts: real verified debts, scripted provider, no ledger writes."""

import asyncio
import json

import pytest

from app.agents.llm_client import LLMReply, LLMUnavailable
from app.api.dependencies import llm_client
from app.main import app

GOOD = (
    "نذكّرك بالمبلغ المتأخر {{fig:overdue_amount}}، "
    "المستحق بتاريخ {{date:oldest_due}}. تكدر تخبرنا بوقت مناسب للتسديد؟"
)


class Scripted:
    def __init__(self, *bodies):
        self.bodies = iter(bodies)
        self.calls = []

    async def complete(self, messages, *, tools=(), **kwargs):
        assert tools == ()
        self.calls.append(messages)
        body = next(self.bodies)
        if isinstance(body, Exception):
            raise body
        return LLMReply(
            "scripted",
            "synthetic",
            json.dumps({"body": body}, ensure_ascii=False),
            (),
            {},
        )


@pytest.fixture
def scripted():
    def install(*bodies):
        client = Scripted(*bodies)
        app.dependency_overrides[llm_client] = lambda: client
        return client

    return install


def draft(api, party="CUST-01", tone="gentle"):
    return api.post(
        "/api/collections/draft", json={"counterparty_id": party, "tone": tone}
    )


def test_valid_draft_fills_exact_ledger_slots_and_adds_only_server_name(
    api, ledger, debt_factory, scripted
):
    from datetime import date

    from app.agents.renderer import format_date, format_iqd

    debt_factory("LATE", 47000, "2026-09-20")
    debt_factory("NOT-DUE", 99000, "2026-09-30")
    ledger.commit()
    client = scripted(GOOD)
    before = tuple(ledger.iterdump())
    response = draft(api)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "drafted" and body["draft_kind"] == "model"
    assert body["renderer"] == {"attempts": 1, "fell_back_to_template": False}
    assert "أبو حيدر" in body["text"]
    assert format_iqd(47000) in body["text"]
    assert format_date(date(2026, 9, 20)) in body["text"]
    assert body["dates"]["oldest_due"] == "2026-09-20"
    assert body["figures"][0]["source_ids"] == ["LATE"]
    assert body["figures"][0]["amount_iqd"] == 47000
    assert "{{" not in body["text"]
    assert len(client.calls) == 1
    assert tuple(ledger.iterdump()) == before


@pytest.mark.parametrize(
    "bad",
    [
        "عليك 47000 دينار",
        "عليك ٤٧٠٠٠ دينار",
        "عليك Ⅳ دينار",
        "المبلغ {{fig:invented}}",
        "راجع الشرطة {{fig:overdue_amount}} {{date:oldest_due}}",
        "راح نفضحك {{fig:overdue_amount}} {{date:oldest_due}}",
        "المحكمة {{fig:overdue_amount}} {{date:oldest_due}}",
        "pay by Monday {{fig:overdue_amount}} {{date:oldest_due}}",
        "يوم عشرين ايلول {{fig:overdue_amount}} {{date:oldest_due}}",
        "عليك خمسين ألف {{fig:overdue_amount}} {{date:oldest_due}}",
        "افتح https://example.com {{fig:overdue_amount}} {{date:oldest_due}}",
        "يا أبو حيدر {{fig:overdue_amount}} {{date:oldest_due}}",
        "لو ما تدفع راح نجي نكسر محلك {{fig:overdue_amount}} {{date:oldest_due}}",
        "يا كذاب سدد {{fig:overdue_amount}} {{date:oldest_due}}",
        "من شهر آب {{fig:overdue_amount}} {{date:oldest_due}}",
        "مستحق باجر {{fig:overdue_amount}} {{date:oldest_due}}",
        "ممنونين على تسديدك السابق {{fig:overdue_amount}} {{date:oldest_due}}",
    ],
)
def test_invalid_draft_retries_once_then_tone_template(
    api, ledger, debt_factory, scripted, bad
):
    debt_factory("LATE", 47000, "2026-09-20")
    ledger.commit()
    client = scripted(bad, bad)
    before = tuple(ledger.iterdump())
    body = draft(api, tone="firm").json()
    assert body["draft_kind"] == "template", body
    assert body["renderer"] == {"attempts": 2, "fell_back_to_template": True}
    assert body["figures"][0]["amount_iqd"] == 47000
    assert body["review_status"] == "APPROVED"
    assert len(client.calls) == 2
    assert "الشرطة" not in body["text"] and "المحكمة" not in body["text"]
    assert tuple(ledger.iterdump()) == before


def test_one_rejected_draft_can_recover_on_retry(api, ledger, debt_factory, scripted):
    debt_factory("LATE", 47000, "2026-09-20")
    ledger.commit()
    scripted("المبلغ 47", GOOD)
    body = draft(api).json()
    assert body["draft_kind"] == "model"
    assert body["renderer"]["attempts"] == 2


def test_model_receives_only_minimized_safe_context(
    api, ledger, debt_factory, scripted
):
    debt_factory("LATE", 47000, "2026-09-20")
    debt_factory("OTHER", 83000, "2026-09-12", party="CUST-02")
    ledger.commit()
    client = scripted(GOOD)
    assert draft(api).status_code == 200
    payload = json.loads(client.calls[0][-1]["content"])
    assert set(payload) == {
        "tone",
        "days_overdue_bucket",
        "reminder_count",
        "has_partial_payment",
        "slots",
    }
    all_input = json.dumps(client.calls, ensure_ascii=False)
    for forbidden in (
        "أبو حيدر",
        "CUST-",
        "LATE",
        "OTHER",
        "47000",
        "83000",
        "2026-09",
        "description",
        "notes",
    ):
        assert forbidden not in all_input


def test_provider_outage_returns_known_figures_template(
    api, ledger, debt_factory, scripted
):
    debt_factory("LATE", 47000, "2026-09-20")
    ledger.commit()
    client = scripted(LLMUnavailable("needs_internet"))
    before = tuple(ledger.iterdump())
    response = draft(api)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["draft_kind"] == "template"
    assert body["figures"][0]["amount_iqd"] == 47000
    assert body["dates"]["oldest_due"] == "2026-09-20"
    assert len(client.calls) == 1
    assert tuple(ledger.iterdump()) == before


def test_not_due_and_nothing_owed_never_call_drafter(api, j1_shop, scripted):
    client = scripted()
    for party, status in (("CUST-01", "not_due"), ("CUST-02", "nothing_owed")):
        body = draft(api, party=party).json()
        assert body["status"] == status
        assert body["draft_kind"] is None
        assert body["text"]
        if status == "not_due":
            assert body["dates"]["next_due"] == "2026-09-30"
    assert not client.calls


def test_unknown_or_supplier_id_cannot_draft(api, scripted):
    client = scripted()
    for party in ("UNKNOWN", "SUP-01"):
        assert draft(api, party=party).status_code == 404
    assert not client.calls


def test_other_customer_first_name_is_rejected(api, ledger, debt_factory, scripted):
    ledger.execute(
        "INSERT INTO counterparties VALUES ('CUST-03','أحمد علي','customer')"
    )
    debt_factory("LATE", 47000, "2026-09-20")
    ledger.commit()
    bad = "يا أحمد {{fig:overdue_amount}} {{date:oldest_due}}"
    scripted(bad, bad)
    assert draft(api).json()["draft_kind"] == "template"


def test_specialist_tools_cannot_mutate_even_from_scripted_model(ledger, debt_factory):
    import sqlite3
    from datetime import date, datetime

    from app.agents.collection_agent import create_draft
    from app.schemas.collections import CollectionDraftRequest
    from app.services.business_clock import BusinessClock

    debt_factory("LATE", 47000, "2026-09-20")
    ledger.commit()

    class AttemptedWrite(Scripted):
        async def complete(self, messages, **kwargs):
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                ledger.execute(
                    "INSERT INTO counterparties VALUES ('BAD','synthetic','customer')"
                )
            return await super().complete(messages, **kwargs)

    before = tuple(ledger.iterdump())
    body = asyncio.run(
        create_draft(
            CollectionDraftRequest(counterparty_id="CUST-01"),
            client=AttemptedWrite(GOOD),
            connection=ledger,
            clock=BusinessClock(date(2026, 9, 28)),
            known_at=datetime.fromisoformat("2026-09-28T23:59:59+03:00"),
        )
    )
    assert body.draft_kind == "model"
    assert tuple(ledger.iterdump()) == before
    assert ledger.execute("PRAGMA query_only").fetchone()[0] == 0
