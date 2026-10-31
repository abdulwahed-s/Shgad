"""D59 / FINANCIAL_RULES §7: immediate supplier payment uses all open invoices."""

from datetime import date, datetime

from app.agents.planner import Stop, plan
from app.agents.renderer import has_evidence
from app.agents.tool_registry import invoke
from app.schemas.interpretation import Interpretation
from app.services.business_clock import BusinessClock

CLOCK = BusinessClock(date(2026, 9, 28))
KNOWN = datetime.fromisoformat("2026-09-28T23:59:59+03:00")


def immediate(db):
    return invoke(
        "get_debts",
        {"direction": "payable", "counterparty_query": "Synthetic supplier"},
        connection=db,
        clock=CLOCK,
        known_at=KNOWN,
        server_plan="payment_now",
    )


def test_now_includes_overdue_and_later_invoices_but_no_receivables(
    j1_shop, debt_factory
):
    debt_factory("PAST", 20000, "2026-09-27", kind="payable")
    debt_factory("LATER", 30000, "2026-12-01", kind="payable")
    j1_shop.commit()
    result = immediate(j1_shop)
    assert result.ok
    view = result.result["payment_now"]
    assert view["cash_on_hand"]["amount_iqd"] == 420000
    assert view["supplier_due"]["amount_iqd"] == 700000
    assert view["position_confirmed"]["amount_iqd"] == -280000
    assert {"J1-P", "PAST", "LATER"} <= set(view["supplier_due"]["source_ids"])
    assert "J1-R" not in view["position_confirmed"]["source_ids"]


def test_unnamed_now_with_multiple_open_suppliers_clarifies(j1_shop, debt_factory):
    j1_shop.execute(
        "INSERT INTO counterparties VALUES ('SUP-02', 'Other supplier', 'supplier')"
    )
    debt_factory("OTHER", 1000, "2026-12-01", kind="payable", party="SUP-02")
    j1_shop.commit()
    result = plan(
        Interpretation(behavior="answer", intent="supplier_sufficiency"),
        connection=j1_shop,
        clock=CLOCK,
        known_at=KNOWN,
    )
    assert isinstance(result, Stop)
    assert result.reason == "AMBIGUOUS_COUNTERPARTY"
    assert {p.id for p in result.options} == {"SUP-01", "SUP-02"}


def test_no_open_invoices_has_a_proven_zero_and_sourced_surplus(ledger, insert_event):
    insert_event(type="DAILY_CASH_COUNT", amount_iqd=420000)
    ledger.commit()
    result = immediate(ledger)
    assert result.ok
    due = next(f for f in result.figures if f.key == "payment_now.supplier_due")
    assert due.amount_iqd == 0 and has_evidence(due)
    assert result.result["payment_now"]["position_confirmed"]["amount_iqd"] == 420000
