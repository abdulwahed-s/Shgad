"""T19: aggregate-only artifacts and refusal gates using fabricated sentinel rows."""

import json
from pathlib import Path

import pytest
from scripts import run_evaluation
from scripts.evaluation_metrics import grade_question
from scripts.evaluation_reports import markdown, public_report, write_report


def metadata():
    return dict(
        started_at="2026-10-23T00:00:00+00:00",
        executed_at="2026-10-23T00:00:01+00:00",
        code_commit="a" * 40,
        source_hashes={},
        dataset_sha256="b" * 64,
        input_hashes={},
        question_sha256="c" * 64,
        provider="synthetic-replay",
        model_id="synthetic-format-sentinel",
        settings={},
        prompt_hash="d" * 64,
        prompt_version="sentinel",
        intent_prompt_hash="e" * 64,
        tool_schema_hash="f" * 64,
        requests=dict(provider_requests=0),
        freeze_sha256="0" * 64,
        frozen_code_commit="a" * 40,
        python_version="test",
        sqlite_version="test",
        PRIVATE_PATH="DO_NOT_EXPORT_PATH",
    )


def row():
    spec = dict(
        expected_behavior="answer",
        intent="sales",
        expected_tools=["get_sales"],
        counterparty_ids=[],
        resolved_period=None,
    )
    return dict(
        id="DO_NOT_EXPORT_ID",
        category="sales",
        expected_behavior="answer",
        question_ar="DO_NOT_EXPORT_QUESTION",
        response="DO_NOT_EXPORT_RESPONSE",
        spec=dict(error_code="DO_NOT_EXPORT_SPEC"),
        **grade_question(spec, {}, set(), dict(behavior="error")),
    )


def report(split):
    return public_report(
        split=split,
        mode="replay",
        rows=[row()],
        metadata=metadata(),
        reconciliation={},
        forecast=dict(frozen_code_commit="a" * 40, summary={}),
    )


def test_t19_heldout_json_markdown_are_whitelisted_aggregate_only_with_full_counts(
    tmp_path,
):
    result = report("heldout")
    assert "cases" not in result
    assert result["metrics"]["historical_accuracy"] == dict(
        numerator=0, denominator=1, rate=0.0
    )
    assert result["metrics"]["categories"]["sales"] == dict(total=1, passed=0, failed=1)
    assert "DO_NOT_EXPORT" not in json.dumps(result) + markdown(result)
    path = tmp_path / "sentinel.json"
    write_report(path, result)
    assert "DO_NOT_EXPORT" not in path.read_text() + path.with_suffix(".md").read_text()


def test_dev_failure_ids_permitted_but_metadata_still_excludes_private_paths():
    result = report("dev")
    assert "DO_NOT_EXPORT_ID" in markdown(result)
    assert "PRIVATE_PATH" not in result and "DO_NOT_EXPORT_PATH" not in json.dumps(
        result
    )


def test_existing_results_and_markdown_are_never_overwritten(tmp_path):
    path = tmp_path / "receipt.json"
    write_report(path, report("heldout"))
    original = path.read_bytes(), path.with_suffix(".md").read_bytes()
    with pytest.raises(ValueError, match="RESULT_ALREADY_EXISTS"):
        write_report(path, report("dev"))
    assert original == (path.read_bytes(), path.with_suffix(".md").read_bytes())


@pytest.mark.parametrize(
    "args,code",
    [
        (["--split", "dev", "--mode", "live"], "PAID_CALLS_NOT_AUTHORIZED"),
        (
            ["--split", "heldout", "--mode", "live", "--authorize-paid"],
            "HELDOUT_NOT_AUTHORIZED",
        ),
        (["--split", "heldout", "--mode", "replay"], "HELDOUT_REPLAY_PROHIBITED"),
    ],
)
def test_cli_refuses_before_plan_credentials_or_private_access(
    args, code, monkeypatch, capsys
):
    monkeypatch.setattr(
        run_evaluation, "plan", lambda *a, **kw: pytest.fail("premature IO")
    )
    assert run_evaluation.main(args) == 1
    assert json.loads(capsys.readouterr().err) == {"error": code}


@pytest.mark.parametrize("split", ["dev", "heldout"])
def test_unresolved_required_fact_policy_blocks_even_authorized_live_flags(
    split, monkeypatch, capsys
):
    monkeypatch.setattr(
        run_evaluation, "plan", lambda *a, **kw: pytest.fail("premature IO")
    )
    assert (
        run_evaluation.main(
            [
                "--split",
                split,
                "--mode",
                "live",
                "--authorize-paid",
                "--authorize-heldout",
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().err) == dict(
        error="REQUIRED_FACT_POLICY_NOT_FROZEN"
    )


def test_heldout_plan_never_reads_env_or_question_file(monkeypatch):
    from scripts import evaluation_reports

    monkeypatch.setattr(
        run_evaluation.os, "getenv", lambda _: pytest.fail("private env read")
    )
    monkeypatch.setattr(
        evaluation_reports,
        "frozen_snapshot",
        lambda **_: dict(settings=evaluation_reports.SETTINGS),
    )
    result = run_evaluation.plan("heldout")
    assert result["question_count"] == 60 and result["max_requests"] == 180
    assert result["heldout_opened"] is False and result["credentials_loaded"] is False


def test_unknown_failure_text_cannot_escape_into_heldout_aggregates():
    bad = row() | dict(failures=["DO_NOT_EXPORT_PROVIDER_ERROR"])
    with pytest.raises(ValueError, match="INVALID_PUBLIC_FAILURE_CODE"):
        public_report(
            split="heldout",
            mode="live",
            rows=[bad],
            metadata=metadata(),
            reconciliation={},
            forecast={},
        )


def test_corrected_report_discloses_original_run_and_preserves_unmet_targets():
    result = public_report(
        split="heldout",
        mode="live",
        rows=[row()],
        metadata=metadata(),
        reconciliation={},
        forecast=dict(frozen_code_commit="a" * 40, summary={}),
    )
    assert result["target_assessment"]["historical_accuracy"]["met"] is False
    assert (
        result["post_run_changes"][0]["after_run"]
        == "evaluation_replay_2026-10-23.json"
    )
    assert result["post_run_changes"][0]["original_results_preserved"] is True


def test_original_freeze_refuses_after_post_run_evaluator_change():
    from scripts.evaluation_reports import ROOT, frozen_snapshot, verify_freeze

    with pytest.raises(ValueError, match="EVALUATOR_CHANGED_SINCE_FREEZE"):
        verify_freeze(
            ROOT / "results/evaluation_method_freeze.json",
            frozen_snapshot(require_clean=False),
        )


def test_public_seal_metadata_line_endings_do_not_change_observed_dataset_digest(
    tmp_path,
):
    from scripts.evaluation_reports import digest, input_inventory

    folder = tmp_path / "evaluation"
    folder.mkdir()
    path = folder / "heldout_60_manifest.json"
    path.write_bytes(b'{"format_sentinel":true}\r\n')
    windows = digest(input_inventory(tmp_path))
    path.write_bytes(b'{"format_sentinel":true}\n')
    assert digest(input_inventory(tmp_path)) == windows


def test_independent_catalogue_does_not_import_backend_services():
    import ast

    source = Path(__file__).resolve().parents[3] / "scripts/evaluation_truth.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("app")
        elif isinstance(node, ast.Import):
            assert all(not item.name.startswith("app") for item in node.names)


@pytest.mark.parametrize(
    "mode,flag,error",
    [
        ("replay", "--replay-file", "PUBLIC_REPLAY_PATH_REQUIRED"),
        ("replay", "--freeze-manifest", "PUBLIC_FREEZE_PATH_REQUIRED"),
        ("plan", "--freeze-manifest", "PUBLIC_FREEZE_PATH_REQUIRED"),
    ],
)
def test_alternate_public_artifacts_cannot_read_external_private_input(
    tmp_path, monkeypatch, capsys, mode, flag, error
):
    probe = tmp_path / "fabricated-private-format-sentinel.jsonl"
    probe.write_text("DO_NOT_EXPORT_EXTERNAL_SENTINEL")
    monkeypatch.setattr(
        run_evaluation, "plan", lambda *a, **kw: pytest.fail("path gate was bypassed")
    )
    args = ["--split", "dev", "--mode", mode, flag, str(probe)]
    if mode == "plan":
        args.append("--write-freeze")
    assert run_evaluation.main(args) == 1
    assert json.loads(capsys.readouterr().err) == dict(error=error)
