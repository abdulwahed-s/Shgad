"""T24/T31: slot-only rendering from this turn's verified financial results."""

from datetime import date, datetime

import pytest

from app.agents.renderer import DraftValidationError, render_draft, render_reply
from app.agents.tool_registry import invoke
from app.services.business_clock import BusinessClock
from app.services.errors import FinancialRuleError

CLOCK = BusinessClock(date(2026, 9, 28))
KNOWN = datetime.fromisoformat("2026-09-28T23:59:59+03:00")


def call(ledger, name, args):
    result = invoke(name, args, connection=ledger, clock=CLOCK, known_at=KNOWN)
    assert result.ok, result.error
    return result


def test_t24_verified_iqd_dates_and_evidence(j1_shop):
    output = call(
        j1_shop, "get_debts", {"direction": "both", "due_period": "next_n_days:7"}
    )
    rendered = render_draft(
        "عندك {{fig:upcoming.cash_on_hand}}؛ لغاية {{date:end}}.", outputs=[output]
    )
    assert "٤٢٠ ألف" in rendered.reply_ar
    assert "٢٨/٠٩/٢٠٢٦" in rendered.reply_ar and "٠٤/١٠/٢٠٢٦" in rendered.reply_ar
    assert rendered.figures[0].source_ids == ("CNT-090",)
    assert rendered.figures[0].formula
    assert "مو مضمون" in rendered.reply_ar
    assert rendered.resolved_range == output.resolved_range


@pytest.mark.parametrize(
    "number", ["420000", "٤٢٠٠٠٠", "۴۲۰۰۰۰", "４２００００", "²", "Ⅻ"]
)
def test_t24_rejects_all_literal_numeric_characters(tool_history, number):
    output = call(tool_history, "get_sales", {"period": "today"})
    with pytest.raises(DraftValidationError, match="RAW_NUMBER"):
        render_draft(f"المبلغ {number}", outputs=[output])


@pytest.mark.parametrize(
    "draft",
    [
        "{{fig:invented}}",
        "{{date:invented}}",
        "{{text:customer}}",
        "{{fig:cash_sales}",
        "{{{{fig:cash_sales}}}}",
    ],
)
def test_unknown_or_malformed_slots_rejected(tool_history, draft):
    output = call(tool_history, "get_sales", {"period": "today"})
    with pytest.raises(DraftValidationError):
        render_draft(draft, outputs=[output])


def test_user_digits_only_allowed_as_verbatim_quoted_data(tool_history):
    output = call(tool_history, "get_sales", {"period": "today"})
    user = "ذكرت ١٥٠٠٠٠ بس أريد المبيعات"
    rendered = render_draft(
        "قلت «ذكرت ١٥٠٠٠٠ بس أريد المبيعات»؛ المسجل {{fig:cash_sales}}.",
        outputs=[output],
        user_message=user,
    )
    assert "«ذكرت ١٥٠٠٠٠ بس أريد المبيعات»" in rendered.reply_ar
    assert "١٠ ألف" in rendered.reply_ar
    with pytest.raises(DraftValidationError):
        render_draft("المبيعات ١٥٠٠٠٠", outputs=[output], user_message=user)


def test_t24_one_retry_then_template_and_no_unverified_amount(tool_history):
    output = call(tool_history, "get_sales", {"period": "today"})
    attempts = []

    def retry(reason):
        attempts.append(reason)
        return "الجواب 999999"

    rendered = render_reply("الجواب 888888", outputs=[output], retry=retry)
    assert len(attempts) == 1
    assert rendered.renderer.attempts == 2 and rendered.renderer.fell_back_to_template
    assert "888888" not in rendered.reply_ar and "999999" not in rendered.reply_ar
    assert "١٠ ألف" in rendered.reply_ar and rendered.figures
    assert all(f.source_ids and f.formula for f in rendered.figures)


def test_retry_can_return_valid_slots_once(tool_history):
    output = call(tool_history, "get_sales", {"period": "today"})
    rendered = render_reply(
        "الجواب 9", outputs=[output], retry=lambda _: "المسجل {{fig:cash_sales}}"
    )
    assert (
        rendered.renderer.attempts == 2 and not rendered.renderer.fell_back_to_template
    )


def test_missing_or_unsourced_figures_cannot_render(ledger):
    output = call(ledger, "get_sales", {"period": "today"})
    for key in ("cash_sales", "unexplained_cash_difference"):
        with pytest.raises(DraftValidationError):
            render_draft("{{fig:" + key + "}}", outputs=[output])
    rendered = render_reply("{{fig:cash_sales}}", outputs=[output])
    assert not rendered.figures
    assert "أرقام موثقة" in rendered.reply_ar


def test_t31_customer_and_period_always_come_from_verified_context(
    ledger, debt_factory
):
    ledger.execute(
        "INSERT INTO counterparties VALUES ('T31', 'أبو حيدر الجديد', 'customer')"
    )
    debt_factory("T31-R", 45000, "2026-09-30", party="T31")
    output = call(
        ledger,
        "get_debts",
        {"counterparty_query": "أبو حيدر الجديد", "due_period": "this_week"},
    )
    rendered = render_draft("تمت مراجعة السجلات.", outputs=[output])
    assert "أبو حيدر الجديد" in rendered.reply_ar
    assert "٢٦/٠٩/٢٠٢٦" in rendered.reply_ar and "٢٨/٠٩/٢٠٢٦" in rendered.reply_ar
    assert rendered.resolved_counterparty.id == "T31"
    assert rendered.resolved_range.start == date(2026, 9, 26)


def test_margin_always_restates_coverage_and_cost_exclusions(tool_history):
    output = call(tool_history, "get_margin", {"period": "today"})
    rendered = render_draft("الهامش {{fig:gross_margin}}.", outputs=[output])
    assert "٪" in rendered.reply_ar
    assert any(m.key == "coverage_pct" for m in rendered.metrics)
    assert "غير المسجلة" in rendered.reply_ar


def test_forecast_always_names_scenario_and_estimate(tool_history):
    output = call(tool_history, "forecast", {"scenario": "stress"})
    rendered = render_reply("9", outputs=[output])
    assert "تقدير" in rendered.reply_ar and "ضغط" in rendered.reply_ar
    assert "مو مضمون" in rendered.reply_ar


def test_renderer_rejects_mutated_or_untrusted_outputs(tool_history):
    output = call(tool_history, "get_sales", {"period": "today"})
    output.result["cash_sales"]["amount_iqd"] += 1
    with pytest.raises(FinancialRuleError):
        render_reply("{{fig:cash_sales}}", outputs=[output])


def test_multiple_outputs_need_namespaced_keys_when_periods_conflict(tool_history):
    today = call(tool_history, "get_sales", {"period": "today"})
    week = call(tool_history, "get_sales", {"period": "this_week"})
    with pytest.raises(DraftValidationError):
        render_draft("{{fig:cash_sales}}", outputs=[today, week])
    rendered = render_draft(
        "اليومي {{fig:tool_0.cash_sales}}، والأسبوعي {{fig:tool_1.cash_sales}}.",
        outputs=[today, week],
    )
    assert "١٠ ألف" in rendered.reply_ar and "٣٠ ألف" in rendered.reply_ar
    assert len(rendered.contexts) == 2
