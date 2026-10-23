"""D50: independently sealed figure selectors, never model inputs or answers.

Only run_evaluation's authorized measured path may load real private annotations.
Plan reads public seals only. Tests use explicitly fabricated format sentinels.
"""

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "shgad-requirements-v1"
MANIFEST_KEYS = {
    "schema_version",
    "split",
    "question_sha256",
    "sha256",
    "total_count",
    "answer_count",
    "human_reviewed",
    "independent_of_build",
    "generator_tool",
    "generator_model_id",
    "reviewed_at",
    "reviewed_count",
    "counts_by_behavior",
    "selector_spec_sha256",
}
SCALAR_FIELDS = {
    "cash_on_hand",
    "cash_sales",
    "credit_sales",
    "total_sales",
    "selected_sales",
    "unexplained_cash_difference",
    "gross_margin",
    "coverage_pct",
    "unpriced_sales_count",
    "priced_sales",
    "cost_of_goods",
    "after_recorded_expenses",
}
PATTERNS = (
    r"weekly\.(?:owner_drawings|operating_expenses|collections)",
    r"(?:receivables|payables)\.total_outstanding",
    r"(?:receivables|payables)\.aging\.(?:not_due|d1_7|d8_30|d31_60|d60_plus)",
    r"(?:receivables|payables)\.customers\.[0-9]+\.(?:outstanding|days_overdue)",
    r"(?:receivables|payables)\.customers\.[0-9]+\.obligations\.[0-9]+\.(?:original|outstanding)",
    r"price_basis\.[0-9]+\.buy_price",
    r"j1\.(?:cash_on_hand|supplier_due|expected_collection|shortfall_with_collection|shortfall_without_collection)",
    r"upcoming\.(?:cash_on_hand|dues_total|expected_total|position_confirmed|position_with_expected)",
    r"upcoming\.days\.(?:[0-9]|[12][0-9])\.(?:dues_iqd|expected_iqd|running_confirmed_iqd|running_with_expected_iqd)",
)


class RequirementsError(ValueError):
    """Fixed public codes only; never include private IDs/selectors/paths."""


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError()
            result[key] = value
        return result

    def constant(_):
        raise ValueError()

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def status(split, question_sha256, *, data_root=ROOT / "data"):
    if split not in {"dev", "heldout"}:
        raise RequirementsError("INVALID_SPLIT")
    path = Path(data_root) / "evaluation" / (split + "_requirements_manifest.json")
    if path.resolve() != path.absolute():
        raise RequirementsError("INVALID_REQUIREMENTS_MANIFEST")
    if not path.exists():
        return dict(status="missing", blocker="REQUIREMENTS_SEAL_REQUIRED")
    try:
        raw = path.read_bytes()
        manifest = strict_json(raw)
        if not isinstance(manifest, dict) or set(manifest) != MANIFEST_KEYS:
            raise ValueError()
        if manifest["schema_version"] != SCHEMA or manifest["split"] != split:
            raise ValueError()
        for field in ("sha256", "question_sha256", "selector_spec_sha256"):
            if not isinstance(manifest[field], str) or not re.fullmatch(
                "[0-9a-f]{64}", manifest[field]
            ):
                raise ValueError()
        total, answers = manifest["total_count"], manifest["answer_count"]
        if type(total) is not int or type(answers) is not int:
            raise ValueError()
        if not 1 <= total <= 100 or not 0 <= answers <= total:
            raise ValueError()
        if type(manifest["reviewed_count"]) is not int:
            raise ValueError()
        if manifest["reviewed_count"] != total:
            raise ValueError()
        counts = manifest["counts_by_behavior"]
        if not isinstance(counts, dict) or not counts.keys() <= {
            "answer",
            "clarify",
            "refuse",
        }:
            raise ValueError()
        if any(type(n) is not int or n < 0 for n in counts.values()):
            raise ValueError()
        if sum(counts.values()) != total or counts.get("answer", 0) != answers:
            raise ValueError()
        if manifest["human_reviewed"] is not True:
            raise ValueError()
        if manifest["independent_of_build"] is not True:
            raise ValueError()
        for field in ("generator_tool", "generator_model_id"):
            if not isinstance(manifest[field], str) or not re.fullmatch(
                r"[A-Za-z0-9_.+ /:-]{1,80}", manifest[field]
            ):
                raise ValueError()
        reviewed = datetime.fromisoformat(manifest["reviewed_at"])
        if reviewed.tzinfo is None:
            raise ValueError()
        spec = Path(data_root) / "evaluation/REQUIREMENTS_SPEC.md"
        if spec.resolve() != spec.absolute():
            raise ValueError()
        if (
            hashlib.sha256(spec.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            != (manifest["selector_spec_sha256"])
        ):
            raise ValueError()
    except (OSError, ValueError, TypeError, KeyError):
        raise RequirementsError("INVALID_REQUIREMENTS_MANIFEST") from None
    if manifest["question_sha256"] != question_sha256:
        raise RequirementsError("REQUIREMENTS_QUESTION_HASH_MISMATCH")
    return manifest | dict(
        status="sealed",
        manifest_sha256=hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
    )


def load(
    split, questions, question_sha256, *, authorized=False, data_root=ROOT / "data"
):
    if split == "heldout" and not authorized:
        raise RequirementsError("HELDOUT_NOT_AUTHORIZED")
    receipt = status(split, question_sha256, data_root=data_root)
    if receipt["status"] != "sealed":
        raise RequirementsError("REQUIREMENTS_SEAL_REQUIRED")
    if split == "heldout":
        value = os.getenv("HELDOUT_PATH")
        if not value:
            raise RequirementsError("HELDOUT_PATH_REQUIRED")
        question_path = Path(value).resolve()
        if question_path.is_relative_to(ROOT):
            raise RequirementsError("HELDOUT_MUST_BE_EXTERNAL")
        path = question_path.with_name(question_path.name + ".requirements.jsonl")
    else:
        path = Path(data_root) / "evaluation/development_requirements.jsonl"
    if path.resolve() != path.absolute():
        raise RequirementsError("REQUIREMENTS_PATH_INVALID")
    try:
        if path.stat().st_size > 2_000_000:
            raise RequirementsError("REQUIREMENTS_FILE_TOO_LARGE")
        raw = path.read_bytes()
    except OSError:
        raise RequirementsError("REQUIREMENTS_INPUT_UNAVAILABLE") from None
    if hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
        raise RequirementsError("REQUIREMENTS_HASH_MISMATCH")
    try:
        rows = [strict_json(line) for line in raw.decode("utf-8-sig").splitlines()]
        result = {}
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"id", "required_fields"}:
                raise ValueError()
            key, selected = row["id"], row["required_fields"]
            if not isinstance(key, str) or not key or key in result:
                raise ValueError()
            if not isinstance(selected, list) or len(selected) > 1000:
                raise ValueError()
            if any(
                not isinstance(field, str)
                or not (
                    field in SCALAR_FIELDS
                    or any(re.fullmatch(pattern, field) for pattern in PATTERNS)
                )
                for field in selected
            ) or len(selected) != len(set(selected)):
                raise ValueError()
            result[key] = set(selected)
        if len(questions) != receipt["total_count"] or set(result) != {
            q["id"] for q in questions
        }:
            raise ValueError()
        answers = 0
        counts = {}
        for question in questions:
            behavior = question["spec"]["expected_behavior"]
            counts[behavior] = counts.get(behavior, 0) + 1
            answer = behavior == "answer"
            answers += answer
            if bool(result[question["id"]]) != answer:
                raise ValueError()
        if answers != receipt["answer_count"]:
            raise ValueError()
        if {k: v for k, v in receipt["counts_by_behavior"].items() if v} != counts:
            raise ValueError()
    except (UnicodeError, ValueError, TypeError, KeyError):
        raise RequirementsError("REQUIREMENTS_FORMAT_INVALID") from None
    return result, receipt
