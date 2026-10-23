"""T19: fabricated format sentinels only. Never use actual HELDOUT_PATH."""

import hashlib
import json
from pathlib import Path

import pytest
from scripts import run_evaluation as harness


def sentinel(index, behavior="answer"):
    return dict(
        id=f"FORMAT-SENTINEL-{index}",
        category="sales",
        question_ar="FORMAT ONLY",
        business_as_of="2026-09-28",
        dataset="small_happy_path",
        arabic_review="approved",
        spec=dict(
            intent="sales",
            expected_tools=["get_sales"] if behavior == "answer" else [],
            counterparty_ids=[],
            resolved_period=dict(start="2026-09-28", end="2026-09-28"),
            expected_behavior=behavior,
            calculation="sales" if behavior == "answer" else "none",
            parameters={},
        ),
    )


def sealed_sentinels(tmp_path, monkeypatch):
    root = tmp_path / "public-format-fixture"
    folder = root / "evaluation"
    folder.mkdir(parents=True)
    path = tmp_path / "fabricated-format-probe.jsonl"
    rows = [
        sentinel(i, "answer" if i < 40 else "clarify" if i < 51 else "refuse")
        for i in range(60)
    ]
    raw = "".join(json.dumps(q) + "\n" for q in rows).encode()
    path.write_bytes(raw)
    manifest = dict(
        sha256=hashlib.sha256(raw).hexdigest(),
        total_count=60,
        counts_by_category={"sales": 60},
        counts_by_behavior={"answer": 40, "clarify": 11, "refuse": 9},
    )
    (folder / "heldout_60_manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setenv("HELDOUT_PATH", str(path))
    return root, path, rows, manifest


def test_t19_heldout_checks_hash_and_all_counts_before_return(tmp_path, monkeypatch):
    root, _, rows, manifest = sealed_sentinels(tmp_path, monkeypatch)
    actual, digest = harness.load_questions("heldout", authorized=True, data_root=root)
    assert actual == rows and digest == manifest["sha256"]


def test_hash_mismatch_refuses_before_parse_even_invalid_utf8(tmp_path, monkeypatch):
    root, path, _, _ = sealed_sentinels(tmp_path, monkeypatch)
    path.write_bytes(b"\xffSECRET_SENTINEL")
    monkeypatch.setattr(
        harness, "validate_question", lambda _: pytest.fail("parsed mismatch")
    )
    with pytest.raises(harness.EvaluationError, match="HELDOUT_HASH_MISMATCH") as error:
        harness.load_questions("heldout", authorized=True, data_root=root)
    assert "SECRET" not in str(error.value) and str(path) not in str(error.value)


def test_private_question_newlines_still_require_exact_bytes(tmp_path, monkeypatch):
    root, path, _, _ = sealed_sentinels(tmp_path, monkeypatch)
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    with pytest.raises(harness.EvaluationError, match="HELDOUT_HASH_MISMATCH"):
        harness.load_questions("heldout", authorized=True, data_root=root)


def test_heldout_requires_explicit_gate_before_env_or_file_access(monkeypatch):
    monkeypatch.setattr(
        harness.os, "getenv", lambda _: pytest.fail("read env before gate")
    )
    with pytest.raises(harness.EvaluationError, match="HELDOUT_NOT_AUTHORIZED"):
        harness.load_questions("heldout")


def test_dev_never_reads_heldout_env_or_manifest(tmp_path, monkeypatch):
    folder = tmp_path / "evaluation"
    folder.mkdir()
    row = sentinel(0)
    (folder / "development_questions.jsonl").write_text(json.dumps(row) + "\n")
    monkeypatch.setattr(
        harness.os, "getenv", lambda _: pytest.fail("dev read heldout env")
    )
    rows, _ = harness.load_questions("dev", data_root=tmp_path)
    assert rows == [row]


@pytest.mark.parametrize(
    "mutation", ["duplicate", "pending", "counts", "extra", "blank"]
)
def test_heldout_format_failures_are_sanitized(tmp_path, monkeypatch, mutation):
    root, path, rows, manifest = sealed_sentinels(tmp_path, monkeypatch)
    if mutation == "duplicate":
        rows[1] = rows[0]
    elif mutation == "pending":
        rows[0]["arabic_review"] = "pending"
    elif mutation == "counts":
        rows.pop()
    elif mutation == "extra":
        rows[0]["expected_answer_SECRET"] = 123
    raw = "".join(json.dumps(q) + "\n" for q in rows).encode()
    if mutation == "blank":
        raw += b"\n"
    path.write_bytes(raw)
    manifest["sha256"] = hashlib.sha256(raw).hexdigest()
    (root / "evaluation/heldout_60_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(harness.EvaluationError) as error:
        harness.load_questions("heldout", authorized=True, data_root=root)
    assert "FORMAT-SENTINEL" not in str(error.value) and "SECRET" not in str(
        error.value
    )


def test_question_selection_cannot_be_an_input_path(tmp_path, monkeypatch):
    root, path, rows, manifest = sealed_sentinels(tmp_path, monkeypatch)
    rows[0]["dataset"] = "../../future_30d_ground_truth.csv"
    raw = "".join(json.dumps(q) + "\n" for q in rows).encode()
    path.write_bytes(raw)
    manifest["sha256"] = hashlib.sha256(raw).hexdigest()
    (root / "evaluation/heldout_60_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(harness.EvaluationError, match="QUESTION_FORMAT_INVALID"):
        harness.load_questions("heldout", authorized=True, data_root=root)


def test_heldout_must_resolve_outside_repository(tmp_path, monkeypatch):
    root, _, _, _ = sealed_sentinels(tmp_path, monkeypatch)
    monkeypatch.setenv("HELDOUT_PATH", str(Path(harness.ROOT) / "not-opened.jsonl"))
    with pytest.raises(harness.EvaluationError, match="HELDOUT_MUST_BE_EXTERNAL"):
        harness.load_questions("heldout", authorized=True, data_root=root)


@pytest.mark.parametrize(
    "manifest",
    [
        None,
        [],
        "sentinel",
        1,
        {},
        {"sha256": "0" * 64, "total_count": True},
    ],
)
def test_malformed_manifest_fails_before_private_file_is_opened(
    tmp_path, monkeypatch, manifest
):
    root, path, _, _ = sealed_sentinels(tmp_path, monkeypatch)
    (root / "evaluation/heldout_60_manifest.json").write_text(json.dumps(manifest))
    path.unlink()
    with pytest.raises(harness.EvaluationError, match="INVALID_SEAL_MANIFEST"):
        harness.load_questions("heldout", authorized=True, data_root=root)
