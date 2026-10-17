"""Human approval follows reviewed content, never a blanket or cached flag."""

import copy
import json

import pytest
from scripts.data_contract import read_json
from scripts.development_questions import development_questions
from scripts.generate_synthetic_data import ROOT, generate


@pytest.fixture
def sources():
    return (
        read_json(ROOT / "data/generation/business_mechanics.json"),
        read_json(ROOT / "data/generation/scenario_templates.json"),
    )


def test_generated_review_keeps_uncertain_notes_pending(tmp_path):
    manifest = generate(seed=20260701, output_root=tmp_path)
    assert manifest["human_reviews"] == {
        "arabic": "partial",
        "plausibility": "approved",
    }
    review = manifest["human_review"]
    assert review["pending_arabic_items"] == ["NOTE-01", "NOTE-02"]
    assert review["reviewed_on"] == "2026-10-17"
    assert review["reviewer_identity"] == "recorded_locally"
    assert len(review["responses_sha256"]) == 64
    questions = [
        json.loads(line)
        for line in (tmp_path / "evaluation/development_questions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(questions) == 32
    assert all(row["arabic_review"] == "approved" for row in questions)


@pytest.mark.parametrize("changed", ["text", "customer", "period"])
def test_changed_joint_question_content_cannot_inherit_approval(sources, changed):
    from scripts.generate_synthetic_data import human_review_status

    mechanics, templates = sources
    assert all(row["arabic_review"] == "pending" for row in development_questions())
    signatures = templates["human_review"]["approved_questions"]
    questions = development_questions(approved_signatures=signatures)
    row = next(row for row in questions if row["id"] == "DEV-006")
    assert row["arabic_review"] == "approved"
    if changed == "text":
        row["question_ar"] += "!"
    elif changed == "customer":
        row["spec"]["counterparty_ids"] = ["CUST-02"]
    else:
        row["spec"]["resolved_period"]["start"] = "2026-09-27"
    # Deliberately leave the cached question status approved: content wins.
    status = human_review_status(mechanics, templates, questions)
    assert "DEV-006" in status["pending_arabic_items"]
    assert status["arabic"] == "partial"


def test_changed_note_or_mechanics_invalidates_only_its_review_scope(sources):
    from scripts.generate_synthetic_data import human_review_status

    mechanics, templates = sources
    questions = development_questions(
        approved_signatures=templates["human_review"]["approved_questions"]
    )
    original = human_review_status(mechanics, templates, questions)
    assert original["plausibility"] == "approved"
    updated = copy.deepcopy(templates)
    updated["notes"]["CREDIT_SALE"][0] += "!"
    status = human_review_status(mechanics, updated, questions)
    assert set(status["pending_arabic_items"]) == {"NOTE-01", "NOTE-02", "NOTE-03"}
    assert status["plausibility"] == "approved"
    mechanics["credit_term_days"] += 1
    assert human_review_status(mechanics, templates, questions)["plausibility"] == (
        "pending"
    )


def test_declared_approval_without_content_evidence_is_not_approval(sources):
    from scripts.generate_synthetic_data import human_review_status

    mechanics, templates = sources
    templates.pop("human_review", None)
    templates["human_reviews"] = {"arabic": "approved", "plausibility": "approved"}
    status = human_review_status(mechanics, templates, development_questions())
    assert status["arabic"] == status["plausibility"] == "pending"
    assert len(status["pending_arabic_items"]) == 48
