"""Allowlisted validated read-only dispatch, independent of any LLM (§8.1)."""

import sqlite3
import sys
from contextlib import contextmanager
from datetime import date
from time import monotonic

from pydantic import BaseModel, ValidationError

from app.agents.verification import verify_tool_output
from app.schemas.forecast import Amount
from app.schemas.queries import DateRangeView, ImmediateDebtsResult
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
from app.services.financial_queries import (
    QuerySnapshot,
    historical_range,
    immediate_payment_capacity,
    sources,
)
from app.services.known_zero import query_evidence
from app.services.margin import margin_metrics
from app.services.period_phrases import resolve_period
from app.services.tool_evidence import debt_metrics, forecast_figures, upcoming_figures
from app.services.weekly_tool_views import movement_result, weekly_tool_result
from app.tools import forecast, get_debts, get_margin, get_sales, reconcile

TOOLS = {
    "get_sales": (SalesArguments, get_sales.run),
    "get_debts": (DebtsArguments, get_debts.run),
    "get_margin": (MarginArguments, get_margin.run),
    "reconcile": (ReconcileArguments, reconcile.run),
    "forecast": (ForecastArguments, forecast.run),
}
TOOL_TIMEOUT_SECONDS = 10
PLANS = {
    None,
    "weekly_summary",
    "cash_sufficiency",
    "period_movements",
    "interpretation",
    "payment_now",
}


class _ToolTimeout(Exception):
    pass


@contextmanager
def _python_deadline(deadline):
    """Interrupt Python loops on this synchronous SQLite thread, then restore it.

    SQL uses a progress callback too. Bounded C operations are checked on return.
    The loop never awaits while the thread-local trace hook is installed.
    """
    previous = sys.gettrace()
    lines = 0

    def trace(frame, event, arg):
        nonlocal lines
        if event == "line":
            lines += 1
            if lines % 1024 == 0 and monotonic() >= deadline:
                sys.settrace(previous)
                raise _ToolTimeout
        return trace

    try:
        sys.settrace(trace)
        yield
    finally:
        sys.settrace(previous)


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


def _invoke(
    name,
    arguments,
    *,
    connection,
    clock,
    known_at=None,
    user_message="",
    server_period_set=False,
    server_plan=None,
    server_month=None,
    server_range=None,
):
    """Explicit dates need user-text proof, a matched server month, or a D58
    server range that BusinessClock resolved from a verified interpretation."""
    try:
        if server_plan not in PLANS:
            raise FinancialRuleError("VALIDATION_ERROR")
        weekly_plan = server_plan == "weekly_summary"
        movements_plan = server_plan == "period_movements"
        if not isinstance(name, str) or name not in TOOLS:
            raise FinancialRuleError("VALIDATION_ERROR")
        model, service = TOOLS[name]
        args = model.model_validate(arguments)
        trusted_range = None
        if server_month is not None:
            phrase = resolve_period(user_message, weekday=clock.today.weekday())
            if (
                name not in {"get_sales", "get_margin", "reconcile"}
                or phrase.status != "resolved"
                or phrase.month != server_month
            ):
                raise FinancialRuleError("VALIDATION_ERROR")
            trusted_range = clock.named_month(server_month)
        if server_range is not None:
            if server_month is not None or name not in {
                "get_sales",
                "get_margin",
                "reconcile",
            }:
                raise FinancialRuleError("VALIDATION_ERROR")
            trusted_range = server_range
        if trusted_range is not None:
            if args.period != "explicit" or (args.start_date, args.end_date) != (
                trusted_range.start,
                trusted_range.end,
            ):
                raise FinancialRuleError("VALIDATION_ERROR")
        explicit = any(
            getattr(args, key, None) == "explicit"
            for key in ("period", "due_period", "until")
        )
        if (
            explicit
            and trusted_range is None
            and (
                args.start_date is None
                or args.end_date is None
                or not all(
                    day.isoformat() in user_message
                    for day in (args.start_date, args.end_date)
                )
            )
        ):
            raise FinancialRuleError(
                "VALIDATION_ERROR", details={"reason": "DATES_NOT_USER_SUPPLIED"}
            )
        snapshot = QuerySnapshot(
            connection, clock=clock, known_at=None if name == "forecast" else known_at
        )
        if weekly_plan and name in {"get_sales", "get_margin"}:
            if trusted_range is not None:
                # weekly_tool_result rejects any range that is not that week.
                resolved = historical_range(
                    clock,
                    "explicit",
                    start_date=trusted_range.start,
                    end_date=trusted_range.end,
                    trusted_range=trusted_range,
                )
            elif args.period in {"this_week", "last_week"}:
                resolved = historical_range(clock, args.period)
            else:
                raise FinancialRuleError("VALIDATION_ERROR")
            result, party = weekly_tool_result(snapshot, resolved, name), None
        elif movements_plan:
            if name != "get_sales" or trusted_range is None:
                raise FinancialRuleError("VALIDATION_ERROR")
            resolved = historical_range(
                clock,
                "explicit",
                start_date=trusted_range.start,
                end_date=trusted_range.end,
                trusted_range=trusted_range,
            )
            result, party = movement_result(snapshot, resolved), None
        else:
            result, resolved, party = service(
                snapshot,
                clock=clock,
                arguments=args,
                dates_from_user=explicit and trusted_range is None,
                **({"trusted_range": trusted_range} if trusted_range else {}),
                **(
                    {"with_collections": True}
                    if name == "reconcile" and server_plan == "interpretation"
                    else {}
                ),
            )
        if server_plan == "payment_now":
            if (
                name != "get_debts"
                or party is None
                or args.direction != "payable"
                or args.due_period is not None
                or args.overdue_only
            ):
                raise FinancialRuleError("VALIDATION_ERROR")
            result = ImmediateDebtsResult(
                **result.model_dump(),
                payment_now=immediate_payment_capacity(snapshot, party.id),
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
        figures = [
            f.model_copy(
                update={
                    "query_evidence": query_evidence(
                        f,
                        snapshot=snapshot,
                        tool_name=name,
                        resolved=resolved,
                        result=data,
                    )
                }
            )
            for f in figures
        ]
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
                    | ({"period_set_by_server"} if server_period_set else set())
                    | ({f"tool_plan_{server_plan}"} if server_plan else set())
                )
            ),
        )
        return verify_tool_output(
            envelope,
            snapshot=snapshot,
            tool_name=name,
            weekly_plan=weekly_plan,
            movements_plan=movements_plan,
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


def invoke(
    name,
    arguments,
    *,
    connection,
    clock,
    known_at=None,
    user_message="",
    server_period_set=False,
    server_plan=None,
    server_month=None,
    server_range=None,
):
    """Hold one consistent SQLite read snapshot through service and provenance."""
    deadline = monotonic() + TOOL_TIMEOUT_SECONDS
    query_only = connection.execute("PRAGMA query_only").fetchone()[0]
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.set_progress_handler(lambda: int(monotonic() >= deadline), 1000)
        connection.execute("SAVEPOINT read_only_tool")
        try:
            with _python_deadline(deadline):
                result = _invoke(
                    name,
                    arguments,
                    connection=connection,
                    clock=clock,
                    known_at=known_at,
                    user_message=user_message,
                    server_period_set=server_period_set,
                    server_plan=server_plan,
                    server_month=server_month,
                    server_range=server_range,
                )
            if monotonic() >= deadline:
                raise sqlite3.OperationalError("TOOL_TIMEOUT")
            return result
        finally:
            connection.set_progress_handler(None, 0)
            connection.execute("RELEASE SAVEPOINT read_only_tool")
    except (sqlite3.Error, _ToolTimeout):
        return ToolEnvelope(
            ok=False,
            result=None,
            error=ErrorDetail(code="INTERNAL", message_key="error_internal"),
            clarification_key="clarify_internal",
        )
    finally:
        connection.set_progress_handler(None, 0)
        connection.execute(f"PRAGMA query_only={int(query_only)}")


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
