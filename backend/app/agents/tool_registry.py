"""Allowlisted validated read-only dispatch, independent of any LLM (§8.1)."""

import sqlite3
from datetime import date

from pydantic import BaseModel, ValidationError

from app.agents.verification import verify_tool_output
from app.schemas.forecast import Amount
from app.schemas.queries import DateRangeView
from app.schemas.tools import (
    DebtsArguments,
    ErrorDetail,
    Figure,
    ForecastArguments,
    MarginArguments,
    ReconcileArguments,
    SalesArguments,
    ToolEnvelope,
)
from app.services.business_clock import DateRange
from app.services.errors import FinancialRuleError
from app.services.financial_queries import QuerySnapshot, sources
from app.services.margin import margin_metrics
from app.services.tool_evidence import debt_metrics, forecast_figures, upcoming_figures
from app.tools import forecast, get_debts, get_margin, get_sales, reconcile

TOOLS = {
    "get_sales": (SalesArguments, get_sales.run),
    "get_debts": (DebtsArguments, get_debts.run),
    "get_margin": (MarginArguments, get_margin.run),
    "reconcile": (ReconcileArguments, reconcile.run),
    "forecast": (ForecastArguments, forecast.run),
}


def _metadata(value, path=""):
    figures, dates = [], {}
    if isinstance(value, Amount):
        figures.append(Figure(**value.model_dump(), key=path))
    elif isinstance(value, (BaseModel, dict)):
        entries = (
            ((key, getattr(value, key)) for key in type(value).model_fields)
            if isinstance(value, BaseModel)
            else value.items()
        )
        for key, item in entries:
            found, resolved = _metadata(item, f"{path}.{key}" if path else key)
            figures.extend(found)
            dates.update(resolved)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found, resolved = _metadata(item, f"{path}.{index}")
            figures.extend(found)
            dates.update(resolved)
    elif type(value) is date:
        dates[path] = value
    return figures, dates


def _invoke(name, arguments, *, connection, clock, known_at=None, user_message=""):
    """Only trusted server context can establish explicit user-supplied dates."""
    try:
        if not isinstance(name, str) or name not in TOOLS:
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
        snapshot = QuerySnapshot(
            connection, clock=clock, known_at=None if name == "forecast" else known_at
        )
        result, resolved, party = service(
            snapshot, clock=clock, arguments=args, dates_from_user=explicit
        )
        data = result.model_dump(mode="json")
        figures, dates = _metadata(result)
        metrics = (
            margin_metrics(snapshot, resolved, result) if name == "get_margin" else ()
        )
        if name == "get_debts":
            metrics = debt_metrics(result)
            if result.upcoming is not None:
                figures.extend(upcoming_figures(result.upcoming))
        if name == "forecast":
            projected, metrics = forecast_figures(
                connection, clock=clock, report=result
            )
            figures.extend(projected)
        assumptions = tuple(getattr(result, "assumption_keys", ()))
        if name == "get_debts" and result.upcoming is not None:
            assumptions = ("collections_expected_not_guaranteed",)
        if name == "get_margin":
            assumptions = (
                "margin_excludes_unrecorded_costs",
                "unexplained_difference_excluded",
            )
        resolved = resolved or DateRange(snapshot.day, snapshot.day)
        dates.update({"start": resolved.start, "end": resolved.end})
        envelope = ToolEnvelope(
            ok=True,
            result=data,
            figures=tuple(figures),
            metrics=metrics,
            dates=dates,
            evidence_source_ids=sources(*(f.source_ids for f in (*figures, *metrics))),
            resolved_range=DateRangeView(start=resolved.start, end=resolved.end),
            resolved_counterparty=party,
            assumptions=assumptions,
            warnings=tuple(
                sorted(
                    {f"missing_{f.label_key}" for f in figures if f.kind == "missing"}
                )
            ),
        )
        return verify_tool_output(envelope, snapshot=snapshot, tool_name=name)
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


def invoke(name, arguments, *, connection, clock, known_at=None, user_message=""):
    """Hold one consistent SQLite read snapshot through service and provenance."""
    try:
        connection.execute("SAVEPOINT read_only_tool")
        try:
            return _invoke(
                name,
                arguments,
                connection=connection,
                clock=clock,
                known_at=known_at,
                user_message=user_message,
            )
        finally:
            connection.execute("RELEASE SAVEPOINT read_only_tool")
    except sqlite3.Error:
        return ToolEnvelope(
            ok=False,
            result=None,
            error=ErrorDetail(code="INTERNAL", message_key="error_internal"),
            clarification_key="clarify_internal",
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
