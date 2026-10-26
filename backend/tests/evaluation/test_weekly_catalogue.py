"""D55 narrowly authorized catalogue extension; no scorer or original rescore."""

from datetime import date

import pytest
from scripts.evaluation_metrics import compare_claim
from scripts.evaluation_truth import claim_catalogue
from scripts.make_ground_truth import TruthLedger


@pytest.mark.parametrize(
    "key,event",
    [
        ("supplier_payments", "SUPPLIER_PAYMENT"),
        ("capital_injections", "CAPITAL_INJECTION"),
    ],
)
def test_missing_weekly_movement_catalogue_retains_exact_provenance(key, event):
    ledger = TruthLedger(
        [
            dict(
                transaction_id="observed",
                source_id="observed",
                type=event,
                amount_iqd=1200,
                business_date="2026-09-28",
                occurred_at="2026-09-28T12:00:00+03:00",
                recorded_at="2026-09-28T12:00:00+03:00",
                category_id=None,
                quantity=None,
                obligation_id=None,
                counterparty_id=None,
                due_date=None,
            )
        ]
    )
    catalogue = claim_catalogue(
        ledger, date(2026, 9, 28), date(2026, 9, 26), date(2026, 9, 28)
    )
    expected = catalogue["weekly." + key]
    assert expected == dict(value=1200, unit="IQD", label=key, source_ids=["observed"])
    assert compare_claim(
        expected, {**expected, "formula": "sum active recorded events"}
    ) == (True, True)
