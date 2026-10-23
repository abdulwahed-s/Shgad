"""D50/T19: handmade format selectors only, never actual sealed annotations."""

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from scripts import evaluation_requirements as requirements
from scripts import run_evaluation
from scripts.evaluation_metrics import grade_question
from scripts.evaluation_requirements import RequirementsError


def fixture(tmp_path, *, split="heldout"):
    root = tmp_path / "public"
    folder = root / "evaluation"
    folder.mkdir(parents=True)
    spec = folder / "REQUIREMENTS_SPEC.md"
    spec.write_text("HANDMADE SELECTOR FORMAT SPEC\n", encoding="utf-8", newline="\n")
    questions = [
        dict(id="FORMAT-A", spec=dict(expected_behavior="answer")),
        dict(id="FORMAT-B", spec=dict(expected_behavior="clarify")),
    ]
    question_sha = "a" * 64
    private = tmp_path / "format-questions.jsonl"
    private.write_text("FORMAT ONLY, NEVER READ BY REQUIREMENTS LOADER")
    sidecar = private.with_name(private.name + ".requirements.jsonl")
    if split == "dev":
        sidecar = folder / "development_requirements.jsonl"
    rows = [
        dict(id="FORMAT-A", required_fields=["total_sales"]),
        dict(id="FORMAT-B", required_fields=[]),
    ]
    manifest = dict(
        schema_version="shgad-requirements-v1",
        split=split,
        question_sha256=question_sha,
        sha256="",
        total_count=2,
        answer_count=1,
        human_reviewed=True,
        independent_of_build=True,
        generator_tool="handmade-test",
        generator_model_id="not_exposed",
        reviewed_at="2026-10-23T00:00:00+00:00",
        reviewed_count=2,
        counts_by_behavior=dict(answer=1, clarify=1),
        selector_spec_sha256=hashlib.sha256(spec.read_bytes()).hexdigest(),
    )
    seal = folder / (split + "_requirements_manifest.json")

    def write(*, reseal=True):
        raw = "".join(json.dumps(row) + "\n" for row in rows).encode()
        sidecar.write_bytes(raw)
        if reseal:
            manifest["sha256"] = hashlib.sha256(raw).hexdigest()
        seal.write_text(json.dumps(manifest), encoding="utf-8")

    write()
    return root, questions, question_sha, private, sidecar, rows, manifest, write


def test_absent_manifest_is_public_blocker_without_private_access(tmp_path):
    assert requirements.status("heldout", "a" * 64, data_root=tmp_path) == dict(
        status="missing", blocker="REQUIREMENTS_SEAL_REQUIRED"
    )


def test_unauthorized_heldout_requirements_never_read_private_env(monkeypatch):
    monkeypatch.setattr(
        requirements.os, "getenv", lambda _: pytest.fail("read private env")
    )
    with pytest.raises(RequirementsError, match="HELDOUT_NOT_AUTHORIZED"):
        requirements.load("heldout", [], "a" * 64)


def test_hash_before_parse_and_error_does_not_export_private_bytes(
    tmp_path, monkeypatch
):
    root, questions, sha, path, sidecar, _, _, _ = fixture(tmp_path)
    monkeypatch.setenv("HELDOUT_PATH", str(path))
    sidecar.write_bytes(b"\xffPRIVATE_REQUIREMENT_SENTINEL")
    with pytest.raises(RequirementsError, match="REQUIREMENTS_HASH_MISMATCH") as error:
        requirements.load("heldout", questions, sha, authorized=True, data_root=root)
    assert "PRIVATE" not in str(error.value) and str(sidecar) not in str(error.value)


@pytest.mark.parametrize("split", ["dev", "heldout"])
def test_separate_seal_and_exact_question_binding(tmp_path, monkeypatch, split):
    root, questions, sha, path, _, _, manifest, _ = fixture(tmp_path, split=split)
    if split == "heldout":
        monkeypatch.setenv("HELDOUT_PATH", str(path))
    else:
        monkeypatch.setattr(
            requirements.os, "getenv", lambda _: pytest.fail("dev private access")
        )
    selected, receipt = requirements.load(
        split, questions, sha, authorized=True, data_root=root
    )
    assert selected == {"FORMAT-A": {"total_sales"}, "FORMAT-B": set()}
    assert receipt["sha256"] == manifest["sha256"]
    assert "FORMAT-A" not in json.dumps(receipt)
    with pytest.raises(RequirementsError, match="REQUIREMENTS_QUESTION_HASH_MISMATCH"):
        requirements.status(split, "b" * 64, data_root=root)


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "missing",
        "extra",
        "answer_empty",
        "unsafe_number",
        "value",
        "unknown",
        "projection",
        "duplicates",
        "blank",
    ],
)
def test_strict_shape_complete_ids_and_selectors(tmp_path, monkeypatch, mutation):
    root, questions, sha, path, sidecar, rows, _, write = fixture(tmp_path)
    if mutation == "duplicate":
        rows[1] = rows[0]
    elif mutation == "missing":
        rows.pop()
    elif mutation == "extra":
        rows[1]["id"] = "FORMAT-C"
    elif mutation == "answer_empty":
        rows[0]["required_fields"] = []
    elif mutation == "unsafe_number":
        rows[1]["required_fields"] = ["cash_sales"]
    elif mutation == "value":
        rows[0]["expected_value"] = 123
    elif mutation in {"unknown", "projection"}:
        rows[0]["required_fields"] = [
            "PRIVATE_LABEL" if mutation == "unknown" else "forecast.base.days.0.closing"
        ]
    elif mutation == "duplicates":
        rows[0]["required_fields"] *= 2
    write()
    if mutation == "blank":
        sidecar.write_bytes(sidecar.read_bytes() + b"\n")
        # Re-seal only these fabricated bytes so parsing, not hashing, rejects.
        manifest_path = root / "evaluation/heldout_requirements_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["sha256"] = hashlib.sha256(sidecar.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
    monkeypatch.setenv("HELDOUT_PATH", str(path))
    with pytest.raises(RequirementsError, match="REQUIREMENTS_FORMAT_INVALID"):
        requirements.load("heldout", questions, sha, authorized=True, data_root=root)


@pytest.mark.parametrize(
    "change",
    [
        "review",
        "independent",
        "count",
        "schema",
        "extra",
        "selector_spec",
        "behavior",
        "review_count",
        "date",
    ],
)
def test_public_manifest_fails_closed_before_private_env(tmp_path, monkeypatch, change):
    root, _, sha, _, _, _, manifest, write = fixture(tmp_path)
    key, value = {
        "review": ("human_reviewed", False),
        "independent": ("independent_of_build", False),
        "count": ("total_count", True),
        "schema": ("schema_version", "other"),
        "extra": ("PRIVATE_TEXT", "never export"),
        "selector_spec": ("selector_spec_sha256", "b" * 64),
        "behavior": ("counts_by_behavior", dict(answer=1, refuse=2)),
        "review_count": ("reviewed_count", 1),
        "date": ("reviewed_at", "2026-10-23"),
    }[change]
    manifest[key] = value
    write()
    monkeypatch.setattr(
        requirements.os, "getenv", lambda _: pytest.fail("premature private access")
    )
    with pytest.raises(RequirementsError, match="INVALID_REQUIREMENTS_MANIFEST"):
        requirements.load("heldout", [], sha, authorized=True, data_root=root)


def test_total_and_breakdown_are_independent_and_not_interchangeable():
    spec = dict(
        expected_behavior="answer",
        intent="sales",
        expected_tools=["get_sales"],
        counterparty_ids=[],
        resolved_period=None,
        calculation="sales",
        parameters=dict(kind="all"),
    )
    truth = {
        "total_sales": dict(value=100, unit="IQD", label="total", source_ids=["S"])
    }
    observed = dict(
        behavior="answer",
        intent="sales",
        tools=["get_sales"],
        counterparty_ids=[],
        period=None,
        claims=[
            dict(
                field="total_sales",
                value=100,
                unit="IQD",
                label="total",
                source_ids=["S"],
                formula="sum",
            )
        ],
    )
    assert grade_question(spec, truth, {"total_sales"}, observed)["numeric_correct"]
    assert not grade_question(spec, truth, {"cash_sales", "credit_sales"}, observed)[
        "numeric_correct"
    ]


def question(key="FORMAT-SECRET-ID"):
    return dict(
        id=key,
        category="sales",
        dataset="primary",
        question_ar="FORMAT ONLY",
        business_as_of="2026-09-28",
        arabic_review="approved",
        spec=dict(
            expected_behavior="answer",
            intent="sales",
            expected_tools=["get_sales"],
            counterparty_ids=[],
            resolved_period=dict(start="2026-09-28", end="2026-09-28"),
            calculation="sales",
            parameters=dict(kind="all"),
        ),
    )


def test_all_reference_preflight_rejects_later_absent_field_before_any_answer():
    questions = [question("FORMAT-A"), question("FORMAT-B")]
    with pytest.raises(RequirementsError, match="REQUIREMENTS_REFERENCE_INVALID"):
        run_evaluation.prepare_references(
            questions,
            {
                "FORMAT-A": {"total_sales"},
                "FORMAT-B": {"receivables.customers.999.outstanding"},
            },
        )


def test_live_preflight_aborts_before_loading_credentials_or_constructing_client(
    tmp_path, monkeypatch, capsys
):
    from scripts import evaluation_reports

    from app import config

    monkeypatch.setattr(requirements, "status", lambda *a, **kw: dict(status="sealed"))
    monkeypatch.setattr(
        run_evaluation,
        "plan",
        lambda *a, **kw: dict(settings=evaluation_reports.SETTINGS, max_requests=96),
    )
    monkeypatch.setattr(evaluation_reports, "verify_freeze", lambda *a: {})
    monkeypatch.setattr(
        run_evaluation, "load_questions", lambda *a, **kw: ([question()], "a" * 64)
    )
    monkeypatch.setattr(
        requirements,
        "load",
        lambda *a, **kw: (
            {"FORMAT-SECRET-ID": {"receivables.customers.999.outstanding"}},
            {},
        ),
    )
    monkeypatch.setattr(config, "runtime_settings", lambda: pytest.fail("credentials"))
    assert (
        run_evaluation.main(
            [
                "--split",
                "dev",
                "--mode",
                "live",
                "--authorize-paid",
                "--output",
                str(tmp_path / "result.json"),
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().err) == dict(
        error="REQUIREMENTS_REFERENCE_INVALID"
    )


def test_sealed_selector_replaces_legacy_and_never_enters_model_messages():
    from scripts.evaluation_clients import ReplayClient

    client = ReplayClient()
    q = question()
    script = dict(
        intent="sales",
        turns=[
            dict(
                calls=[
                    dict(name="get_sales", arguments=dict(period="today", kind="all"))
                ]
            ),
            dict(action=dict(status="answered", draft_ar="{{fig:total_sales}}")),
        ],
    )
    rows = asyncio.run(
        run_evaluation.evaluate_questions(
            [q],
            client=client,
            replay={q["id"]: script},
            requirements={q["id"]: {"total_sales"}},
        )
    )
    assert rows[0]["numeric_correct"]
    context = json.dumps(client.messages)
    assert "FORMAT-SECRET-ID" not in context and "required_fields" not in context
    assert "FORMAT ONLY" in context and client.receipt()["provider_requests"] == 0


def test_sidecar_exact_newlines_and_external_path_boundary(tmp_path, monkeypatch):
    root, questions, sha, path, sidecar, _, _, _ = fixture(tmp_path)
    monkeypatch.setenv("HELDOUT_PATH", str(path))
    sidecar.write_bytes(sidecar.read_bytes().replace(b"\n", b"\r\n"))
    with pytest.raises(RequirementsError, match="REQUIREMENTS_HASH_MISMATCH"):
        requirements.load("heldout", questions, sha, authorized=True, data_root=root)
    monkeypatch.setenv("HELDOUT_PATH", str(Path(run_evaluation.ROOT) / "not-opened"))
    with pytest.raises(RequirementsError, match="HELDOUT_MUST_BE_EXTERNAL"):
        requirements.load("heldout", questions, sha, authorized=True, data_root=root)


def test_resolved_sidecar_escape_refuses_before_open(tmp_path, monkeypatch):
    root, questions, sha, path, sidecar, _, _, _ = fixture(tmp_path)
    monkeypatch.setenv("HELDOUT_PATH", str(path))
    original = Path.resolve

    def redirected(self, *args, **kwargs):
        if self == sidecar:
            return tmp_path / "another-directory" / sidecar.name
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", redirected)
    with pytest.raises(RequirementsError, match="REQUIREMENTS_PATH_INVALID"):
        requirements.load("heldout", questions, sha, authorized=True, data_root=root)


def test_early_dev_seal_gate_rejects_external_question_link_before_hash(
    tmp_path, monkeypatch, capsys
):
    from scripts import data_contract

    public = run_evaluation.ROOT / "data/evaluation/development_questions.jsonl"
    original = Path.resolve

    def escaped(self, *args, **kwargs):
        if self == public:
            return tmp_path / "external-private-never-opened.jsonl"
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", escaped)
    monkeypatch.setattr(data_contract, "sha256", lambda _: pytest.fail("unsafe hash"))
    assert (
        run_evaluation.main(["--split", "dev", "--mode", "live", "--authorize-paid"])
        == 1
    )
    assert json.loads(capsys.readouterr().err) == dict(
        error="PUBLIC_INPUT_PATH_REQUIRED"
    )


def test_standalone_cash_selector_loads_and_preflights_without_private_questions(
    tmp_path, monkeypatch
):
    root, questions, sha, _, _, rows, _, write = fixture(tmp_path, split="dev")
    rows[0]["required_fields"] = ["cash_on_hand"]
    write()
    monkeypatch.setattr(requirements.os, "getenv", lambda _: pytest.fail("private env"))
    selected, _ = requirements.load("dev", questions, sha, data_root=root)
    q = question("FORMAT-A")
    q["spec"]["calculation"] = "cash"
    q["spec"]["parameters"] = {}
    references = run_evaluation.prepare_references([q], {q["id"]: selected[q["id"]]})
    assert references[q["id"]][3] == {"cash_on_hand"}
    assert references[q["id"]][2]["cash_on_hand"]["unit"] == "IQD"


@pytest.mark.parametrize("field", sorted(requirements.HISTORICAL_FIELDS))
def test_approved_historical_selectors_load_from_handmade_format_only(tmp_path, field):
    root, questions, sha, _, _, rows, _, write = fixture(tmp_path, split="dev")
    rows[0]["required_fields"] = [field]
    write()
    selected, _ = requirements.load("dev", questions, sha, data_root=root)
    assert selected["FORMAT-A"] == {field}


def test_historical_selector_requires_original_unique_period_never_defaults_today():
    q = question()
    q["spec"]["resolved_period"] = None
    with pytest.raises(RequirementsError, match="REQUIREMENTS_REFERENCE_INVALID"):
        run_evaluation.prepare_references([q], {q["id"]: {"period_end.cash_on_hand"}})


def test_selected_cash_movement_preflight_needs_no_unrequested_cash_baseline(tmp_path):
    from scripts.data_contract import write_csv

    q = question()
    q["dataset"] = "small_happy_path"
    q["spec"]["calculation"] = "cash"
    q["spec"]["parameters"] = {}
    row = dict(
        transaction_id="FORMAT-SALE",
        source_id="FORMAT-SALE",
        type="CASH_SALE",
        amount_iqd=30,
        business_date="2026-09-28",
        occurred_at="2026-09-28T12:00:00+03:00",
        recorded_at="2026-09-28T12:00:00+03:00",
        category_id=None,
        quantity=None,
        obligation_id=None,
        counterparty_id=None,
        due_date=None,
    )
    write_csv(tmp_path / "fixtures/small_happy_path.csv", [row], row.keys())
    result = run_evaluation.prepare_references(
        [q], {q["id"]: {"period.cash_inflows_iqd"}}, data_root=tmp_path
    )
    assert result[q["id"]][2]["period.cash_inflows_iqd"]["value"] == 30
