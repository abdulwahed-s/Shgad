"""D56/T19: all private-looking files here are fabricated temporary sentinels."""

import json
from pathlib import Path

import pytest
from scripts import evaluation_requirements as requirements
from scripts import evaluation_v2 as v2
from scripts import run_evaluation as harness
from test_evaluation_split import sealed_sentinels


def test_v1_cli_defaults_are_unchanged():
    args = harness.parser().parse_args(["--split", "heldout"])
    assert args.heldout_seal is None and args.heldout_requirements is None
    assert (
        args.freeze_manifest
        == harness.ROOT / "results/evaluation_method_freeze_reviewed_requirements.json"
    )
    assert v2.validate_selection(args) is False


@pytest.mark.parametrize(
    "option", ["--heldout-seal", "--heldout-requirements", "--freeze-manifest"]
)
def test_every_selected_v2_manifest_must_be_external(tmp_path, option):
    values = {
        "--heldout-seal": tmp_path / "seal.json",
        "--heldout-requirements": tmp_path / "requirements.json",
        "--freeze-manifest": tmp_path / "freeze.json",
    }
    values[option] = harness.ROOT / "never-opened.json"
    args = harness.parser().parse_args(
        ["--split", "heldout", *[str(x) for pair in values.items() for x in pair]]
    )
    with pytest.raises(harness.EvaluationError, match="V2_MANIFESTS_MUST_BE_EXTERNAL"):
        v2.validate_selection(args)


def test_selected_question_seal_is_checked_before_parsing(tmp_path, monkeypatch):
    root, path, rows, manifest = sealed_sentinels(tmp_path, monkeypatch)
    seal = tmp_path / "v2-seal.json"
    seal.write_text(json.dumps(manifest), encoding="utf-8")
    assert harness.load_questions(
        "heldout", authorized=True, data_root=root, heldout_seal=seal
    ) == (rows, manifest["sha256"])
    path.write_bytes(b"\xffNEVER_PRINT_SENTINEL")
    with pytest.raises(harness.EvaluationError, match="HELDOUT_HASH_MISMATCH"):
        harness.load_questions(
            "heldout", authorized=True, data_root=root, heldout_seal=seal
        )


def test_selected_requirement_manifest_binds_the_exact_question_hash(tmp_path):
    from test_evaluation_requirements import fixture

    root, _, sha, _, _, _, _, _ = fixture(tmp_path)
    source = root / "evaluation/heldout_requirements_manifest.json"
    selected = tmp_path / "v2-requirements-seal.json"
    selected.write_bytes(source.read_bytes())
    assert (
        requirements.status("heldout", sha, data_root=root, manifest_path=selected)[
            "status"
        ]
        == "sealed"
    )
    with pytest.raises(
        requirements.RequirementsError, match="REQUIREMENTS_QUESTION_HASH_MISMATCH"
    ):
        requirements.status("heldout", "b" * 64, data_root=root, manifest_path=selected)


@pytest.mark.parametrize("failure", ["tag", "commit", "dirty"])
def test_application_gate_refuses_wrong_tag_commit_and_dirty_tree(monkeypatch, failure):
    def git(*args):
        if args[0] == "rev-parse":
            return "b" * 40 if failure == "tag" else v2.APPLICATION_COMMIT
        if args[0] == "diff":
            return "backend/app/frozen.py" if failure == "commit" else ""
        if args[0] == "status":
            return " M backend/app/frozen.py" if failure == "dirty" else ""
        pytest.fail("unexpected git request")

    monkeypatch.setattr(v2, "git", git)
    with pytest.raises(harness.EvaluationError, match="FROZEN_APPLICATION"):
        v2.check_application()


def test_output_json_or_markdown_must_be_new(tmp_path):
    output = tmp_path / "new.json"
    v2.check_output(output)
    output.with_suffix(".md").write_text("PRESERVE", encoding="utf-8")
    with pytest.raises(harness.EvaluationError, match="RESULT_ALREADY_EXISTS"):
        v2.check_output(output)


def test_selected_annotations_are_hash_checked_before_parse(tmp_path, monkeypatch):
    from test_evaluation_requirements import fixture

    root, questions, sha, path, sidecar, _, _, _ = fixture(tmp_path)
    selected = tmp_path / "requirements-seal.json"
    selected.write_bytes(
        (root / "evaluation/heldout_requirements_manifest.json").read_bytes()
    )
    monkeypatch.setenv("HELDOUT_PATH", str(path))
    result, _ = requirements.load(
        "heldout",
        questions,
        sha,
        authorized=True,
        data_root=root,
        manifest_path=selected,
    )
    assert result["FORMAT-A"] == {"total_sales"}
    sidecar.write_bytes(b"\xffNEVER_PRINT_ANNOTATION")
    with pytest.raises(
        requirements.RequirementsError, match="REQUIREMENTS_HASH_MISMATCH"
    ):
        requirements.load(
            "heldout",
            questions,
            sha,
            authorized=True,
            data_root=root,
            manifest_path=selected,
        )


def test_v2_plan_prints_command_and_caps_without_private_or_credentials(
    tmp_path, monkeypatch
):
    from scripts import evaluation_reports
    from test_evaluation_requirements import fixture

    root, _, rows, seal = sealed_sentinels(tmp_path, monkeypatch)
    # A second temporary fixture supplies the public annotation contract/metadata.
    req_root, _, _, _, _, _, manifest, _ = fixture(tmp_path / "annotation")
    spec = req_root / "evaluation/REQUIREMENTS_SPEC.md"
    (root / "evaluation/REQUIREMENTS_SPEC.md").write_bytes(spec.read_bytes())
    manifest.update(
        question_sha256=seal["sha256"],
        total_count=60,
        answer_count=40,
        reviewed_count=60,
        counts_by_behavior=seal["counts_by_behavior"],
    )
    question_seal = tmp_path / "V2_SEAL.json"
    question_seal.write_text(json.dumps(seal), encoding="utf-8")
    req_seal = tmp_path / "V2_REQUIREMENTS_SEAL.json"
    req_seal.write_text(json.dumps(manifest), encoding="utf-8")
    freeze = tmp_path / "method.json"
    freeze.write_text(
        json.dumps(dict(settings=dict(evidence_method=v2.METHOD_V2))), encoding="utf-8"
    )
    monkeypatch.setattr(v2, "check_application", lambda: None)
    monkeypatch.setattr(
        v2, "snapshot", lambda **_: dict(settings=evaluation_reports.SETTINGS)
    )
    monkeypatch.setattr(evaluation_reports, "verify_freeze", lambda *a: {})
    monkeypatch.setattr(
        harness.os, "getenv", lambda *a: pytest.fail("plan read private env")
    )
    original = Path.read_bytes

    def read_bytes(path):
        if path.suffix == ".jsonl":
            pytest.fail("plan opened private questions or annotations")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    result = harness.plan(
        "heldout",
        max_requests=180,
        data_root=root,
        heldout_seal=question_seal,
        heldout_requirements=req_seal,
        freeze_manifest=freeze,
        output=tmp_path / "new.json",
    )
    assert result["max_requests"] == 180 and result["question_count"] == len(rows)
    assert result["provider_requests"] == 0 and result["credentials_loaded"] is False
    assert result["heldout_opened"] is False
    assert "--heldout-seal" in result["live_command"]
    assert "--heldout-requirements" in result["live_command"]
    assert "--max-requests 180" in result["live_command"]
    assert "application_matches_freeze_tag" in result["checks"]


def test_v2_freeze_requires_named_method_and_preserves_v1_selection(tmp_path):
    old = tmp_path / "v1.json"
    old.write_text(json.dumps(dict(settings={})), encoding="utf-8")
    assert v2.method_from_freeze(old) == "row_provenance_v1"
    new = tmp_path / "v2.json"
    new.write_text(
        json.dumps(dict(settings=dict(evidence_method=v2.METHOD_V2))), encoding="utf-8"
    )
    assert v2.method_from_freeze(new) == v2.METHOD_V2


def test_external_v2_live_freeze_reaches_cli_preflight(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(harness, "seal_metadata", lambda **_: {"sha256": "a" * 64})
    monkeypatch.setattr(requirements, "status", lambda *a, **kw: dict(status="sealed"))

    def preflight(*args, **kwargs):
        assert kwargs["freeze_manifest"] == tmp_path / "method.json"
        raise harness.EvaluationError("V2_PREFLIGHT_REACHED")

    monkeypatch.setattr(harness, "plan", preflight)
    assert (
        harness.main(
            [
                "--split",
                "heldout",
                "--mode",
                "live",
                "--authorize-paid",
                "--authorize-heldout",
                "--heldout-seal",
                str(tmp_path / "seal.json"),
                "--heldout-requirements",
                str(tmp_path / "requirements.json"),
                "--freeze-manifest",
                str(tmp_path / "method.json"),
                "--output",
                str(tmp_path / "new.json"),
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().err)["error"] == "V2_PREFLIGHT_REACHED"


@pytest.mark.parametrize(
    "change",
    [dict(gemini_reasoning_effort="default"), dict(llm_primary_timeout_seconds=30)],
)
def test_v2_refuses_runtime_settings_different_from_frozen_settings(change):
    from app.config import Settings

    with pytest.raises(harness.EvaluationError, match="V2_RUNTIME_SETTINGS_MISMATCH"):
        v2.check_runtime_settings(Settings(**change))


def test_v2_safe_disclosures_reach_aggregate_only_json_and_markdown():
    from scripts.evaluation_reports import markdown, public_report
    from test_evaluation_reports import metadata, row

    data = metadata() | dict(
        settings=dict(evidence_method=v2.METHOD_V2),
        application_commit=v2.APPLICATION_COMMIT,
        application_tag="freeze-heldout-v2",
        dataset_disclosure="questions unseen, ledger previously used in development",
        primary_seed=20260701,
        method_change=dict(
            decision="D56",
            original_results_preserved=True,
            scope="evaluator_only_independent_zero_and_sourced_reconciliation_mapping",
        ),
    )
    report = public_report(
        split="heldout",
        mode="live",
        rows=[row()],
        metadata=data,
        reconciliation={},
        forecast=dict(frozen_code_commit="a" * 40, summary={}),
    )
    assert report["dataset_disclosure"] == data["dataset_disclosure"]
    assert report["application_commit"] == v2.APPLICATION_COMMIT
    assert report["method_change"]["decision"] == "D56"
    assert "questions unseen, ledger previously used in development" in markdown(report)
    assert "cases" not in report and "DO_NOT_EXPORT" not in json.dumps(report)
