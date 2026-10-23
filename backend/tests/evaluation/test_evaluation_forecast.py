"""Forecast reporting tests use handmade rows only; final outcomes stay unopened."""

from datetime import date, timedelta

from scripts.evaluation_forecast import series_rows


def test_cutoff_75_csv_contains_30_predictions_but_only_15_realized_dates():
    start = date(2026, 9, 13)
    days = [
        dict(date=str(start + timedelta(days=i)), closing_iqd=100 - i)
        for i in range(1, 31)
    ]
    case = dict(
        shop="format-sentinel",
        cutoff_day=75,
        as_of=str(start),
        scored_days=15,
        predictions=dict(scenarios={"base": dict(days=days)}, baseline=dict(days=days)),
    )
    opened = []

    def realized(day):
        assert day <= date(2026, 9, 28)
        opened.append(day)
        return 100

    predictions, outcomes = series_rows(case, realized)
    assert len(predictions) == 60 and len(outcomes) == len(opened) == 15
    assert sum(r["scored"] for r in predictions) == 30
    assert outcomes[-1]["date"] == "2026-09-28"


def test_final_csv_wrapper_refuses_before_source_or_data_access(tmp_path, monkeypatch):
    import pytest
    from scripts import evaluation_forecast, run_forecast_eval

    monkeypatch.setattr(
        run_forecast_eval,
        "source_provenance",
        lambda: pytest.fail("premature source/data IO"),
    )
    with pytest.raises(ValueError, match="FINAL_TEST_NOT_AUTHORIZED"):
        evaluation_forecast.run_and_write("test", tmp_path / "probe.json")
