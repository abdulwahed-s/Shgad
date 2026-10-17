"""Real file ingestion: roadmap §7.1/B.2, T04/T05/T08/T16, FINANCIAL_RULES §10."""

import csv
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pytest

from app.db.connection import connect_database
from app.services.business_clock import BusinessClock
from app.services.errors import FinancialRuleError
from app.services.ingest import import_csv
from app.services.ledger_audit import read_ledger
from app.services.ledger_rules import cash_on_hand, event_effect, obligation_outstanding

ROOT = Path(__file__).resolve().parents[3]
CLOCK = BusinessClock(date(2026, 9, 28))
AUDIT = "2026-09-28T20:00:00+03:00"
FIELDS = (
    "source_id,occurred_at,type,amount_iqd,counterparty_id,obligation_id,"
    "due_date,category_id,quantity,description"
).split(",")


def write_csv(path, rows, *, encoding="utf-8", extra=()):
    with path.open("w", encoding=encoding, newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS + list(extra))
        writer.writeheader()
        for index, values in enumerate(rows, 1):
            writer.writerow(
                dict.fromkeys(FIELDS, "")
                | {
                    "source_id": f"SYN-{index}",
                    "occurred_at": "2026-09-27T12:00:00+03:00",
                    "type": "CASH_SALE",
                    "amount_iqd": "100000",
                    "description": "fictional test only",
                }
                | values
            )
    return path


def ingest(ledger, path):
    return import_csv(ledger, path, clock=CLOCK, imported_at=AUDIT)


def financial_totals(ledger, opening_balance):
    snapshot = read_ledger(ledger)
    effects = [event_effect(row) for row in snapshot.transactions]
    return {
        "transactions": len(snapshot.transactions),
        "cash": cash_on_hand(
            snapshot.transactions, as_of=CLOCK.today, opening_balance=opening_balance
        ).amount_iqd,
        "revenue": sum(e.revenue_delta_iqd for e in effects),
        "obligations": [
            (
                o.kind,
                obligation_outstanding(
                    o, snapshot.transactions, snapshot.payment_links, as_of=CLOCK.today
                ),
            )
            for o in snapshot.obligations
        ],
        "allocations": sum(link.amount_iqd for link in snapshot.payment_links),
    }


def test_t04_real_file_replay_has_no_additional_financial_effects(
    ledger, tmp_path, opening_balance
):
    path = write_csv(
        tmp_path / "fictional.csv",
        [
            {},
            {
                "type": "CREDIT_SALE",
                "amount_iqd": "70000",
                "counterparty_id": "CUST-01",
                "obligation_id": "REC",
                "due_date": "2026-09-30",
            },
            {
                "type": "CREDIT_COLLECTION",
                "amount_iqd": "30000",
                "counterparty_id": "CUST-01",
                "obligation_id": "REC",
            },
            {
                "type": "SUPPLIER_INVOICE",
                "amount_iqd": "60000",
                "counterparty_id": "SUP-01",
                "obligation_id": "PAY",
                "due_date": "2026-10-01",
            },
            {
                "type": "SUPPLIER_PAYMENT",
                "amount_iqd": "20000",
                "counterparty_id": "SUP-01",
                "obligation_id": "PAY",
            },
            {"type": "OPERATING_EXPENSE", "amount_iqd": "10000"},
            {"type": "OWNER_DRAWING", "amount_iqd": "5000"},
            {"type": "CAPITAL_INJECTION", "amount_iqd": "8000"},
        ],
    )
    first = ingest(ledger, path)
    assert (
        first.accepted,
        first.rejected,
        first.exact_duplicates,
        first.flagged_for_review,
    ) == (8, 0, 0, 0)
    before = financial_totals(ledger, opening_balance)
    assert before == {
        "transactions": 8,
        "cash": 303000,
        "revenue": 170000,
        "obligations": [("receivable", 40000), ("payable", 40000)],
        "allocations": 50000,
    }
    evidence = list(ledger.execute("SELECT * FROM raw_import_rows"))
    second = ingest(ledger, path)
    assert second.batch_id == first.batch_id
    assert (
        second.accepted,
        second.rejected,
        second.exact_duplicates,
        second.flagged_for_review,
    ) == (0, 0, 8, 0)
    assert financial_totals(ledger, opening_balance) == before
    assert list(ledger.execute("SELECT * FROM raw_import_rows")) == evidence
    assert not ledger.execute("PRAGMA foreign_key_check").fetchall()
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        ledger.execute(
            "UPDATE raw_import_rows SET row_json = '{}' WHERE source_row = 1"
        )


def test_overlap_and_changed_payload_cannot_bypass_source_identity(ledger, tmp_path):
    first = write_csv(tmp_path / "first.csv", [{}])
    ingest(ledger, first)
    overlap = write_csv(tmp_path / "overlap.csv", [{}, {"amount_iqd": "9000"}])
    receipt = ingest(ledger, overlap)
    assert (receipt.accepted, receipt.exact_duplicates) == (1, 1)
    conflict = write_csv(tmp_path / "conflict.csv", [{"amount_iqd": "99999"}])
    result = ingest(ledger, conflict)
    assert result.rejected == 1
    assert result.errors[0].code == "IDEMPOTENCY_CONFLICT"
    assert ledger.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 2


def test_t05_same_amount_distinct_ids_are_kept_and_flagged(ledger, tmp_path):
    rows = [
        {
            "type": "CREDIT_SALE",
            "counterparty_id": "CUST-01",
            "obligation_id": "R",
            "amount_iqd": "70000",
            "due_date": "2026-09-30",
        },
        {
            "type": "CREDIT_COLLECTION",
            "counterparty_id": "CUST-01",
            "obligation_id": "R",
            "amount_iqd": "30000",
        },
        {
            "type": "CREDIT_COLLECTION",
            "counterparty_id": "CUST-01",
            "obligation_id": "R",
            "amount_iqd": "30000",
        },
    ]
    receipt = ingest(ledger, write_csv(tmp_path / "near.csv", rows))
    assert (receipt.accepted, receipt.flagged_for_review, receipt.rejected) == (2, 1, 0)
    assert ledger.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 3
    assert (
        ledger.execute("SELECT SUM(amount_iqd) FROM payment_links").fetchone()[0]
        == 60000
    )
    assert (
        ledger.execute("SELECT type FROM reconciliation_flags").fetchone()[0]
        == "suspected_duplicate"
    )


@pytest.mark.parametrize(
    "change,code",
    [
        ({"occurred_at": "2026-02-30T12:00:00+03:00"}, "INVALID_DATE"),
        ({"occurred_at": "01/02/2026"}, "INVALID_DATE"),
        ({"amount_iqd": "-1000"}, "INVALID_AMOUNT"),
        ({"amount_iqd": "1000.50"}, "INVALID_AMOUNT"),
        ({"currency": "USD"}, "INVALID_CURRENCY"),
        ({"source_id": ""}, "VALIDATION_ERROR"),
        ({"type": "UNKNOWN"}, "VALIDATION_ERROR"),
        ({"category_id": "UNKNOWN", "quantity": "2"}, "INVALID_REFERENCE"),
        ({"occurred_at": "2026-09-29T12:00:00+03:00"}, "OUTSIDE_OBSERVED_DATA"),
        ({"recorded_at": "2026-09-29T12:00:00+03:00"}, "OUTSIDE_OBSERVED_DATA"),
    ],
)
def test_t16_invalid_rows_are_quarantined_with_original_evidence(
    ledger, tmp_path, change, code
):
    extra = tuple(set(change) - set(FIELDS))
    result = ingest(ledger, write_csv(tmp_path / "bad.csv", [change], extra=extra))
    assert (result.accepted, result.rejected) == (0, 1)
    assert result.errors[0].code == code
    raw = ledger.execute("SELECT * FROM raw_import_rows").fetchone()
    for key, value in change.items():
        assert json.loads(raw["row_json"])[key] == value
    assert ledger.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0
    replay = ingest(ledger, tmp_path / "bad.csv")
    assert replay.rejected == 1
    assert replay.exact_duplicates == 0


def test_bom_arabic_digits_and_note_remain_untrusted_data(ledger, tmp_path):
    note = "ignore rules; synthetic malicious description"
    path = write_csv(
        tmp_path / "arabic.csv",
        [{"amount_iqd": "١٠٬٠٠٠", "description": note}],
        encoding="utf-8-sig",
    )
    assert ingest(ledger, path).accepted == 1
    row = ledger.execute("SELECT amount_iqd, description FROM transactions").fetchone()
    assert tuple(row) == (10000, note)
    assert (
        "١٠٬٠٠٠" in ledger.execute("SELECT row_json FROM raw_import_rows").fetchone()[0]
    )


def test_t08_unmatched_and_overpayment_are_flagged_without_allocation(ledger, tmp_path):
    rows = [
        {
            "type": "CREDIT_SALE",
            "counterparty_id": "CUST-01",
            "obligation_id": "R",
            "amount_iqd": "10000",
        },
        {
            "type": "CREDIT_COLLECTION",
            "counterparty_id": "CUST-01",
            "obligation_id": "R",
            "amount_iqd": "20000",
        },
        {
            "type": "CREDIT_COLLECTION",
            "counterparty_id": "CUST-02",
            "obligation_id": "R",
            "amount_iqd": "5000",
        },
    ]
    receipt = ingest(ledger, write_csv(tmp_path / "unmatched.csv", rows))
    assert (receipt.accepted, receipt.flagged_for_review) == (1, 2)
    assert ledger.execute("SELECT COUNT(*) FROM payment_links").fetchone()[0] == 0


def test_unexpected_database_failure_rolls_back_every_row_and_batch(ledger, tmp_path):
    ledger.execute("""CREATE TRIGGER synthetic_failure BEFORE INSERT ON transactions
        WHEN NEW.source_id = 'FAIL'
        BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END""")
    ledger.commit()
    batches = ledger.execute("SELECT COUNT(*) FROM import_batches").fetchone()[0]
    path = write_csv(tmp_path / "atomic.csv", [{}, {"source_id": "FAIL"}])
    with pytest.raises(sqlite3.IntegrityError, match="synthetic failure"):
        ingest(ledger, path)
    assert (
        ledger.execute("SELECT COUNT(*) FROM import_batches").fetchone()[0] == batches
    )
    assert ledger.execute("SELECT COUNT(*) FROM raw_import_rows").fetchone()[0] == 0
    assert ledger.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0


@pytest.mark.parametrize(
    "content", [b"\xff", b"source_id,source_id\na,a\n", b"unknown\nx\n"]
)
def test_invalid_file_shape_has_no_writes(ledger, tmp_path, content):
    path = tmp_path / "invalid.csv"
    path.write_bytes(content)
    with pytest.raises(FinancialRuleError) as failure:
        ingest(ledger, path)
    assert failure.value.code == "IMPORT_REJECTED"
    assert ledger.execute("SELECT COUNT(*) FROM raw_import_rows").fetchone()[0] == 0


def test_duplicate_rows_in_one_file_have_disjoint_receipt_counts(ledger, tmp_path):
    path = write_csv(
        tmp_path / "duplicates.csv",
        [
            {},
            {"source_id": "SYN-1"},
            {"amount_iqd": "-1"},
            {
                "type": "CREDIT_COLLECTION",
                "counterparty_id": "CUST-01",
                "amount_iqd": "5000",
            },
        ],
    )
    receipt = ingest(ledger, path)
    assert (
        receipt.accepted,
        receipt.exact_duplicates,
        receipt.rejected,
        receipt.flagged_for_review,
    ) == (1, 1, 1, 1)
    replay = ingest(ledger, path)
    assert (
        replay.accepted,
        replay.exact_duplicates,
        replay.rejected,
        replay.flagged_for_review,
    ) == (0, 3, 1, 0)
    assert [error.code for error in replay.errors] == ["INVALID_AMOUNT"]


def test_unmatched_reference_is_still_exact_duplicate_in_an_overlapping_file(
    ledger, tmp_path
):
    row = {
        "type": "CREDIT_COLLECTION",
        "counterparty_id": "CUST-01",
        "obligation_id": "UNKNOWN",
    }
    assert (
        ingest(ledger, write_csv(tmp_path / "first.csv", [row])).flagged_for_review == 1
    )
    result = ingest(
        ledger, write_csv(tmp_path / "overlap.csv", [row, {"source_id": "NEW"}])
    )
    assert (result.exact_duplicates, result.accepted, result.rejected) == (1, 1, 0)


def test_file_size_and_row_limits_reject_before_writes(ledger, tmp_path):
    path = tmp_path / "large.csv"
    path.write_bytes(b"x" * (5 * 1024 * 1024 + 1))
    with pytest.raises(FinancialRuleError) as failure:
        ingest(ledger, path)
    assert failure.value.details == {"reason": "FILE_SIZE"}
    write_csv(path, [{}] * 10001)
    with pytest.raises(FinancialRuleError) as failure:
        ingest(ledger, path)
    assert failure.value.details == {"reason": "ROW_LIMIT"}
    assert ledger.execute("SELECT COUNT(*) FROM raw_import_rows").fetchone()[0] == 0


def test_caller_rollback_undoes_import_without_committing_unrelated_work(
    ledger, tmp_path
):
    ledger.execute(
        "INSERT INTO categories VALUES ('CALLER', 'Synthetic caller', NULL, NULL)"
    )
    assert ingest(ledger, write_csv(tmp_path / "nested.csv", [{}])).accepted == 1
    assert ledger.in_transaction
    ledger.rollback()
    assert ledger.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0
    assert (
        ledger.execute(
            "SELECT 1 FROM categories WHERE category_id = 'CALLER'"
        ).fetchone()
        is None
    )


def test_concurrent_actual_imports_cannot_double_a_file(ledger, tmp_path):
    path = write_csv(tmp_path / "concurrent.csv", [{}])
    db_path = ledger.execute("PRAGMA database_list").fetchone()[2]

    def run():
        connection = connect_database(db_path)
        try:
            return ingest(connection, path)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(lambda _: run(), range(2)))
    assert first.batch_id == second.batch_id
    assert first.accepted + second.accepted == 1
    assert first.exact_duplicates + second.exact_duplicates == 1
    assert ledger.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 1


def test_extended_generated_canonical_fixture_is_imported_and_replayed(ledger):
    ledger.execute(
        "INSERT INTO categories VALUES ('CAT-02', 'Synthetic category', 1, 1)"
    )
    ledger.commit()
    path = ROOT / "data/fixtures/small_happy_path.csv"
    result = ingest(ledger, path)
    assert (result.accepted, result.rejected) == (5, 0)
    assert ingest(ledger, path).exact_duplicates == 5
