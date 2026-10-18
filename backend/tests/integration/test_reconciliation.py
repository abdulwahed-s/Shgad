"""§7.2/FINANCIAL_RULES §10: deterministic settlement, flags and no fuzzy links."""

import csv
import io
from datetime import date, datetime
from pathlib import Path

import pytest

from app.services.ledger_audit import read_ledger
from app.services.ledger_rules import cash_on_hand, obligation_outstanding

FIELDS = (
    "source_id,occurred_at,type,amount_iqd,counterparty_id,obligation_id,"
    "due_date,category_id,quantity,description"
).split(",")


def import_rows(api, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    for index, row in enumerate(rows, 1):
        writer.writerow(
            dict.fromkeys(FIELDS, "")
            | {
                "source_id": f"REC-{index}",
                "occurred_at": "2026-09-27T12:00:00+03:00",
                "type": "CASH_SALE",
                "amount_iqd": "70000",
                "description": "fictional reconciliation",
            }
            | row
        )
    return api.post(
        "/api/imports/csv",
        files={"file": ("fictional.csv", stream.getvalue().encode(), "text/csv")},
    )


def debt(
    obligation="R",
    *,
    party="CUST-01",
    due="2026-09-28",
    amount="70000",
    source="ORIGIN",
):
    return {
        "source_id": source,
        "type": "CREDIT_SALE",
        "counterparty_id": party,
        "obligation_id": obligation,
        "due_date": due,
        "amount_iqd": amount,
        "occurred_at": "2026-09-26T12:00:00+03:00",
    }


def payment(source="PAY", *, party="CUST-01", amount="30000", reference=""):
    return {
        "source_id": source,
        "type": "CREDIT_COLLECTION",
        "counterparty_id": party,
        "amount_iqd": amount,
        "obligation_id": reference,
    }


def report(ledger):
    from app.services.business_clock import BusinessClock
    from app.services.reconcile import reconciliation_report

    return reconciliation_report(
        ledger, clock=BusinessClock(), known_at="2026-09-28T23:59:59+03:00"
    )


def test_t05_strong_partial_collections_keep_distinct_ids_and_replay_safely(
    api, ledger
):
    response = import_rows(api, [debt(), payment("ONE"), payment("TWO")])
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert [receipt[k] for k in ("accepted", "flagged_for_review", "rejected")] == [
        2,
        1,
        0,
    ]
    snapshot = read_ledger(ledger)
    assert len(snapshot.transactions) == 3 and len(snapshot.payment_links) == 2
    assert {link.match_basis for link in snapshot.payment_links} == {"strong"}
    assert sum(link.amount_iqd for link in snapshot.payment_links) == 60000
    assert (
        obligation_outstanding(
            snapshot.obligations[0],
            snapshot.transactions,
            snapshot.payment_links,
            as_of=date(2026, 9, 28),
        )
        == 10000
    )
    result = report(ledger)
    assert [match.level for match in result.matches] == ["strong", "strong"]
    assert all(match.unallocated_iqd == 0 for match in result.matches)
    assert any(flag.type == "suspected_duplicate" for flag in result.flags)
    replay = import_rows(api, [debt(), payment("ONE"), payment("TWO")])
    assert replay.json()["exact_duplicates"] == 3
    assert read_ledger(ledger) == snapshot


@pytest.mark.parametrize(
    "due,level,reason",
    [
        ("2026-09-28", "strong", None),
        ("2026-07-01", "candidate", "outside_due_window"),
        ("", "candidate", "missing_due_date"),
    ],
)
def test_matching_levels_require_one_exact_party_and_due_window(
    api, ledger, due, level, reason
):
    response = import_rows(api, [debt(due=due), payment()])
    assert response.status_code == 200, response.text
    match = report(ledger).matches[0]
    assert match.level == level and match.reason_key == reason
    assert len(read_ledger(ledger).payment_links) == (1 if level == "strong" else 0)
    assert match.candidate_obligation_ids == ("R",)
    if reason:
        assert any(
            flag.reason_key == reason and "PAY" in flag.source_ids
            for flag in report(ledger).flags
        )


def test_explicit_reference_is_definite_outside_heuristic_window(api, ledger):
    assert (
        import_rows(api, [debt(due="2026-07-01"), payment(reference="R")]).status_code
        == 200
    )
    match = report(ledger).matches[0]
    assert match.level == "definite" and match.unallocated_iqd == 0
    assert read_ledger(ledger).payment_links[0].match_basis == "definite"


def test_t07_normalized_similar_names_are_candidates_without_merging_or_linking(
    api, ledger
):
    response = import_rows(api, [debt(), payment(party="CUST-02")])
    assert response.status_code == 200, response.text
    result = report(ledger)
    assert result.matches[0].level == "candidate"
    assert result.matches[0].reason_key == "similar_name_only"
    assert result.matches[0].candidate_obligation_ids == ("R",)
    assert read_ledger(ledger).payment_links == ()
    assert (
        ledger.execute(
            "SELECT COUNT(*) FROM counterparties WHERE kind='customer'"
        ).fetchone()[0]
        == 2
    )
    detail = api.get("/api/ledger/transactions/PAY").json()
    assert detail["status"] == "flagged"
    assert any(
        flag["reason_key"] == "similar_name_only" and "ORIGIN" in flag["source_ids"]
        for flag in detail["flags"]
    )


def test_multiple_open_obligations_are_flagged_without_automatic_approval(api, ledger):
    response = import_rows(api, [debt("A"), debt("B", source="OTHER"), payment()])
    assert response.status_code == 200, response.text
    result = report(ledger)
    assert result.matches[0].level == "candidate"
    assert result.matches[0].reason_key == "ambiguous_obligations"
    assert set(result.matches[0].candidate_obligation_ids) == {"A", "B"}
    assert read_ledger(ledger).payment_links == ()
    before = ledger.total_changes
    ledger.execute("PRAGMA query_only = ON")
    assert report(ledger) == result
    assert ledger.total_changes == before
    ledger.execute("PRAGMA query_only = OFF")


def test_t08_unmatched_and_excess_payments_have_amount_reason_and_sources(api, ledger):
    response = import_rows(
        api,
        [
            debt(amount="10000"),
            payment(amount="20000", reference="R"),
            payment("MISSING", party="CUST-02", reference="UNKNOWN"),
        ],
    )
    assert response.status_code == 200, response.text
    assert response.json()["flagged_for_review"] == 2
    result = report(ledger)
    assert {m.reason_key for m in result.matches} == {
        "payment_exceeds_outstanding",
        "unmatched_payment",
    }
    assert read_ledger(ledger).payment_links == ()
    flag = next(
        f for f in result.flags if f.reason_key == "payment_exceeds_outstanding"
    )
    assert flag.amount.amount_iqd == 20000 and "PAY" in flag.source_ids


def test_late_partial_remains_overdue_until_settled_and_void_restores_flags(
    api, ledger
):
    import_rows(api, [debt(due="2026-09-25"), payment(reference="R")])
    result = report(ledger)
    assert {f.type for f in result.flags} >= {"overdue", "partially_paid"}
    assert (
        next(f.amount.amount_iqd for f in result.flags if f.type == "overdue") == 40000
    )
    collection = api.post(
        "/api/entries",
        json={
            "client_entry_id": "settle",
            "type": "CREDIT_COLLECTION",
            "amount_iqd": 40000,
            "business_date": "2026-09-28",
            "counterparty_id": "CUST-01",
            "obligation_id": "R",
        },
    ).json()
    assert not {f.type for f in report(ledger).flags} & {"overdue", "partially_paid"}
    assert (
        api.post(
            f"/api/entries/{collection['source_id']}/void",
            json={
                "client_entry_id": "restore",
                "reason": "merchant correction",
            },
        ).status_code
        == 200
    )
    assert (
        next(f.amount.amount_iqd for f in report(ledger).flags if f.type == "overdue")
        == 40000
    )


def test_voided_origin_does_not_silently_relink_payment(api, ledger):
    import_rows(api, [debt(), payment(reference="R")])
    assert (
        api.post(
            "/api/entries/ORIGIN/void",
            json={
                "client_entry_id": "void-origin",
                "reason": "merchant correction",
            },
        ).status_code
        == 200
    )
    import_rows(api, [debt("OTHER", source="NEW-ORIGIN")])
    match = report(ledger).matches[0]
    assert match.level == "unmatched" and match.reason_key == "origin_voided"
    assert "ORIGIN" in match.evidence_source_ids
    assert match.unallocated_iqd == 30000
    assert len(read_ledger(ledger).payment_links) == 1


def test_later_allocation_is_not_visible_to_earlier_reconciliation(api, ledger):
    from app.services.business_clock import BusinessClock
    from app.services.reconcile import reconciliation_report

    import_rows(api, [debt(), payment(reference="R")])
    current = report(ledger)
    early = reconciliation_report(
        ledger, clock=BusinessClock(), known_at="2026-09-27T23:59:59+03:00"
    )
    # These uploads were learned on day 90, so the earlier knowledge snapshot is empty.
    assert early.matches == early.flags == ()
    assert current.matches[0].unallocated_iqd == 0


def test_t10_t30_primary_observed_import_preserves_planted_positions(tmp_path):
    from app.db.connection import connect_database
    from app.db.migrations import apply_migrations
    from app.services.business_clock import BusinessClock
    from app.services.ingest import import_csv

    root = Path(__file__).resolve().parents[3] / "data" / "synthetic"
    db = connect_database(tmp_path / "primary.sqlite")
    try:
        apply_migrations(db)
        for filename, query in [
            (
                "counterparties.csv",
                """INSERT INTO counterparties VALUES
                (:counterparty_id, :display_name, :kind)""",
            ),
            (
                "categories.csv",
                """INSERT INTO categories VALUES
                (:category_id, :name, :buy_price_iqd, :sell_price_iqd)""",
            ),
        ]:
            with (root / filename).open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            if filename == "categories.csv":
                rows = [
                    r
                    | {
                        k: int(r[k]) if r[k] else None
                        for k in ("buy_price_iqd", "sell_price_iqd")
                    }
                    for r in rows
                ]
            db.executemany(query, rows)
        db.commit()
        first = import_csv(
            db,
            root / "observed_90d.csv",
            clock=BusinessClock(),
            imported_at="2026-09-28T23:59:59+03:00",
        )
        assert first.rejected == 0
        snapshot = read_ledger(db)
        cash = cash_on_hand(snapshot.transactions, as_of=date(2026, 9, 28)).amount_iqd
        outstanding = {
            o.obligation_id: obligation_outstanding(
                o,
                snapshot.transactions,
                snapshot.payment_links,
                as_of=date(2026, 9, 28),
            )
            for o in snapshot.obligations
        }
        dues = sum(
            outstanding[o.obligation_id]
            for o in snapshot.obligations
            if o.kind == "payable" and o.due_date <= date(2026, 10, 4)
        )
        expected = sum(
            outstanding[o.obligation_id]
            for o in snapshot.obligations
            if o.kind == "receivable"
            and date(2026, 9, 28) <= o.due_date <= date(2026, 10, 4)
        )
        assert (cash, dues, expected) == (420000, 650000, 150000)
        assert (cash - dues, cash + expected - dues) == (-230000, -80000)
        replay = import_csv(
            db,
            root / "observed_90d.csv",
            clock=BusinessClock(),
            imported_at="2026-09-28T23:59:59+03:00",
        )
        assert replay.accepted == replay.flagged_for_review == 0
        assert read_ledger(db) == snapshot
    finally:
        db.close()


def test_current_duplicate_flags_clear_after_merchant_void(api, ledger):
    response = import_rows(
        api,
        [
            {"source_id": "FIRST", "amount_iqd": "1000"},
            {"source_id": "SECOND", "amount_iqd": "1000"},
        ],
    )
    assert response.json()["flagged_for_review"] == 1
    assert any(flag.type == "suspected_duplicate" for flag in report(ledger).flags)
    assert (
        api.post(
            "/api/entries/FIRST/void",
            json={
                "client_entry_id": "void-duplicate",
                "reason": "merchant confirmed correction",
            },
        ).status_code
        == 200
    )
    assert not any(flag.type == "suspected_duplicate" for flag in report(ledger).flags)


def test_changed_source_knowledge_time_is_an_idempotency_conflict(api, ledger):
    fields = FIELDS + ["recorded_at"]

    def send(recorded_at):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            dict.fromkeys(fields, "")
            | {
                "source_id": "KNOWLEDGE",
                "type": "CASH_SALE",
                "amount_iqd": "1000",
                "occurred_at": "2026-09-27T12:00:00+03:00",
                "recorded_at": recorded_at,
            }
        )
        return api.post(
            "/api/imports/csv",
            files={"file": ("fictional.csv", stream.getvalue().encode(), "text/csv")},
        )

    assert send("2026-09-27T13:00:00+03:00").json()["accepted"] == 1
    receipt = send("2026-09-28T13:00:00+03:00").json()
    assert receipt["rejected"] == 1
    assert receipt["errors"][0]["code"] == "IDEMPOTENCY_CONFLICT"
    assert read_ledger(ledger).transactions[0].recorded_at == datetime.fromisoformat(
        "2026-09-27T13:00:00+03:00"
    )


def test_future_knowledge_does_not_create_a_duplicate_flag(api, ledger, insert_event):
    insert_event(
        source_id="LATER-KNOWLEDGE",
        occurred_at="2026-09-27T12:00:00+03:00",
        recorded_at="2026-09-29T12:00:00+03:00",
        amount_iqd=70000,
    )
    ledger.commit()
    response = import_rows(api, [{"source_id": "EARLIER"}])
    assert response.status_code == 200, response.text
    assert response.json()["accepted"] == 1
    assert response.json()["flagged_for_review"] == 0
