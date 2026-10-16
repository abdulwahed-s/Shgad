"""Revised T22/T28/T34 and cutoff-aware effects: FINANCIAL_RULES §2–5/§11."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas import ledger as models
from app.services import ledger_rules as rules

DAY = date(2026, 9, 28)


@pytest.fixture
def close_rows(transaction_factory):
    make = transaction_factory
    return [
        make(
            "PREV",
            type="DAILY_CASH_COUNT",
            amount_iqd=300_000,
            occurred_at="2026-09-27T21:00:00+03:00",
        ),
        make("SALE", amount_iqd=120_000, category_id="CAT-01", quantity=20),
        make(
            "COLLECT",
            type="CREDIT_COLLECTION",
            amount_iqd=30_000,
            counterparty_id="CUST-01",
            obligation_id="OB-1",
        ),
        make("EXPENSE", type="OPERATING_EXPENSE", amount_iqd=20_000),
        make("DRAW", type="OWNER_DRAWING", amount_iqd=10_000),
        make(
            "CLOSE",
            type="DAILY_CASH_COUNT",
            amount_iqd=445_000,
            occurred_at="2026-09-28T21:00:00+03:00",
        ),
    ]


def test_t22_expected_close_difference_and_recorded_sales_are_separate(close_rows):
    close = rules.daily_close(close_rows, business_date=DAY)
    assert close.expected_close_iqd == 420_000
    assert close.unexplained_difference_iqd == 25_000
    assert close.kind == "flagged"
    assert close.recorded_cash_sales_iqd == 120_000
    assert set(close.source_ids) == {row.source_id for row in close_rows}
    assert not hasattr(close, "cause")
    assert not hasattr(rules, "derived_cash_sales")


def test_t22_negative_difference_stays_signed(close_rows, transaction_factory):
    close_rows[-1] = transaction_factory(
        "CLOSE",
        type="DAILY_CASH_COUNT",
        amount_iqd=395_000,
        occurred_at="2026-09-28T21:00:00+03:00",
    )
    result = rules.daily_close(close_rows, business_date=DAY)
    assert result.expected_close_iqd == 420_000
    assert result.unexplained_difference_iqd == -25_000
    assert result.recorded_cash_sales_iqd == 120_000


@pytest.mark.parametrize("missing", ["PREV", "CLOSE", "both", "nonconsecutive"])
def test_t22_missing_counts_are_unavailable(close_rows, missing):
    if missing == "nonconsecutive":
        close_rows[0] = models.Transaction.model_validate(
            close_rows[0].model_dump()
            | {"occurred_at": "2026-09-26T21:00:00+03:00", "business_date": None}
        )
    else:
        close_rows = [
            r
            for r in close_rows
            if r.source_id != missing
            and not (missing == "both" and r.type == "DAILY_CASH_COUNT")
        ]
    result = rules.daily_close(close_rows, business_date=DAY)
    assert result.kind == "missing"
    assert result.unexplained_difference_iqd is None
    assert result.recorded_cash_sales_iqd == 120_000
    if missing != "CLOSE":
        assert result.expected_close_iqd is None


def test_t22_range_difference_requires_complete_consecutive_coverage(close_rows):
    assert (
        rules.cash_difference_in_range(close_rows, start=DAY, end=DAY).amount_iqd
        == 25_000
    )
    result = rules.cash_difference_in_range(
        close_rows, start=date(2026, 9, 27), end=DAY
    )
    assert result.amount_iqd is None
    assert result.kind == "missing"


def test_capital_is_cash_only_and_does_not_change_margin(
    transaction_factory, opening_balance
):
    capital = transaction_factory("CAP", type="CAPITAL_INJECTION", amount_iqd=25_000)
    sale = transaction_factory(
        "SALE", amount_iqd=120_000, category_id="CAT-01", quantity=20
    )
    effect = rules.event_effect(capital)
    assert effect.cash_delta_iqd == 25_000
    assert effect.collections_iqd == 0
    assert effect.revenue_delta_iqd == effect.receivable_created_iqd == 0
    assert (
        effect.payable_created_iqd
        == effect.operating_expenses_iqd
        == effect.owner_drawings_iqd
        == 0
    )
    assert effect.cash_count_iqd is None
    assert (
        rules.cash_on_hand(
            [sale, capital], as_of=DAY, opening_balance=opening_balance
        ).amount_iqd
        == 345_000
    )
    assert rules.recorded_cash_sales([sale, capital], as_of=DAY) == 120_000
    assert (
        sum(rules.event_effect(r).revenue_delta_iqd for r in [sale, capital])
        - sale.quantity * 1_000
        == 100_000
    )


@pytest.mark.parametrize("bad", [True, 1.5, "25000", 0, -1, 2**63])
def test_capital_preserves_strict_iqd(transaction_factory, bad):
    with pytest.raises(ValidationError):
        transaction_factory(type="CAPITAL_INJECTION", amount_iqd=bad)


def test_t28_capital_resolution_is_recomputed_once(close_rows, transaction_factory):
    close_rows.append(
        transaction_factory(
            "REVIEW",
            type="CAPITAL_INJECTION",
            amount_iqd=25_000,
            source_system="synthetic_entry",
            source="daily_close_review",
            client_entry_id="CLIENT-1",
            occurred_at="2026-09-28T21:00:00+03:00",
            recorded_at="2026-09-28T21:01:00+03:00",
        )
    )
    result = rules.daily_close(close_rows, business_date=DAY)
    assert result.expected_close_iqd == 445_000
    assert result.unexplained_difference_iqd == 0
    assert result.recorded_cash_sales_iqd == 120_000
    assert rules.cash_on_hand(close_rows, as_of=DAY).amount_iqd == 445_000


def test_voided_sale_and_count_are_excluded_at_their_cutoff(close_rows):
    audit = models.EntryVoid(
        void_id="VOID-1",
        transaction_id="SALE",
        source_id="SALE",
        client_entry_id="CLIENT-VOID",
        reason="Synthetic correction",
        voided_at="2026-09-28T22:00:00+03:00",
    )
    before = rules.daily_close(
        close_rows,
        business_date=DAY,
        voids=[audit],
        known_at="2026-09-28T21:30:00+03:00",
    )
    after = rules.daily_close(close_rows, business_date=DAY, voids=[audit])
    assert before.unexplained_difference_iqd == 25_000
    assert after.recorded_cash_sales_iqd == 0
    assert after.unexplained_difference_iqd == 145_000
    assert (
        rules.transaction_status(
            close_rows[1], voids=[audit], known_at="2026-09-28T21:30:00+03:00"
        )
        == "valid"
    )
    assert (
        rules.transaction_status(
            close_rows[1], voids=[audit], known_at="2026-09-28T23:00:00+03:00"
        )
        == "voided"
    )
    count_void = models.EntryVoid.model_validate(
        audit.model_dump()
        | {
            "transaction_id": "CLOSE",
            "source_id": "CLOSE",
            "void_id": "VOID-2",
            "client_entry_id": "CLIENT-2",
        }
    )
    assert (
        rules.daily_close(close_rows, business_date=DAY, voids=[count_void]).kind
        == "missing"
    )
    assert (
        rules.cash_on_hand(close_rows, as_of=DAY, voids=[count_void]).amount_iqd
        == 420_000
    )


def test_entries_recorded_after_knowledge_cutoff_are_unavailable(
    transaction_factory, opening_balance
):
    late = transaction_factory(recorded_at="2026-09-29T10:00:00+03:00")
    assert (
        rules.cash_on_hand(
            [late], as_of=DAY, opening_balance=opening_balance
        ).amount_iqd
        == 200_000
    )
    assert (
        rules.cash_on_hand(
            [late],
            as_of=DAY,
            opening_balance=opening_balance,
            known_at="2026-09-29T11:00:00+03:00",
        ).amount_iqd
        == 300_000
    )


@pytest.mark.parametrize(
    "resolution",
    [
        "cash_sale_unitemized",
        "capital_injection",
        "expense_unrecorded",
        "owner_drawing_unrecorded",
    ],
)
@pytest.mark.parametrize("bad", [None, True, 0, -1, 1.5, "25000"])
def test_review_request_requires_positive_strict_iqd(resolution, bad):
    with pytest.raises(ValidationError):
        models.DifferenceReviewRequest(
            client_entry_id="CLIENT", resolution=resolution, amount_iqd=bad
        )


def test_review_has_no_default_choice_and_leave_requires_null():
    with pytest.raises(ValidationError):
        models.DifferenceReviewRequest(client_entry_id="CLIENT", amount_iqd=25_000)
    for bad in (0, 25_000):
        with pytest.raises(ValidationError):
            models.DifferenceReviewRequest(
                client_entry_id="CLIENT", resolution="leave_unexplained", amount_iqd=bad
            )
    request = models.DifferenceReviewRequest(
        client_entry_id="CLIENT", resolution="leave_unexplained", amount_iqd=None
    )
    assert request.amount_iqd is None


def test_collections_primitive_separates_collections_from_other_cash_inflows(
    transaction_factory,
):
    collection = transaction_factory(
        type="CREDIT_COLLECTION",
        amount_iqd=30_000,
        counterparty_id="CUST-01",
        obligation_id="OB-1",
    )
    assert rules.event_effect(collection).collections_iqd == 30_000
    assert rules.event_effect(transaction_factory()).collections_iqd == 0


def test_t22_all_cash_terms_and_non_cash_events(close_rows, transaction_factory):
    close_rows.extend(
        [
            transaction_factory("CAP", type="CAPITAL_INJECTION", amount_iqd=15_000),
            transaction_factory(
                "SUP-PAY",
                type="SUPPLIER_PAYMENT",
                amount_iqd=20_000,
                counterparty_id="SUP-01",
                obligation_id="OB-SUP",
            ),
            transaction_factory(
                "CREDIT",
                type="CREDIT_SALE",
                amount_iqd=50_000,
                counterparty_id="CUST-01",
                obligation_id="OB-2",
            ),
            transaction_factory(
                "INVOICE",
                type="SUPPLIER_INVOICE",
                amount_iqd=60_000,
                counterparty_id="SUP-01",
                obligation_id="OB-SUP",
            ),
        ]
    )
    result = rules.daily_close(close_rows, business_date=DAY)
    assert result.expected_close_iqd == 415_000
    assert result.unexplained_difference_iqd == 30_000
    assert result.recorded_cash_sales_iqd == 120_000
