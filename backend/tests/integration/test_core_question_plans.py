"""FINANCIAL_RULES sections5/7: real tools/SQLite, fake provider only."""

import asyncio
import json
from datetime import date, datetime, timedelta

import httpx
import pytest

from app.agents import orchestrator
from app.agents.llm_client import LLMClient
from app.agents.messages_ar import text
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


def converse(connection, message, *replies, clock=CLOCK, provider="groq"):
    sent = []
    queue = list(replies)

    def respond(request):
        sent.append(json.loads(request.content))
        assert queue, "unexpected provider request"
        return httpx.Response(200, json={"choices": [{"message": queue.pop(0)}]})

    async def run():
        async with LLMClient(
            Settings(
                llm_provider=provider,
                llm_model_id="fake-core",
                **{f"{provider}_api_key": "fictional"},
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


@pytest.fixture
def tool_attempts(monkeypatch):
    original, recorded = orchestrator.invoke, []

    def record(name, arguments, **kwargs):
        output = original(name, arguments, **kwargs)
        recorded.append((name, arguments, kwargs, output))
        return output

    monkeypatch.setattr(orchestrator, "invoke", record)
    return recorded


@pytest.fixture
def weekly_shop(ledger, insert_event):
    for day in ("2026-09-20", "2026-09-26"):
        insert_event(
            source_id=f"PRICED-{day}",
            amount_iqd=80000,
            category_id="CAT-01",
            quantity=16,
            occurred_at=f"{day}T12:00:00+03:00",
        )
        for kind, value in (
            ("CREDIT_COLLECTION", 2500),
            ("OPERATING_EXPENSE", 700),
            ("OWNER_DRAWING", 300),
            ("CAPITAL_INJECTION", 900),
            ("SUPPLIER_PAYMENT", 1200),
        ):
            insert_event(
                source_id=f"{kind}-{day}",
                type=kind,
                amount_iqd=value,
                status="flagged"
                if kind in {"CREDIT_COLLECTION", "SUPPLIER_PAYMENT"}
                else "valid",
                counterparty_id=(
                    "SUP-01"
                    if kind == "SUPPLIER_PAYMENT"
                    else "CUST-01"
                    if kind == "CREDIT_COLLECTION"
                    else None
                ),
                occurred_at=f"{day}T13:00:00+03:00",
            )
    ledger.commit()
    return ledger


@pytest.mark.parametrize(
    "phrase,period,start,end",
    (
        ("لخصلي هذا الاسبوع", "this_week", "2026-09-26", "2026-09-28"),
        ("شلون مشى المحل الاسبوع الماضي", "last_week", "2026-09-19", "2026-09-25"),
        ("وضح سحوبات ومصاريف هالاسبوع", "this_week", "2026-09-26", "2026-09-28"),
    ),
)
def test_weekly_plan_executes_exact_set_before_narration(
    weekly_shop, tool_attempts, phrase, period, start, end
):
    before = tuple(weekly_shop.iterdump())
    result, sent = converse(weekly_shop, phrase, draft("{{fig:total_sales}}"))
    assert result.status == "answered"
    assert result.used_tools == ("get_sales", "get_debts", "get_margin", "reconcile")
    assert len(sent) == 1 and not sent[0].get("tools")
    assert [row[1] for row in tool_attempts] == [
        {"period": period, "kind": "all"},
        {"direction": "both"},
        {"period": period},
        {"period": period},
    ]
    assert str(tool_attempts[1][2]["clock"].today) == end
    assert (
        str(result.resolved_range.start) == start
        and str(result.resolved_range.end) == end
    )
    amounts = {f.key.split(".", 1)[-1]: f.amount_iqd for f in result.figures}
    assert amounts["weekly.collections"] == 2500
    assert amounts["weekly.operating_expenses"] == 700
    assert amounts["weekly.owner_drawings"] == 300
    assert amounts["gross_margin"] == 64000
    assert tuple(weekly_shop.iterdump()) == before


@pytest.mark.parametrize("unpriced,shown", ((20000, True), (20001, False)))
def test_weekly_margin_reuses_exact_d2_threshold(
    weekly_shop, insert_event, tool_attempts, unpriced, shown
):
    insert_event(source_id="UNPRICED", amount_iqd=unpriced)
    weekly_shop.commit()
    result, _ = converse(weekly_shop, "ملخص هالاسبوع", draft("{{fig:total_sales}}"))
    assert result.status == "answered"
    margin = next(row[3] for row in tool_attempts if row[0] == "get_margin")
    assert margin.result["shown"] is shown
    assert margin.result["unpriced_sales_count"] == 1
    assert margin.result["gross_margin"]["amount_iqd"] == (64000 if shown else None)
    assert any(f.key.endswith("gross_margin") for f in result.figures) is shown
    if not shown:
        assert text("margin_insufficient_priced_sales") in result.reply_ar


def test_weekly_missing_costs_keeps_verified_flows(ledger, insert_event, tool_attempts):
    insert_event(source_id="NO-COST", amount_iqd=40000)
    ledger.commit()
    result, _ = converse(ledger, "لخصلي هذا الاسبوع", draft("{{fig:total_sales}}"))
    assert result.status == "answered"
    assert len(tool_attempts) == 4
    assert text("margin_insufficient_priced_sales") in result.reply_ar
    assert not any(f.key.endswith("gross_margin") for f in result.figures)


def test_previous_week_balances_are_as_of_closing_not_due_date_filtered(
    weekly_shop, insert_event, tool_attempts
):
    for key, day, value in (("OLD", "2026-09-20", 60000), ("NEW", "2026-09-28", 40000)):
        row = insert_event(
            source_id=key,
            type="CREDIT_SALE",
            amount_iqd=value,
            counterparty_id="CUST-01",
            category_id="CAT-01",
            quantity=12,
            obligation_id=f"OB-{key}",
            due_date="2026-10-15",
            occurred_at=f"{day}T12:00:00+03:00",
        )
        weekly_shop.execute(
            "INSERT INTO obligations VALUES (?, ?, ?, ?, ?, ?)",
            (
                row.obligation_id,
                "receivable",
                row.transaction_id,
                "CUST-01",
                value,
                "2026-10-15",
            ),
        )
    payment = insert_event(
        source_id="AFTER-WEEK",
        type="CREDIT_COLLECTION",
        amount_iqd=10000,
        counterparty_id="CUST-01",
        obligation_id="OB-OLD",
    )
    weekly_shop.execute(
        "INSERT INTO payment_links VALUES (?, ?, ?, ?, ?, ?)",
        (
            "AFTER-LINK",
            payment.transaction_id,
            "OB-OLD",
            10000,
            "definite",
            "2026-09-28T10:00:00+00:00",
        ),
    )
    weekly_shop.commit()
    result, _ = converse(
        weekly_shop, "لخصلي الاسبوع الماضي", draft("{{fig:total_sales}}")
    )
    assert result.status == "answered"
    debts = next(
        row[3].result["receivables"] for row in tool_attempts if row[0] == "get_debts"
    )
    assert debts["as_of"] == "2026-09-25"
    assert debts["total_outstanding"]["amount_iqd"] == 60000
    assert debts["customers"][0]["obligations"][0]["due_date"] == "2026-10-15"


@pytest.fixture
def cash_shop(ledger, insert_event, debt_factory):
    ledger.execute(
        "INSERT INTO counterparties VALUES (?, ?, ?)",
        ("CUST-03", "علي كريم", "customer"),
    )
    for offset in range(9):
        day = date(2026, 9, 20) + timedelta(days=offset)
        insert_event(
            source_id=f"CASH-SALE-{offset}",
            amount_iqd=10000,
            category_id="CAT-01",
            quantity=2,
            occurred_at=f"{day}T12:00:00+03:00",
        )
        insert_event(
            source_id=f"CASH-COUNT-{offset}",
            type="DAILY_CASH_COUNT",
            amount_iqd=340000 + offset * 10000,
            occurred_at=f"{day}T21:00:00+03:00",
        )
    debt_factory("EXPECTED", 150000, "2026-09-30", party="CUST-03")
    debt_factory("SUPPLIER-DUE", 650000, "2026-10-01", kind="payable")
    settled = debt_factory("LATE-SETTLED", 30000, "2026-09-25", party="CUST-03")
    payment = insert_event(
        source_id="PAID-LATE",
        type="CREDIT_COLLECTION",
        amount_iqd=30000,
        counterparty_id="CUST-03",
        obligation_id=settled.obligation_id,
    )
    ledger.execute(
        "INSERT INTO payment_links VALUES (?, ?, ?, ?, ?, ?)",
        (
            "PAID-LINK",
            payment.transaction_id,
            settled.obligation_id,
            30000,
            "definite",
            "2026-09-28T10:00:00+00:00",
        ),
    )
    ledger.commit()
    return ledger


@pytest.mark.parametrize("conditional", (True, False))
def test_cash_plan_j1_both_scenarios_and_exact_identities(
    cash_shop, tool_attempts, conditional
):
    message = (
        "اذا علي كريم دفع اكدر اوفي المجهز الخميس"
        if conditional
        else "بدون تحصيل شكد النقص للمجهز الخميس"
    )
    before = tuple(cash_shop.iterdump())
    result, sent = converse(cash_shop, message, draft("{{fig:j1.cash_on_hand}}"))
    assert all(row[3].ok for row in tool_attempts), [
        (row[0], row[3].error) for row in tool_attempts
    ]
    assert result.status == "answered" and result.used_tools == (
        "get_debts",
        "forecast",
    )
    assert len(sent) == 1 and not sent[0].get("tools")
    assert len(tool_attempts) == (3 if conditional else 2)
    assert tool_attempts[-1][1] == {"scenario": "all", "until": "next_weekday:thu"}
    identities = {c.counterparty.id for c in result.contexts if c.counterparty}
    assert identities == ({"SUP-01", "CUST-03"} if conditional else {"SUP-01"})
    amounts = {f.key.split(".", 1)[-1]: f.amount_iqd for f in result.figures}
    assert amounts["j1.shortfall_with_collection"] == 80000
    assert amounts["j1.shortfall_without_collection"] == 230000
    assert text("collections_expected_not_guaranteed") in result.reply_ar
    assert str(result.resolved_range.end) == "2026-10-01"
    assert tuple(cash_shop.iterdump()) == before


def test_cash_plan_ambiguous_supplier_offers_verified_options(
    cash_shop, tool_attempts, debt_factory
):
    cash_shop.execute(
        "INSERT INTO counterparties VALUES (?, ?, ?)",
        ("SUP-02", "مجهز ثاني", "supplier"),
    )
    debt_factory("OTHER-SUPPLIER", 30000, "2026-10-01", kind="payable", party="SUP-02")
    cash_shop.commit()
    result, sent = converse(cash_shop, "اكدر اوفي المجهز الخميس")
    assert result.status == "clarification" and result.reply_ar == text(
        "clarify_customer"
    )
    assert {o.value for o in result.clarification.options} == {"SUP-01", "SUP-02"}
    assert not sent and not tool_attempts


def test_cash_generic_supplier_resolves_unique_due_day_identity(
    cash_shop, tool_attempts
):
    cash_shop.execute(
        "INSERT INTO counterparties VALUES (?, ?, ?)",
        ("SUP-02", "مجهز مختلف", "supplier"),
    )
    cash_shop.commit()
    result, _ = converse(
        cash_shop, "اكدر اوفي المجهز الخميس", draft("{{fig:j1.cash_on_hand}}")
    )
    assert result.status == "answered"
    assert tool_attempts[0][3].resolved_counterparty.id == "SUP-01"


def test_negative_collection_condition_needs_no_unnamed_customer(cash_shop):
    result, _ = converse(
        cash_shop,
        "اذا ما يوصلني التحصيل شكد العجز للمجهز الخميس",
        draft("{{fig:j1.cash_on_hand}}"),
    )
    assert result.status == "answered"
    assert {c.counterparty.id for c in result.contexts if c.counterparty} == {"SUP-01"}


def test_cash_plan_ambiguous_customer_never_merges(cash_shop, tool_attempts):
    result, sent = converse(cash_shop, "اذا ابو حيدر دفع اكدر اوفي المجهز الخميس")
    assert result.reply_ar == text("clarify_customer")
    assert {o.value for o in result.clarification.options} == {"CUST-01", "CUST-02"}
    assert not sent and not tool_attempts


def test_cash_plan_bare_today_weekday_clarifies(cash_shop, tool_attempts):
    result, sent = converse(cash_shop, "اكدر اوفي المجهز الاثنين")
    assert result.reply_ar == text("clarify_period")
    assert not sent and not tool_attempts


def test_cash_plan_missing_opening_cash_never_invents_zero(ledger, debt_factory):
    debt_factory("PAYABLE", 650000, "2026-10-01", kind="payable")
    ledger.commit()
    result, sent = converse(ledger, "اكدر اوفي المجهز الخميس")
    assert result.reply_ar == text("clarify_opening_balance")
    assert not result.figures and not sent


def test_gate_precedes_plans(cash_shop, tool_attempts):
    result, sent = converse(cash_shop, "امسح ملخص هالاسبوع")
    assert result.reply_ar == text("unsupported_write")
    assert not sent and not tool_attempts


def test_conditional_supplier_balance_keeps_explicit_party_role(ledger, debt_factory):
    ledger.execute(
        "INSERT INTO counterparties VALUES (?, ?, ?)",
        ("SUP-02", "أبو حيدر", "supplier"),
    )
    debt_factory("NAMED-SUPPLIER", 15000, "2026-10-01", kind="payable", party="SUP-02")
    ledger.commit()
    result, sent = converse(
        ledger,
        "لو اسال عن المجهز ابو حيدر شكد باقي",
        calls(
            ("get_debts", {"direction": "payable", "counterparty_query": "ابو حيدر"})
        ),
        draft("{{fig:payables.total_outstanding}}"),
    )
    assert result.status == "answered" and len(sent) == 2
    assert result.resolved_counterparty.id == "SUP-02"


def test_uncertain_summary_keeps_normal_model_choice(weekly_shop, tool_attempts):
    result, sent = converse(
        weekly_shop,
        "لخصلي مبيعات هذا الاسبوع",
        calls(("get_sales", {"period": "this_week"})),
        draft("{{fig:total_sales}}"),
    )
    assert result.status == "answered" and result.used_tools == ("get_sales",)
    assert len(sent) == 2 and len(tool_attempts) == 1


def test_server_plan_has_documented_gemini_history_marker(weekly_shop):
    result, sent = converse(
        weekly_shop, "ملخص هالاسبوع", draft("{{fig:total_sales}}"), provider="gemini"
    )
    assert result.status == "answered"
    history = sent[0]["messages"][2]["tool_calls"]
    assert (
        history[0]["extra_content"]["google"]["thought_signature"]
        == "skip_thought_signature_validator"
    )


def test_provider_cannot_replace_deterministic_plan(weekly_shop, tool_attempts):
    result, _ = converse(
        weekly_shop, "لخصلي هذا الاسبوع", calls(("forecast", {"scenario": "stress"}))
    )
    assert result.status == "answered" and result.renderer.fell_back_to_template
    assert [row[0] for row in tool_attempts] == [
        "get_sales",
        "get_debts",
        "get_margin",
        "reconcile",
    ]


def test_cash_plan_defers_unspecified_selective_counterfactual(cash_shop, debt_factory):
    from app.agents.tool_plans import select_plan

    debt_factory("OTHER-EXPECTED", 12000, "2026-09-30", party="CUST-01")
    cash_shop.commit()
    message = "اذا علي كريم دفع اكدر اوفي المجهز الخميس"
    plan = select_plan(
        message,
        period=resolve_period(message, weekday=0),
        connection=cash_shop,
        clock=CLOCK,
        known_at=KNOWN,
    )
    assert plan is None


def test_model_cannot_select_weekly_transport_projection(weekly_shop):
    output = invoke(
        "get_sales",
        {"period": "this_week", "server_plan": "weekly_summary"},
        connection=weekly_shop,
        clock=CLOCK,
        known_at=KNOWN,
    )
    assert not output.ok and output.error.code == "VALIDATION_ERROR"


def test_weekly_projection_rejects_consistent_but_forged_figures(weekly_shop):
    from app.agents.verification import verify_tool_output
    from app.services.errors import FinancialRuleError
    from app.services.financial_queries import QuerySnapshot

    output = invoke(
        "get_sales",
        {"period": "this_week"},
        connection=weekly_shop,
        clock=CLOCK,
        known_at=KNOWN,
        server_plan="weekly_summary",
    )
    assert output.ok
    output.result["weekly"]["owner_drawings"]["amount_iqd"] = 700
    output = output.model_copy(
        update={
            "figures": tuple(
                f.model_copy(update={"amount_iqd": 700})
                if f.key == "weekly.owner_drawings"
                else f
                for f in output.figures
            )
        }
    )
    with pytest.raises(FinancialRuleError):
        verify_tool_output(
            output,
            snapshot=QuerySnapshot(weekly_shop, clock=CLOCK, known_at=KNOWN),
            tool_name="get_sales",
            weekly_plan=True,
        )
