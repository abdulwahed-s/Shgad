"""A duplicate export needs its origin ledger; expected anomaly labels stay fixed."""

from pathlib import Path

from scripts.evaluation_reconciliation import evaluate


def test_duplicate_export_has_parent_obligation_context_before_precision_scoring():
    root = Path(__file__).resolve().parents[3]
    result = evaluate(root / "data")
    assert result["metrics"]["suspected_duplicate"]["tp"] == 1
    assert result["metrics"]["unmatched"]["tp"] == 1
    # HAPPY-R exists in small_happy_path; the duplicate export only repeats its
    # collection and adds a second distinct partial collection. Neither is an
    # unmatched payment when the fixture's documented origin is present.
    assert result["metrics"]["combined"]["fp"] == 0
    assert result["metrics"]["combined"]["fn"] == 0
    assert result["metrics"]["combined"]["precision"]["rate"] == 1.0
