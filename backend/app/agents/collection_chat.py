"""Coordinator delegation for D61 only; existing financial plans are untouched."""

import re

from app.agents.collection_agent import create_draft
from app.agents.messages_ar import text
from app.agents.planner import Stop, resolve_parties
from app.agents.renderer import _render_body, format_date, render_projected_draft
from app.schemas.chat import ChatResponse, InterpretationView
from app.schemas.collections import CollectionAction, CollectionDraftRequest
from app.schemas.queries import DateRangeView
from app.schemas.renderer import RendererStats, ResolvedContext
from app.services.collections import collection_report, verified_debts
from app.services.errors import FinancialRuleError
from app.services.financial_queries import QuerySnapshot
from app.services.morning_brief import morning_brief, require_brief_verified
from app.services.reconcile import normalize_name


def collection_refusal(message):
    from app.agents.answer_policy import SafeDecision

    value = normalize_name(message).lower()
    if re.search(r"رساله|تذكير|ذكر|remind|message", value) and re.search(
        r"تهديد|هدد|فضح|شرطه|محكم|threat|sham|police", value
    ):
        return SafeDecision("unsafe_instruction", status="refused")
    return None


def _tone(message):
    value = normalize_name(message).lower()
    if re.search(r"حازم|firm", value):
        return "firm"
    return "normal" if re.search(r"عادي|normal", value) else "gentle"


def _response(
    body,
    *,
    clock,
    intent,
    figures=(),
    metrics=(),
    dates=None,
    party=None,
    action=None,
    brief=None,
    renderer=None,
):
    period = DateRangeView(start=clock.today, end=clock.today)
    context_line = text("period").format(
        start=format_date(clock.today), end=format_date(clock.today)
    )
    if party is not None:
        context_line += "\n" + text("customer").format(name=party.display_name)
    tools = ("get_debts", "reconcile") if intent == "daily_brief" else ("get_debts",)
    return ChatResponse(
        status="answered",
        reply_ar=context_line + "\n" + body,
        figures=figures,
        metrics=metrics,
        dates=(dates or {}) | {"start": clock.today, "end": clock.today},
        contexts=(ResolvedContext(range=period, counterparty=party),),
        resolved_range=period,
        resolved_counterparty=party,
        used_tools=tools,
        collection_action=action,
        brief=brief,
        renderer=renderer or RendererStats(attempts=1, fell_back_to_template=False),
        interpretation=InterpretationView(
            behavior="answer",
            intent=intent,
            tools=tools,
            period=period,
            counterparty_ids=(party.id,) if party else (),
        ),
    )


def _brief_reply(report, clock):
    require_brief_verified(report)
    figures = {
        name: getattr(report, name)
        for name in ("cash_on_hand", "dues_today", "dues_week", "overdue_total")
    }
    metrics = {
        m.key: m for m in (report.overdue_customer_count, report.open_flags_count)
    }
    lines = [text("brief_title")]
    for key, label in (
        ("cash_on_hand", "cash_on_hand"),
        ("dues_today", "brief_dues_today"),
        ("dues_week", "brief_dues_week"),
        ("overdue_total", "collection_overdue_amount"),
        ("overdue_customer_count", "brief_overdue_count"),
        ("open_flags_count", "brief_flags_count"),
    ):
        lines.append(text(label) + ": {{fig:" + key + "}}.")
    used = ({}, {}, {})
    rendered = _render_body(
        "\n".join(lines),
        figures=figures,
        metrics=metrics,
        dates={},
        used=used,
        user_message="",
    )
    if report.top_customers:
        rendered += "\n" + "، ".join(p.display_name for p in report.top_customers)
    return _response(
        rendered,
        clock=clock,
        intent="daily_brief",
        figures=tuple(figures.values()),
        metrics=tuple(metrics.values()),
        brief=report,
        action=CollectionAction(kind="priorities"),
    )


async def collection_turn(
    understood, *, request, client, connection, clock, known_at, deadline=None
):
    from app.agents.orchestrator import ERROR_COPY, _stop_response, fixed

    if understood.behavior != "answer":
        # Keep the same refusal/help/clarification handling as ordinary intents.
        from app.agents.planner import plan

        return _stop_response(
            plan(understood, connection=connection, clock=clock, known_at=known_at),
            understood,
        )
    try:
        if understood.intent == "daily_brief":
            return _brief_reply(
                morning_brief(connection, clock=clock, known_at=known_at), clock
            )
        snapshot = QuerySnapshot(connection, clock=clock, known_at=known_at)
        parties = resolve_parties(snapshot, understood.party_mentions, {"customer"})
        if isinstance(parties, Stop):
            return _stop_response(parties, understood)
        if understood.intent == "draft_reminder":
            if len(parties) != 1:
                return _stop_response(
                    Stop("AMBIGUOUS_COUNTERPARTY", "clarify_customer", options=parties),
                    understood,
                )
            tone = _tone(request.message)
            drafted = await create_draft(
                CollectionDraftRequest(counterparty_id=parties[0].id, tone=tone),
                client=client,
                connection=connection,
                clock=clock,
                known_at=known_at,
                deadline=deadline,
            )
            return _response(
                drafted.text,
                clock=clock,
                intent=understood.intent,
                figures=drafted.figures,
                metrics=drafted.metrics,
                dates=drafted.dates,
                party=drafted.counterparty,
                action=CollectionAction(
                    kind="draft", counterparty_id=parties[0].id, tone=tone
                )
                if drafted.status == "drafted"
                else None,
                renderer=drafted.renderer,
            )
        report = collection_report(connection, clock=clock, known_at=known_at)
        debts, output = verified_debts(connection, clock=clock, known_at=known_at)
        selected = [
            p
            for p in report.items
            if not parties or p.counterparty_id in {p.id for p in parties}
        ]
        lines = [
            text("collection_priorities") if selected else text("collection_empty")
        ]
        figures, metrics, dates = [], [], {}
        for rank, party in enumerate(selected):
            index = next(
                i
                for i, p in enumerate(debts.customers)
                if p.counterparty_id == party.counterparty_id
            )
            prefix = f"customer_{rank}"
            amount_slot, days_slot, due_slot = (
                prefix + ".overdue_amount",
                prefix + ".days_overdue",
                prefix + ".oldest_due",
            )
            draft = (
                "{{fig:"
                + amount_slot
                + "}}؛ "
                + text("collection_days_overdue")
                + ": {{fig:"
                + days_slot
                + "}}؛ {{date:"
                + due_slot
                + "}}."
            )
            rendered = render_projected_draft(
                draft,
                output=output,
                figure_keys={amount_slot: f"receivables.customers.{index}.outstanding"},
                metric_keys={days_slot: f"receivables.customers.{index}.days_overdue"},
                date_keys={due_slot: f"receivables.customers.{index}.oldest_due_date"},
            )
            lines.append(party.display_name + ": " + rendered.reply_ar)
            figures.extend(rendered.figures)
            metrics.extend(rendered.metrics)
            dates.update(rendered.dates)
        return _response(
            "\n".join(lines),
            clock=clock,
            intent=understood.intent,
            figures=tuple(figures),
            metrics=tuple(metrics),
            dates=dates,
            action=CollectionAction(kind="priorities"),
            party=parties[0] if len(parties) == 1 else None,
        )
    except FinancialRuleError as exc:
        response = fixed("clarification", ERROR_COPY.get(exc.code, "clarify_request"))
        return response.model_copy(
            update={
                "interpretation": InterpretationView(
                    behavior="clarify", intent=understood.intent, reason=exc.code
                )
            }
        )
