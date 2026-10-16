"""Real SQLite audit writes and financial effects (FINANCIAL_RULES §3/§11)."""

import importlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest

from app.db.connection import connect_database
from app.schemas import ledger as models
from app.services import ledger_rules as rules
from app.services.errors import FinancialRuleError

DAY = date(2026, 9, 28)
REVIEWED_AT = "2026-09-28T22:00:00+03:00"


@pytest.fixture
def audit():
    return importlib.import_module("app.services.ledger_audit")


@pytest.fixture
def recorded_close(ledger, insert_event, create_obligation):
    create_obligation(amount=90_000)
    insert_event(
        source_id="PREV",
        type="DAILY_CASH_COUNT",
        amount_iqd=300_000,
        occurred_at="2026-09-27T21:00:00+03:00",
    )
    insert_event(
        source_id="SALE", amount_iqd=120_000, category_id="CAT-01", quantity=20
    )
    insert_event(
        source_id="COLLECT",
        type="CREDIT_COLLECTION",
        amount_iqd=30_000,
        counterparty_id="CUST-01",
        obligation_id="OB-001",
    )
    insert_event(source_id="EXPENSE", type="OPERATING_EXPENSE", amount_iqd=20_000)
    insert_event(source_id="DRAW", type="OWNER_DRAWING", amount_iqd=10_000)
    insert_event(
        source_id="CLOSE",
        type="DAILY_CASH_COUNT",
        amount_iqd=445_000,
        occurred_at="2026-09-28T21:00:00+03:00",
    )
    ledger.commit()


def request(client="REVIEW-1", resolution="capital_injection", amount=25_000):
    return models.DifferenceReviewRequest(
        client_entry_id=client,
        resolution=resolution,
        amount_iqd=amount,
        note="Synthetic review",
    )


def table_counts(ledger):
    return tuple(
        ledger.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in (
            "transactions",
            "raw_import_rows",
            "import_batches",
            "difference_reviews",
            "entry_voids",
        )
    )


def test_t28_capital_review_provenance_replay_and_margin(ledger, recorded_close, audit):
    before = table_counts(ledger)
    first = audit.resolve_difference(
        ledger, request(), business_date=DAY, recorded_at=REVIEWED_AT
    )
    assert first.duplicate is False
    assert first.daily_close.unexplained_difference_iqd == 0
    assert first.daily_close.recorded_cash_sales_iqd == 120_000
    assert first.entry.type == "CAPITAL_INJECTION"
    assert first.entry.source == "daily_close_review"
    assert first.entry.client_entry_id == "REVIEW-1"
    assert first.entry.business_date == DAY
    assert rules.event_effect(first.entry).revenue_delta_iqd == 0
    snapshot = audit.read_ledger(ledger)
    assert (
        rules.cash_on_hand(
            snapshot.transactions, as_of=DAY, voids=snapshot.voids
        ).amount_iqd
        == 445_000
    )
    sale = next(r for r in snapshot.transactions if r.source_id == "SALE")
    assert rules.event_effect(sale).revenue_delta_iqd - sale.quantity * 1_000 == 100_000
    raw = ledger.execute(
        "SELECT row_json FROM raw_import_rows WHERE import_batch_id = ?",
        (first.entry.import_batch_id,),
    ).fetchone()[0]
    assert json.loads(raw)["client_entry_id"] == "REVIEW-1"
    after = table_counts(ledger)
    assert after == tuple(n + d for n, d in zip(before, (1, 1, 1, 1, 0), strict=True))
    second = audit.resolve_difference(
        ledger, request(), business_date=DAY, recorded_at="2026-09-28T23:00:00+03:00"
    )
    assert second.duplicate is True
    assert second.entry == first.entry
    assert second.daily_close.unexplained_difference_iqd == 0
    assert table_counts(ledger) == after
    with pytest.raises(FinancialRuleError, match="VALIDATION_ERROR"):
        audit.resolve_difference(
            ledger, request(amount=20_000), business_date=DAY, recorded_at=REVIEWED_AT
        )
    assert table_counts(ledger) == after


def test_review_partial_remaining_and_leave_unexplained(ledger, recorded_close, audit):
    first = audit.resolve_difference(
        ledger, request(amount=10_000), business_date=DAY, recorded_at=REVIEWED_AT
    )
    assert first.daily_close.unexplained_difference_iqd == 15_000
    leave = request("LEAVE", "leave_unexplained", None)
    result = audit.resolve_difference(
        ledger, leave, business_date=DAY, recorded_at=REVIEWED_AT
    )
    assert result.entry is None
    assert result.daily_close.unexplained_difference_iqd == 15_000
    assert audit.resolve_difference(
        ledger, leave, business_date=DAY, recorded_at=REVIEWED_AT
    ).duplicate
    final = audit.resolve_difference(
        ledger,
        request("REVIEW-2", amount=15_000),
        business_date=DAY,
        recorded_at=REVIEWED_AT,
    )
    assert final.daily_close.unexplained_difference_iqd == 0
    assert ledger.execute("SELECT COUNT(*) FROM difference_reviews").fetchone()[0] == 3


@pytest.mark.parametrize(
    ("resolution", "amount", "code"),
    [
        ("expense_unrecorded", 25_000, "DIFFERENCE_SIGN_MISMATCH"),
        ("owner_drawing_unrecorded", 25_000, "DIFFERENCE_SIGN_MISMATCH"),
        ("capital_injection", 25_001, "DIFFERENCE_EXCEEDED"),
    ],
)
def test_t34_invalid_review_changes_no_ledger(
    ledger, recorded_close, audit, resolution, amount, code
):
    before = table_counts(ledger)
    with pytest.raises(FinancialRuleError) as error:
        audit.resolve_difference(
            ledger,
            request(resolution=resolution, amount=amount),
            business_date=DAY,
            recorded_at=REVIEWED_AT,
        )
    assert error.value.code == code
    assert table_counts(ledger) == before


@pytest.mark.parametrize(
    "resolution", ["expense_unrecorded", "owner_drawing_unrecorded"]
)
def test_negative_review_reduces_outflow_gap_without_changing_sales(
    ledger, recorded_close, insert_event, audit, resolution
):
    original = next(
        r for r in audit.read_ledger(ledger).transactions if r.source_id == "CLOSE"
    )
    audit.void_entry(
        ledger,
        models.VoidRequest(
            client_entry_id="VOID-CLOSE", reason="Synthetic count correction"
        ),
        transaction_id=original.transaction_id,
        voided_at=REVIEWED_AT,
    )
    insert_event(
        source_id="LOW-CLOSE",
        type="DAILY_CASH_COUNT",
        amount_iqd=395_000,
        occurred_at="2026-09-28T21:00:00+03:00",
    )
    ledger.commit()
    result = audit.resolve_difference(
        ledger,
        request(resolution=resolution),
        business_date=DAY,
        recorded_at=REVIEWED_AT,
    )
    assert result.daily_close.unexplained_difference_iqd == 0
    assert result.daily_close.expected_close_iqd == 395_000
    assert result.daily_close.recorded_cash_sales_iqd == 120_000
    assert rules.event_effect(result.entry).cash_delta_iqd == -25_000


def test_cash_sale_review_is_unpriced_and_only_records_confirmed_amount(
    ledger, recorded_close, audit
):
    result = audit.resolve_difference(
        ledger,
        request(resolution="cash_sale_unitemized"),
        business_date=DAY,
        recorded_at=REVIEWED_AT,
    )
    assert result.entry.type == "CASH_SALE"
    assert result.entry.category_id is result.entry.quantity is None
    assert result.daily_close.recorded_cash_sales_iqd == 145_000
    assert result.daily_close.unexplained_difference_iqd == 0


@pytest.mark.parametrize("resolution", ["capital_injection", "leave_unexplained"])
def test_review_missing_counts_fails_without_any_writes(ledger, audit, resolution):
    before = table_counts(ledger)
    with pytest.raises(FinancialRuleError, match="MISSING_COUNT"):
        audit.resolve_difference(
            ledger,
            request(
                resolution=resolution,
                amount=None if resolution == "leave_unexplained" else 25_000,
            ),
            business_date=DAY,
            recorded_at=REVIEWED_AT,
        )
    assert table_counts(ledger) == before


def test_review_write_failure_rolls_back_all_evidence(ledger, recorded_close, audit):
    before = table_counts(ledger)
    ledger.execute(
        "CREATE TRIGGER reject_review BEFORE INSERT ON difference_reviews "
        "BEGIN SELECT RAISE(ABORT, 'injected failure'); END"
    )
    with pytest.raises(sqlite3.IntegrityError, match="injected failure"):
        audit.resolve_difference(
            ledger, request(), business_date=DAY, recorded_at=REVIEWED_AT
        )
    assert table_counts(ledger) == before
    assert not ledger.in_transaction


def test_audit_savepoint_preserves_callers_pending_work(ledger, recorded_close, audit):
    ledger.execute(
        "INSERT INTO counterparties VALUES ('PENDING', 'Synthetic pending', 'customer')"
    )
    audit.resolve_difference(
        ledger, request(), business_date=DAY, recorded_at=REVIEWED_AT
    )
    assert ledger.in_transaction
    ledger.rollback()
    assert ledger.execute("SELECT COUNT(*) FROM difference_reviews").fetchone()[0] == 0
    assert (
        ledger.execute(
            "SELECT * FROM counterparties WHERE counterparty_id = 'PENDING'"
        ).fetchone()
        is None
    )


def link(ledger, payment, amount, link_id):
    created_at = max("2026-09-28T12:00:00+00:00", payment.recorded_at.isoformat())
    ledger.execute(
        "INSERT INTO payment_links VALUES (?, ?, ?, ?, ?, ?)",
        (link_id, payment.transaction_id, "OB-001", amount, "confirmed", created_at),
    )


def test_t27_three_instalments_void_correction_cutoffs_and_evidence(
    ledger, create_obligation, insert_event, audit
):
    create_obligation(amount=90_000)
    payments = []
    for index, amount in enumerate((30_000, 25_000, 35_000)):
        p = insert_event(
            source_id=f"PAY-{index}",
            type="CREDIT_COLLECTION",
            amount_iqd=amount,
            counterparty_id="CUST-01",
            obligation_id="OB-001",
        )
        link(ledger, p, amount, f"LINK-{index}")
        payments.append(p)
    ledger.commit()
    original = dict(
        ledger.execute(
            "SELECT * FROM transactions WHERE transaction_id = ?",
            (payments[1].transaction_id,),
        ).fetchone()
    )
    raw = [
        tuple(r)
        for r in ledger.execute("SELECT * FROM raw_import_rows ORDER BY raw_row_id")
    ]
    void_request = models.VoidRequest(
        client_entry_id="VOID-CLIENT", reason="Synthetic wrong amount"
    )
    voided = audit.void_entry(
        ledger,
        void_request,
        transaction_id=payments[1].transaction_id,
        voided_at="2026-09-28T20:00:00+03:00",
    )
    assert not voided.duplicate
    assert voided.audit.source_id == payments[1].source_id
    assert voided.audit.reason == "Synthetic wrong amount"
    assert audit.void_entry(
        ledger,
        void_request,
        transaction_id=payments[1].transaction_id,
        voided_at=REVIEWED_AT,
    ).duplicate
    with pytest.raises(FinancialRuleError, match="VALIDATION_ERROR"):
        audit.void_entry(
            ledger,
            models.VoidRequest(client_entry_id="VOID-CLIENT", reason="Changed reason"),
            transaction_id=payments[1].transaction_id,
            voided_at=REVIEWED_AT,
        )
    new = insert_event(
        source_id="CORRECT",
        type="CREDIT_COLLECTION",
        amount_iqd=20_000,
        counterparty_id="CUST-01",
        obligation_id="OB-001",
        recorded_at="2026-09-28T20:01:00+03:00",
    )
    link(ledger, new, 20_000, "LINK-CORRECT")
    ledger.commit()
    snapshot = audit.read_ledger(ledger)
    obligation = snapshot.obligations[0]

    def balance(known_at):
        return rules.obligation_outstanding(
            obligation,
            snapshot.transactions,
            snapshot.payment_links,
            as_of=DAY,
            voids=snapshot.voids,
            known_at=known_at,
        )

    assert balance("2026-09-28T19:00:00+03:00") == 0
    assert balance("2026-09-28T20:00:00+03:00") == 25_000
    assert balance("2026-09-28T21:00:00+03:00") == 5_000
    # Independently reproduce the current balance from the schema alone.
    cutoff = "2026-09-28T18:00:00+00:00"
    sql_balance = ledger.execute(
        """SELECT o.original_amount_iqd - COALESCE((
        SELECT SUM(l.amount_iqd) FROM payment_links l
        JOIN transactions p ON p.transaction_id = l.payment_transaction_id
        WHERE l.obligation_id = o.obligation_id AND l.created_at <= ?
        AND p.recorded_at <= ? AND p.business_date <= ?
        AND NOT EXISTS (SELECT 1 FROM entry_voids v
            WHERE v.transaction_id = p.transaction_id AND v.voided_at <= ?)
    ), 0) FROM obligations o WHERE o.obligation_id = 'OB-001'""",
        (cutoff, cutoff, DAY.isoformat(), cutoff),
    ).fetchone()[0]
    assert sql_balance == 5_000
    cash = sum(
        rules.event_effect(t).cash_delta_iqd
        for t in rules.active_transactions(
            snapshot.transactions, as_of=DAY, voids=snapshot.voids
        )
    )
    assert cash == 85_000
    assert (
        dict(
            ledger.execute(
                "SELECT * FROM transactions WHERE transaction_id = ?",
                (payments[1].transaction_id,),
            ).fetchone()
        )
        == original
    )
    assert [
        tuple(r)
        for r in ledger.execute("SELECT * FROM raw_import_rows ORDER BY raw_row_id")
        if r[0] != f"RAW-{new.source_row}"
    ] == raw
    assert len(snapshot.payment_links) == 4
    assert ledger.execute("SELECT COUNT(*) FROM entry_voids").fetchone()[0] == 1
    for statement in (
        "DELETE FROM entry_voids",
        "UPDATE entry_voids SET reason = 'changed'",
        "INSERT OR REPLACE INTO entry_voids SELECT * FROM entry_voids",
        "DELETE FROM transactions",
        "DELETE FROM payment_links",
        "DELETE FROM raw_import_rows",
    ):
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            ledger.execute(statement)


def test_void_rejects_wrong_source_missing_target_and_prior_timestamp(
    ledger, insert_event, audit
):
    event = insert_event()
    ledger.commit()
    req = models.VoidRequest(client_entry_id="VOID", reason="Synthetic correction")
    with pytest.raises(FinancialRuleError, match="NOT_FOUND"):
        audit.void_entry(ledger, req, transaction_id="MISSING", voided_at=REVIEWED_AT)
    with pytest.raises(FinancialRuleError, match="VALIDATION_ERROR"):
        audit.void_entry(
            ledger,
            req,
            transaction_id=event.transaction_id,
            voided_at="2026-09-27T12:00:00+03:00",
        )
    with pytest.raises(sqlite3.IntegrityError):
        ledger.execute(
            "INSERT INTO entry_voids VALUES (?, ?, ?, ?, ?, ?)",
            (
                "BAD",
                event.transaction_id,
                "WRONG-SOURCE",
                "BAD-CLIENT",
                "Synthetic",
                "2026-09-28T20:00:00+00:00",
            ),
        )
    assert ledger.execute("SELECT COUNT(*) FROM entry_voids").fetchone()[0] == 0


@pytest.mark.parametrize(
    ("resolution", "amount", "error"),
    [
        ("expense_unrecorded", 25_000, "DIFFERENCE_SIGN_MISMATCH"),
        ("capital_injection", 25_001, "DIFFERENCE_EXCEEDED"),
        ("capital_injection", 25_000, None),
    ],
)
def test_database_independently_validates_review_sign_amount_and_provenance(
    ledger,
    recorded_close,
    transaction_factory,
    resolution,
    amount,
    error,
):
    before = table_counts(ledger)

    def write_sql():
        with ledger:
            ledger.execute(
                """INSERT INTO import_batches VALUES
                ('SQL-BATCH', 'synthetic_entry', 'aggregate_cash', ?, ?,
                 1, 1, 0, 0, 'completed')""",
                ("b" * 64, "2026-09-28T19:00:00+00:00"),
            )
            ledger.execute(
                "INSERT INTO raw_import_rows VALUES (?, ?, ?, ?, ?, ?)",
                ("SQL-RAW", "SQL-BATCH", 1, '{"synthetic":true}', "[]", "accepted"),
            )
            entry = transaction_factory(
                "SQL-ENTRY",
                type="OPERATING_EXPENSE"
                if resolution == "expense_unrecorded"
                else "CAPITAL_INJECTION",
                amount_iqd=amount,
                source_system="synthetic_entry",
                source="daily_close_review",
                client_entry_id="SQL-CLIENT",
                import_batch_id="SQL-BATCH",
                occurred_at="2026-09-28T21:00:00+03:00",
                recorded_at=REVIEWED_AT,
            )
            payload = entry.model_dump(mode="json")
            columns = ", ".join(payload)
            params = ", ".join(f":{k}" for k in payload)
            ledger.execute(
                f"INSERT INTO transactions ({columns}) VALUES ({params})", payload
            )
            ledger.execute(
                """INSERT INTO difference_reviews VALUES
                ('SQL-REVIEW', 'SQL-CLIENT', '2026-09-28', ?, ?, NULL, ?,
                 'PREV', 'CLOSE', 'SQL-ENTRY')""",
                (resolution, amount, "2026-09-28T19:00:00+00:00"),
            )

    if error:
        with pytest.raises(sqlite3.IntegrityError, match=error):
            write_sql()
        assert table_counts(ledger) == before
    else:
        write_sql()
        rows = tuple(
            models.Transaction.model_validate(dict(r))
            for r in ledger.execute("SELECT * FROM transactions")
        )
        assert (
            rules.daily_close(rows, business_date=DAY).unexplained_difference_iqd == 0
        )
        assert rules.recorded_cash_sales(rows, as_of=DAY) == 120_000
        for statement in (
            "DELETE FROM difference_reviews",
            "UPDATE difference_reviews SET note = 'changed'",
            "INSERT OR REPLACE INTO difference_reviews "
            "SELECT * FROM difference_reviews",
        ):
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                ledger.execute(statement)


def test_sql_review_requires_consecutive_active_counts(ledger):
    with pytest.raises(sqlite3.IntegrityError, match="MISSING_COUNT"):
        ledger.execute("""INSERT INTO difference_reviews VALUES
            ('REVIEW', 'CLIENT', '2026-09-28', 'leave_unexplained', NULL, NULL,
             '2026-09-28T19:00:00+00:00', 'MISSING-PREV', 'MISSING-CLOSE', NULL)""")


def test_review_after_zero_and_after_void_recomputes_from_events(
    ledger, recorded_close, audit
):
    first = audit.resolve_difference(
        ledger, request(), business_date=DAY, recorded_at=REVIEWED_AT
    )
    with pytest.raises(FinancialRuleError, match="DIFFERENCE_EXCEEDED"):
        audit.resolve_difference(
            ledger,
            request("EXTRA", amount=1),
            business_date=DAY,
            recorded_at=REVIEWED_AT,
        )
    audit.void_entry(
        ledger,
        models.VoidRequest(
            client_entry_id="VOID-REVIEW", reason="Synthetic correction"
        ),
        transaction_id=first.entry.transaction_id,
        voided_at=REVIEWED_AT,
    )
    second = audit.resolve_difference(
        ledger, request("REPLACEMENT"), business_date=DAY, recorded_at=REVIEWED_AT
    )
    assert second.daily_close.unexplained_difference_iqd == 0
    assert second.daily_close.recorded_cash_sales_iqd == 120_000
    assert len(audit.read_ledger(ledger).reviews) == 2


@pytest.mark.parametrize(
    ("kind", "event", "counterparty"),
    [
        ("receivable", "CREDIT_COLLECTION", "CUST-01"),
        ("payable", "SUPPLIER_PAYMENT", "SUP-01"),
    ],
)
def test_void_restores_receivable_and_payable_without_relinking(
    ledger,
    create_obligation,
    insert_event,
    audit,
    kind,
    event,
    counterparty,
):
    origin = create_obligation(kind=kind, amount=90_000)
    payment = insert_event(
        type=event,
        amount_iqd=30_000,
        counterparty_id=counterparty,
        obligation_id="OB-001",
    )
    link(ledger, payment, 30_000, "LINK")
    ledger.commit()
    audit.void_entry(
        ledger,
        models.VoidRequest(client_entry_id="VOID-PAY", reason="Synthetic correction"),
        transaction_id=payment.transaction_id,
        voided_at="2026-09-29T10:00:00+03:00",
    )
    snapshot = audit.read_ledger(ledger)
    assert (
        rules.obligation_outstanding(
            snapshot.obligations[0],
            snapshot.transactions,
            snapshot.payment_links,
            as_of=DAY,
            voids=snapshot.voids,
        )
        == 60_000
    )
    assert (
        rules.obligation_outstanding(
            snapshot.obligations[0],
            snapshot.transactions,
            snapshot.payment_links,
            as_of=date(2026, 9, 29),
            voids=snapshot.voids,
        )
        == 90_000
    )
    audit.void_entry(
        ledger,
        models.VoidRequest(
            client_entry_id="VOID-ORIGIN", reason="Synthetic origin correction"
        ),
        transaction_id=origin.transaction_id,
        voided_at="2026-09-29T11:00:00+03:00",
    )
    snapshot = audit.read_ledger(ledger)
    assert (
        rules.obligation_outstanding(
            snapshot.obligations[0],
            snapshot.transactions,
            snapshot.payment_links,
            as_of=date(2026, 9, 29),
            voids=snapshot.voids,
        )
        is None
    )
    assert (
        ledger.execute("SELECT payment_transaction_id FROM payment_links").fetchone()[0]
        == payment.transaction_id
    )


def test_concurrent_review_requests_cannot_explain_the_same_cash_twice(
    ledger, recorded_close, audit
):
    path = ledger.execute("PRAGMA database_list").fetchone()[2]

    def write(client):
        connection = connect_database(path)
        try:
            audit.resolve_difference(
                connection,
                request(client, amount=20_000),
                business_date=DAY,
                recorded_at=REVIEWED_AT,
            )
            return "saved"
        except FinancialRuleError as error:
            return error.code
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = sorted(executor.map(write, ("RACE-A", "RACE-B")))
    assert results == ["DIFFERENCE_EXCEEDED", "saved"]
    snapshot = audit.read_ledger(ledger)
    assert (
        rules.daily_close(
            snapshot.transactions, business_date=DAY
        ).unexplained_difference_iqd
        == 5_000
    )
    assert len(snapshot.reviews) == 1


def test_late_verified_link_is_only_applied_after_its_knowledge_time(
    ledger,
    create_obligation,
    insert_event,
    audit,
):
    create_obligation(amount=90_000)
    payment = insert_event(
        type="CREDIT_COLLECTION",
        amount_iqd=30_000,
        counterparty_id="CUST-01",
        obligation_id="OB-001",
    )
    ledger.execute(
        "INSERT INTO payment_links VALUES (?, ?, ?, ?, ?, ?)",
        (
            "LATE-LINK",
            payment.transaction_id,
            "OB-001",
            30_000,
            "confirmed",
            "2026-09-29T07:00:00+00:00",
        ),
    )
    ledger.commit()
    snapshot = audit.read_ledger(ledger)
    assert (
        rules.obligation_outstanding(
            snapshot.obligations[0],
            snapshot.transactions,
            snapshot.payment_links,
            as_of=DAY,
            voids=snapshot.voids,
        )
        == 90_000
    )
    assert (
        rules.obligation_outstanding(
            snapshot.obligations[0],
            snapshot.transactions,
            snapshot.payment_links,
            as_of=DAY,
            known_at="2026-09-29T11:00:00+03:00",
        )
        == 60_000
    )


def test_ledger_read_is_one_snapshot_during_a_concurrent_review(
    ledger,
    recorded_close,
    audit,
):
    assert ledger.execute("PRAGMA journal_mode = WAL").fetchone()[0] == "wal"
    writer = connect_database(ledger.execute("PRAGMA database_list").fetchone()[2])
    written = False

    def commit_between_table_reads(sql):
        nonlocal written
        if sql.startswith("SELECT * FROM obligations") and not written:
            written = True
            audit.resolve_difference(
                writer,
                request("CONCURRENT-REVIEW"),
                business_date=DAY,
                recorded_at=REVIEWED_AT,
            )

    ledger.set_trace_callback(commit_between_table_reads)
    try:
        snapshot = audit.read_ledger(ledger)
    finally:
        ledger.set_trace_callback(None)
        writer.close()
    assert written
    ids = {row.transaction_id for row in snapshot.transactions}
    assert all(review.transaction_id in ids for review in snapshot.reviews)
    assert snapshot.reviews == ()
    assert ledger.execute("SELECT COUNT(*) FROM difference_reviews").fetchone()[0] == 1
    assert not ledger.in_transaction
