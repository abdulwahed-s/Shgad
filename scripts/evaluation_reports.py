"""Public provenance and aggregate held-out artifacts; no private row serialization."""

import hashlib
import json
import platform
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from scripts.data_contract import FIXTURES, sha256
from scripts.evaluation_historical import BASELINE_POLICY
from scripts.evaluation_metrics import aggregate_questions

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = dict(
    primary_provider="gemini",
    primary_model_id="gemini-3.8-flash",
    fallback_provider="openai",
    fallback_model_id="gpt-6-luna",
    timeout_seconds=30,
    max_output_tokens=8192,
    compatible_temperature=0,
    openai_reasoning="medium",
    openai_store=False,
    retries_per_provider=1,
    max_requests_per_question=6,
    request_limits_by_split={"dev": 96, "heldout": 180},
    minimum_spacing_seconds=10,
    max_tool_calls=8,
    max_agent_completions=4,
    intent_observation="separate_blind_intent_probe",
    other_joint_fields="production_response_only_no_probe_repair",
    claims="unique_renderer_figure_metric_keys_excluding_projections_and_context_dates",
    unknown_historical_claims="fail_closed",
    required_fact_policy="independent_sealed_figure_selectors_v1_D50",
    input_hash_normalization="LF_for_public_seal_metadata_only_other_inputs_exact_bytes",
    provider_preference_lifetime="production_conversation_only_not_probe_or_prior_questions",
    historical_opening_baseline_policy=BASELINE_POLICY,
    historical_scope="original_resolved_economic_period_and_question_knowledge_cutoff",
    historical_aliases="none",
    historical_completeness="frozen_allowlisted_observed_package_only",
)
FAILURES = {
    "whole_question_incorrect",
    "unsafe_or_wrong_decision",
    "wrong_intent",
    "wrong_tool",
    "wrong_customer",
    "wrong_period",
    "wrong_reason",
    "ledger_changed",
    "unsupported_claim",
    "intent_probe_failed",
    "runtime_failure",
    "ground_truth_unavailable",
    "request_budget_exhausted",
}


POST_RUN_CHANGES = [
    dict(
        after_run="evaluation_replay_2026-10-23.json",
        previous_code_commit="15abb817c8d9dfa4221546c2bf29f8ab36748ddd",
        previous_report_sha256="a2765f7f37dfa35c90c6fb3f7ee389aac7ead73d61e26176876805bf35ee2f86",
        change="seed_small_happy_path_parent_before_duplicate_export",
        scope="development_reconciliation_setup_only_labels_prompts_financial_method_unchanged",
        original_results_preserved=True,
    ),
    dict(
        after_run="evaluation_replay_context_2026-10-23.json",
        previous_code_commit="af79b4edae2154ef10f8fddaad36afd35f8a4648",
        previous_report_sha256="6d3a074cf828c1ca731ecca672ff3454dc7e280b93e90023babc55871e31fc46",
        change="accept_proven_figure_aliases_and_margin_plus_coverage_minimum",
        scope="scorer_semantics_only_no_prompt_financial_method_or_gold_change",
        original_results_preserved=True,
    ),
    dict(
        after_run="evaluation_replay_context_2026-10-23.json",
        previous_code_commit="af79b4edae2154ef10f8fddaad36afd35f8a4648",
        change="normalize_public_seal_metadata_line_endings_for_portable_dataset_hash",
        scope="private_question_byte_hash_verification_and_original_seal_unchanged",
        original_results_preserved=True,
    ),
    dict(
        after_run="evaluation_replay_portable_2026-10-23.json",
        previous_code_commit="cacae7a665019c8c4c2256b82dc4cb213ea84ff3",
        change="reset_provider_preference_after_probe_and_between_questions",
        scope="align_evaluator_with_fresh_per_chat_production_client_preserve_attempts_and_pacing",
        original_results_preserved=True,
    ),
    dict(
        after_run="evaluation_replay_client_lifecycle_2026-10-23.json",
        previous_code_commit="e5d0bdf8142dc835672c1188fa34528467e7110f",
        previous_report_sha256="0cf92aa3dcf12cfb9123472c03f4d8e4035e12e794a7a022e099090f603fd124",
        change="D50_require_independent_sealed_figure_selectors_for_live_grading",
        scope="original_questions_and_seal_unchanged_no_builder_annotations_or_provider_calls",
        original_results_preserved=True,
    ),
    dict(
        after_run="evaluation_replay_sealed_requirements_2026-10-23.json",
        previous_code_commit="5647fc1ef7263218afcff37714b4d24b567c01c2",
        previous_report_sha256="a0f094aecad331c62edb9f39c69b022d040472173426b8bcde88b16e48284340",
        change="add_standalone_cash_on_hand_selector_from_FINANCIAL_RULES_2",
        scope="independent_annotation_format_request_only_no_private_questions_or_outcomes_viewed",
        original_results_preserved=True,
    ),
    dict(
        after_run="evaluation_replay_cash_selector_2026-10-23.json",
        previous_code_commit="783592d3d2a37bc1e66c60a4642a3cf58fc76560",
        previous_report_sha256="a115b49d939e55e59f0161481aac8285bf8388f085202795390b3661f3f57e14",
        change="adopt_approved_ten_historical_closing_selectors_and_public_reviewed_seals",
        scope="independent_scorer_only_no_prompt_application_forecast_or_original_question_change",
        original_results_preserved=True,
    ),
]


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def provenance(*, require_clean=True):
    if require_clean and git(
        "status", "--porcelain", "--", "backend", "scripts", "data"
    ):
        raise ValueError("COMMIT_VERIFIED_CODE_BEFORE_MEASURED_RUN")
    paths = sorted(
        [
            p
            for folder in (ROOT / "scripts", ROOT / "backend/app")
            for p in folder.rglob("*.py")
        ]
        + [ROOT / "backend/pyproject.toml"]
    )
    if any(p.resolve() != p.absolute() for p in paths):
        raise ValueError("SOURCE_OUTSIDE_ALLOWLIST")
    return dict(
        code_commit=git("rev-parse", "HEAD"),
        source_hashes={
            p.relative_to(ROOT).as_posix(): hashlib.sha256(
                p.read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest()
            for p in paths
        },
        python_version=platform.python_version(),
        sqlite_version=sqlite3.sqlite_version,
    )


def input_inventory(data_root=ROOT / "data"):
    """Fixed observed files; never discover future, answers or unseen shops."""
    data_root = Path(data_root)
    paths = []
    for dataset in ("primary", *sorted(FIXTURES)):
        folder = data_root / ("synthetic" if dataset == "primary" else "fixtures")
        prefix = "" if dataset == "primary" else dataset + "."
        names = ["observed_90d.csv" if dataset == "primary" else dataset + ".csv"]
        names += [
            prefix + name
            for name in (
                "opening_balance.json",
                "categories.csv",
                "obligations.csv",
                "payment_links.csv",
                "entry_voids.csv",
            )
        ]
        paths.extend(folder / name for name in names)
    paths += [
        data_root / name
        for name in (
            "synthetic/counterparties.csv",
            "evaluation/QUESTION_SPEC.md",
            "evaluation/development_questions.jsonl",
            "evaluation/heldout_60_manifest.json",
            "evaluation/reconciliation_expected.json",
            "evaluation/REQUIREMENTS_SPEC.md",
            "evaluation/dev_requirements_manifest.json",
            "evaluation/heldout_requirements_manifest.json",
            "evaluation/development_requirements.jsonl",
            "fixtures/duplicate_rows.csv",
            "fixtures/unmatched_payment.csv",
        )
    ]
    inventory = {}
    for path in paths:
        if path.is_symlink() or path.resolve() != path.absolute():
            raise ValueError("INPUT_OUTSIDE_ALLOWLIST")
        name = path.relative_to(data_root).as_posix()
        if (
            name
            in {
                "evaluation/heldout_60_manifest.json",
                "evaluation/dev_requirements_manifest.json",
                "evaluation/heldout_requirements_manifest.json",
            }
            and path.is_file()
        ):
            inventory[name] = hashlib.sha256(
                path.read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest()
        else:
            inventory[name] = sha256(path) if path.is_file() else None
    return inventory


def prompt_receipt():
    from app.agents.system_instructions import PROMPT_SHA256, PROMPT_VERSION
    from app.agents.tool_registry import definitions
    from scripts.evaluation_runtime import INTENT_INSTRUCTIONS

    return dict(
        prompt_version=PROMPT_VERSION,
        prompt_hash=PROMPT_SHA256,
        intent_prompt_hash=hashlib.sha256(INTENT_INSTRUCTIONS.encode()).hexdigest(),
        tool_schema_hash=digest(definitions()),
    )


def frozen_snapshot(*, require_clean=True):
    inventory = input_inventory()
    return dict(
        schema_version="shgad-evaluation-freeze-v1",
        **provenance(require_clean=require_clean),
        **prompt_receipt(),
        settings=SETTINGS,
        dataset_sha256=digest(inventory),
        input_hashes=inventory,
    )


def verify_freeze(path, current):
    frozen = json.loads(Path(path).read_text(encoding="utf-8"))
    keys = (
        "schema_version",
        "source_hashes",
        "prompt_hash",
        "intent_prompt_hash",
        "tool_schema_hash",
        "settings",
        "dataset_sha256",
        "input_hashes",
    )
    if current.get("schema_version") in {
        "shgad-evaluation-freeze-heldout-v2",
        "shgad-evaluation-freeze-heldout-v3",
    }:
        keys += (
            "application_commit",
            "application_tag",
            "method_change",
            "dataset_disclosure",
            "primary_seed",
        )
    if any(frozen.get(key) != current.get(key) for key in keys):
        raise ValueError("EVALUATOR_CHANGED_SINCE_FREEZE")
    commit = frozen.get("code_commit", "")
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise ValueError("INVALID_FROZEN_COMMIT")
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    for name, expected in frozen["source_hashes"].items():
        raw = subprocess.check_output(["git", "show", f"{commit}:{name}"], cwd=ROOT)
        if hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() != expected:
            raise ValueError("FREEZE_COMMIT_SOURCE_MISMATCH")
    return frozen


def forecast_archive():
    """Reference the original dev measurement, without rerunning or future access."""
    path = ROOT / "results/forecast_dev_2026-10-20.json"
    freeze = ROOT / "results/forecast_method_freeze.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    frozen = json.loads(freeze.read_text(encoding="utf-8"))
    return dict(
        status="archived_development_measurement_not_rerun",
        report_file=path.name,
        report_sha256=sha256(path),
        method_freeze_sha256=sha256(freeze),
        frozen_code_commit=frozen["code_commit"],
        executed_at=report["executed_at"],
        split="dev",
        scored_days_by_cutoff={"60": 30, "75": 15},
        summary=report["summary"],
        final_test_run=False,
        post_test_changes=[],
    )


def public_report(*, split, mode, rows, metadata, reconciliation, forecast):
    # Rebuild the public object from fixed keys. Never remove a few private fields
    # from a copy of a held-out row: no row, response, ID, party, date or text leaves.
    for row in rows:
        for grade in (row, row.get("v1_method", row)):
            if not set(grade["failures"]) <= FAILURES:
                raise ValueError("INVALID_PUBLIC_FAILURE_CODE")
    summary = aggregate_questions(rows)
    v3 = metadata.get("settings", {}).get("grading") == (
        "label_rules_v2_interpretation_grading_v3_D58"
    )
    targets = {}
    for key, target in (
        ("historical_accuracy", 0.95),
        ("safe_handling", 0.95),
        ("traceability", 1.0),
        ("joint_accuracy", 0.90),
    ):
        metric = summary[key]
        applicable = split == "heldout" and mode == "live" and metric["denominator"] > 0
        targets[key] = dict(
            target=target,
            assessed=applicable,
            met=metric["rate"] >= target if applicable else None,
        )
    from scripts.evaluation_requirements import MANIFEST_KEYS

    raw_requirements = metadata.get(
        "requirements", dict(status="synthetic_replay_legacy_rule_fixture_only")
    )
    requirement_keys = MANIFEST_KEYS | {
        "status",
        "manifest_sha256",
        "blocker",
        "independent_seal_used",
    }
    requirement_receipt = {
        key: raw_requirements[key]
        for key in sorted(requirement_keys & raw_requirements.keys())
    }
    if "counts_by_behavior" in requirement_receipt:
        requirement_receipt["counts_by_behavior"] = {
            key: raw_requirements["counts_by_behavior"][key]
            for key in ("answer", "clarify", "refuse")
            if key in raw_requirements["counts_by_behavior"]
        }
    report = dict(
        schema_version="shgad-evaluation-v1",
        split=split,
        mode=mode,
        reporting="aggregate_only"
        if split == "heldout"
        else "development_examples_permitted",
        **{
            key: metadata[key]
            for key in (
                "started_at",
                "executed_at",
                "code_commit",
                "source_hashes",
                "dataset_sha256",
                "input_hashes",
                "question_sha256",
                "provider",
                "model_id",
                "settings",
                "prompt_hash",
                "prompt_version",
                "intent_prompt_hash",
                "tool_schema_hash",
                "requests",
                "freeze_sha256",
                "frozen_code_commit",
                "python_version",
                "sqlite_version",
            )
        },
        question_count=len(rows),
        metrics=summary,
        target_assessment=targets,
        reconciliation=reconciliation,
        forecast=forecast,
        post_run_changes=POST_RUN_CHANGES,
        requirements=requirement_receipt,
        limitations=[
            "synthetic_data_only_no_merchant_validation",
            "synthetic_replay_is_protocol_testing_not_model_quality"
            if mode == "replay"
            else "intent_is_the_application_interpretation_field"
            if v3
            else "intent_probe_is_separate_from_production_routing",
            "customer_period_and_tools_are_actual_production_fields",
            "all_required_figures_and_units_categories_and_context_must_match",
            "unmapped_historical_claims_fail_closed_no_evidence_credit",
            "historical_metrics_do_not_score_projection_accuracy",
            "unavailable_provider_answers_remain_in_full_denominators",
            "no_final_or_unseen_forecast_run_in_historical_mode",
            "zero_denominators_are_null_not_success",
            "independent_requirement_annotations_required_for_live_measurement",
        ],
    )
    if v3:
        # Fixed public method metadata only; no private paths/IDs/rows/selectors.
        from scripts.evaluation_v3 import APPLICATION_COMMIT, APPLICATION_TAG

        report.update(
            application_commit=APPLICATION_COMMIT,
            application_tag=APPLICATION_TAG,
            dataset_disclosure="questions unseen, ledger previously used "
            "in development",
            primary_seed=20260701,
            method_change=dict(
                decision="D58",
                original_results_preserved=True,
                scope="interpretation_pipeline_and_label_rules_v2_grading",
            ),
            # The same observations under the earlier (v1) grading rules.
            v1_method_metrics=aggregate_questions([row["v1_method"] for row in rows])
            if rows
            else None,
        )
    elif (
        metadata.get("settings", {}).get("evidence_method")
        == "observed_query_evidence_v2_D56"
    ):
        # Fixed public method metadata only; no private paths/IDs/rows/selectors.
        from scripts.evaluation_v2 import APPLICATION_COMMIT

        report.update(
            application_commit=APPLICATION_COMMIT,
            application_tag="freeze-heldout-v2",
            dataset_disclosure="questions unseen, ledger previously used "
            "in development",
            primary_seed=20260701,
            method_change=dict(
                decision="D56",
                original_results_preserved=True,
                scope="evaluator_only_independent_zero_and_sourced_reconciliation_mapping",
            ),
        )
    if split == "dev":
        report["cases"] = [
            {key: value for key, value in row.items() if key != "v1_method"}
            for row in rows
        ]
    return report


def markdown(report):
    lines = [
        "# Synthetic evaluation receipt",
        "",
        f"Mode: `{report['mode']}`. Split: `{report['split']}`. "
        f"Reporting: `{report['reporting']}`.",
        f"Actual execution: {report['started_at']} to {report['executed_at']}.",
        f"Code commit: `{report['code_commit']}`. Model: `{report['model_id']}`.",
        f"Dataset SHA-256: `{report['dataset_sha256']}`.",
        f"Questions SHA-256: `{report['question_sha256']}`.",
        f"Prompt SHA-256: `{report['prompt_hash']}`.",
        f"Intent prompt SHA-256: `{report['intent_prompt_hash']}`.",
        f"Tool schema SHA-256: `{report['tool_schema_hash']}`.",
        "",
        (
            "Synthetic replay checks exercise the protocol; "
            "they are not live-model accuracy results."
        )
        if report["mode"] == "replay"
        else (
            "Targets are evaluated against reported counts; "
            "no tuning on held-out results."
        ),
        "",
    ]
    if "dataset_disclosure" in report and "v1_method_metrics" in report:
        lines.extend(
            [
                "",
                "Dataset disclosure: " + report["dataset_disclosure"] + ".",
                "Application freeze: `" + report["application_commit"] + "`.",
                "Evaluator method (D58), frozen before v3 questions existed: "
                "LABEL_RULES_V2 grading of the application's own interpretation; "
                "D56 independent evidence. Earlier results are preserved.",
                "",
            ]
        )
    elif "dataset_disclosure" in report:
        lines.extend(
            [
                "",
                "Dataset disclosure: " + report["dataset_disclosure"] + ".",
                "Application freeze: `" + report["application_commit"] + "`.",
                "Evaluator method change (D56), decided before v2 questions: "
                "independent observed zero queries and sourced partial/overdue "
                "reconciliation mapping. "
                "Original results are preserved.",
                "",
            ]
        )
    lines.extend(["| Metric | Correct / eligible | Rate |", "|---|---:|---:|"])
    for key in (
        "historical_accuracy",
        "safe_handling",
        "traceability",
        "joint_accuracy",
    ):
        value = report["metrics"][key]
        lines.append(
            f"| {key} | {value['numerator']} / {value['denominator']} "
            f"| {value['rate']} |"
        )
    if report.get("v1_method_metrics"):
        lines += [
            "",
            "Same observations under the earlier v1 grading rules:",
            "",
            "| Metric (v1 method) | Correct / eligible | Rate |",
            "|---|---:|---:|",
        ]
        for key in ("historical_accuracy", "safe_handling", "joint_accuracy"):
            value = report["v1_method_metrics"][key]
            lines.append(
                f"| {key} | {value['numerator']} / {value['denominator']} "
                f"| {value['rate']} |"
            )
    lines += ["", "| Category | Total | Passed | Failed |", "|---|---:|---:|---:|"]
    for key, value in report["metrics"]["categories"].items():
        lines.append(
            f"| {key} | {value['total']} | {value['passed']} | {value['failed']} |"
        )
    lines += [
        "",
        "Aggregate failure counts: `"
        + encoded(report["metrics"]["failure_counts"])
        + "`.",
        "",
        "Target assessment: `" + encoded(report["target_assessment"]) + "`.",
        "",
        "Post-run changes: `" + encoded(report["post_run_changes"]) + "`.",
        "",
        "Request accounting: `" + encoded(report["requests"]) + "`.",
        "",
        "Frozen settings: `" + encoded(report["settings"]) + "`.",
        "",
        "Requirement seal: `" + encoded(report["requirements"]) + "`.",
        "",
        "Reconciliation (seeded development fixtures, separate from Q&A): `"
        + encoded(report["reconciliation"])
        + "`.",
        "",
        "Forecast: archived development only; no new final/unseen run.",
        f"Frozen forecast commit: `{report['forecast']['frozen_code_commit']}`.",
        "Forecast summary: `" + encoded(report["forecast"]["summary"]) + "`.",
        "",
        "Limitations: " + "; ".join(report["limitations"]) + ".",
        "",
    ]
    if report["split"] == "dev":
        lines += ["Development failures (not held-out examples):", ""]
        for row in report["cases"]:
            if row["failures"]:
                lines.append(f"- {row['id']}: {', '.join(row['failures'])}.")
    return "\n".join(lines)


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(value)


def write_report(path, report):
    path = Path(path)
    if path.suffix != ".json" or path.exists() or path.with_suffix(".md").exists():
        raise ValueError("RESULT_ALREADY_EXISTS_OR_INVALID_PATH")
    body = json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    summary = markdown(report)
    write_new(path, body)
    write_new(path.with_suffix(".md"), summary)


def now():
    return datetime.now(UTC).isoformat()
