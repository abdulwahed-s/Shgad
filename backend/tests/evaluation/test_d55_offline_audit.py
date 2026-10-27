"""Public development reproduction, explicitly not recovered provider output."""

from scripts.audit_d55_dev import run_audit


def test_six_fake_provider_reproductions_account_for_thirteen_unsupported_claims():
    receipt = run_audit()
    assert receipt["kind"] == "re-graded replay, not a new measurement"
    assert receipt["original_claim_identities_recovered"] is False
    assert receipt["provider_requests"] == 0
    assert receipt["totals"]["classes"] == dict(a=12, b=1, c=0)
    assert receipt["totals"]["replay_claims_before"] == dict(
        numerator=38, denominator=51
    )
    assert receipt["totals"]["replay_claims_after"] == dict(
        numerator=51, denominator=51
    )
    assert all(row["retained_counts_match_reproduction"] for row in receipt["cases"])
