"""D61 deterministic brief: fixed verified queries, no provider or forecast."""

import hashlib

from app.agents.tool_registry import invoke
from app.agents.verification import require_verified
from app.schemas.collections import EmptyFlagsQuery, MorningBrief, SourcedCount
from app.schemas.queries import DateRangeView
from app.schemas.tools import KnownZeroScheduleQuery
from app.services.collections import collection_report
from app.services.errors import FinancialRuleError
from app.services.financial_queries import sources


def require_brief_verified(report):
    if (
        not isinstance(report, MorningBrief)
        or report._render_fingerprint
        != hashlib.sha256(report.model_dump_json().encode()).hexdigest()
    ):
        raise FinancialRuleError("VALIDATION_ERROR")


def morning_brief(connection, *, clock, known_at):
    query_only = connection.execute("PRAGMA query_only").fetchone()[0]
    connection.execute("PRAGMA query_only=ON")
    connection.execute("SAVEPOINT morning_brief")
    try:

        def checked(name, args):
            result = invoke(
                name, args, connection=connection, clock=clock, known_at=known_at
            )
            if not result.ok:
                raise FinancialRuleError(
                    result.error.code, details=result.error.details
                )
            require_verified(result)
            return result

        today = checked(
            "get_debts", {"direction": "both", "due_period": "next_n_days:1"}
        )
        days = (4 - clock.today.weekday()) % 7 + 1
        week = checked(
            "get_debts", {"direction": "both", "due_period": f"next_n_days:{days}"}
        )
        flags = checked("reconcile", {"period": "this_week"})
        collections = collection_report(connection, clock=clock, known_at=known_at)

        def figure(output, key, alias):
            selected = next(f for f in output.figures if f.key == key)
            if key == "upcoming.dues_total" and selected.amount_iqd == 0:
                view = output.result["upcoming"]
                if selected.source_ids or view["dues"]:
                    raise FinancialRuleError("INTERNAL")
                selected = selected.model_copy(
                    update={
                        "query_evidence": KnownZeroScheduleQuery(
                            tool="get_debts",
                            as_of=clock.today,
                            schedule="dues",
                            start=view["range"]["start"],
                            end=view["range"]["end"],
                            counterparty_id=None,
                            known_at=known_at,
                        )
                    }
                )
            return selected.model_copy(update={"key": alias})

        cash = figure(today, "upcoming.cash_on_hand", "cash_on_hand")
        if cash.amount_iqd is None:
            raise FinancialRuleError("MISSING_OPENING_BALANCE")
        items = flags.result["items"]
        flag_sources = sources(*(item["source_ids"] for item in items))
        report = MorningBrief(
            as_of=clock.today,
            week=DateRangeView.model_validate(week.result["upcoming"]["range"]),
            cash_on_hand=cash,
            dues_today=figure(today, "upcoming.dues_total", "dues_today"),
            dues_week=figure(week, "upcoming.dues_total", "dues_week"),
            overdue_total=collections.total_overdue.model_copy(
                update={"key": "overdue_total"}
            ),
            overdue_customer_count=collections.customer_count,
            top_customers=collections.items[:3],
            open_flags_count=SourcedCount(
                key="open_flags_count",
                value=len(items),
                unit="count",
                kind="calculated",
                label_key="brief_flags_count",
                source_ids=flag_sources,
                formula="count verified reconciliation flags whose evidence "
                "touches Saturday..today",
                query_evidence=EmptyFlagsQuery(
                    period=flags.resolved_range, known_at=known_at
                )
                if not items
                else None,
            ),
        )
        report._render_fingerprint = hashlib.sha256(
            report.model_dump_json().encode()
        ).hexdigest()
        return report
    finally:
        connection.execute("RELEASE SAVEPOINT morning_brief")
        connection.execute(f"PRAGMA query_only={int(query_only)}")
