"""D59 reconciliation summaries on the synthetic primary shop."""

from datetime import date

import pytest
from scripts.evaluation_runtime import (
    observed_history,
    production_database,
    reference_parties,
)
from scripts.make_ground_truth import cutoff
from test_interpretation_pipeline import ROOT, ask, period, understood

from app.services.business_clock import BusinessClock

pytestmark = pytest.mark.pipeline("interpretation")


def test_d59_unspecified_reconciliation_lists_every_week_flag_and_cash_difference():
    from app.services.reconcile import reconciliation_report

    as_of = date(2026, 9, 28)
    history = observed_history("primary", as_of, ROOT / "data")
    with production_database(
        history, reference_parties(ROOT / "data"), as_of=as_of
    ) as db:
        expected = reconciliation_report(
            db, clock=BusinessClock(as_of), known_at=cutoff(as_of)
        ).flags
        selected = {
            r["source_id"]
            for r in history.rows
            if "2026-09-26" <= r["business_date"] <= "2026-09-28"
        }
        expected = [f for f in expected if selected.intersection(f.source_ids)]
    response = ask(
        "اكو شي غريب بالحسابات لازم انتبهله؟", understood(intent="reconciliation")
    )
    assert response.status == "answered"
    assert period(response) == ("2026-09-26", "2026-09-28")
    figures = {f.key: f for f in response.figures}
    for i, flag in enumerate(expected):
        shown = figures[f"tool_0.items.{i}.amount"]
        assert shown.amount_iqd == flag.amount.amount_iqd
        assert shown.source_ids == flag.source_ids
        assert all(source in response.reply_ar for source in flag.source_ids)
    assert any("cash_differences." in f.key for f in response.figures)
    assert all(f.source_ids or f.query_evidence for f in response.figures)
    assert "سرق" not in response.reply_ar
