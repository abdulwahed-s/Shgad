"""D59: reconciliation templates list all flags and an explicit empty state."""

from datetime import date, datetime

from app.agents.messages_ar import text
from app.agents.renderer import render_reply
from app.agents.tool_registry import invoke
from app.services.business_clock import BusinessClock


def summary(db):
    output = invoke(
        "reconcile",
        {"period": "today"},
        connection=db,
        clock=BusinessClock(date(2026, 9, 28)),
        known_at=datetime.fromisoformat("2026-09-28T23:59:59+03:00"),
        # This helper exercises the no-period summary selected by the planner.
        server_plan="reconciliation_summary",
    )
    assert output.ok, output.error
    return render_reply(None, outputs=[output])


def test_every_flag_is_rendered_even_after_the_fifth(api, ledger, insert_event):
    for i in range(7):
        insert_event(
            source_id=f"UNMATCHED-{i}",
            type="CREDIT_COLLECTION",
            amount_iqd=1000 + i,
            counterparty_id="CUST-01",
            status="flagged",
        )
    ledger.commit()
    expected = api.get("/api/flags").json()["items"]
    assert len(expected) == 7
    rendered = summary(ledger)
    figures = {f.key: f for f in rendered.figures}
    for i, flag in enumerate(expected):
        shown = figures[f"tool_0.items.{i}.amount"]
        assert shown.amount_iqd == flag["amount"]["amount_iqd"]
        assert list(shown.source_ids) == flag["source_ids"]
        assert all(s in rendered.reply_ar for s in shown.source_ids)


def test_no_flags_uses_the_approved_no_action_line(ledger):
    rendered = summary(ledger)
    assert text("no_action_needed") in rendered.reply_ar
    assert not any(
        "items." in f.key or "cash_differences." in f.key for f in rendered.figures
    )
