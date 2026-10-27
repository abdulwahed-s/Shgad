"""D58: v3 sealing, loading, grading and reporting with public stand-in questions.

The stand-ins are reviewed public development questions copied to a temporary
folder; no held-out file is created, read or reconstructed here.
"""

import copy
import json

import pytest
from scripts import evaluation_v3 as v3
from scripts import run_evaluation as harness
from scripts.data_contract import QUESTION_SCHEMA_V2, validate_question_v2
from scripts.evaluation_metrics import grade_question_v3
from scripts.evaluation_reports import public_report
from scripts.hash_heldout import seal_manifest


def public_v2_questions():
    path = harness.ROOT / "data/evaluation/development_questions_v3.jsonl"
    rows = [json.loads(line) for line in path.read_text("utf-8").splitlines()]
    for row in rows:
        row.pop("difficulty", None)
    return [r for r in rows if r["arabic_review"] == "approved"]


def sixty(tmp_path):
    rows = public_v2_questions()
    answers = [r for r in rows if r["spec"]["expected_behavior"] == "answer"][:40]
    others = [r for r in rows if r["spec"]["expected_behavior"] != "answer"][:20]
    path = tmp_path / "standin_60.jsonl"
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in answers + others) + "\n",
        encoding="utf-8",
    )
    return path


def test_v2_validator_follows_label_rules():
    rows = public_v2_questions()
    for row in rows:
        validate_question_v2(row)
    answer = next(
        r
        for r in rows
        if r["spec"]["intent"] == "debts" and r["spec"]["counterparty_ids"]
    )
    for mutate in (
        lambda s: s.update(expected_tools=["get_sales"]),
        lambda s: s.update(
            resolved_period={"start": "2026-07-01", "end": "2026-07-02"}
        ),
        lambda s: s.update(calculation="sales"),
    ):
        broken = copy.deepcopy(answer)
        mutate(broken["spec"])
        with pytest.raises(ValueError):
            validate_question_v2(broken)
    clarify = next(r for r in rows if r["spec"]["expected_behavior"] == "clarify")
    for mutate in (
        lambda s: s.update(expected_tools=["get_debts"]),
        lambda s: s.update(error_code="SOMETHING_ELSE"),
        lambda s: s.pop("error_code"),
    ):
        broken = copy.deepcopy(clarify)
        mutate(broken["spec"])
        with pytest.raises(ValueError):
            validate_question_v2(broken)
    with pytest.raises(ValueError):
        validate_question_v2(answer | {"difficulty": "hard"})


def test_v2_seal_records_its_schema_and_loader_uses_the_v2_validator(
    tmp_path, monkeypatch
):
    path = sixty(tmp_path)
    manifest = seal_manifest(path, schema="v2")
    assert manifest["question_schema"] == QUESTION_SCHEMA_V2
    assert manifest["total_count"] == 60
    seal = tmp_path / "v3-seal.json"
    seal.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("HELDOUT_PATH", str(path))
    rows, digest = harness.load_questions("heldout", authorized=True, heldout_seal=seal)
    assert len(rows) == 60 and digest == manifest["sha256"]
    with pytest.raises(ValueError):
        seal_manifest(path)  # v1 validator rejects the v2 intents/labels
    manifest["question_schema"] = "shgad-question-v9"
    seal.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(harness.EvaluationError, match="INVALID_SEAL_MANIFEST"):
        harness.seal_metadata(heldout_seal=seal)


def view(**fields):
    return {"behavior": "answer", "claims": [], "interpretation": fields}


def test_grading_v3_answers_and_decisions():
    spec = {
        "intent": "debts",
        "expected_behavior": "answer",
        "counterparty_ids": ["CUST-01"],
        "resolved_period": {"start": "2026-09-28", "end": "2026-09-28"},
        "parameters": {},
    }
    fact = {
        "value": 5,
        "unit": "IQD",
        "label": "total_outstanding",
        "source_ids": ["A"],
    }
    claim = {
        "field": "receivables.total_outstanding",
        "value": 5,
        "unit": "IQD",
        "label": "total_outstanding",
        "source_ids": ["A"],
        "formula": "f",
    }
    observed = view(
        intent="debts",
        tools=["get_debts"],
        counterparty_ids=["CUST-01"],
        period=spec["resolved_period"],
    ) | {"claims": [claim]}
    catalogue = {"receivables.total_outstanding": fact}
    graded = grade_question_v3(
        spec, catalogue, {"receivables.total_outstanding"}, observed
    )
    assert graded["joint_correct"] and graded["numeric_correct"]
    wrong_tools = observed | {
        "interpretation": observed["interpretation"] | {"tools": ["get_sales"]}
    }
    assert not grade_question_v3(
        spec, catalogue, {"receivables.total_outstanding"}, wrong_tools
    )["joint_correct"]
    clarify = {
        "intent": "debts",
        "expected_behavior": "clarify",
        "error_code": "AMBIGUOUS_COUNTERPARTY",
        "counterparty_ids": ["CUST-02", "CUST-03"],
        "resolved_period": None,
        "parameters": {},
    }
    decided = {
        "behavior": "clarify",
        "claims": [],
        "interpretation": {
            "intent": "debts",
            "reason": "AMBIGUOUS_COUNTERPARTY",
            "counterparty_ids": ["CUST-03", "CUST-02"],
        },
    }
    assert grade_question_v3(clarify, {}, set(), decided)["joint_correct"]
    other = decided | {
        "interpretation": decided["interpretation"] | {"reason": "OUT_OF_SCOPE"}
    }
    assert not grade_question_v3(clarify, {}, set(), other)["joint_correct"]
    assert not grade_question_v3(clarify, {}, set(), {"behavior": "clarify"})[
        "joint_correct"
    ]


def test_v3_report_is_aggregate_only_with_the_v1_method_beside_it():
    row = {
        "id": "PRIVATE-ID-NEVER-PUBLIC",
        "category": "sales",
        "expected_behavior": "answer",
        "numeric_correct": True,
        "safe_correct": False,
        "joint_correct": True,
        "fields": dict(intent=True, tool=True, customer=True, period=True, reason=True),
        "traceability": {"numerator": 1, "denominator": 1, "rate": 1.0},
        "failures": [],
    }
    # The measured loop stores the bare v1 grade, without category/behavior.
    row["v1_method"] = {
        key: value
        for key, value in row.items()
        if key not in {"id", "category", "expected_behavior"}
    } | {"joint_correct": False, "failures": ["wrong_intent"]}
    metadata = {
        key: "x"
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
    } | {"settings": {"grading": v3.GRADING}}
    report = public_report(
        split="heldout",
        mode="live",
        rows=[row],
        metadata=metadata,
        reconciliation={},
        forecast={},
    )
    assert report["metrics"]["joint_accuracy"]["numerator"] == 1
    assert report["v1_method_metrics"]["joint_accuracy"]["numerator"] == 0
    assert report["method_change"]["decision"] == "D58"
    assert "PRIVATE-ID-NEVER-PUBLIC" not in json.dumps(report, default=str)


def test_v3_gate_refuses_until_the_application_is_tagged(monkeypatch):
    monkeypatch.setattr(v3, "APPLICATION_COMMIT", None)
    with pytest.raises(harness.EvaluationError, match="V3_APPLICATION_NOT_FROZEN"):
        v3.check_application()


@pytest.mark.pipeline("interpretation")
def test_measured_loop_grades_v3_without_a_probe_and_keeps_the_v1_grade():
    import asyncio

    from scripts.evaluation_evidence import METHOD_V2

    question = next(
        r
        for r in public_v2_questions()
        if r["id"].startswith("DV3T")
        and r["spec"]["intent"] == "debts"
        and r["spec"]["counterparty_ids"]
        and r["dataset"] == "primary"
    )
    requirements = {question["id"]: {"receivables.total_outstanding"}}
    references = harness.prepare_references([question], requirements, method=METHOD_V2)

    class Reply:
        tool_calls = ()

        def __init__(self, content):
            self.content = content
            self.message = {"role": "assistant", "content": content}

    class Client:
        def __init__(self):
            self.json_modes = []

        def begin_question(self, _=None):
            pass

        async def complete(self, messages, *, tools=(), json_mode=False):
            self.json_modes.append(json_mode)
            return Reply("not json")

    client = Client()
    rows = asyncio.run(
        harness.evaluate_questions(
            [question],
            client=client,
            requirements=requirements,
            references=references,
            method=METHOD_V2,
            grading="v3",
        )
    )
    # Two interpretation attempts, both rejected: no separate intent probe call.
    assert client.json_modes == [True, True]
    assert "v1_method" in rows[0] and "reason" in rows[0]["fields"]
    assert not rows[0]["joint_correct"]
