"""Production SQLite forecast: FINANCIAL_RULES §§2/3/5/6/11, T12/T26/T29.

All records here are inline synthetic history. No evaluation answers or realized
final outcomes are inputs to these tests.
"""

import builtins
import csv
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.db.connection import connect_database
from app.db.forecast_repository import read_forecast_snapshot
from app.schemas.ledger import VoidRequest
from app.services.business_clock import BusinessClock
from app.services.errors import FinancialRuleError
from app.services.forecast import forecast
from app.services.ingest import import_csv
from app.services.ledger_audit import void_entry

START = date(2026, 7, 1)
CUTOFF = START + timedelta(days=59)
CLOCK = BusinessClock(CUTOFF)


@pytest.fixture
def history(ledger, insert_event):
    cash = 200000
    for offset in range(60):
        day = START + timedelta(days=offset)
        for kind, amount in [
            ("CASH_SALE", 100000),
            ("OPERATING_EXPENSE", 10000),
            ("OWNER_DRAWING", 5000),
        ]:
            insert_event(
                type=kind, amount_iqd=amount, occurred_at=f"{day}T12:00:00+03:00"
            )
        cash += 85000 + (-3000 if day.weekday() == 2 else 2000)
        insert_event(
            type="DAILY_CASH_COUNT",
            amount_iqd=cash,
            occurred_at=f"{day}T21:00:00+03:00",
        )
    ledger.commit()
    return cash


def add_debt(
    ledger,
    insert_event,
    source,
    *,
    kind="receivable",
    amount=70000,
    due=None,
    occurred=None,
    recorded=None,
    customer="CUST-01",
):
    row = insert_event(
        source_id=source,
        type="CREDIT_SALE" if kind == "receivable" else "SUPPLIER_INVOICE",
        amount_iqd=amount,
        counterparty_id=customer if kind == "receivable" else "SUP-01",
        obligation_id=f"OB-{source}",
        due_date=due,
        occurred_at=occurred or f"{CUTOFF}T10:00:00+03:00",
        recorded_at=recorded,
    )
    ledger.execute(
        "INSERT INTO obligations VALUES (?, ?, ?, ?, ?, ?)",
        (
            row.obligation_id,
            kind,
            row.transaction_id,
            row.counterparty_id,
            amount,
            due,
        ),
    )
    return row


def add_collection(
    ledger, insert_event, origin, *, source, amount, occurred, linked=None
):
    row = insert_event(
        source_id=source,
        type="CREDIT_COLLECTION",
        amount_iqd=amount,
        counterparty_id=origin.counterparty_id,
        obligation_id=origin.obligation_id,
        occurred_at=occurred,
    )
    if linked:
        ledger.execute(
            "INSERT INTO payment_links VALUES (?, ?, ?, ?, ?, ?)",
            (
                f"LINK-{source}",
                row.transaction_id,
                origin.obligation_id,
                amount,
                "definite",
                linked,
            ),
        )
    return row


def test_t29_production_recurrence_has_three_exact_integer_scenarios(ledger, history):
    before = ledger.total_changes
    result = forecast(ledger, clock=CLOCK)
    assert ledger.total_changes == before
    assert result.as_of == CUTOFF
    assert set(result.scenarios) == {"base", "conservative", "stress"}
    for scenario in result.scenarios.values():
        assert len(scenario.days) == 30
        previous = history
        for row in scenario.days:
            assert row.opening_iqd == previous
            assert row.cash_sales_iqd == 100000
            assert row.expenses_iqd == 10000
            assert row.owner_drawings_iqd == 5000
            assert row.unlinked_cash_iqd == (-3000 if row.date.weekday() == 2 else 2000)
            assert row.closing_iqd == previous + 85000 + row.unlinked_cash_iqd
            assert all(
                type(value) is int
                for key, value in row.model_dump().items()
                if key != "date"
            )
            previous = row.closing_iqd
    assert "unlinked_cash_projected_from_counts" in result.assumption_keys
    assert forecast(ledger, clock=CLOCK) == result
    assert set(forecast(ledger, clock=CLOCK, scenario="stress").scenarios) == {"stress"}


def test_t12_future_entries_links_and_voids_do_not_affect_earlier_runtime_forecast(
    ledger, insert_event, history
):
    due = (CUTOFF + timedelta(days=2)).isoformat()
    receivable = add_debt(ledger, insert_event, "VISIBLE-R", due=due)
    invoice = add_debt(
        ledger,
        insert_event,
        "VISIBLE-P",
        kind="payable",
        amount=250000,
        due=(CUTOFF + timedelta(days=3)).isoformat(),
    )
    ledger.commit()
    before = forecast(ledger, clock=CLOCK, scenario="base")
    snapshot = read_forecast_snapshot(ledger, clock=CLOCK)
    assert {o.obligation_id for o in snapshot.obligations} == {
        receivable.obligation_id,
        invoice.obligation_id,
    }
    assert before.scenarios["base"].days[1].collections_iqd == 70000
    assert before.scenarios["base"].days[2].supplier_payments_iqd == 250000
    later = CUTOFF + timedelta(days=1)
    add_debt(
        ledger,
        insert_event,
        "LATE-RECORDED",
        due=due,
        recorded=f"{later}T10:00:00+03:00",
    )
    add_debt(
        ledger,
        insert_event,
        "FUTURE-ORIGIN",
        due=due,
        occurred=f"{later}T10:00:00+03:00",
    )
    add_collection(
        ledger,
        insert_event,
        receivable,
        source="LATE-PAYMENT",
        amount=70000,
        occurred=f"{later}T11:00:00+03:00",
        linked=f"{later}T09:00:00+00:00",
    )
    void_entry(
        ledger,
        VoidRequest(client_entry_id="late-void", reason="synthetic late audit"),
        transaction_id=invoice.transaction_id,
        voided_at=f"{later}T12:00:00+03:00",
    )
    insert_event(
        type="DAILY_CASH_COUNT",
        amount_iqd=999999999,
        occurred_at="2026-09-29T21:00:00+03:00",
    )
    ledger.commit()
    assert read_forecast_snapshot(ledger, clock=CLOCK) == snapshot
    assert forecast(ledger, clock=CLOCK, scenario="base") == before


def test_t12_link_created_later_and_then_voided_payment_preserve_prior_snapshot(
    ledger, insert_event, history
):
    debt = add_debt(
        ledger,
        insert_event,
        "R",
        due=(CUTOFF + timedelta(days=2)).isoformat(),
        occurred=f"{CUTOFF}T09:00:00+03:00",
    )
    payment = add_collection(
        ledger,
        insert_event,
        debt,
        source="P",
        amount=20000,
        occurred=f"{CUTOFF}T10:00:00+03:00",
    )
    ledger.commit()
    before = forecast(ledger, clock=CLOCK, scenario="base")
    later = CUTOFF + timedelta(days=1)
    ledger.execute(
        "INSERT INTO payment_links VALUES (?, ?, ?, ?, ?, ?)",
        (
            "LATE-LINK",
            payment.transaction_id,
            debt.obligation_id,
            20000,
            "definite",
            f"{later}T12:00:00+00:00",
        ),
    )
    ledger.commit()
    assert forecast(ledger, clock=CLOCK, scenario="base") == before
    later_clock = BusinessClock(later)
    assert (
        forecast(ledger, clock=later_clock, scenario="base")
        .scenarios["base"]
        .days[0]
        .collections_iqd
        == 50000
    )
    void_entry(
        ledger,
        VoidRequest(client_entry_id="void-P", reason="synthetic correction"),
        transaction_id=payment.transaction_id,
        voided_at=f"{later}T20:00:00+03:00",
    )
    ledger.commit()
    assert forecast(ledger, clock=CLOCK, scenario="base") == before
    assert (
        forecast(ledger, clock=later_clock, scenario="base")
        .scenarios["base"]
        .days[0]
        .collections_iqd
        == 70000
    )


def test_t26_customer_median_and_fallback_use_settlement_completion(
    ledger, insert_event, history
):
    for index, late in enumerate((2, 5)):
        due = START + timedelta(days=12 + 10 * index)
        origin = add_debt(
            ledger,
            insert_event,
            f"SETTLED-{index}",
            amount=10000,
            due=str(due),
            occurred=f"{due - timedelta(days=2)}T10:00:00+03:00",
        )
        add_collection(
            ledger,
            insert_event,
            origin,
            source=f"PART-{index}",
            amount=4000,
            occurred=f"{due}T10:00:00+03:00",
            linked=f"{due}T07:00:00+00:00",
        )
        end = due + timedelta(days=late)
        add_collection(
            ledger,
            insert_event,
            origin,
            source=f"END-{index}",
            amount=6000,
            occurred=f"{end}T10:00:00+03:00",
            linked=f"{end}T07:00:00+00:00",
        )
    due = CUTOFF + timedelta(days=2)
    add_debt(ledger, insert_event, "OPEN", amount=70000, due=str(due))
    add_debt(
        ledger, insert_event, "FALLBACK", amount=30000, due=str(due), customer="CUST-02"
    )
    add_debt(
        ledger,
        insert_event,
        "OVERDUE",
        amount=90000,
        due=str(CUTOFF - timedelta(days=1)),
    )
    ledger.commit()
    result = forecast(ledger, clock=CLOCK)
    assert result.scenarios["base"].days[1].collections_iqd == 100000
    # Median 3.5 rounds half up once to 4 days; partial payment was not settlement.
    assert result.scenarios["conservative"].days[5].collections_iqd == 100000
    assert (
        sum(d.collections_iqd for d in result.scenarios["conservative"].days) == 100000
    )
    assert result.overdue_excluded[0].outstanding.amount_iqd == 90000
    collection_driver = next(
        driver
        for driver in result.scenarios["conservative"].top_inflows
        if driver.label_key == "collections"
    )
    assert {"SETTLED-0", "PART-0", "END-0", "SETTLED-1", "PART-1", "END-1"} <= set(
        collection_driver.amount.source_ids
    )
    assert all(d.collections_iqd == 0 for d in result.scenarios["stress"].days)
    assert all(
        s.closing_iqd <= b.closing_iqd
        for s, b in zip(
            result.scenarios["stress"].days, result.scenarios["base"].days, strict=True
        )
    )


def test_missing_starting_cash_is_typed(ledger):
    with pytest.raises(FinancialRuleError) as failure:
        forecast(ledger, clock=CLOCK)
    assert failure.value.code == "MISSING_OPENING_BALANCE"


def test_missing_consecutive_counts_never_becomes_zero_driver(ledger, insert_event):
    for offset in range(60):
        day = START + timedelta(days=offset)
        insert_event(amount_iqd=1000, occurred_at=f"{day}T10:00:00+03:00")
    insert_event(
        type="DAILY_CASH_COUNT",
        amount_iqd=200000,
        occurred_at=f"{CUTOFF}T21:00:00+03:00",
    )
    ledger.commit()
    with pytest.raises(FinancialRuleError) as failure:
        forecast(ledger, clock=CLOCK)
    assert failure.value.code == "MISSING_FORECAST_HISTORY"


def test_missing_lateness_and_missing_due_date_are_typed(ledger, insert_event, history):
    row = add_debt(ledger, insert_event, "UNKNOWN", due=None)
    ledger.commit()
    with pytest.raises(FinancialRuleError) as failure:
        forecast(ledger, clock=CLOCK, scenario="base")
    assert failure.value.code == "MISSING_DUE_DATE"
    void_entry(
        ledger,
        VoidRequest(client_entry_id="void-unknown", reason="synthetic"),
        transaction_id=row.transaction_id,
        voided_at=f"{CUTOFF}T22:00:00+03:00",
    )
    add_debt(ledger, insert_event, "NO-LATENESS", due=str(CUTOFF + timedelta(days=2)))
    ledger.commit()
    assert (
        forecast(ledger, clock=CLOCK, scenario="base")
        .scenarios["base"]
        .days[1]
        .collections_iqd
        == 70000
    )
    with pytest.raises(FinancialRuleError) as failure:
        forecast(ledger, clock=CLOCK)
    assert failure.value.code == "MISSING_FORECAST_HISTORY"


@pytest.mark.parametrize("invalid", [date(2026, 9, 29), date(2026, 6, 30)])
def test_runtime_observed_boundary_cannot_be_extended_by_business_clock(
    ledger, invalid
):
    with pytest.raises(FinancialRuleError) as failure:
        forecast(ledger, clock=BusinessClock(invalid))
    assert failure.value.code == "VALIDATION_ERROR"


def test_real_file_import_to_production_forecast_vertical_slice(ledger, tmp_path):
    path = tmp_path / "synthetic_history.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "source_id",
                "occurred_at",
                "type",
                "amount_iqd",
                "counterparty_id",
                "obligation_id",
                "due_date",
                "category_id",
                "quantity",
                "description",
            ]
        )
        for offset in range(60):
            day = START + timedelta(days=offset)
            writer.writerow(
                [
                    f"SALE-{offset}",
                    f"{day}T12:00:00+03:00",
                    "CASH_SALE",
                    1000,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "synthetic",
                ]
            )
            writer.writerow(
                [
                    f"COUNT-{offset}",
                    f"{day}T21:00:00+03:00",
                    "DAILY_CASH_COUNT",
                    200000 + (offset + 1) * 1100,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "synthetic",
                ]
            )
    first = import_csv(
        ledger, path, clock=CLOCK, imported_at=f"{CUTOFF}T23:00:00+03:00"
    )
    assert first.accepted == 120
    result = forecast(ledger, clock=CLOCK)
    assert result.scenarios["base"].days[0].closing_iqd == 267100
    assert (
        import_csv(
            ledger, path, clock=CLOCK, imported_at=f"{CUTOFF}T23:01:00+03:00"
        ).exact_duplicates
        == 120
    )
    assert forecast(ledger, clock=CLOCK) == result


def test_t12_production_forecast_uses_no_files_and_ignores_late_cash_knowledge(
    ledger, insert_event, history, monkeypatch
):
    before = forecast(ledger, clock=CLOCK)
    late = CUTOFF + timedelta(days=1)
    sale = insert_event(
        amount_iqd=800000,
        occurred_at=f"{CUTOFF}T10:00:00+03:00",
        recorded_at=f"{late}T10:00:00+03:00",
    )
    insert_event(
        type="DAILY_CASH_COUNT",
        amount_iqd=999999999,
        occurred_at=f"{CUTOFF}T22:00:00+03:00",
        recorded_at=f"{late}T10:00:00+03:00",
    )
    void_entry(
        ledger,
        VoidRequest(client_entry_id="void-late-sale", reason="synthetic"),
        transaction_id=sale.transaction_id,
        voided_at=f"{late}T12:00:00+03:00",
    )
    ledger.commit()

    def forbidden_open(*args, **kwargs):
        raise AssertionError("Production forecast must use SQLite only")

    monkeypatch.setattr(builtins, "open", forbidden_open)
    monkeypatch.setattr(Path, "open", forbidden_open)
    assert forecast(ledger, clock=CLOCK) == before


def test_t12_day90_boundary_with_inline_history_not_final_outcomes(
    ledger, insert_event, history
):
    cash = history
    for offset in range(60, 90):
        day = START + timedelta(days=offset)
        insert_event(amount_iqd=100000, occurred_at=f"{day}T12:00:00+03:00")
        cash += 102000
        insert_event(
            type="DAILY_CASH_COUNT",
            amount_iqd=cash,
            occurred_at=f"{day}T21:00:00+03:00",
        )
    clock = BusinessClock(date(2026, 9, 28))
    ledger.commit()
    before = forecast(ledger, clock=clock)
    insert_event(amount_iqd=999999999, occurred_at="2026-09-29T12:00:00+03:00")
    ledger.commit()
    assert forecast(ledger, clock=clock) == before


@pytest.mark.parametrize(
    "kind,amount,field,expected",
    [
        ("CASH_SALE", 4, "cash_sales_iqd", 100001),
        ("OPERATING_EXPENSE", 14, "expenses_iqd", 10001),
        ("OWNER_DRAWING", 14, "owner_drawings_iqd", 5001),
    ],
)
def test_series_round_half_up_once_without_float_money(
    ledger, insert_event, history, kind, amount, field, expected
):
    wednesday = date(2026, 8, 26)
    insert_event(
        type=kind, amount_iqd=amount, occurred_at=f"{wednesday}T13:00:00+03:00"
    )
    ledger.commit()
    result = forecast(ledger, clock=CLOCK)
    day = next(row for row in result.scenarios["base"].days if row.date.weekday() == 2)
    assert getattr(day, field) == expected
    if kind == "CASH_SALE":
        assert day.unlinked_cash_iqd == -3001  # -3000.5 rounds away from zero


def test_shortfall_lowest_and_top_driver_evidence(ledger, insert_event, history):
    invoice = add_debt(
        ledger,
        insert_event,
        "LARGE-P",
        kind="payable",
        amount=history + 300000,
        due=str(CUTOFF + timedelta(days=2)),
    )
    ledger.commit()
    result = forecast(ledger, clock=CLOCK)
    scenario = result.scenarios["base"]
    assert scenario.first_shortfall_date == CUTOFF + timedelta(days=1)
    assert scenario.lowest.date == CUTOFF + timedelta(days=2)
    assert scenario.lowest.closing_iqd == min(row.closing_iqd for row in scenario.days)
    assert scenario.top_outflows[0].label_key == "supplier_payments"
    assert scenario.top_outflows[0].amount.source_ids == (invoice.source_id,)
    known_ids = {
        r.source_id for r in read_forecast_snapshot(ledger, clock=CLOCK).transactions
    }
    for drivers in (scenario.top_inflows, scenario.top_outflows):
        assert len(drivers) <= 3
        assert [d.amount.amount_iqd for d in drivers] == sorted(
            (d.amount.amount_iqd for d in drivers), reverse=True
        )
        assert all(set(driver.amount.source_ids) <= known_ids for driver in drivers)


def test_t26_each_customer_uses_own_median_and_unknown_uses_shop_median(
    ledger, insert_event, history
):
    ledger.execute(
        """INSERT INTO counterparties
        VALUES ('CUST-03', 'Synthetic third customer', 'customer')"""
    )
    for index, (customer, late) in enumerate(
        [("CUST-01", 2), ("CUST-01", 4), ("CUST-02", 10), ("CUST-02", 12)]
    ):
        due = START + timedelta(days=6 + index * 7)
        origin = add_debt(
            ledger,
            insert_event,
            f"PAID-{index}",
            amount=10000,
            due=str(due),
            occurred=f"{due - timedelta(days=1)}T10:00:00+03:00",
            customer=customer,
        )
        paid = due + timedelta(days=late)
        add_collection(
            ledger,
            insert_event,
            origin,
            source=f"COLL-{index}",
            amount=10000,
            occurred=f"{paid}T10:00:00+03:00",
            linked=f"{paid}T07:00:00+00:00",
        )
    for customer in ("CUST-01", "CUST-02", "CUST-03"):
        add_debt(
            ledger,
            insert_event,
            f"OPEN-{customer}",
            amount=10000,
            due=str(CUTOFF + timedelta(days=2)),
            customer=customer,
        )
    ledger.commit()
    scenario = forecast(ledger, clock=CLOCK).scenarios["conservative"]
    assert [
        (i + 1, row.collections_iqd)
        for i, row in enumerate(scenario.days)
        if row.collections_iqd
    ] == [(5, 10000), (9, 10000), (13, 10000)]


def test_snapshot_is_consistent_when_void_commits_between_table_reads(
    ledger, insert_event, history
):
    origin = add_debt(
        ledger, insert_event, "CONCURRENT", due=str(CUTOFF + timedelta(days=2))
    )
    ledger.commit()
    ledger.execute("PRAGMA journal_mode = WAL")
    db_path = ledger.execute("PRAGMA database_list").fetchone()[2]
    other = connect_database(db_path)
    baseline = forecast(ledger, clock=CLOCK, scenario="base")
    committed = False

    def commit_between_reads(sql):
        nonlocal committed
        if not committed and "SELECT o.* FROM obligations" in sql:
            committed = True
            void_entry(
                other,
                VoidRequest(client_entry_id="concurrent", reason="synthetic"),
                transaction_id=origin.transaction_id,
                voided_at=f"{CUTOFF}T22:00:00+03:00",
            )

    ledger.set_trace_callback(commit_between_reads)
    try:
        assert forecast(ledger, clock=CLOCK, scenario="base") == baseline
    finally:
        ledger.set_trace_callback(None)
        other.close()
    assert committed
    assert (
        forecast(ledger, clock=CLOCK, scenario="base")
        .scenarios["base"]
        .days[1]
        .collections_iqd
        == 0
    )


def test_missing_count_days_are_skipped_without_bridging_or_zero_filling(
    ledger, history
):
    count = ledger.execute(
        """SELECT transaction_id FROM transactions WHERE type = 'DAILY_CASH_COUNT'
        AND business_date = '2026-08-20'"""
    ).fetchone()[0]
    void_entry(
        ledger,
        VoidRequest(client_entry_id="missing-count", reason="synthetic"),
        transaction_id=count,
        voided_at=f"{CUTOFF}T22:00:00+03:00",
    )
    result = forecast(ledger, clock=CLOCK)
    assert all(
        row.unlinked_cash_iqd == (-3000 if row.date.weekday() == 2 else 2000)
        for row in result.scenarios["base"].days
    )


def test_forecast_succeeds_on_query_only_connection(ledger, history):
    ledger.execute("PRAGMA query_only = ON")
    try:
        assert len(forecast(ledger, clock=CLOCK).scenarios["base"].days) == 30
    finally:
        ledger.execute("PRAGMA query_only = OFF")
