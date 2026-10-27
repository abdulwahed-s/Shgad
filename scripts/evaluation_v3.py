"""D58 held-out v3 gates, layered on the audited v2 selection path.

The independent evidence rules stay those of METHOD_V2 (D56). What changes is
the application under test (the interpretation pipeline, frozen by its own
tag) and the grading: LABEL_RULES_V2 §7 on the application's own
interpretation, with the v1 method reported beside it from the same
observations. No private question or annotation reads here.
"""

import hashlib
from pathlib import Path

from scripts.evaluation_evidence import METHOD_V2
from scripts.evaluation_reports import ROOT, frozen_snapshot, git

APPLICATION_TAG = "freeze-heldout-v3"
APPLICATION_COMMIT = None  # Set to the tagged commit when the application freezes.
APPLICATION_PATHS = ("backend/app", "frontend", ":(exclude)frontend/test/**")
GRADING = "label_rules_v2_interpretation_grading_v3_D58"
QUESTION_SCHEMA = "shgad-question-v2"
SCHEMA_VERSION = "shgad-evaluation-freeze-heldout-v3"
LABEL_RULES = ROOT / "data/evaluation/LABEL_RULES_V2.md"


def fail(code):
    from scripts.run_evaluation import EvaluationError

    raise EvaluationError(code)


def grading_from_freeze(path):
    from scripts.run_evaluation import strict_json

    frozen = strict_json(Path(path).read_bytes())
    return frozen.get("settings", {}).get("grading")


def is_v3(path):
    return path is not None and grading_from_freeze(path) == GRADING


def check_application():
    if APPLICATION_COMMIT is None:
        fail("V3_APPLICATION_NOT_FROZEN")
    if git("rev-parse", APPLICATION_TAG) != APPLICATION_COMMIT:
        fail("FROZEN_APPLICATION_TAG_MISMATCH")
    if git("diff", "--name-only", APPLICATION_COMMIT, "HEAD", "--", *APPLICATION_PATHS):
        fail("FROZEN_APPLICATION_COMMIT_MISMATCH")
    if git("status", "--porcelain", "--", *APPLICATION_PATHS):
        fail("FROZEN_APPLICATION_DIRTY")


def label_rules_sha256():
    raw = LABEL_RULES.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def snapshot(*, require_clean=True):
    from app.agents.interpreter import INTERPRETER_SHA256, INTERPRETER_VERSION

    current = frozen_snapshot(require_clean=require_clean)
    return current | dict(
        schema_version=SCHEMA_VERSION,
        application_commit=APPLICATION_COMMIT,
        application_tag=APPLICATION_TAG,
        settings=current["settings"]
        | dict(
            evidence_method=METHOD_V2,
            zero_policy="independent_active_event_query_with_observed_coverage",
            reconciliation_mapping="independent_fully_allocated_partial_overdue_only",
            primary_timeout_seconds=15,
            gemini_reasoning_effort="low",
            grading=GRADING,
            agent_pipeline="interpretation",
            intent_observation="application_interpretation_field_no_probe",
            interpreter_version=INTERPRETER_VERSION,
            interpreter_prompt_hash=INTERPRETER_SHA256,
            question_schema=QUESTION_SCHEMA,
            label_rules_sha256=label_rules_sha256(),
            secondary_grading="v1_method_on_the_same_observations",
        ),
        method_change=dict(
            decision="D58",
            before_v3_questions=True,
            original_results_preserved=True,
            scope="interpretation_pipeline_and_label_rules_v2_grading",
        ),
        dataset_disclosure="questions unseen, ledger previously used in development",
        primary_seed=20260701,
    )


def write_method_freeze(path):
    """Public method only; written before any v3 question exists."""
    import json

    from scripts.evaluation_reports import now, write_new

    check_application()
    value = snapshot() | dict(frozen_at=now())
    write_new(Path(path), json.dumps(value, sort_keys=True, indent=2) + "\n")
