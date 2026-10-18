"""Per-scalar evidence for structured projection tables, never model arithmetic."""

from app.db.forecast_repository import read_forecast_snapshot
from app.schemas.tools import Figure, Metric
from app.services.financial_queries import sources
from app.services.forecast import _balances, _historical_drivers, _schedule
from app.services.ledger_rules import cash_on_hand


def upcoming_figures(report, *, prefix="upcoming"):
    figures = []
    for index, row in enumerate(report.days):
        due_today = [
            i for i in report.dues if max(report.as_of, i.due_date) == row.date
        ]
        expected_today = [i for i in report.expected if i.due_date == row.date]
        due_so_far = [i for i in report.dues if i.due_date <= row.date]
        expected_so_far = [i for i in report.expected if i.due_date <= row.date]

        def evidence(items):
            return sources(*(i.outstanding.source_ids for i in items))

        daily = {
            "dues_iqd": (
                evidence(due_today),
                "sum known supplier dues scheduled on this date; overdue due now",
            ),
            "expected_iqd": (
                evidence(expected_today),
                "sum non-overdue expected collections due on this date",
            ),
            "running_confirmed_iqd": (
                sources(report.cash_on_hand.source_ids, evidence(due_so_far)),
                "starting confirmed cash - supplier dues through this date",
            ),
            "running_with_expected_iqd": (
                sources(
                    report.cash_on_hand.source_ids,
                    evidence(due_so_far),
                    evidence(expected_so_far),
                ),
                "starting cash + non-overdue expected collections "
                "- supplier dues through this date",
            ),
        }
        for key, (ids, formula) in daily.items():
            value = getattr(row, key)
            figures.append(
                Figure(
                    key=f"{prefix}.days.{index}.{key}",
                    amount_iqd=value,
                    kind="missing"
                    if value is None
                    else "expected"
                    if key == "expected_iqd"
                    else "calculated",
                    label_key=key.removesuffix("_iqd"),
                    source_ids=ids,
                    formula=formula,
                )
            )
    return tuple(figures)


def debt_metrics(result):
    metrics = []
    for direction in ("receivables", "payables"):
        report = getattr(result, direction)
        if report is None:
            continue
        for index, party in enumerate(report.customers):
            metrics.append(
                Metric(
                    key=f"{direction}.customers.{index}.days_overdue",
                    value=party.days_overdue,
                    unit="days",
                    kind="missing" if party.days_overdue is None else "calculated",
                    label_key="days_overdue",
                    source_ids=party.outstanding.source_ids,
                    formula="max(0, business_as_of - oldest outstanding due date)",
                )
            )
    return tuple(metrics)


def forecast_figures(connection, *, clock, report):
    """Reuse the production driver's observed inputs; do not read outcome files."""
    snapshot = read_forecast_snapshot(connection, clock=clock)
    starting = cash_on_hand(
        snapshot.transactions,
        as_of=clock.today,
        opening_balance=snapshot.opening_balance,
    )
    _, _, _, _, historical = _historical_drivers(snapshot, clock.today)
    obligations, lateness = _balances(snapshot)
    figures = []
    for name, scenario in report.scenarios.items():
        _, _, collections, payments = _schedule(
            obligations, lateness, cutoff=clock.today, scenario=name
        )
        drivers = historical | {
            "collections": collections,
            "supplier_payments": payments,
        }
        running_sources = starting.source_ids
        closings = {}
        for index, row in enumerate(scenario.days):
            base = f"scenarios.{name}.days.{index}"
            figures.append(
                Figure(
                    key=f"{base}.opening_iqd",
                    amount_iqd=row.opening_iqd,
                    kind="expected",
                    label_key="forecast_opening",
                    source_ids=running_sources,
                    formula="cutoff cash first; previous projected closing thereafter",
                )
            )
            for field, ids in drivers.items():
                figures.append(
                    Figure(
                        key=f"{base}.{field}_iqd",
                        amount_iqd=getattr(row, f"{field}_iqd"),
                        kind="expected",
                        label_key=field,
                        source_ids=ids,
                        formula=f"FINANCIAL_RULES §6: {name} projected {field} "
                        "from cutoff-visible history/schedule",
                    )
                )
                running_sources = sources(running_sources, ids)
            figures.append(
                Figure(
                    key=f"{base}.closing_iqd",
                    amount_iqd=row.closing_iqd,
                    kind="expected",
                    label_key="forecast_closing",
                    source_ids=running_sources,
                    formula="opening + recorded-sales estimate + signed difference "
                    "+ expected collections - supplier payments - expenses - drawings",
                )
            )
            closings[row.date] = running_sources
        figures.append(
            Figure(
                key=f"scenarios.{name}.lowest.closing_iqd",
                amount_iqd=scenario.lowest.closing_iqd,
                kind="expected",
                label_key="forecast_lowest",
                source_ids=closings[scenario.lowest.date],
                formula="minimum projected closing across 30 days",
            )
        )
    return tuple(figures), (
        Metric(
            key="horizon_days",
            value=30,
            unit="days",
            kind="calculated",
            label_key="forecast_horizon",
            source_ids=starting.source_ids,
            formula="length of fixed 30-day projected series",
        ),
    )
