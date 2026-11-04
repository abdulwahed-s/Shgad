"""FINANCIAL_RULES §12: deterministic ranking and separate merchant memory.

Debt figures are projections of the existing verified read-only tool. A reminder
is an operational handoff record, never a transaction or confirmed delivery.
"""

from datetime import UTC, date

from app.agents.tool_registry import invoke
from app.agents.verification import require_verified
from app.schemas.collections import (
    CollectionCustomer,
    CollectionsReport,
    ReminderArguments,
    ReminderReceipt,
    RemindersResult,
    ReminderSummary,
    SourcedCount,
)
from app.schemas.evidence import CounterpartyView
from app.schemas.queries import DebtReport
from app.schemas.tools import KnownZeroDebtQuery
from app.services.errors import FinancialRuleError
from app.services.ledger_rules import knowledge_cutoff


def verified_debts(connection, *, clock, known_at, overdue_only=True):
    output = invoke(
        "get_debts",
        {"direction": "receivable", "overdue_only": overdue_only},
        connection=connection,
        clock=clock,
        known_at=known_at,
    )
    if not output.ok:
        raise FinancialRuleError(output.error.code, details=output.error.details)
    require_verified(output)
    return DebtReport.model_validate(output.result["receivables"]), output


def customer(connection, counterparty_id):
    row = connection.execute(
        "SELECT display_name FROM counterparties "
        "WHERE counterparty_id=? AND kind='customer'",
        (counterparty_id,),
    ).fetchone()
    if row is None:
        raise FinancialRuleError("NOT_FOUND")
    return CounterpartyView(id=counterparty_id, display_name=row[0])


def get_reminders(connection, counterparty_ids, *, clock, known_at):
    args = ReminderArguments(counterparty_ids=tuple(dict.fromkeys(counterparty_ids)))
    ids = tuple(dict.fromkeys(args.counterparty_ids))
    for key in ids:
        customer(connection, key)
    # This is the actual audit cutoff, not the financial snapshot's September
    # day-end. A November action with a September business date remains visible.
    if known_at.tzinfo is None:
        raise FinancialRuleError("VALIDATION_ERROR")
    cutoff = known_at.astimezone(UTC).isoformat()
    query_only = connection.execute("PRAGMA query_only").fetchone()[0]
    try:
        connection.execute("PRAGMA query_only=ON")
        summaries = []
        for key in ids:
            rows = connection.execute(
                "SELECT reminder_id,business_date FROM reminders "
                "WHERE counterparty_id=? AND business_date<=? AND recorded_at<=? "
                "ORDER BY business_date,recorded_at,reminder_id",
                (key, str(clock.today), cutoff),
            ).fetchall()
            last = date.fromisoformat(rows[-1][1]) if rows else None
            summaries.append(
                ReminderSummary(
                    counterparty_id=key,
                    count=len(rows),
                    last_business_date=last,
                    days_since_last=(clock.today - last).days if last else None,
                    reminder_ids=tuple(row[0] for row in rows),
                )
            )
        return RemindersResult(as_of=clock.today, items=tuple(summaries))
    finally:
        connection.execute(f"PRAGMA query_only={int(query_only)}")


def collection_report(connection, *, clock, known_at):
    report, output = verified_debts(connection, clock=clock, known_at=known_at)
    ids = tuple(p.counterparty_id for p in report.customers)
    memory = {}
    for start in range(0, len(ids), 200):
        batch = get_reminders(
            connection, ids[start : start + 200], clock=clock, known_at=known_at
        )
        memory.update({p.counterparty_id: p for p in batch.items})
    figures = {f.key: f for f in output.figures}
    items = []
    for index, party in enumerate(report.customers):
        log = memory[party.counterparty_id]
        figure = figures[f"receivables.customers.{index}.outstanding"].model_copy(
            update={"key": "overdue_amount"}
        )
        items.append(
            CollectionCustomer(
                counterparty_id=party.counterparty_id,
                display_name=party.display_name,
                overdue_amount=figure,
                oldest_due_date=party.oldest_due_date,
                days_overdue=party.days_overdue,
                source_ids=figure.source_ids,
                reminder_count=log.count,
                last_reminder_business_date=log.last_business_date,
                days_since_last_reminder=log.days_since_last,
            )
        )
    items.sort(
        key=lambda p: (-p.overdue_amount.amount_iqd, -p.days_overdue, p.counterparty_id)
    )
    total = figures["receivables.total_outstanding"].model_copy(
        update={"key": "total_overdue"}
    )
    if not items:
        if total.amount_iqd != 0 or total.source_ids:
            raise FinancialRuleError("INTERNAL")
        # D61 current-business snapshots also support an actual later audit time.
        # The entire debt report was independently verified above; no matching
        # positive balance exists under its exact filters. Legacy tools unchanged.
        total = total.model_copy(
            update={
                "query_evidence": KnownZeroDebtQuery(
                    tool="get_debts",
                    as_of=clock.today,
                    filters=report.filters,
                    known_at=knowledge_cutoff(clock.today, known_at),
                )
            }
        )
    return CollectionsReport(
        as_of=clock.today,
        total_overdue=total,
        customer_count=SourcedCount(
            key="overdue_customer_count",
            value=len(items),
            unit="count",
            kind="calculated",
            label_key="overdue_customer_count",
            source_ids=total.source_ids,
            formula="count distinct customer IDs in verified overdue-only receivables",
            query_evidence=total.query_evidence if not items else None,
        ),
        items=tuple(items),
    )


def log_reminder(connection, request, *, clock, now):
    if now.tzinfo is None:
        raise FinancialRuleError("VALIDATION_ERROR")
    own_transaction = not connection.in_transaction
    if own_transaction:
        connection.execute("BEGIN IMMEDIATE")
    connection.execute("SAVEPOINT merchant_reminder")
    try:
        customer(connection, request.counterparty_id)
        report = collection_report(connection, clock=clock, known_at=now)
        selected = next(
            (p for p in report.items if p.counterparty_id == request.counterparty_id),
            None,
        )
        if selected is None:
            raise FinancialRuleError("NO_OVERDUE_DEBT")
        recorded_at = now.astimezone(UTC)
        cursor = connection.execute(
            "INSERT INTO reminders (counterparty_id,business_date,recorded_at,"
            "overdue_amount_iqd,tone,channel,edited) VALUES (?,?,?,?,?,?,?)",
            (
                request.counterparty_id,
                str(clock.today),
                recorded_at.isoformat(),
                selected.overdue_amount.amount_iqd,
                request.tone,
                request.channel,
                int(request.edited),
            ),
        )
        receipt = ReminderReceipt(
            **request.model_dump(),
            reminder_id=cursor.lastrowid,
            business_date=clock.today,
            recorded_at=recorded_at,
            overdue_amount=selected.overdue_amount,
        )
        connection.execute("RELEASE SAVEPOINT merchant_reminder")
        if own_transaction:
            connection.commit()
        return receipt
    except Exception:
        connection.execute("ROLLBACK TO SAVEPOINT merchant_reminder")
        connection.execute("RELEASE SAVEPOINT merchant_reminder")
        if own_transaction:
            connection.rollback()
        raise
