"""V2 method/selection gates. No private question or annotation reads here."""

from pathlib import Path

from scripts.evaluation_evidence import METHOD_V1, METHOD_V2
from scripts.evaluation_reports import ROOT, frozen_snapshot, git

APPLICATION_COMMIT = "a0272d99387db5ed0e6444cf229796a9daa1296d"
APPLICATION_PATHS = ("backend/app", "frontend", ":(exclude)frontend/test/**")


def fail(code):
    from scripts.run_evaluation import EvaluationError

    raise EvaluationError(code)


def external(path):
    return not Path(path).resolve().is_relative_to(ROOT)


def validate_selection(args):
    selected = args.heldout_seal is not None or args.heldout_requirements is not None
    if not selected:
        return False
    if args.split != "heldout" or not (args.heldout_seal and args.heldout_requirements):
        fail("V2_REQUIRES_BOTH_HELDOUT_MANIFESTS")
    if not all(
        external(p)
        for p in (args.heldout_seal, args.heldout_requirements, args.freeze_manifest)
    ):
        fail("V2_MANIFESTS_MUST_BE_EXTERNAL")
    if args.write_freeze:
        fail("V2_METHOD_MUST_BE_FROZEN_BEFORE_QUESTION_SELECTION")
    return True


def check_application():
    if git("rev-parse", "freeze-heldout-v2") != APPLICATION_COMMIT:
        fail("FROZEN_APPLICATION_TAG_MISMATCH")
    if git("diff", "--name-only", APPLICATION_COMMIT, "HEAD", "--", *APPLICATION_PATHS):
        fail("FROZEN_APPLICATION_COMMIT_MISMATCH")
    if git("status", "--porcelain", "--", *APPLICATION_PATHS):
        fail("FROZEN_APPLICATION_DIRTY")


def check_output(output):
    if output is None:
        fail("V2_EXPLICIT_NEW_OUTPUT_REQUIRED")
    output = Path(output)
    if (
        output.suffix != ".json"
        or output.exists()
        or output.with_suffix(".md").exists()
    ):
        fail("RESULT_ALREADY_EXISTS_OR_INVALID_PATH")


def check_runtime_settings(settings):
    # Refuse hidden environment drift; do not change frozen app configuration.
    if (
        settings.llm_primary_timeout_seconds != 15
        or settings.gemini_reasoning_effort != "low"
    ):
        fail("V2_RUNTIME_SETTINGS_MISMATCH")


def method_from_freeze(path):
    from scripts.run_evaluation import strict_json

    frozen = strict_json(Path(path).read_bytes())
    method = frozen.get("settings", {}).get("evidence_method", METHOD_V1)
    if method not in {METHOD_V1, METHOD_V2}:
        fail("UNKNOWN_EVALUATION_METHOD")
    return method


def snapshot(*, require_clean=True):
    current = frozen_snapshot(require_clean=require_clean)
    return current | dict(
        schema_version="shgad-evaluation-freeze-heldout-v2",
        application_commit=APPLICATION_COMMIT,
        application_tag="freeze-heldout-v2",
        settings=current["settings"]
        | dict(
            evidence_method=METHOD_V2,
            zero_policy="independent_active_event_query_with_observed_coverage",
            reconciliation_mapping="independent_fully_allocated_partial_overdue_only",
            primary_timeout_seconds=15,
            gemini_reasoning_effort="low",
        ),
        method_change=dict(
            decision="D56",
            before_v2_questions=True,
            original_results_preserved=True,
            scope="evaluator_only_independent_zero_and_sourced_reconciliation_mapping",
        ),
        dataset_disclosure="questions unseen, ledger previously used in development",
        primary_seed=20260701,
    )


def command(*, seal, requirements, freeze, output, max_requests=180):
    def quoted(value):
        return "'" + str(value).replace("'", "''") + "'"

    return (
        "& "
        + quoted(ROOT / "backend/.venv/Scripts/python.exe")
        + " "
        + quoted(ROOT / "scripts/run_evaluation.py")
        + " --split heldout --mode live --max-requests "
        + str(max_requests)
        + " --heldout-seal "
        + quoted(seal)
        + " --heldout-requirements "
        + quoted(requirements)
        + " --freeze-manifest "
        + quoted(freeze)
        + " --output "
        + quoted(output)
        + " --authorize-paid --authorize-heldout"
    )


def write_method_freeze(path):
    """Public method only; seal before v2 content is generated or selected."""
    import json

    from scripts.evaluation_reports import now, write_new

    check_application()
    value = snapshot() | dict(frozen_at=now())
    write_new(Path(path), json.dumps(value, sort_keys=True, indent=2) + "\n")
