"""Mandatory slot renderer and bounded retry/template fallback (§8.2a).

No provider dependency. This module never derives a financial value or date.
Arabic copy and its human review status are centralized in messages_ar.py.
"""

import re
from datetime import date

from app.agents.messages_ar import text
from app.agents.verification import require_verified
from app.schemas.renderer import RenderedReply, RendererStats, ResolvedContext

_SLOT = re.compile(r"\{\{(fig|date):([A-Za-z][A-Za-z0-9_.-]*)\}\}")
_DIGITS = str.maketrans("0123456789,-", "٠١٢٣٤٥٦٧٨٩٬−")


class DraftValidationError(ValueError):
    pass


def has_evidence(entry):
    """Called only after the exact envelope passes require_verified."""
    return bool(
        entry.formula and (entry.source_ids or getattr(entry, "query_evidence", None))
    )


def format_iqd(value, *, evidence=False):
    if type(value) is not int:
        raise TypeError("IQD must be an exact integer")
    if not evidence and abs(value) < 1000000 and value % 1000 == 0:
        return f"{str(value // 1000).translate(_DIGITS)} {text('thousand')}"
    return f"{format(value, ',d').translate(_DIGITS)} {text('iqd')}"


def format_date(value):
    if type(value) is not date:
        raise TypeError("A verified business date is required")
    return f"{value.day:02}/{value.month:02}/{value.year:04}".translate(_DIGITS)


def _slots(outputs):
    figures, metrics, dates, contexts = {}, {}, {}, []
    aliases = ({}, {}, {})
    for index, output in enumerate(outputs):
        require_verified(output)
        for target, unqualified, values in (
            (figures, aliases[0], {f.key: f for f in output.figures}),
            (metrics, aliases[1], {m.key: m for m in output.metrics}),
            (dates, aliases[2], output.dates),
        ):
            for key, value in values.items():
                target[f"tool_{index}.{key}"] = value
                if key not in unqualified:
                    unqualified[key] = value
                elif unqualified[key] != value:
                    unqualified[key] = None
        context = ResolvedContext(
            range=output.resolved_range, counterparty=output.resolved_counterparty
        )
        if context not in contexts:
            contexts.append(context)
    for target, unqualified in zip((figures, metrics, dates), aliases, strict=True):
        target.update(
            {key: value for key, value in unqualified.items() if value is not None}
        )
    return figures, metrics, dates, tuple(contexts)


def _render_body(draft, *, figures, metrics, dates, used, user_message):
    if not isinstance(draft, str) or not draft.strip() or len(draft) > 12000:
        raise DraftValidationError("INVALID_DRAFT")
    if any(0xE000 <= ord(c) <= 0xF8FF for c in draft):
        raise DraftValidationError("INVALID_DRAFT")
    quotes = {}

    def mask_quote(match):
        quoted = match.group(1)
        if quoted and quoted in user_message:
            marker = chr(0xE000 + len(quotes))
            quotes[marker] = match.group(0)
            return marker
        return match.group(0)

    masked = re.sub(r"«([^«»]*)»", mask_quote, draft)
    residual = _SLOT.sub("", masked)
    if "{" in residual or "}" in residual:
        raise DraftValidationError("INVALID_SLOT")
    if any(char.isnumeric() for char in residual):
        raise DraftValidationError("RAW_NUMBER")

    def replace(match):
        kind, key = match.groups()
        if kind == "date":
            if key not in dates:
                raise DraftValidationError("UNKNOWN_SLOT")
            used[2][key] = dates[key]
            return format_date(dates[key])
        figure = figures.get(key)
        metric = metrics.get(key)
        if figure is None and metric is None:
            raise DraftValidationError("UNKNOWN_SLOT")
        value = figure.amount_iqd if figure is not None else metric.value
        entry = figure if figure is not None else metric
        if value is None:
            raise DraftValidationError("MISSING_FIGURE")
        if not has_evidence(entry):
            raise DraftValidationError("MISSING_EVIDENCE")
        used[0 if figure is not None else 1][key] = entry.model_copy(
            update={"key": key}
        )
        return (
            format_iqd(value)
            if figure is not None
            else format(value, ",d").translate(_DIGITS)
            + ("٪" if metric.unit == "percent" else "")
        )

    rendered = _SLOT.sub(replace, masked)
    for marker, original in quotes.items():
        rendered = rendered.replace(marker, original)
    return rendered


def _server_context(outputs, contexts, *, figures, metrics, dates, used, debt_list):
    parts = []

    def include(index, key, label):
        qualified = f"tool_{index}.{key}"
        entry = figures.get(qualified)
        if entry is None or entry.kind == "missing" or not has_evidence(entry):
            return
        if "tool_plan_period_movements" in outputs[index].warnings and (
            qualified in used[0] or (key in used[0] and figures.get(key) == entry)
        ):
            return
        parts.append(
            _render_body(
                label + ": {{fig:" + qualified + "}}.",
                figures=figures,
                metrics=metrics,
                dates=dates,
                used=used,
                user_message="",
            )
        )

    for index, context in enumerate(contexts):
        parts.append(
            text("period").format(
                start=format_date(context.range.start),
                end=format_date(context.range.end),
            )
        )
        used[2][f"context_{index}.start"] = context.range.start
        used[2][f"context_{index}.end"] = context.range.end
        if context.counterparty is not None:
            parts.append(
                text("customer").format(name=context.counterparty.display_name)
            )
    assumptions = set()
    for index, output in enumerate(outputs):
        if output.result.get("note_key") == "expense_kind_unrecorded":
            parts.append(text("expense_kind_unrecorded"))
        if "weekly" in output.result and "cash_sales" in output.result:
            for key in (
                "cash_sales",
                "credit_sales",
                "total_sales",
                "unexplained_cash_difference",
            ):
                include(index, key, text(figures[f"tool_{index}.{key}"].label_key))
            if output.result["unexplained_cash_difference"]["amount_iqd"] not in (
                None,
                0,
            ):
                parts.append(text("difference_note"))
            for key, label in (
                ("collections", "collection"),
                ("supplier_payments", "supplierPayment"),
                ("operating_expenses", "operatingExpense"),
                ("owner_drawings", "ownerDrawing"),
                ("capital_injections", "capitalInjection"),
            ):
                include(index, f"weekly.{key}", text(label))
        if "shown" in output.result:
            if output.result["shown"]:
                include(index, "gross_margin", text("estimated_gross_margin"))
            else:
                parts.append(text("margin_insufficient_priced_sales"))
        if "items" in output.result:
            for item_index, flag in enumerate(output.result["items"]):
                label = {
                    "suspected_duplicate": "review_duplicate_payment",
                    "unmatched": "review_unmatched_payment",
                    "ambiguous": "review_unmatched_payment",
                }.get(flag["type"], "review_debts")
                include(index, f"items.{item_index}.amount", text(label))
                parts.append(
                    text("flag_sources").format(ids="، ".join(flag["source_ids"]))
                )
            for gap_index, gap in enumerate(output.result.get("cash_differences", ())):
                include(
                    index,
                    f"cash_differences.{gap_index}.amount",
                    text("unexplained_cash_difference")
                    + " ("
                    + "{{date:tool_"
                    + f"{index}.cash_differences.{gap_index}.date"
                    + "}}"
                    + ")",
                )
                parts.append(
                    text("flag_sources").format(
                        ids="، ".join(gap["amount"]["source_ids"])
                    )
                )
            if output.result.get("cash_differences"):
                parts.append(text("difference_note"))
            if not output.result["items"] and not output.result.get("cash_differences"):
                parts.append(text("no_action_needed"))
        if "tool_plan_cash_sufficiency" in output.warnings and output.result.get("j1"):
            for key in (
                "cash_on_hand",
                "supplier_due",
                "expected_collection",
                "shortfall_with_collection",
                "shortfall_without_collection",
            ):
                include(index, f"j1.{key}", text(key))
        if debt_list:
            for direction in ("receivables", "payables"):
                report = output.result.get(direction)
                if report is None:
                    continue
                for party_index, party in enumerate(report["customers"]):
                    key = (
                        f"tool_{index}.{direction}.customers.{party_index}.outstanding"
                    )
                    # Names are verified server text, never draft instructions/slots.
                    parts.append(text("customer").format(name=party["display_name"]))
                    parts.append(
                        text(direction)
                        + ": "
                        + _render_body(
                            "{{fig:" + key + "}}",
                            figures=figures,
                            metrics=metrics,
                            dates=dates,
                            used=used,
                            user_message="",
                        )
                    )
        scenarios = output.result.get("scenarios")
        if scenarios:
            parts.append(
                text("forecast").format(
                    scenarios="، ".join(text(name) for name in scenarios)
                )
            )
        if "gross_margin" in output.result and "coverage_pct" in output.result:
            coverage_key = (
                "coverage_pct" if len(outputs) == 1 else f"tool_{index}.coverage_pct"
            )
            metric = metrics.get(coverage_key)
            copy = text("coverage").format(value="{{fig:" + coverage_key + "}}")
            if metric is not None and metric.value is not None and metric.source_ids:
                parts.append(
                    _render_body(
                        copy,
                        figures=figures,
                        metrics=metrics,
                        dates=dates,
                        used=used,
                        user_message="",
                    )
                )
        for key in output.assumptions:
            if (
                key
                in {
                    "collections_expected_not_guaranteed",
                    "margin_excludes_unrecorded_costs",
                    "unexplained_difference_excluded",
                }
                and key not in assumptions
            ):
                parts.append(text(key))
                assumptions.add(key)
    return parts


def render_draft(draft, *, outputs, user_message="", debt_list=False):
    outputs = tuple(outputs)
    figures, metrics, dates, contexts = _slots(outputs)
    used = ({}, {}, {})
    body = _render_body(
        draft,
        figures=figures,
        metrics=metrics,
        dates=dates,
        used=used,
        user_message=user_message,
    )
    prefix = _server_context(
        outputs,
        contexts,
        figures=figures,
        metrics=metrics,
        dates=dates,
        used=used,
        debt_list=debt_list,
    )
    ranges = tuple(dict.fromkeys((c.range.start, c.range.end) for c in contexts))
    parties = {
        c.counterparty.id: c.counterparty
        for c in contexts
        if c.counterparty is not None
    }
    return RenderedReply(
        reply_ar=" ".join([*prefix, body]),
        figures=tuple(used[0].values()),
        metrics=tuple(used[1].values()),
        dates=used[2],
        contexts=contexts,
        resolved_range=contexts[0].range if len(ranges) == 1 else None,
        resolved_counterparty=next(iter(parties.values()))
        if len(parties) == 1
        else None,
        renderer=RendererStats(attempts=1, fell_back_to_template=False),
    )


def _template(outputs):
    lines = []
    for index, output in enumerate(outputs):
        data = output.result
        available = {f.key: f for f in (*output.figures, *output.metrics)}

        def add(key, label=None, suffix=""):
            entry = available.get(key)
            if entry is None or entry.kind == "missing" or not has_evidence(entry):
                return
            label = label or text(entry.label_key)
            lines.append(
                label + ": {{fig:tool_" + str(index) + "." + key + "}}" + suffix + "."
            )

        if data.get("j1"):
            for key in (
                "cash_on_hand",
                "supplier_due",
                "expected_collection",
                "shortfall_with_collection",
                "shortfall_without_collection",
            ):
                add(f"j1.{key}")
        elif data.get("upcoming"):
            for key in (
                "cash_on_hand",
                "dues_total",
                "expected_total",
                "position_confirmed",
                "position_with_expected",
            ):
                add(f"upcoming.{key}")
        elif "gross_margin" in data:
            for key in (
                "gross_margin",
                "after_recorded_expenses",
                "unpriced_sales_count",
            ):
                add(key)
        elif data.get("note_key") == "expense_kind_unrecorded":
            add("weekly.operating_expenses", text("operatingExpense"))
        elif "kind" in data:
            if data["kind"] in {"cash", "all"}:
                add("cash_sales")
                add("unexplained_cash_difference")
                if data["unexplained_cash_difference"]["amount_iqd"] not in (None, 0):
                    lines.append(text("difference_note"))
            if data["kind"] in {"credit", "all"}:
                add("credit_sales")
            if data["kind"] == "all":
                add("total_sales")
        elif "receivables" in data:
            for key in ("receivables", "payables"):
                add(f"{key}.total_outstanding", text(key))
        elif "scenarios" in data:
            for name in data["scenarios"]:
                add(
                    f"scenarios.{name}.lowest.closing_iqd",
                    text("forecast_lowest") + " (" + text(name) + ")",
                    "؛ {{date:tool_"
                    + str(index)
                    + ".scenarios."
                    + name
                    + ".lowest.date}}",
                )
        elif "items" in data:
            add("weekly.collections", text("collection"))
    return " ".join(lines) or text("no_figures")


def render_reply(draft, *, outputs, user_message="", retry=None, debt_list=False):
    outputs = tuple(outputs)
    for output in outputs:
        require_verified(output)
    attempts = 1
    try:
        return render_draft(
            draft, outputs=outputs, user_message=user_message, debt_list=debt_list
        )
    except DraftValidationError as exc:
        if retry is not None:
            try:
                revised = retry(str(exc))
            except Exception:
                revised = None
            if revised is not None:
                attempts += 1
                try:
                    rendered = render_draft(
                        revised,
                        outputs=outputs,
                        user_message=user_message,
                        debt_list=debt_list,
                    )
                    return rendered.model_copy(
                        update={
                            "renderer": RendererStats(
                                attempts=attempts, fell_back_to_template=False
                            )
                        }
                    )
                except DraftValidationError:
                    pass
    rendered = render_draft(_template(outputs), outputs=outputs, debt_list=debt_list)
    return rendered.model_copy(
        update={
            "renderer": RendererStats(attempts=attempts, fell_back_to_template=True)
        }
    )
