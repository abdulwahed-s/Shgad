"""D58 end to end on the synthetic primary ledger with a scripted provider.

The provider only supplies the interpretation and a slot draft; every period,
identity, tool choice and figure below comes from the server.
"""

import asyncio
import json
from datetime import date
from pathlib import Path

import pytest
from scripts.evaluation_runtime import (
    observed_history,
    production_database,
    reference_parties,
)
from scripts.make_ground_truth import cutoff

from app.agents import orchestrator
from app.schemas.chat import ChatRequest
from app.services.business_clock import BusinessClock

ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.pipeline("interpretation")


class Reply:
    def __init__(self, content):
        self.content = content
        self.tool_calls = ()
        self.message = {"role": "assistant", "content": content}


class Scripted:
    def __init__(self, *contents):
        self.contents, self.calls = list(contents), []

    async def complete(self, messages, *, tools=(), json_mode=False):
        self.calls.append(json_mode)
        if not self.contents:
            return Reply("not json")
        return Reply(self.contents.pop(0))


def understood(**fields):
    value = {"behavior": "answer", "intent": "sales"} | fields
    return json.dumps(value, ensure_ascii=False)


def ask(question, *replies, as_of=date(2026, 9, 28), dataset="primary"):
    history = observed_history(dataset, as_of, ROOT / "data")
    with production_database(
        history, reference_parties(ROOT / "data"), as_of=as_of
    ) as db:
        client = Scripted(*replies)
        before = tuple(db.iterdump())
        response = asyncio.run(
            orchestrator.converse(
                ChatRequest(message=question, conversation_id="pipeline"),
                client=client,
                connection=db,
                clock=BusinessClock(as_of),
                known_at=cutoff(as_of),
            )
        )
        assert tuple(db.iterdump()) == before
    return response


def period(response):
    view = response.interpretation.period
    return (view.start.isoformat(), view.end.isoformat()) if view else None


def test_sales_with_a_past_weekday_resolves_on_the_server():
    response = ask(
        "الخميس شكد بعت كاش",
        understood(
            sales_kind="cash",
            time={"type": "weekday_past", "weekday": "thu", "evidence": "الخميس"},
        ),
    )
    assert response.status == "answered"
    assert response.interpretation.tools == ("get_sales",)
    assert period(response) == ("2026-09-24", "2026-09-24")
    assert response.used_tools == ("get_sales",)
    assert any(f.key.endswith("cash_sales") for f in response.figures)


def test_named_debt_is_a_snapshot_with_the_exact_party():
    response = ask(
        "ابو حيدر شكد باقي عليه",
        understood(intent="debts", party_mentions=["ابو حيدر"]),
    )
    assert response.status == "answered"
    assert response.interpretation.counterparty_ids == ("CUST-01",)
    assert period(response) == ("2026-09-28", "2026-09-28")


def test_supplier_named_with_role_words_resolves_and_sets_direction():
    response = ask(
        "المجهز مال الرف شكد اطلبه",
        understood(intent="debts", party_mentions=["المجهز مال الرف"]),
    )
    assert response.interpretation.counterparty_ids == ("SUP-01",)
    assert response.status == "answered"


def test_ambiguous_name_clarifies_with_both_candidates_and_no_figures():
    response = ask(
        "ابو علي شكد عليه",
        understood(intent="debts", party_mentions=["ابو علي"]),
    )
    assert response.status == "clarification"
    assert response.interpretation.reason == "AMBIGUOUS_COUNTERPARTY"
    assert response.interpretation.counterparty_ids == ("CUST-02", "CUST-03")
    assert not response.figures and not response.used_tools


def test_unknown_name_clarifies():
    response = ask(
        "ابو كرار شكد عليه", understood(intent="debts", party_mentions=["ابو كرار"])
    )
    assert response.interpretation.reason == "UNKNOWN_COUNTERPARTY"
    assert response.status == "clarification"


def test_supplier_sufficiency_uses_the_due_supplier_and_named_collection():
    response = ask(
        "اذا ابو حيدر دفع اكدر ادفع للمجهز الخميس",
        understood(
            intent="supplier_sufficiency",
            collection_party_mentions=["ابو حيدر"],
            time={"type": "weekday_next", "weekday": "thu", "evidence": "الخميس"},
        ),
    )
    assert response.status == "answered"
    assert response.interpretation.counterparty_ids == ("CUST-01", "SUP-01")
    assert response.interpretation.tools == ("get_debts", "forecast")
    assert period(response) == ("2026-09-28", "2026-10-01")
    assert any(
        f.key.endswith("j1.shortfall_without_collection") for f in response.figures
    )


@pytest.mark.parametrize(
    "time", [{"type": "today", "evidence": "هسه"}, {"type": "none"}]
)
def test_d59_supplier_now_uses_all_unpaid_invoices_and_no_collections(time):
    from app.services.financial_queries import QuerySnapshot

    as_of = date(2026, 9, 28)
    history = observed_history("primary", as_of, ROOT / "data")
    with production_database(
        history, reference_parties(ROOT / "data"), as_of=as_of
    ) as db:
        snapshot = QuerySnapshot(db, clock=BusinessClock(as_of), known_at=cutoff(as_of))
        due = sum(
            b.amount_iqd
            for b in snapshot.balances
            if b.obligation.kind == "payable"
            and b.obligation.counterparty_id == "SUP-01"
        )
    response = ask(
        "اكدر ادفع لمجهز الرف كل اللي عليه هسه؟",
        understood(
            intent="supplier_sufficiency", party_mentions=["مجهز الرف"], time=time
        ),
    )
    assert response.status == "answered"
    assert period(response) == ("2026-09-28", "2026-09-28")
    assert response.interpretation.counterparty_ids == ("SUP-01",)
    assert response.used_tools == response.interpretation.tools == ("get_debts",)
    figures = {f.key.split(".", 1)[1]: f for f in response.figures}
    assert set(figures) == {
        "payment_now.cash_on_hand",
        "payment_now.supplier_due",
        "payment_now.position_confirmed",
    }
    assert figures["payment_now.cash_on_hand"].amount_iqd == 420000
    assert figures["payment_now.supplier_due"].amount_iqd == due
    assert figures["payment_now.position_confirmed"].amount_iqd == 420000 - due
    assert all(f.source_ids and f.formula for f in figures.values())


def test_d59_supplier_now_without_opening_cash_clarifies():
    response = ask(
        "اكدر ادفع لمجهز الرف هسه؟",
        understood(intent="supplier_sufficiency", party_mentions=["مجهز الرف"]),
        dataset="missing_opening_balance",
    )
    assert response.status == "clarification"
    assert response.interpretation.reason == "MISSING_OPENING_BALANCE"
    assert not response.figures


def test_upcoming_window_from_copied_days():
    response = ask(
        "شنو علي خلال ٥ ايام الجاية",
        understood(
            intent="upcoming_obligations",
            days=5,
            time={"type": "next_n_days", "n": 5, "evidence": "خلال ٥ ايام الجاية"},
        ),
    )
    assert period(response) == ("2026-09-28", "2026-10-02")
    assert response.status == "answered"


def test_d59_this_week_payments_include_the_thursday_invoice():
    response = ask(
        "شكد لازم ادفع للمجاهزين هالاسبوع؟",
        understood(
            intent="upcoming_obligations",
            time={"type": "this_week", "evidence": "هالاسبوع"},
        ),
    )
    assert response.status == "answered"
    assert period(response) == ("2026-09-28", "2026-10-02")
    dues = next(f for f in response.figures if f.key.endswith("upcoming.dues_total"))
    assert dues.amount_iqd == 650000
    assert dues.source_ids and dues.formula


def test_drawings_for_a_month_use_period_movements():
    response = ask(
        "شكد سحبت للبيت بشهر آب",
        understood(
            intent="period_movements",
            movement="owner_drawings",
            time={"type": "month", "month": 8, "evidence": "بشهر آب"},
        ),
    )
    assert response.status == "answered"
    assert period(response) == ("2026-08-01", "2026-08-31")
    assert any(f.key.endswith("weekly.owner_drawings") for f in response.figures)


@pytest.mark.parametrize(
    ("time", "expected"),
    [
        (
            {"type": "last_week", "evidence": "الاسبوع اللي فات"},
            ("2026-09-19", "2026-09-25"),
        ),
        ({"type": "month", "month": 8, "evidence": "آب"}, ("2026-08-01", "2026-08-31")),
    ],
)
def test_summary_for_a_week_or_any_range(time, expected):
    question = "لخصلي الشغل " + time["evidence"]
    response = ask(question, understood(intent="weekly_summary", time=time))
    assert response.status == "answered"
    assert period(response) == expected
    assert set(response.used_tools) == {
        "get_sales",
        "get_debts",
        "get_margin",
        "reconcile",
    }


def test_cash_on_hand_is_a_snapshot_and_missing_opening_clarifies():
    response = ask("شكد الكاش بالدرج هسه", understood(intent="cash_on_hand"))
    assert response.status == "answered"
    assert period(response) == ("2026-09-28", "2026-09-28")
    missing = ask(
        "شكد الكاش بالدرج هسه",
        understood(intent="cash_on_hand"),
        dataset="missing_opening_balance",
    )
    assert missing.status == "clarification"
    assert missing.interpretation.reason == "MISSING_OPENING_BALANCE"


def test_past_today_weekday_and_future_history_clarify_from_the_resolver():
    same_day = ask(
        "الاثنين شكد بعت",
        understood(
            time={"type": "weekday_past", "weekday": "mon", "evidence": "الاثنين"}
        ),
    )
    assert same_day.interpretation.reason == "AMBIGUOUS_DATE"
    early = ask(
        "شكد بعت بشهر حزيران",
        understood(time={"type": "month", "month": 6, "evidence": "بشهر حزيران"}),
    )
    assert early.interpretation.reason == "NO_HISTORICAL_DATA"


def test_write_backstop_refuses_without_calling_the_provider():
    client_replies = ()
    response = ask("سجل دفعة لابو حيدر", *client_replies)
    assert response.status == "refused"
    assert response.interpretation.behavior == "refuse"


def test_unproven_interpretation_fails_closed_to_clarification():
    response = ask(
        "شكد بعت اليوم",
        understood(time={"type": "day", "day": 12, "evidence": "اليوم"}),
        understood(time={"type": "day", "day": 12, "evidence": "اليوم"}),
    )
    assert response.status == "clarification"
    assert not response.figures


def test_slot_draft_is_rendered_from_verified_figures():
    response = ask(
        "شكد بعنا اليوم",
        understood(time={"type": "today", "evidence": "اليوم"}),
        json.dumps(
            {
                "status": "answered",
                "draft_ar": "مبيعات اليوم {{fig:tool_0.total_sales}}",
            }
        ),
    )
    assert response.status == "answered"
    assert not response.renderer.fell_back_to_template


def test_role_words_alone_are_not_names():
    response = ask(
        "اكدر اوفي المجهز الخميس",
        understood(
            intent="supplier_sufficiency",
            party_mentions=["المجهز"],
            time={"type": "weekday_next", "weekday": "thu", "evidence": "الخميس"},
        ),
    )
    assert response.status == "answered"
    assert response.interpretation.counterparty_ids == ("SUP-01",)
    totals = ask(
        "شكد بقي على الزباين", understood(intent="debts", party_mentions=["الزباين"])
    )
    assert totals.status == "answered"
    assert totals.interpretation.counterparty_ids == ()


def test_qualified_similar_names_resolve_to_one_party():
    response = ask(
        "اريد الباقي على ابو علي دفتر ب",
        understood(intent="debts", party_mentions=["ابو علي دفتر ب"]),
    )
    assert response.interpretation.counterparty_ids == ("CUST-03",)


def test_month_summary_includes_movements_and_current_balances():
    response = ask(
        "شغل آب شلون جان",
        understood(
            intent="weekly_summary",
            time={"type": "month", "month": 8, "evidence": "آب"},
        ),
    )
    keys = {f.key.split(".", 1)[1] for f in response.figures}
    assert {"total_sales", "weekly.owner_drawings", "weekly.operating_expenses"} <= keys
    debts = [c for c in response.contexts if c.range.start == c.range.end]
    assert all(c.range.end.isoformat() == "2026-09-28" for c in debts)


def test_collections_audit_answers_even_without_flags():
    response = ask(
        "دقق تحصيلات امس",
        understood(
            intent="reconciliation", time={"type": "yesterday", "evidence": "امس"}
        ),
    )
    assert response.status == "answered"
    assert any(f.key.endswith("weekly.collections") for f in response.figures)


def test_cash_answer_offers_and_templates_only_the_cash_figure():
    response = ask("شكد الكاش بالدرج هسه", understood(intent="cash_on_hand"))
    assert [f.key for f in response.figures] == ["tool_0.upcoming.cash_on_hand"]
    assert response.renderer.fell_back_to_template


def test_upcoming_answer_never_offers_whole_ledger_balances():
    from app.agents.orchestrator import answers

    assert answers("upcoming_obligations", "upcoming.dues_total")
    assert not answers("upcoming_obligations", "payables.total_outstanding")
    assert not answers("upcoming_obligations", "upcoming.days.0.dues_iqd")
    assert not answers("upcoming_obligations", "upcoming.dues.0.outstanding")
    assert answers("upcoming_obligations", "upcoming.days.0.dues_iqd", per_day=True)
    response = ask(
        "شنو علي خلال ٥ ايام الجاية",
        understood(
            intent="upcoming_obligations",
            days=5,
            time={"type": "next_n_days", "n": 5, "evidence": "خلال ٥ ايام الجاية"},
        ),
    )
    assert response.figures
    assert all(f.key.startswith("tool_0.upcoming.") for f in response.figures)


def test_empty_schedule_zero_is_shown_and_independently_supported():
    from scripts.evaluation_evidence import METHOD_V2
    from scripts.evaluation_metrics import compare_claim
    from scripts.evaluation_truth import claim_catalogue

    as_of = date(2026, 9, 28)
    response = ask(
        "شكد مطلوب ندفع بهاليومين",
        understood(
            intent="upcoming_obligations",
            days=2,
            time={"type": "next_n_days", "n": 2, "evidence": "بهاليومين"},
        ),
        json.dumps(
            {
                "status": "answered",
                "draft_ar": "المطلوب {{fig:tool_0.upcoming.dues_total}}، باليوم الأول "
                "{{fig:tool_0.upcoming.days.0.dues_iqd}}",
            }
        ),
    )
    figures = {f.key.split(".", 1)[1]: f for f in response.figures}
    for key in ("upcoming.dues_total", "upcoming.days.0.dues_iqd"):
        assert figures[key].amount_iqd == 0 and figures[key].query_evidence
    history = observed_history("primary", as_of, ROOT / "data")
    catalogue = claim_catalogue(
        history,
        as_of,
        as_of,
        date(2026, 9, 29),
        parameters={"days": 2},
        method=METHOD_V2,
    )
    for key in ("upcoming.dues_total", "upcoming.days.0.dues_iqd"):
        figure = figures[key]
        claim = dict(
            field=key,
            value=0,
            unit="IQD",
            label=figure.label_key,
            source_ids=[],
            formula=figure.formula,
            query_evidence=figure.query_evidence.model_dump(mode="json"),
        )
        assert compare_claim(catalogue[key], claim, method=METHOD_V2) == (True, True)
