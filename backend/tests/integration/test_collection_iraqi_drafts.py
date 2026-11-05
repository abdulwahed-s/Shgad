"""Approved Iraqi drafts keep the real slot/evidence/ledger guarantees."""

import json
from datetime import date
from pathlib import Path

import pytest
from test_collection_agent import Scripted, draft

from app.agents.llm_client import LLMUnavailable
from app.agents.messages_ar import text
from app.agents.renderer import format_date, format_iqd
from app.api.dependencies import llm_client
from app.main import app

APPROVAL = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/APPROVED_IRAQI_COPY_2026-11-05.json"
    ).read_bytes()
)


@pytest.mark.parametrize("tone", ["gentle", "normal", "firm"])
@pytest.mark.parametrize("offline", [False, True], ids=["scripted-model", "template"])
def test_iraqi_draft_keeps_exact_slots_and_never_changes_ledger(
    api, ledger, debt_factory, monkeypatch, tone, offline
):
    # This validates approved fixed text and rendering, not generated model quality.
    approved_body = APPROVAL["backend"]["reminder_" + tone]
    debt_factory("LATE", 47000, "2026-09-20")
    ledger.commit()
    client = Scripted(LLMUnavailable("offline") if offline else approved_body)
    monkeypatch.setitem(app.dependency_overrides, llm_client, lambda: client)
    before = tuple(ledger.iterdump())

    response = draft(api, tone=tone)

    assert response.status_code == 200
    body = response.json()
    assert body["draft_kind"] == ("template" if offline else "model")
    assert body["review_status"] == "APPROVED"
    assert body["figures"][0]["amount_iqd"] == 47000
    assert body["figures"][0]["source_ids"] == ["LATE"]
    assert body["dates"]["oldest_due"] == "2026-09-20"
    rendered_body = approved_body.replace(
        "{{fig:overdue_amount}}", format_iqd(47000)
    ).replace("{{date:oldest_due}}", format_date(date(2026, 9, 20)))
    assert body["text"] == "\n".join(
        [
            text("collection_greeting").format(
                name=body["counterparty"]["display_name"]
            ),
            rendered_body,
            APPROVAL["backend"]["collection_zaincash"],
            APPROVAL["backend"]["collection_signoff"],
        ]
    )
    assert len(client.calls) == 1
    assert tuple(ledger.iterdump()) == before


def test_rejected_draft_fallback_keeps_the_signoff_last(
    api, ledger, debt_factory, monkeypatch
):
    debt_factory("LATE", 47000, "2026-09-20")
    ledger.commit()
    client = Scripted("47000", "47000")
    monkeypatch.setitem(app.dependency_overrides, llm_client, lambda: client)

    response = draft(api, tone="firm")

    assert response.status_code == 200
    body = response.json()
    assert body["renderer"] == {"attempts": 2, "fell_back_to_template": True}
    assert body["review_status"] == "APPROVED"
    assert body["text"].splitlines()[-2:] == [
        APPROVAL["backend"]["collection_zaincash"],
        APPROVAL["backend"]["collection_signoff"],
    ]
    assert len(client.calls) == 2
