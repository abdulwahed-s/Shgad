"""§8.2: verify deterministic output before the private renderer handoff.

The private fingerprint binds the exact server-verified object. JSON from a
provider/client cannot mark itself verified; edits after verification invalidate it.
"""

import hashlib
from collections import Counter
from datetime import timedelta

from app.schemas.queries import DebtsResult, FlagsReport
from app.schemas.tools import Figure, Metric, ToolEnvelope
from app.services.business_clock import DateRange
from app.services.errors import FinancialRuleError
from app.services.financial_queries import payment_capacity, sale_totals, sources
from app.services.margin import margin_report
from app.services.weekly_tool_views import weekly_tool_result


def _reject():
    raise FinancialRuleError(
        "VALIDATION_ERROR", details={"reason": "UNVERIFIED_TOOL_OUTPUT"}
    )


def _fingerprint(envelope):
    return hashlib.sha256(envelope.model_dump_json().encode("utf-8")).hexdigest()


def require_verified(envelope):
    if (
        not isinstance(envelope, ToolEnvelope)
        or not envelope.ok
        or envelope._verified_fingerprint != _fingerprint(envelope)
    ):
        _reject()


def _lookup(data, key):
    try:
        for part in key.split("."):
            data = data[int(part)] if isinstance(data, list) else data[part]
        return data
    except (KeyError, ValueError, TypeError, IndexError):
        _reject()


def _leaves(data, path=""):
    if isinstance(data, dict):
        if "amount_iqd" in data:
            yield path, data
        else:
            for key, value in data.items():
                yield from _leaves(value, f"{path}.{key}" if path else key)
    elif isinstance(data, list):
        for index, value in enumerate(data):
            yield from _leaves(value, f"{path}.{index}")
    else:
        yield path, data


def _verify_debts(data, snapshot):
    parsed = DebtsResult.model_validate(data)
    balances = {b.obligation.obligation_id: b for b in snapshot.balances}
    for report in (parsed.receivables, parsed.payables):
        if report is None:
            continue
        total = 0
        seen = set()
        for party in report.customers:
            subtotal = 0
            for obligation in party.obligations:
                balance = balances.get(obligation.obligation_id)
                if balance is None or obligation.obligation_id in seen:
                    _reject()
                seen.add(obligation.obligation_id)
                if (
                    obligation.outstanding.amount_iqd != balance.amount_iqd
                    or obligation.original.amount_iqd
                    != balance.obligation.original_amount_iqd
                    or party.counterparty_id != balance.obligation.counterparty_id
                ):
                    _reject()
                subtotal += balance.amount_iqd
            if subtotal != party.outstanding.amount_iqd:
                _reject()
            total += subtotal
        if report.total_outstanding.amount_iqd != total:
            _reject()
    if parsed.upcoming is not None:
        view = parsed.upcoming
        dues = sum(i.outstanding.amount_iqd for i in view.dues)
        expected = sum(i.outstanding.amount_iqd for i in view.expected)
        if (
            dues != view.dues_total.amount_iqd
            or expected != view.expected_total.amount_iqd
        ):
            _reject()
        if any(i.due_date < snapshot.day for i in view.expected):
            _reject()
        cash = view.cash_on_hand.amount_iqd
        confirmed, combined = cash, cash
        for index, row in enumerate(view.days):
            if row.date != snapshot.day + timedelta(days=index):
                _reject()
            if cash is not None:
                confirmed -= row.dues_iqd
                combined += row.expected_iqd - row.dues_iqd
            if (
                row.running_confirmed_iqd != confirmed
                or row.running_with_expected_iqd != combined
            ):
                _reject()
        if (
            view.position_confirmed.amount_iqd != confirmed
            or view.position_with_expected.amount_iqd != combined
        ):
            _reject()


def _verify_forecast(data, snapshot):
    from app.tools.forecast import ForecastResult

    parsed = ForecastResult.model_validate(data)
    starting, _ = snapshot.cash()
    for name, forecast in parsed.scenarios.items():
        if len(forecast.days) != 30:
            _reject()
        opening = starting.amount_iqd
        for index, row in enumerate(forecast.days, 1):
            if (
                row.date != snapshot.day + timedelta(days=index)
                or row.opening_iqd != opening
            ):
                _reject()
            closing = (
                opening
                + row.cash_sales_iqd
                + row.unlinked_cash_iqd
                + row.collections_iqd
                - row.supplier_payments_iqd
                - row.expenses_iqd
                - row.owner_drawings_iqd
            )
            if row.closing_iqd != closing or (
                name == "stress" and row.collections_iqd != 0
            ):
                _reject()
            opening = closing
        lowest = min(forecast.days, key=lambda row: row.closing_iqd)
        if (
            forecast.lowest.date != lowest.date
            or forecast.lowest.closing_iqd != lowest.closing_iqd
        ):
            _reject()
    if parsed.j1 is not None and parsed.j1 != payment_capacity(
        snapshot, parsed.j1.due_date
    ):
        _reject()


def verify_tool_output(envelope, *, snapshot, tool_name, weekly_plan=False):
    if not envelope.ok or envelope.resolved_range is None:
        _reject()
    figure_map = {figure.key: figure for figure in envelope.figures}
    metric_map = {metric.key: metric for metric in envelope.metrics}
    if (
        len(figure_map) != len(envelope.figures)
        or len(metric_map) != len(envelope.metrics)
        or figure_map.keys() & metric_map.keys()
    ):
        _reject()
    known = Counter(row.source_id for row in snapshot.rows)
    known.update({key: 1 for key in snapshot.categories})
    if snapshot.opening is not None:
        known[snapshot.opening.source_id] += 1
    for figure in (*envelope.figures, *envelope.metrics):
        if not figure.formula or any(known[key] != 1 for key in figure.source_ids):
            _reject()
        value = figure.amount_iqd if figure.key in figure_map else figure.value
        if value not in (None, 0) and not figure.source_ids:
            _reject()
        original = _lookup(envelope.result, figure.key)
        if isinstance(original, dict):
            if not isinstance(figure, Figure):
                _reject()
            if figure.model_dump(mode="json", exclude={"key"}) != original:
                _reject()
        elif original != value or (original is not None and type(original) is not int):
            _reject()
        elif figure.key.endswith("_iqd"):
            if not isinstance(figure, Figure):
                _reject()
        else:
            expected_unit = {
                "coverage_pct": "percent",
                "unpriced_sales_count": "count",
                "days_overdue": "days",
                "horizon_days": "days",
            }.get(figure.key.rsplit(".", 1)[-1])
            if not isinstance(figure, Metric) or figure.unit != expected_unit:
                _reject()
    for key, value in _leaves(envelope.result):
        if isinstance(value, float):
            _reject()
        if isinstance(value, dict) and key not in figure_map:
            _reject()
        if type(value) is int and key not in figure_map and key not in metric_map:
            _reject()
    for key, value in envelope.dates.items():
        original = (
            getattr(envelope.resolved_range, key)
            if key in {"start", "end"}
            else _lookup(envelope.result, key)
        )
        if str(original) != value.isoformat():
            _reject()
    if envelope.evidence_source_ids != sources(
        *(f.source_ids for f in (*envelope.figures, *envelope.metrics))
    ):
        _reject()
    resolved = DateRange(
        envelope.resolved_range.start,
        envelope.resolved_range.end,
        partial=envelope.result.get("range", {}).get("partial", False),
    )
    if weekly_plan and tool_name in {"get_sales", "get_margin"}:
        if (
            weekly_tool_result(snapshot, resolved, tool_name).model_dump(mode="json")
            != envelope.result
        ):
            _reject()
    elif tool_name == "get_sales":
        expected = sale_totals(snapshot, resolved, kind=envelope.result["kind"])
        if expected.model_dump(mode="json") != envelope.result:
            _reject()
    elif tool_name == "get_margin":
        if margin_report(snapshot, resolved).model_dump(mode="json") != envelope.result:
            _reject()
    elif tool_name == "get_debts":
        _verify_debts(envelope.result, snapshot)
    elif tool_name == "forecast":
        _verify_forecast(envelope.result, snapshot)
    elif tool_name == "reconcile":
        FlagsReport.model_validate(envelope.result)
    else:
        _reject()
    envelope._verified_fingerprint = _fingerprint(envelope)
    return envelope
