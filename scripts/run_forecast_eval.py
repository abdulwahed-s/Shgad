"""Offline production forecast benchmark; development never opens final outcomes.

Dev: cutoff 60 scores 30 days; cutoff 75 scores 15 days, both predict 30.
Final: explicit later authorization + verified freeze, cutoff 90, four shops.
No provider/config/credential loading or question inputs exist in this script.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.data_contract import read_csv, read_json, sha256, write_json  # noqa: E402
from scripts.forecast_inputs import (  # noqa: E402
    cutoff_history,
    load_observed_inputs,
    production_predictions,
)
from scripts.forecast_metrics import (  # noqa: E402
    balance_errors,
    false_ok,
    first_shortfall,
    ratio,
    rounded_mean,
    shortfall_timing,
)
from scripts.make_ground_truth import TruthError, TruthLedger, cutoff, stamp  # noqa: E402

DAY_ONE = date(2026, 7, 1)
SCENARIOS = ("base", "conservative", "stress")
METHOD_SETTINGS = {
    "method_id": "recorded-weekday-cash-v1",
    "cash_sales_and_difference_lookback_days": 56,
    "expense_and_drawing_lookback_days": 28,
    "prediction_days": 30,
    "money_rounding": "half_up_once_per_series_integer_iqd",
    "customer_lateness_minimum_settlements": 2,
    "customer_lateness_fallback": "shop_median",
    "overdue_receivables": "excluded_all_scenarios",
    "stress_collections": "zero",
    "baseline": "cash_at_cutoff_plus_day_times_rounded_count_delta_over_seven",
    "mae_display_rounding": "half_up_integer_iqd_with_exact_error_sum",
    "shortfall": "closing_negative_or_below_next_day_known_scheduled_dues",
    "shortfall_timing_tolerance_days": 2,
    "false_ok": "FINANCIAL_RULES_7b_per_invoice_own_payment_only",
    "development_cutoffs_and_scored_days": [[60, 30], [75, 15]],
    "final_cutoff_and_scored_days": [90, 30],
}
SOURCE_FILES = (
    "scripts/run_forecast_eval.py",
    "scripts/forecast_inputs.py",
    "scripts/forecast_metrics.py",
    "scripts/make_ground_truth.py",
    "scripts/data_contract.py",
    "backend/app/services/forecast.py",
    "backend/app/db/forecast_repository.py",
    "backend/app/services/financial_queries.py",
    "backend/app/services/ledger_rules.py",
    "backend/app/services/ledger_audit.py",
    "backend/app/services/observed.py",
    "backend/app/services/business_clock.py",
    "backend/app/services/validation.py",
    "backend/app/services/errors.py",
    "backend/app/services/reconcile.py",
    "backend/app/db/connection.py",
    "backend/app/db/migrations.py",
    "backend/app/db/records.py",
    "backend/app/schemas/forecast.py",
    "backend/app/schemas/ledger.py",
    "backend/app/schemas/queries.py",
    "backend/app/schemas/evidence.py",
)


@dataclass(frozen=True)
class EvaluationCase:
    shop: str
    cutoff_day: int
    scored_days: int
    prediction_days: int = 30

    @property
    def as_of(self):
        return DAY_ONE + timedelta(days=self.cutoff_day - 1)

    @property
    def scored_end(self):
        return self.as_of + timedelta(days=self.scored_days)


def evaluation_plan(split, *, final_shops=()):
    if split == "dev":
        return (EvaluationCase("primary", 60, 30), EvaluationCase("primary", 75, 15))
    if split != "test" or len(final_shops) != 3 or len(set(final_shops)) != 3:
        raise ValueError("INVALID_EVALUATION_PLAN")
    return tuple(EvaluationCase(shop, 90, 30) for shop in ("primary", *final_shops))


def require_final_authorization(*, allow_final, freeze_path):
    if not allow_final:
        raise ValueError(
            "FINAL_TEST_NOT_AUTHORIZED: use only after explicit user authorization"
        )
    if not Path(freeze_path).is_file():
        raise ValueError("FINAL_TEST_REQUIRES_METHOD_FREEZE")


def _git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def source_provenance():
    if _git("status", "--porcelain", "--", "backend", "scripts", "data"):
        raise ValueError("COMMIT_VERIFIED_CODE_BEFORE_MEASURED_RUN")
    return {
        "code_commit": _git("rev-parse", "HEAD"),
        "source_hashes": {
            name: hashlib.sha256(
                (ROOT / name).read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest()
            for name in SOURCE_FILES
        },
        "method_settings": METHOD_SETTINGS,
    }


def verify_freeze(path, provenance):
    frozen = read_json(path)
    if (
        frozen.get("method_settings") != METHOD_SETTINGS
        or frozen.get("source_hashes") != provenance["source_hashes"]
    ):
        raise ValueError(
            "METHOD_CHANGED_SINCE_FREEZE: disclose post-test changes; "
            "refreeze before testing"
        )
    commit = frozen.get("code_commit", "")
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise ValueError("INVALID_FROZEN_CODE_COMMIT")
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    for name, digest in frozen["source_hashes"].items():
        content = subprocess.check_output(["git", "show", f"{commit}:{name}"], cwd=ROOT)
        # Git stores canonical LF; compare logical source across Windows checkouts.
        if hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest() != digest:
            raise ValueError("FREEZE_COMMIT_SOURCE_MISMATCH")
    return frozen


def _scored_rows(rows, case):
    expected = [str(case.as_of + timedelta(days=i)) for i in range(1, 31)]
    if len(rows) != 30 or [r["date"] for r in rows] != expected:
        raise ValueError("FORECAST_MUST_HAVE_THIRTY_CONSECUTIVE_ROWS")
    return rows[: case.scored_days]


def _invoice_payment(truth, invoice, day):
    visible = {r["transaction_id"]: r for r in truth.visible(day)}
    return sum(
        link["amount_iqd"]
        for link in truth.links
        if link["obligation_id"] == invoice["obligation_id"]
        and link["payment_transaction_id"] in visible
        and visible[link["payment_transaction_id"]]["type"] == "SUPPLIER_PAYMENT"
        and visible[link["payment_transaction_id"]]["business_date"] == str(day)
        and stamp(link["created_at"]) <= cutoff(day)
    )


def _safety(invoices, predicted, realized, truth, *, payment_field=None):
    cases = []
    for invoice in invoices:
        due = invoice["due_date"]
        if due not in predicted:
            continue
        row = predicted[due]
        payment = invoice["outstanding_iqd"]
        if payment_field == "j1":
            closing = row["closing_iqd"]
        elif payment_field:
            closing = row[payment_field]
        else:
            closing = row["closing_iqd"]
        if closing is None:
            return None
        cases.append(
            dict(
                amount_due_iqd=payment,
                predicted_closing_iqd=closing,
                predicted_payment_iqd=payment,
                realized_closing_iqd=realized[due],
                realized_payment_iqd=_invoice_payment(
                    truth, invoice, date.fromisoformat(due)
                ),
            )
        )
    return false_ok(cases)


def score_case(case, bundle, truth):
    """Read outcomes only for the permitted scored days, never the prediction tail."""
    score_dates = [
        case.as_of + timedelta(days=i) for i in range(1, case.scored_days + 1)
    ]
    realized = {str(day): truth.cash(day)["amount_iqd"] for day in score_dates}
    actual_rows = [{"date": day, "closing_iqd": cash} for day, cash in realized.items()]
    invoices = bundle["invoices"]
    eligible = [
        r for r in invoices if str(case.as_of) < r["due_date"] <= str(case.scored_end)
    ]
    scheduled = defaultdict(int)
    for invoice in invoices:
        scheduled[invoice["due_date"]] += invoice["outstanding_iqd"]
    actual_shortfall = first_shortfall(actual_rows, scheduled)
    baseline = bundle["baseline"]
    baseline_rows = _scored_rows(baseline["days"], case) if "days" in baseline else None
    baseline_errors = (
        balance_errors(
            [r["closing_iqd"] for r in baseline_rows], list(realized.values())
        )
        if baseline_rows
        else None
    )
    scenarios = {}
    for name, prediction in bundle["scenarios"].items():
        if "error_code" in prediction:
            scenarios[name] = {"status": "missing_data", "scored_days": 0, **prediction}
            continue
        rows = _scored_rows(prediction["days"], case)
        errors = balance_errors(
            [r["closing_iqd"] for r in rows], list(realized.values())
        )
        scenarios[name] = {
            "status": "scored",
            **errors,
            "baseline_mae_iqd": baseline_errors["mae_iqd"] if baseline_errors else None,
            "baseline_absolute_error_sum_iqd": baseline_errors["absolute_error_sum_iqd"]
            if baseline_errors
            else None,
            "improves_on_baseline": errors["absolute_error_sum_iqd"]
            < baseline_errors["absolute_error_sum_iqd"]
            if baseline_errors
            else None,
            "shortfall_timing": shortfall_timing(
                first_shortfall(rows, scheduled), actual_shortfall
            ),
            "false_ok": _safety(
                eligible, {r["date"]: r for r in rows}, realized, truth
            ),
        }
    seven = bundle["seven_day"]
    seven_rows = {r["date"]: r for r in seven.get("days", []) if r["date"] in realized}
    seven_safety = (
        None
        if "error_code" in seven
        else _safety(
            eligible,
            seven_rows,
            realized,
            truth,
            payment_field="running_with_expected_iqd",
        )
    )
    j1 = bundle["j1"]
    j1_safety = None
    if j1 and "error_code" not in j1 and j1["due_date"] in realized:
        j1_safety = _safety(
            eligible,
            {
                j1["due_date"]: {
                    "closing_iqd": j1["cash_on_hand"]["amount_iqd"]
                    + j1["expected_collection"]["amount_iqd"]
                    - j1["supplier_due"]["amount_iqd"]
                }
            },
            realized,
            truth,
            payment_field="j1",
        )
    return {
        "shop": case.shop,
        "cutoff_day": case.cutoff_day,
        "as_of": str(case.as_of),
        "prediction_days": 30,
        "scored_days": case.scored_days,
        "scored_start": str(score_dates[0]),
        "scored_end": str(case.scored_end),
        "baseline_errors": baseline_errors,
        "baseline_shortfall_timing": shortfall_timing(
            first_shortfall(baseline_rows, scheduled), actual_shortfall
        )
        if baseline_rows
        else None,
        "scenarios": scenarios,
        "seven_day_with_expected_false_ok": seven_safety,
        "j1_with_expected_false_ok": j1_safety,
    }


def aggregate(cases):
    summary = {}
    for name in SCENARIOS:
        values = [
            c["scenarios"][name]
            for c in cases
            if c["scenarios"][name]["status"] == "scored"
        ]
        days = sum(r["scored_days"] for r in values)
        total = sum(r["absolute_error_sum_iqd"] for r in values)
        comparable = [
            r for r in values if r["baseline_absolute_error_sum_iqd"] is not None
        ]
        baseline_days = sum(r["scored_days"] for r in comparable)
        summary[name] = {
            "scored_cases": len(values),
            "missing_cases": len(cases) - len(values),
            "scored_days": days,
            "absolute_error_sum_iqd": total,
            "mae_iqd": rounded_mean(total, days) if days else None,
            "worst_day_error_iqd": max(
                (r["worst_day_error_iqd"] for r in values), default=None
            ),
            "baseline_comparable_days": baseline_days,
            "baseline_mae_iqd": rounded_mean(
                sum(r["baseline_absolute_error_sum_iqd"] for r in comparable),
                baseline_days,
            )
            if baseline_days
            else None,
            "shortfall_timing": ratio(
                sum(r["shortfall_timing"]["numerator"] for r in values),
                sum(r["shortfall_timing"]["denominator"] for r in values),
            ),
            "false_ok": _sum_safety([r["false_ok"] for r in values]),
        }
    for field in ("seven_day_with_expected_false_ok", "j1_with_expected_false_ok"):
        summary[field] = _sum_safety([c[field] for c in cases])
    return summary


def _sum_safety(values):
    available = [v for v in values if v is not None]
    return {
        **ratio(
            sum(v["numerator"] for v in available),
            sum(v["denominator"] for v in available),
        ),
        "eligible_invoices": sum(v["eligible_invoices"] for v in available),
        "available_cases": len(available),
        "unavailable_cases": len(values) - len(available),
    }


def _final_truth(folder, observed):
    # Called only after the final-run flag AND method/code freeze have passed.
    # Never hand this ledger or these paths to production_predictions.
    future = read_csv(folder / "future_30d_ground_truth.csv")
    if any(
        not date(2026, 9, 29)
        <= date.fromisoformat(r["business_date"])
        <= date(2026, 10, 28)
        for r in future
    ):
        raise ValueError("INVALID_FINAL_OUTCOME_RANGE")
    links = read_csv(folder / "evaluation_only/all_120d_payment_links.csv")
    return TruthLedger(
        observed.rows + future,
        opening=observed.opening,
        links=links,
        voids=observed.voids,
    )


def run(split, *, allow_final=False, freeze_path=None):
    if split == "test":
        freeze_path = freeze_path or ROOT / "results/forecast_method_freeze.json"
        require_final_authorization(allow_final=allow_final, freeze_path=freeze_path)
    provenance = source_provenance()
    primary = ROOT / "data/synthetic"
    shops = {"primary": primary}
    frozen = None
    if split == "test":
        frozen = verify_freeze(freeze_path, provenance)
        parent = primary / "forecast_eval_shops"
        paths = sorted(p for p in parent.iterdir() if p.is_dir())
        if len(paths) != 3 or any(
            p.resolve().parent != parent.resolve() for p in paths
        ):
            raise ValueError("FINAL_REQUIRES_THREE_ISOLATED_SHOPS")
        shops.update({p.name: p for p in paths})
    plan = evaluation_plan(split, final_shops=tuple(k for k in shops if k != "primary"))
    cases, input_hashes = [], {}
    for shop, folder in shops.items():
        observed, parties, hashes = load_observed_inputs(folder)
        if (
            frozen
            and shop == "primary"
            and hashes != frozen.get("primary_input_hashes")
        ):
            raise ValueError("PRIMARY_INPUTS_CHANGED_SINCE_FREEZE")
        input_hashes[shop] = hashes
        outcomes = _final_truth(folder, observed) if split == "test" else observed
        if split == "test":
            input_hashes[shop].update(
                {
                    name: sha256(folder / name)
                    for name in (
                        "future_30d_ground_truth.csv",
                        "evaluation_only/all_120d_payment_links.csv",
                    )
                }
            )
        for case in (c for c in plan if c.shop == shop):
            history = cutoff_history(observed, case.as_of)
            bundle = production_predictions(history, parties, case.as_of)
            try:
                bundle["baseline"] = history.baseline(case.as_of)
            except TruthError as exc:
                bundle["baseline"] = {"error_code": str(exc)}
            bundle["invoices"] = [
                r
                for r in history.debts(case.as_of, direction="payable")
                if r["outstanding_iqd"] > 0
            ]
            if any(r["due_date"] is None for r in bundle["invoices"]):
                raise ValueError("MISSING_DUE_DATE")
            scored = score_case(case, bundle, outcomes)
            scored["predictions"] = bundle
            cases.append(scored)
    digest = hashlib.sha256(
        json.dumps(input_hashes, sort_keys=True).encode()
    ).hexdigest()
    return {
        "split": split,
        "executed_at": datetime.now(UTC).isoformat(),
        **provenance,
        "model_id": "deterministic-no-llm",
        "prompt_hash": None,
        "dataset_sha256": digest,
        "input_hashes": input_hashes,
        "frozen_code_commit": frozen["code_commit"] if frozen else None,
        "case_count": len(cases),
        "cases": cases,
        "summary": aggregate(cases),
        "limitations": [
            "synthetic_single_primary_shop_for_development",
            "cutoff_75_scored_only_through_day_90",
            "aggregate_mae_is_scored_day_weighted",
            "zero_safety_denominator_is_not_a_success",
            "safety_counts_are_invoice_cutoff_observations",
            "no_real_world_accuracy_or_heldout_question_claim",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--allow-final-test",
        action="store_true",
        help="Only after explicit user authorization of a frozen final run",
    )
    parser.add_argument("--freeze-manifest", type=Path)
    args = parser.parse_args(argv)
    output = (
        args.output
        or ROOT
        / "results"
        / f"forecast_{args.split}_{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    )
    if output.exists():
        parser.error("RESULT_ALREADY_EXISTS: preserve measured receipts")
    try:
        report = run(
            args.split,
            allow_final=args.allow_final_test,
            freeze_path=args.freeze_manifest,
        )
    except (OSError, ValueError, TruthError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    write_json(output, report)
    print(
        json.dumps(
            {
                "split": report["split"],
                "code_commit": report["code_commit"],
                "case_count": report["case_count"],
                "summary": report["summary"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
