"""Allowlisted validated read-only dispatch, independent of any LLM (§8.1)."""

import re

from pydantic import ValidationError

from app.schemas.queries import DateRangeView
from app.schemas.tools import (
    DebtsArguments,
    ErrorDetail,
    Figure,
    SalesArguments,
    ToolEnvelope,
)
from app.services.business_clock import DateRange
from app.services.errors import FinancialRuleError
from app.services.financial_queries import QuerySnapshot, sources
from app.tools import get_debts, get_sales

TOOLS = {
    "get_sales": (SalesArguments, get_sales.run),
    "get_debts": (DebtsArguments, get_debts.run),
}


def _metadata(value, path=""):
    figures, dates = [], {}
    if isinstance(value, dict):
        if "amount_iqd" in value:
            figures.append(Figure(**value, key=path))
        else:
            for key, item in value.items():
                found, resolved = _metadata(item, f"{path}.{key}" if path else key)
                figures.extend(found)
                dates.update(resolved)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found, resolved = _metadata(item, f"{path}.{index}")
            figures.extend(found)
            dates.update(resolved)
    elif isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        dates[path] = value
    return figures, dates


def invoke(name, arguments, *, connection, clock, known_at=None, user_message=""):
    """Only trusted server context can establish explicit user-supplied dates."""
    try:
        if name not in TOOLS:
            raise FinancialRuleError("VALIDATION_ERROR")
        model, service = TOOLS[name]
        args = model.model_validate(arguments)
        explicit = any(
            getattr(args, key, None) == "explicit"
            for key in ("period", "due_period", "until")
        )
        if explicit and (
            args.start_date is None
            or args.end_date is None
            or not all(
                day.isoformat() in user_message
                for day in (args.start_date, args.end_date)
            )
        ):
            raise FinancialRuleError(
                "VALIDATION_ERROR", details={"reason": "DATES_NOT_USER_SUPPLIED"}
            )
        snapshot = QuerySnapshot(connection, clock=clock, known_at=known_at)
        result, resolved, party = service(
            snapshot, clock=clock, arguments=args, dates_from_user=explicit
        )
        data = result.model_dump(mode="json")
        figures, dates = _metadata(data)
        resolved = resolved or DateRange(snapshot.day, snapshot.day)
        dates.update({"start": resolved.start, "end": resolved.end})
        return ToolEnvelope(
            ok=True,
            result=data,
            figures=tuple(figures),
            dates=dates,
            evidence_source_ids=sources(*(f.source_ids for f in figures)),
            resolved_range=DateRangeView(start=resolved.start, end=resolved.end),
            resolved_counterparty=party,
        )
    except (ValidationError, FinancialRuleError) as exc:
        code = exc.code if isinstance(exc, FinancialRuleError) else "VALIDATION_ERROR"
        return ToolEnvelope(
            ok=False,
            result=None,
            error=ErrorDetail(
                code=code,
                message_key=f"error_{code.lower()}",
                details=exc.details if isinstance(exc, FinancialRuleError) else {},
            ),
            clarification_key=f"clarify_{code.lower()}",
        )


def definitions():
    return tuple(
        {
            "type": "function",
            "function": {
                "name": name,
                "description": f"Read-only deterministic {name}",
                "parameters": model.model_json_schema(),
            },
        }
        for name, (model, _) in TOOLS.items()
    )
