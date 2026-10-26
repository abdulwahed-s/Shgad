"""Bounded read-only tool calling; only the existing verifier/renderer emits values."""

import asyncio
import json
import re

from pydantic import ValidationError

from app.agents import answer_policy
from app.agents.llm_client import LLMUnavailable, strict_json
from app.agents.messages_ar import text
from app.agents.renderer import DraftValidationError, render_draft, render_reply
from app.agents.system_instructions import SYSTEM_INSTRUCTIONS
from app.agents.tool_plans import ToolPlan, select_plan
from app.agents.tool_registry import TOOLS, definitions, invoke
from app.agents.verification import require_verified
from app.schemas.chat import (
    ChatResponse,
    Clarification,
    ClarificationOption,
    DraftAction,
)
from app.schemas.evidence import CounterpartyView
from app.services.errors import FinancialRuleError
from app.services.period_phrases import resolve_period
from app.services.reconcile import normalize_name
from app.services.validation import normalize_digits

ERROR_COPY = {
    "AMBIGUOUS_DATE": "clarify_period",
    "AMBIGUOUS_COUNTERPARTY": "clarify_customer",
    "MISSING_OPENING_BALANCE": "clarify_opening_balance",
    "MISSING_COSTS": "clarify_costs",
    "MISSING_FORECAST_HISTORY": "clarify_history",
    "NOT_FOUND": "clarify_history",
    "MISSING_DUE_DATE": "clarify_due_date",
    "MISSING_COUNT": "clarify_counts",
    "VALIDATION_ERROR": "clarify_request",
}
ASSUMPTIONS = {
    "collections_expected_not_guaranteed",
    "margin_excludes_unrecorded_costs",
    "unexplained_difference_excluded",
}
UNSAFE_NARRATION = re.compile(
    r"صافي\s*الربح|الربح\s*الصافي|net\s+profit|سرق|اختلاس|تزوير|"
    r"\b(?:مليون|مليار|ألف|الف|صفر|عشرة|عشرين|ثلاثين|أربعين|خمسين|"
    r"ستين|سبعين|ثمانين|تسعين|مئة|مائة|مئتين|مائتين|ألفين|الفين)\b",
    re.I,
)
NUMBER_WORDS = set(
    (
        "صفر واحد واحدة وحده اثنان اثنين اثنتان اثنتين ثلاث ثلاثة اربع اربعة خمس خمسة "
        "ست ستة سبع سبعة ثمان ثمانية تسع تسعة عشر عشرة عشرين ثلاثين اربعين خمسين "
        "ستين سبعين ثمانين تسعين مئة مائة مية ميه ميتين مئتين مائتين "
        "الف الفين الفان الاف الوف مليون مليونين ملايين مليار مليارين مليارات "
        "نصف نص ربع ثلث zero one two three four five six seven eight nine ten eleven "
        "twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty "
        "thirty forty fifty sixty seventy eighty ninety hundred thousand "
        "million billion "
        "half quarter"
    ).split()
)
NUMBER_WORDS |= {
    prefix + suffix
    for prefix in ("ثلاث", "اربع", "خمس", "ست", "سبع", "ثمان", "تسع")
    for suffix in ("مية", "ميه", "مئة", "مائة")
}
DATE_WORDS = set(
    (
        "السبت الاحد الاثنين الثلاثاء الاربعاء الخميس الجمعة monday tuesday wednesday "
        "thursday friday saturday sunday"
    ).split()
)


def unsafe_narration(draft):
    # Slots are checked by the renderer. Check only literal prose here so a
    # legitimate date slot named first_short_date is never treated as a number.
    plain = re.sub(r"\{\{(?:fig|date):[^{}]+\}\}", "", draft)
    normalized = normalize_name(plain).lower()
    if UNSAFE_NARRATION.search(normalized):
        return True
    for word in re.findall(r"[^\W\d_]+", normalized):
        variants = {word, word.removesuffix("s")}
        if word.startswith(("و", "ب", "ف", "ك", "ل")):
            variants.add(word[1:])
        variants |= {value[2:] for value in tuple(variants) if value.startswith("ال")}
        if variants & (NUMBER_WORDS | DATE_WORDS):
            return True
    return False


def fixed(status, key, *, used=(), options=()):
    return ChatResponse(
        status=status,
        reply_ar=text(key),
        used_tools=tuple(dict.fromkeys(used)),
        clarification=Clarification(question_ar=text(key), options=options)
        if status == "clarification"
        else None,
    )


def ambiguous_weekday(message, clock):
    normalized = normalize_name(message).lower()
    weekday_names = (
        ("الاثنين", "monday"),
        ("الثلاثاء", "tuesday"),
        ("الاربعاء", "wednesday"),
        ("الخميس", "thursday"),
        ("الجمعة", "friday"),
        ("السبت", "saturday"),
        ("الاحد", "sunday"),
    )[clock.today.weekday()]
    if not any(
        re.search(r"(?<!\w)" + word + r"(?!\w)", normalized) for word in weekday_names
    ):
        return False
    qualifiers = (
        "الجاي",
        "الماضي",
        "الفات",
        "القادم",
        "السابق",
        "اليوم",
        "هسه",
        "هالاسبوع",
        "هذا الاسبوع",
        "this",
        "next",
        "last",
        "today",
    )
    return not any(value in normalized for value in qualifiers) and not re.search(
        r"\d{4}-\d{2}-\d{2}", normalize_digits(message)
    )


def tool_failure(output, used):
    if output.error.code == "INTERNAL":
        return fixed("error", "chat_error", used=used)
    options = []
    if output.error.code == "AMBIGUOUS_COUNTERPARTY":
        for raw in output.error.details.get("options", []):
            party = CounterpartyView.model_validate(raw)
            options.append(
                ClarificationOption(label_ar=party.display_name, value=party.id)
            )
    return fixed(
        "clarification",
        ERROR_COPY.get(output.error.code, "clarify_request"),
        used=used,
        options=tuple(options),
    )


def safe_response(decision, used=()):
    return fixed(
        decision.status,
        decision.key,
        used=used,
        options=tuple(
            ClarificationOption(label_ar=party.display_name, value=party.id)
            for party in decision.options
        ),
    )


def action(reply):
    return DraftAction.model_validate(strict_json(reply.content))


def quoted_output(output, index):
    # Retain full provenance on the server. Send bounded facts/slot names, not
    # every repeated historical source ID and every daily projection scalar.
    require_verified(output)
    selected = []
    for value in (*output.figures, *output.metrics):
        if not value.source_ids or value.kind == "missing":
            continue
        if "scenarios" in output.result and not (
            value.key.startswith("j1.") or value.key.endswith("lowest.closing_iqd")
        ):
            continue
        if ".days." in value.key:
            continue
        selected.append(value)
    selected = selected[:64]
    dates = {
        key: str(value)
        for key, value in output.dates.items()
        if key in {"start", "end"} or key.endswith("due_date") or ".lowest." in key
    }
    names = []
    for direction in ("receivables", "payables"):
        report = output.result.get(direction)
        if report:
            names.extend(
                {
                    "id": party["counterparty_id"],
                    "name": party["display_name"],
                    "direction": direction,
                    "slot_prefix": f"{direction}.customers.{i}",
                }
                for i, party in enumerate(report["customers"][:20])
            )
    return json.dumps(
        {
            "trust": "untrusted_quoted_data",
            "data": {
                "range": output.resolved_range.model_dump(mode="json"),
                "counterparty": output.resolved_counterparty.model_dump(mode="json")
                if output.resolved_counterparty
                else None,
                "counterparties": names,
                "assumptions": output.assumptions,
                "warnings": output.warnings,
                "scenarios": list(output.result.get("scenarios", {})),
                "values": [
                    {
                        "key": f"tool_{index}.{v.key}",
                        "kind": v.kind,
                        "label_key": v.label_key,
                        "value": v.amount_iqd if hasattr(v, "amount_iqd") else v.value,
                    }
                    for v in selected
                ],
            },
            "slot_catalog": {
                "fig": [f"tool_{index}.{value.key}" for value in selected],
                "date": {f"tool_{index}.{key}": value for key, value in dates.items()},
            },
        },
        ensure_ascii=False,
    )


def checked_draft(draft, outputs, user_message):
    if not isinstance(draft, str) or unsafe_narration(draft):
        raise DraftValidationError("UNSAFE_NARRATION")
    return render_draft(
        draft,
        outputs=outputs,
        user_message=user_message,
        debt_list=answer_policy.debt_list_request(user_message),
    )


def response(rendered, outputs, used):
    if (
        rendered.renderer.fell_back_to_template
        and not rendered.figures
        and not rendered.metrics
    ):
        return fixed("clarification", "clarify_request", used=used)
    fields = rendered.model_dump()
    if rendered.resolved_range is None:
        for output in reversed(outputs):
            if (
                output.result.get("j1")
                or output.result.get("upcoming")
                or output.result.get("weekly")
            ):
                fields["resolved_range"] = output.resolved_range
                break
    if rendered.renderer.fell_back_to_template:
        fields["reply_ar"] = text("template_fallback") + " " + fields["reply_ar"]
    return ChatResponse(
        status="answered",
        **fields,
        assumptions_ar=tuple(
            text(key)
            for key in sorted(
                {
                    key
                    for output in outputs
                    for key in output.assumptions
                    if key in ASSUMPTIONS
                }
            )
        ),
        used_tools=tuple(dict.fromkeys(used)),
    )


CONVERSATION_TIMEOUT_SECONDS = 120


async def converse(request, *, client, connection, clock, known_at):
    try:
        async with asyncio.timeout(CONVERSATION_TIMEOUT_SECONDS):
            return await _converse(
                request,
                client=client,
                connection=connection,
                clock=clock,
                known_at=known_at,
            )
    except TimeoutError:
        return fixed("llm_unavailable", "busy")


async def _converse(request, *, client, connection, clock, known_at):
    period = resolve_period(request.message, weekday=clock.today.weekday())
    if period.status == "conflict" or ambiguous_weekday(request.message, clock):
        return fixed("clarification", "clarify_period")
    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTIONS},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "BUSINESS_AS_OF": str(clock.today),
                    "question": request.message,
                    "trust": "quoted_user_data",
                },
                ensure_ascii=False,
            ),
        },
    ]
    outputs, used = [], []
    was_query_only = connection.execute("PRAGMA query_only").fetchone()[0]
    connection.execute("PRAGMA query_only=ON")
    try:
        decision = answer_policy.before_provider(
            request.message,
            connection=connection,
            clock=clock,
            known_at=known_at,
            period=period,
        )
        if decision:
            return safe_response(decision)
        plan = select_plan(
            request.message,
            period=period,
            connection=connection,
            clock=clock,
            known_at=known_at,
        )
        if plan is not None and not isinstance(plan, ToolPlan):
            return safe_response(plan)
        if plan:
            history = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": f"plan-{index}",
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments),
                        },
                    }
                    for index, call in enumerate(plan.calls)
                ],
            }
            # Google's documented marker for client-executed function history.
            # The shared client removes this extension for other providers.
            history["tool_calls"][0]["extra_content"] = {
                "google": {"thought_signature": "skip_thought_signature_validator"}
            }
            messages.append(history)
            for index, call in enumerate(plan.calls):
                decision = answer_policy.after_selection(
                    request.message,
                    call.name,
                    call.arguments,
                    connection=connection,
                    clock=call.clock,
                    known_at=known_at,
                    trusted_party=call.party,
                )
                if decision:
                    return safe_response(decision, used)
                output = invoke(
                    call.name,
                    call.arguments,
                    connection=connection,
                    clock=call.clock,
                    known_at=known_at,
                    user_message=request.message,
                    server_period_set=True,
                    server_plan=plan.kind,
                )
                used.append(call.name)
                if not output.ok:
                    return tool_failure(output, used)
                outputs.append(output)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": f"plan-{index}",
                        "content": quoted_output(output, index),
                    }
                )
        # Reserve the fourth completion for the renderer's one draft retry.
        for _ in range(3):
            try:
                reply = await client.complete(
                    messages, tools=() if plan else definitions()
                )
            except LLMUnavailable as exc:
                if outputs:
                    return response(
                        render_reply(
                            None,
                            outputs=outputs,
                            debt_list=answer_policy.debt_list_request(request.message),
                        ),
                        outputs,
                        used,
                    )
                key = {
                    "not_configured": "provider_unconfigured",
                    "needs_internet": "needs_internet",
                }.get(exc.reason, "busy")
                return fixed("llm_unavailable", key)
            messages.append(reply.message)
            if reply.tool_calls:
                if plan:
                    # A narration-only turn cannot replace/extend its server plan.
                    break
                if len(used) + len(reply.tool_calls) > 8:
                    break
                for call in reply.tool_calls:
                    if call.name not in TOOLS:
                        return fixed("refused", "unsupported_write", used=used)
                    query = call.arguments.get("counterparty_query")
                    if isinstance(query, str) and normalize_name(
                        query
                    ) not in normalize_name(request.message):
                        return fixed("clarification", "clarify_customer", used=used)
                    name, arguments = call.name, dict(call.arguments)
                    if answer_policy.margin_request(request.message):
                        name = "get_margin"
                        arguments = {
                            key: value
                            for key, value in arguments.items()
                            if key in {"period", "start_date", "end_date"}
                        }
                        if "period" not in arguments and period.status == "resolved":
                            arguments["period"] = period.period
                        if "period" not in arguments:
                            return fixed("clarification", "clarify_request", used=used)
                    server_period_set = (
                        period.status == "resolved" and "period" in arguments
                    )
                    if server_period_set:
                        arguments["period"] = period.period
                        arguments.pop("start_date", None)
                        arguments.pop("end_date", None)
                    decision = answer_policy.after_selection(
                        request.message,
                        name,
                        arguments,
                        connection=connection,
                        clock=clock,
                        known_at=known_at,
                    )
                    if decision:
                        return safe_response(decision, used)
                    output = invoke(
                        name,
                        arguments,
                        connection=connection,
                        clock=clock,
                        known_at=known_at,
                        user_message=request.message,
                        server_period_set=server_period_set,
                    )
                    used.append(name)
                    if not output.ok:
                        return tool_failure(output, used)
                    upcoming = output.result.get("upcoming")
                    if upcoming and upcoming["cash_on_hand"]["kind"] == "missing":
                        return fixed(
                            "clarification", "clarify_opening_balance", used=used
                        )
                    outputs.append(output)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": quoted_output(output, len(outputs) - 1),
                        }
                    )
                continue
            try:
                final = action(reply)
            except (ValidationError, ValueError, TypeError):
                final = None
            if final and final.status != "answered":
                status = "answered" if final.status == "help" else final.status
                return fixed(status, final.message_key, used=used)
            if not outputs:
                return fixed("clarification", "clarify_request", used=used)
            draft = final.draft_ar if final else None
            try:
                return response(
                    checked_draft(draft, outputs, request.message), outputs, used
                )
            except DraftValidationError:
                revised = None
                messages.append(
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "render_error": "REJECTED_DRAFT",
                                "instruction": (
                                    "Retry DraftAction once. Only catalog fig/date "
                                    "slots for numbers; no guessed text."
                                ),
                            }
                        ),
                    }
                )
                try:
                    retry = await client.complete(messages, tools=())
                    candidate = action(retry)
                    if not retry.tool_calls and candidate.status in {
                        "clarification",
                        "refused",
                    }:
                        return fixed(candidate.status, candidate.message_key, used=used)
                    if not retry.tool_calls and candidate.status == "answered":
                        revised = (
                            ""
                            if unsafe_narration(candidate.draft_ar)
                            else candidate.draft_ar
                        )
                except (LLMUnavailable, ValidationError, ValueError, TypeError):
                    pass
                # The existing renderer retains ownership of retry counts/templates.
                original = (
                    draft
                    if isinstance(draft, str) and not unsafe_narration(draft)
                    else None
                )
                return response(
                    render_reply(
                        original,
                        outputs=outputs,
                        user_message=request.message,
                        retry=lambda _: revised,
                        debt_list=answer_policy.debt_list_request(request.message),
                    ),
                    outputs,
                    used,
                )
        if outputs:
            return response(
                render_reply(
                    None,
                    outputs=outputs,
                    debt_list=answer_policy.debt_list_request(request.message),
                ),
                outputs,
                used,
            )
        return fixed("clarification", "clarify_request", used=used)
    except FinancialRuleError:
        return fixed("error", "chat_error", used=used)
    finally:
        connection.execute(f"PRAGMA query_only={int(was_query_only)}")
