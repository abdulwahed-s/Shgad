"""§8.2: source existence, units, arithmetic and immutable verified handoff."""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.agents.tool_registry import invoke
from app.agents.verification import require_verified, verify_tool_output
from app.schemas.forecast import Amount
from app.services.business_clock import BusinessClock
from app.services.errors import FinancialRuleError
from app.services.financial_queries import QuerySnapshot

CLOCK = BusinessClock(date(2026, 9, 28))
KNOWN = datetime.fromisoformat("2026-09-28T23:59:59+03:00")


def test_real_tools_are_verified_and_wire_data_cannot_claim_server_trust(tool_history):
    from app.schemas.tools import ToolEnvelope

    for name, args in [
        ("get_sales", {"period": "today"}),
        ("get_debts", {}),
        ("get_margin", {"period": "today"}),
        ("reconcile", {"period": "today"}),
        ("forecast", {"scenario": "all"}),
    ]:
        result = invoke(
            name, args, connection=tool_history, clock=CLOCK, known_at=KNOWN
        )
        assert result.ok, result.error
        require_verified(result)
        with pytest.raises(FinancialRuleError):
            require_verified(ToolEnvelope.model_validate_json(result.model_dump_json()))


def test_tampering_after_verification_is_rejected(tool_history):
    result = invoke(
        "get_sales",
        {"period": "today"},
        connection=tool_history,
        clock=CLOCK,
        known_at=KNOWN,
    )
    require_verified(result)
    result.result["cash_sales"]["amount_iqd"] = 999999
    with pytest.raises(FinancialRuleError):
        require_verified(result)


def test_unknown_evidence_and_changed_consistent_subtotals_fail_verification(
    tool_history,
):
    result = invoke(
        "get_sales",
        {"period": "today"},
        connection=tool_history,
        clock=CLOCK,
        known_at=KNOWN,
    )
    snapshot = QuerySnapshot(tool_history, clock=CLOCK, known_at=KNOWN)
    bad_figure = result.figures[0].model_copy(update={"source_ids": ("INVENTED",)})
    bad = result.model_copy(update={"figures": (bad_figure, *result.figures[1:])})
    with pytest.raises(FinancialRuleError):
        verify_tool_output(bad, snapshot=snapshot, tool_name="get_sales")
    # Even coordinated result/metadata edits cannot change a source-derived sum.
    data = result.model_dump()
    for key in ("cash_sales", "total_sales", "selected_sales"):
        data["result"][key]["amount_iqd"] += 1
    for figure in data["figures"]:
        if figure["key"] in ("cash_sales", "total_sales", "selected_sales"):
            figure["amount_iqd"] += 1
    changed = type(result).model_validate(data)
    with pytest.raises(FinancialRuleError):
        verify_tool_output(changed, snapshot=snapshot, tool_name="get_sales")


@pytest.mark.parametrize(
    "value,kind",
    [(0, "missing"), (None, "verified"), (1.5, "calculated"), (True, "verified")],
)
def test_amount_unknown_and_integer_contract(value, kind):
    with pytest.raises(ValidationError):
        Amount(
            amount_iqd=value,
            kind=kind,
            label_key="probe",
            source_ids=(),
            formula="test",
        )
