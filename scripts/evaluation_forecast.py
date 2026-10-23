"""Reporting wrapper for the existing frozen evaluator; never changes its method."""

import csv
import hashlib
import io
import json
from datetime import date, timedelta
from pathlib import Path

from scripts.evaluation_reports import ROOT, now, write_new


def csv_text(rows, fields):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def series_rows(case, realized_cash):
    """Never even ask for the realized unscored tail (T12/D20)."""
    start = date.fromisoformat(case["as_of"])
    realized = [
        dict(
            shop=case["shop"],
            cutoff_day=case["cutoff_day"],
            date=str(day),
            realized_closing_iqd=realized_cash(day),
        )
        for i in range(1, case["scored_days"] + 1)
        for day in [start + timedelta(days=i)]
    ]
    scored = {row["date"] for row in realized}
    bundle = case["predictions"]
    series = dict(bundle["scenarios"]) | {"baseline": bundle["baseline"]}
    predictions = [
        dict(
            shop=case["shop"],
            cutoff_day=case["cutoff_day"],
            scenario=name,
            date=row["date"],
            predicted_closing_iqd=row["closing_iqd"],
            scored=row["date"] in scored,
        )
        for name, prediction in series.items()
        for row in prediction.get("days", [])
    ]
    return predictions, realized


def run_and_write(split, output, *, allow_final=False):
    from scripts.forecast_inputs import load_observed_inputs
    from scripts.run_forecast_eval import (
        _final_truth,
        run,
        source_provenance,
        verify_freeze,
    )

    output = Path(output)
    csv_paths = [
        output.with_name(output.stem + suffix)
        for suffix in ("_predictions.csv", "_realized.csv")
    ]
    if output.suffix != ".json" or any(
        path.exists() for path in [output, output.with_suffix(".md"), *csv_paths]
    ):
        raise ValueError("RESULT_ALREADY_EXISTS_OR_INVALID_PATH")
    if split == "test" and not allow_final:
        raise ValueError("FINAL_TEST_NOT_AUTHORIZED")
    frozen = verify_freeze(
        ROOT / "results/forecast_method_freeze.json", source_provenance()
    )
    started = now()
    report = run(split, allow_final=allow_final)
    predicted, realized = [], []
    for case in report["cases"]:
        folder = ROOT / "data/synthetic"
        if case["shop"] != "primary":
            if (
                split != "test"
                or not allow_final
                or Path(case["shop"]).name != case["shop"]
            ):
                raise ValueError("UNAUTHORIZED_FORECAST_SHOP")
            folder = folder / "forecast_eval_shops" / case["shop"]
        observed, _, _ = load_observed_inputs(folder)
        # This branch remains behind the same authorization and verified freeze
        # as the existing evaluator. No final inputs are opened for dev reports.
        truth = _final_truth(folder, observed) if split == "test" else observed
        predictions, outcomes = series_rows(
            case, lambda day: truth.cash(day)["amount_iqd"]
        )
        predicted.extend(predictions)
        realized.extend(outcomes)
    bodies = [
        csv_text(
            predicted,
            (
                "shop",
                "cutoff_day",
                "scenario",
                "date",
                "predicted_closing_iqd",
                "scored",
            ),
        ),
        csv_text(realized, ("shop", "cutoff_day", "date", "realized_closing_iqd")),
    ]
    report |= dict(
        started_at=started,
        executed_at=now(),
        frozen_code_commit=frozen["code_commit"],
        provider="none",
        final_test_run=split == "test",
        post_test_changes=[],
        artifacts={
            path.name: hashlib.sha256(body.encode()).hexdigest()
            for path, body in zip(csv_paths, bodies, strict=True)
        },
    )
    summary = "\n".join(
        [
            "# Synthetic forecast evaluation receipt",
            "",
            f"Split: `{split}`. Actual execution: {started} "
            f"to {report['executed_at']}.",
            f"Code commit: `{report['code_commit']}`. "
            f"Frozen method commit: `{report['frozen_code_commit']}`.",
            f"Dataset SHA-256: `{report['dataset_sha256']}`. "
            "Model: `deterministic-no-llm`.",
            "No provider request. Synthetic forecasting, no merchant validation.",
            "",
            "| Shop | Cutoff | Predicted days per series | Scored days per series |",
            "|---|---:|---:|---:|",
            *[
                f"| {case['shop']} | {case['cutoff_day']} | 30 "
                f"| {case['scored_days']} |"
                for case in report["cases"]
            ],
            "",
            "Scored-day-weighted metrics, baseline comparison, first-shortfall "
            "±2 days and false-OK numerator/realized-short denominator/rate:",
            "",
            "```json",
            json.dumps(report["summary"], indent=2, sort_keys=True),
            "```",
            "",
            "Zero denominators are null. No safety target or improvement is assumed.",
            "Development realized CSVs stop at day 90; the prediction tail "
            "has no realized data.",
            "Original reports and freeze records are preserved. "
            "Later method changes require post-test disclosure.",
            "",
        ]
    )
    write_new(output, json.dumps(report, sort_keys=True, indent=2) + "\n")
    write_new(output.with_suffix(".md"), summary)
    for path, body in zip(csv_paths, bodies, strict=True):
        write_new(path, body)
    return report
