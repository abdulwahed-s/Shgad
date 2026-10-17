"""Runtime exclusion without opening private/final files or reading any outcomes."""

from datetime import date
from pathlib import Path

import pytest

from app.services.business_clock import BusinessClock
from app.services.errors import FinancialRuleError
from app.services.ingest import import_csv

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "relative",
    [
        "synthetic/future_30d_ground_truth.csv",
        "synthetic/all_120d_canonical.csv",
        "synthetic/cash_difference_labels.json",
        "synthetic/planted_anomalies.json",
        "synthetic/forecast_eval_shops/unseen/observed_90d.csv",
        "synthetic/evaluation_only/obligations.csv",
        "evaluation/development_expected.json",
        "evaluation/answers.csv",
        "synthetic/observed_90d.csv/../unapproved.csv",
    ],
)
def test_packaged_non_observed_inputs_are_refused_before_open(
    ledger, monkeypatch, relative
):
    opened = []

    def fail_if_opened(path, *args, **kwargs):
        opened.append(path)
        raise AssertionError("An unapproved file must never be opened")

    monkeypatch.setattr(Path, "open", fail_if_opened)
    with pytest.raises(FinancialRuleError) as failure:
        import_csv(
            ledger,
            ROOT / "data" / relative,
            clock=BusinessClock(date(2026, 9, 28)),
            imported_at="2026-09-28T20:00:00+03:00",
        )
    assert failure.value.code == "IMPORT_REJECTED"
    assert opened == []
