"""Only fabricated validator probes; never access an actual sealed file or env."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.data_contract import validate_question
from scripts.hash_heldout import seal_manifest

ROOT = Path(__file__).resolve().parents[3]


def probes():
    # Repeated non-question sentinel text. This is a file-format/privacy probe,
    # not authored evaluation questions or a substitute for independent sealing.
    return [
        {
            "id": f"FORMAT-PROBE-{i:02}",
            "category": "sales" if i < 40 else "injection",
            "question_ar": "SYNTHETIC FORMAT PROBE -- NEVER AN EVALUATION QUESTION",
            "business_as_of": "2026-09-28",
            "dataset": "primary",
            # Field validation only, not a human-review claim.
            "arabic_review": "approved",
            "spec": {
                "intent": "sales" if i < 40 else "unsafe_instruction",
                "expected_tools": ["get_sales"] if i < 40 else [],
                "counterparty_ids": [],
                "resolved_period": {"start": "2026-09-28", "end": "2026-09-28"}
                if i < 40
                else None,
                "expected_behavior": "answer" if i < 40 else "refuse",
                "calculation": "sales" if i < 40 else "none",
                "parameters": {},
            },
        }
        for i in range(60)
    ]


def write_probe(path, rows):
    raw = "".join(json.dumps(q) + "\n" for q in rows).encode()
    path.write_bytes(raw)
    return raw


def test_hash_and_counts_only_using_external_format_probe(tmp_path):
    path = tmp_path / "fabricated-format-probe.jsonl"
    raw = write_probe(path, probes())
    manifest = seal_manifest(path)
    assert manifest == {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "total_count": 60,
        "counts_by_category": {"sales": 40, "injection": 20},
        "counts_by_behavior": {"answer": 40, "refuse": 20},
    }


def test_cli_prints_no_content_or_path_on_success_or_failure(tmp_path):
    path = tmp_path / "fabricated-format-probe.jsonl"
    write_probe(path, probes())
    # Explicit override: no test reads any inherited HELDOUT_PATH.
    env = dict(os.environ, HELDOUT_PATH=str(path))
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/hash_heldout.py")],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["total_count"] == 60
    assert "FORMAT PROBE" not in result.stdout + result.stderr
    assert str(path) not in result.stdout + result.stderr
    path.write_text('{"question_ar":"PRIVATE SENTINEL",oops}\n')
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/hash_heldout.py")],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "PRIVATE SENTINEL" not in result.stdout + result.stderr
    assert str(path) not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "failure",
    ["count", "duplicate", "split", "pending", "future", "bad_category", "traversal"],
)
def test_sealing_rejects_invalid_files_without_printing_content(tmp_path, failure):
    rows = probes()
    if failure == "count":
        rows.pop()
    elif failure == "duplicate":
        rows[-1]["id"] = rows[0]["id"]
    elif failure == "split":
        rows[0]["spec"]["expected_behavior"] = "clarify"
    elif failure == "pending":
        rows[0]["arabic_review"] = "pending"
    elif failure == "future":
        rows[0]["business_as_of"] = "2026-09-29"
    elif failure == "bad_category":
        rows[0]["category"] = "PRIVATE SENTINEL"
    elif failure == "traversal":
        rows[0]["dataset"] = "../synthetic/future_30d_ground_truth"
    path = tmp_path / "fabricated-format-probe.jsonl"
    write_probe(path, rows)
    with pytest.raises(ValueError):
        seal_manifest(path)


def test_sealing_refuses_a_path_inside_the_repository():
    with pytest.raises(ValueError):
        seal_manifest(ROOT / "data/evaluation/development_questions.jsonl")


def test_question_validator_checks_joint_labels_and_period():
    question = probes()[0]
    validate_question(question)
    question["spec"]["resolved_period"]["end"] = "2026-10-01"
    with pytest.raises(ValueError):
        validate_question(question)
