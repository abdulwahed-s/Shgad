"""Approved fallback copy can be handed off; edits never inherit that approval."""

from datetime import date, datetime

import pytest
from test_collection_agent import GOOD, Scripted, draft

from app.agents.llm_client import LLMUnavailable
from app.agents.messages_ar import DraftMessage
from app.agents.renderer import _render_body, format_date
from app.api.dependencies import llm_client
from app.main import app
from app.schemas.collections import ReminderRequest
from app.services.business_clock import BusinessClock
from app.services.collections import get_reminders, log_reminder


@pytest.fixture
def fixed_script(monkeypatch):
    def install(*bodies):
        client = Scripted(*bodies)
        monkeypatch.setitem(app.dependency_overrides, llm_client, lambda: client)
        return client

    return install


def test_approved_fallback_template_is_marked_shareable(
    api, ledger, debt_factory, fixed_script
):
    debt_factory("LATE", 47000, "2026-09-20")
    ledger.commit()
    fixed_script(LLMUnavailable("offline"))
    body = draft(api).json()
    assert body["draft_kind"] == "template"
    assert body["review_status"] == "APPROVED"


def test_edited_fixed_template_loses_approval(
    api, ledger, debt_factory, fixed_script, monkeypatch
):
    from app.agents import messages_ar

    debt_factory("LATE", 47000, "2026-09-20")
    ledger.commit()
    original = messages_ar.text("reminder_gentle")
    monkeypatch.setitem(
        messages_ar.MESSAGES, "reminder_gentle", DraftMessage(original + " changed")
    )
    fixed_script(LLMUnavailable("offline"))
    body = draft(api).json()
    assert body["draft_kind"] == "template"
    assert body["review_status"] == "PENDING_REVIEW"


@pytest.mark.parametrize(
    "key", ["collection_greeting", "collection_signoff", "collection_zaincash"]
)
def test_model_body_cannot_approve_an_edited_fixed_wrapper(
    api, ledger, debt_factory, fixed_script, monkeypatch, key
):
    from app.agents import messages_ar

    debt_factory("LATE", 47000, "2026-09-20")
    ledger.commit()
    monkeypatch.setitem(
        messages_ar.MESSAGES, key, DraftMessage(messages_ar.text(key) + " changed")
    )
    fixed_script(GOOD)
    body = draft(api).json()
    assert body["draft_kind"] == "model"
    assert body["review_status"] == "PENDING_REVIEW"


def test_last_reminded_slot_uses_stored_business_date_not_a_day_count(
    ledger, debt_factory
):
    from app.agents.messages_ar import text

    debt_factory("LATE", 47000, "2026-09-20")
    ledger.commit()
    audit = datetime.fromisoformat("2026-11-04T10:00:00+00:00")
    log_reminder(
        ledger,
        ReminderRequest(
            counterparty_id="CUST-01", tone="gentle", channel="copy", edited=False
        ),
        clock=BusinessClock(date(2026, 9, 28)),
        now=audit,
    )
    last = get_reminders(
        ledger, ("CUST-01",), clock=BusinessClock(date(2026, 9, 28)), known_at=audit
    ).items[0]
    used = ({}, {}, {})
    rendered = _render_body(
        text("collection_reminded"),
        figures={},
        metrics={},
        dates={"last_reminded": last.last_business_date},
        used=used,
        user_message="",
    )
    assert rendered == text("collection_reminded").replace(
        "{{date:last_reminded}}", format_date(date(2026, 9, 28))
    )
    assert used[2] == {"last_reminded": date(2026, 9, 28)}
    assert not used[0] and not used[1]
