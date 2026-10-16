"""Ledger semantics: roadmap §17; FINANCIAL_RULES §2–5 are binding."""

from datetime import date, datetime

import pytest

from app.schemas.ledger import Category
from app.services.errors import FinancialRuleError
from app.services.ledger_rules import (
    cash_on_hand,
    event_effect,
    outstanding_balance,
)

AS_OF = date(2026, 9, 28)


def test_t01_cash_sale_increases_cash_and_revenue_once(
    transaction_factory, opening_balance
):
    sale = transaction_factory(amount_iqd=100_000)
    effect = event_effect(sale)
    assert effect.cash_delta_iqd == 100_000
    assert effect.revenue_delta_iqd == 100_000
    assert effect.receivable_created_iqd == 0
    position = cash_on_hand([sale], as_of=AS_OF, opening_balance=opening_balance)
    assert position.amount_iqd == 300_000
    assert position.source_ids == ("OPEN-001", "TX-001")


def test_t02_credit_sale_creates_debt_and_revenue_without_cash(
    transaction_factory, opening_balance
):
    sale = transaction_factory(
        type="CREDIT_SALE",
        amount_iqd=70_000,
        counterparty_id="CUST-01",
        obligation_id="OB-001",
        due_date=date(2026, 9, 30),
    )
    effect = event_effect(sale)
    assert effect.cash_delta_iqd == 0
    assert effect.revenue_delta_iqd == 70_000
    assert effect.receivable_created_iqd == 70_000
    assert (
        cash_on_hand([sale], as_of=AS_OF, opening_balance=opening_balance).amount_iqd
        == 200_000
    )


def test_t03_partial_collection_is_cash_not_a_second_sale(
    transaction_factory, opening_balance
):
    collection = transaction_factory(
        type="CREDIT_COLLECTION",
        amount_iqd=30_000,
        counterparty_id="CUST-01",
        obligation_id="OB-001",
    )
    effect = event_effect(collection)
    assert effect.cash_delta_iqd == 30_000
    assert effect.revenue_delta_iqd == 0
    assert effect.receivable_created_iqd == 0
    assert outstanding_balance(70_000, [30_000]) == 40_000
    assert (
        cash_on_hand(
            [collection], as_of=AS_OF, opening_balance=opening_balance
        ).amount_iqd
        == 230_000
    )


@pytest.mark.parametrize("with_sale", [False, True])
def test_t06_missing_cash_anchor_is_a_typed_failure(transaction_factory, with_sale):
    rows = [transaction_factory()] if with_sale else []
    with pytest.raises(FinancialRuleError) as error:
        cash_on_hand(rows, as_of=AS_OF)
    assert error.value.code == "MISSING_OPENING_BALANCE"
    assert error.value.message_key == "error_missing_opening_balance"


def test_t06_explicit_zero_opening_is_known(transaction_factory, opening_balance):
    known_zero = opening_balance.model_copy(update={"amount_iqd": 0})
    assert cash_on_hand([], as_of=AS_OF, opening_balance=known_zero).amount_iqd == 0
    assert (
        cash_on_hand(
            [transaction_factory()], as_of=AS_OF, opening_balance=known_zero
        ).amount_iqd
        == 100_000
    )


def test_t06_future_opening_does_not_anchor_past_cash(opening_balance):
    future = opening_balance.model_copy(update={"business_date": date(2026, 10, 1)})
    with pytest.raises(FinancialRuleError, match="MISSING_OPENING_BALANCE"):
        cash_on_hand([], as_of=AS_OF, opening_balance=future)


def test_t17_supplier_invoice_is_payable_without_cash_out(transaction_factory):
    invoice = transaction_factory(
        type="SUPPLIER_INVOICE",
        amount_iqd=650_000,
        counterparty_id="SUP-01",
        obligation_id="OB-SUP",
        due_date=date(2026, 10, 1),
    )
    effect = event_effect(invoice)
    assert effect.payable_created_iqd == 650_000
    assert effect.cash_delta_iqd == 0
    assert effect.revenue_delta_iqd == 0
    assert effect.operating_expenses_iqd == 0


def test_supplier_payment_is_not_automatically_expense(transaction_factory):
    payment = transaction_factory(
        type="SUPPLIER_PAYMENT",
        amount_iqd=200_000,
        counterparty_id="SUP-01",
        obligation_id="OB-SUP",
    )
    effect = event_effect(payment)
    assert effect.cash_delta_iqd == -200_000
    assert effect.operating_expenses_iqd == 0
    assert outstanding_balance(650_000, [200_000]) == 450_000


def test_t21_owner_drawing_reduces_cash_without_expense_or_margin(
    transaction_factory, opening_balance
):
    category = Category(
        category_id="CAT-01", name="Synthetic goods", buy_price_iqd=1_000
    )
    sale = transaction_factory(category_id="CAT-01", quantity=20)
    drawing = transaction_factory("DRAW-001", type="OWNER_DRAWING", amount_iqd=25_000)
    sale_effect, drawing_effect = event_effect(sale), event_effect(drawing)
    assert drawing_effect.cash_delta_iqd == -25_000
    assert drawing_effect.owner_drawings_iqd == 25_000
    assert drawing_effect.operating_expenses_iqd == 0
    assert drawing_effect.revenue_delta_iqd == 0
    cogs = sale.quantity * category.buy_price_iqd
    assert sale_effect.revenue_delta_iqd - cogs == 80_000
    assert (
        sale_effect.revenue_delta_iqd + drawing_effect.revenue_delta_iqd - cogs
        == 80_000
    )
    assert (
        cash_on_hand(
            [sale, drawing], as_of=AS_OF, opening_balance=opening_balance
        ).amount_iqd
        == 275_000
    )


def test_t22_count_is_a_snapshot_and_later_flows_are_added(transaction_factory):
    previous = transaction_factory(
        "CNT-089",
        type="DAILY_CASH_COUNT",
        amount_iqd=380_000,
        occurred_at=datetime.fromisoformat("2026-09-27T21:00:00+03:00"),
    )
    latest = transaction_factory(
        "CNT-090",
        type="DAILY_CASH_COUNT",
        amount_iqd=420_000,
        occurred_at=datetime.fromisoformat("2026-09-28T21:00:00+03:00"),
    )
    before = transaction_factory("SALE-BEFORE", amount_iqd=50_000)
    same_time = transaction_factory("SALE-SAME", occurred_at=latest.occurred_at)
    after = transaction_factory(
        "SALE-AFTER",
        amount_iqd=10_000,
        occurred_at=datetime.fromisoformat("2026-09-28T21:01:00+03:00"),
    )
    future = transaction_factory(
        "FUTURE",
        occurred_at=datetime.fromisoformat("2026-09-29T00:00:00+03:00"),
    )
    effect = event_effect(latest)
    assert effect.cash_delta_iqd == effect.revenue_delta_iqd == 0
    assert effect.cash_count_iqd == 420_000
    result = cash_on_hand(
        [after, future, before, latest, previous, same_time], as_of=AS_OF
    )
    assert result.amount_iqd == 430_000
    assert result.source_ids == ("CNT-090", "SALE-AFTER")
    assert result.basis == "counted_and_recorded_since"
    assert result.counted_on == AS_OF


def test_cash_cutoff_is_baghdad_date_not_utc_date(transaction_factory):
    # 21:30 UTC on the 28th is already the 29th in Baghdad.
    count = transaction_factory("CNT", type="DAILY_CASH_COUNT", amount_iqd=500)
    late = transaction_factory(
        "LATE", occurred_at=datetime.fromisoformat("2026-09-28T21:30:00+00:00")
    )
    assert late.business_date == date(2026, 9, 29)
    assert cash_on_hand([count, late], as_of=AS_OF).amount_iqd == 500


def test_unlinked_flagged_collection_moves_cash_but_creates_no_debt(
    transaction_factory, opening_balance
):
    collection = transaction_factory(
        type="CREDIT_COLLECTION",
        counterparty_id="CUST-01",
        status="flagged",
        amount_iqd=30_000,
    )
    assert event_effect(collection).receivable_created_iqd == 0
    assert (
        cash_on_hand(
            [collection], as_of=AS_OF, opening_balance=opening_balance
        ).amount_iqd
        == 230_000
    )


def test_outstanding_does_not_net_overpayment():
    with pytest.raises(FinancialRuleError) as error:
        outstanding_balance(70_000, [30_000, 50_000])
    assert error.value.code == "VALIDATION_ERROR"
    assert error.value.details["reason"] == "OVERPAYMENT"
    assert outstanding_balance(70_000, [30_000, 40_000]) == 0


@pytest.mark.parametrize("bad", [True, 1.5, "100", -1])
def test_formula_boundaries_reject_non_integer_or_negative_money(bad):
    with pytest.raises(FinancialRuleError):
        outstanding_balance(70_000, [bad])


def test_operating_expense_moves_cash_and_only_recorded_expenses(
    transaction_factory, opening_balance
):
    expense = transaction_factory(type="OPERATING_EXPENSE", amount_iqd=20_000)
    effect = event_effect(expense)
    assert effect.cash_delta_iqd == -20_000
    assert effect.operating_expenses_iqd == 20_000
    assert effect.revenue_delta_iqd == effect.owner_drawings_iqd == 0
    result = cash_on_hand([expense], as_of=AS_OF, opening_balance=opening_balance)
    assert result.amount_iqd == 180_000


def test_duplicate_input_and_simultaneous_counts_require_review(transaction_factory):
    sale = transaction_factory()
    with pytest.raises(FinancialRuleError, match="VALIDATION_ERROR"):
        cash_on_hand([sale, sale], as_of=AS_OF)
    first = transaction_factory("CNT-1", type="DAILY_CASH_COUNT", amount_iqd=300_000)
    second = transaction_factory("CNT-2", type="DAILY_CASH_COUNT", amount_iqd=400_000)
    with pytest.raises(FinancialRuleError, match="VALIDATION_ERROR"):
        cash_on_hand([first, second], as_of=AS_OF)
