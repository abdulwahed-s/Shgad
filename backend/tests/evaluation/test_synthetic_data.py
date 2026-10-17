"""Dataset contract, FINANCIAL_RULES §§1/3/8/11 and T10/T12/T22/T27–30/T34."""

import ast
import csv
import hashlib
import json
from datetime import date
from pathlib import Path

import pytest
from scripts.data_contract import read_csv, read_json, validate_question
from scripts.generate_synthetic_data import generate
from scripts.make_ground_truth import load_ledger

from app.schemas.ledger import (
    Category,
    Counterparty,
    EntryVoid,
    Obligation,
    OpeningBalance,
    PaymentLink,
    Transaction,
)

ROOT = Path(__file__).resolve().parents[3]


def hashes(root):
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    root = tmp_path_factory.mktemp("fictional-data")
    generate(seed=20260701, output_root=root)
    return root


def test_generator_is_byte_reproducible_and_seed_changes_records(dataset, tmp_path):
    generate(seed=20260701, output_root=tmp_path)
    assert hashes(dataset) == hashes(tmp_path)
    generate(seed=17, output_root=tmp_path)
    assert (dataset / "synthetic/observed_90d.csv").read_bytes() != (
        tmp_path / "synthetic/observed_90d.csv"
    ).read_bytes()


def test_manifest_hashes_cover_all_generated_artifacts(dataset):
    manifest = json.loads((dataset / "synthetic/generation_manifest.json").read_text())
    actual = hashes(dataset)
    actual.pop("synthetic/generation_manifest.json")
    assert manifest["file_sha256"] == actual
    assert manifest["seed"] == 20260701
    assert manifest["scenario_drafting"]["prompt"]
    assert manifest["scenario_drafting"]["model_id_status"] == "not_exposed_by_session"
    assert manifest["human_reviews"] == {"arabic": "pending", "plausibility": "pending"}


def test_t10_t30_j1_exact_and_other_dues_outside_window(dataset):
    ledger = load_ledger(dataset / "synthetic")
    result = ledger.j1(date(2026, 9, 28), date(2026, 10, 1))
    assert result["cash_iqd"] == 420000
    assert result["dues_iqd"] == 650000
    assert result["expected_iqd"] == 150000
    assert result["shortfall_with_iqd"] == 80000
    assert result["shortfall_without_iqd"] == 230000
    upcoming = ledger.upcoming(date(2026, 9, 28))
    assert upcoming["position_confirmed_iqd"] == -230000
    assert upcoming["position_with_expected_iqd"] == -80000
    assert upcoming["first_short_date_confirmed"] == "2026-10-01"
    assert upcoming["first_short_date_with_expected"] == "2026-10-01"
    assert upcoming["overdue_receivables"] == []
    assert len(upcoming["dues"]) == len(upcoming["expected"]) == 1
    assert upcoming["expected"][0]["counterparty_id"] == "CUST-01"


def test_counts_are_constructed_from_flows_and_private_labels(dataset):
    ledger = load_ledger(dataset / "synthetic")
    labels = json.loads((dataset / "synthetic/cash_difference_labels.json").read_text())
    assert len(labels) == 90
    balance = ledger.opening["amount_iqd"]
    negative = []
    for label in labels:
        day = date.fromisoformat(label["date"])
        rows = [r for r in ledger.rows if r["business_date"] == label["date"]]
        delta = sum(
            (
                1
                if r["type"] in {"CASH_SALE", "CREDIT_COLLECTION", "CAPITAL_INJECTION"}
                else -1
                if r["type"]
                in {"SUPPLIER_PAYMENT", "OPERATING_EXPENSE", "OWNER_DRAWING"}
                else 0
            )
            * r["amount_iqd"]
            for r in rows
        )
        gap = (
            label["unrecorded_cash_sales_iqd"]
            + label["unrecorded_capital_iqd"]
            - label["unrecorded_expense_iqd"]
        )
        balance += delta + gap
        assert ledger.cash(day)["amount_iqd"] == balance
        recorded = sum(r["amount_iqd"] for r in rows if r["type"] == "CASH_SALE")
        true = recorded + label["unrecorded_cash_sales_iqd"]
        assert 92 * true <= recorded * 100 <= 95 * true
        if day > date(2026, 7, 1):
            assert ledger.daily_close(day)["unexplained_difference_iqd"] == gap
        if gap < 0:
            negative.append(day)
    assert balance == 420000
    assert negative == [date(2026, 8, 21)]
    assert any(r["type"] == "CAPITAL_INJECTION" for r in ledger.rows)
    assert sum(bool(x["unrecorded_capital_iqd"]) for x in labels) == 1


def test_t22_t28_t34_review_fixture(dataset):
    ledger = load_ledger(dataset / "fixtures", fixture="cash_difference_review")
    day = date(2026, 9, 28)
    before = ledger.daily_close(day, known_at="2026-09-28T20:01:00+03:00")
    assert before["expected_close_iqd"] == 420000
    assert before["unexplained_difference_iqd"] == 25000
    assert before["recorded_cash_sales_iqd"] == 120000
    after = ledger.daily_close(day, known_at="2026-09-28T20:06:00+03:00")
    assert after["unexplained_difference_iqd"] == 0
    assert after["recorded_cash_sales_iqd"] == 120000
    requests = json.loads(
        (dataset / "fixtures/cash_difference_review_requests.json").read_text()
    )
    assert requests[0]["expected_error"] == "DIFFERENCE_SIGN_MISMATCH"
    assert requests[1]["resolution"] == "capital_injection"


def test_t27_void_fixture_is_isolated_and_cutoff_aware(dataset):
    ledger = load_ledger(dataset / "fixtures", fixture="three_instalments_void")
    day = date(2026, 9, 28)
    for known, balance in [("19:00", 0), ("20:01", 25000), ("20:06", 5000)]:
        assert (
            ledger.debts(day, known_at=f"2026-09-28T{known}:00+03:00")[0][
                "outstanding_iqd"
            ]
            == balance
        )
    assert ledger.cash(day)["amount_iqd"] == 285000
    assert len(ledger.rows) == 5
    assert len(ledger.voids) == 1
    assert not any(
        "T27" in r["source_id"] for r in load_ledger(dataset / "synthetic").rows
    )


def test_t30_overdue_variant_does_not_add_expected_collection(dataset):
    ledger = load_ledger(dataset / "fixtures", fixture="seven_day_overdue")
    result = ledger.upcoming(date(2026, 9, 28))
    assert result["position_with_expected_iqd"] == -80000
    assert result["overdue_receivables"][0]["outstanding_iqd"] == 40000
    assert result["dues"][0]["due_now"] is True


def test_t12_d20_development_truth_and_final_metadata(dataset):
    protocol = json.loads((dataset / "evaluation/forecast_protocol.json").read_text())
    assert [
        (x["cutoff_day"], x["scored_days"], x["score_end_day"])
        for x in protocol["development"]
    ] == [(60, 30, 90), (75, 15, 90)]
    assert protocol["final_test"]["requires_method_freeze"] is True
    assert len(protocol["final_test"]["extra_shops"]) == 3
    expected = json.loads((dataset / "evaluation/forecast_expected.json").read_text())
    assert expected["realized_outcomes_read"] is False
    assert expected["split"] == "development"
    assert set(expected["cutoffs"]) == {"60", "75"}
    for result in expected["cutoffs"].values():
        for scenario in ("base", "conservative", "stress"):
            assert len(result["scenarios"][scenario]["days"]) == 30
        assert all(
            x["collections_iqd"] == 0 for x in result["scenarios"]["stress"]["days"]
        )
    for shop in (dataset / "synthetic/forecast_eval_shops").iterdir():
        with (shop / "observed_90d.csv").open(encoding="utf-8", newline="") as f:
            assert all(
                r["business_date"] <= "2026-09-28"
                and r["recorded_at"] <= "2026-09-28T23:59:59+03:00"
                for r in csv.DictReader(f)
            )


def test_independent_calculator_and_application_boundary():
    tree = ast.parse(
        (ROOT / "scripts/make_ground_truth.py").read_text(encoding="utf-8")
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(
                ("app", "backend", "scripts.generate", "scripts.synthetic")
            )
        if isinstance(node, ast.Import):
            assert all(not x.name.startswith(("app", "backend")) for x in node.names)
    for path in (ROOT / "backend/app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for forbidden in (
            "future_30d_ground_truth",
            "all_120d_canonical",
            "forecast_eval_shops",
            "planted_anomalies",
            "cash_difference_labels",
            "data/evaluation",
            "from scripts",
            "import scripts",
        ):
            assert forbidden not in text, (path, forbidden)


def test_development_questions_have_joint_labels_and_no_numeric_answers(dataset):
    rows = [
        json.loads(line)
        for line in (dataset / "evaluation/development_questions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(rows) >= 24
    assert len({q["id"] for q in rows}) == len(rows)
    for q in rows:
        validate_question(q)
        assert q["id"].startswith("DEV-")
        assert "answer" not in q
        assert set(q["spec"]) >= {
            "intent",
            "expected_tools",
            "counterparty_ids",
            "resolved_period",
            "expected_behavior",
            "calculation",
            "parameters",
        }
        assert q["arabic_review"] == "pending"
    assert not (dataset / "evaluation/heldout_60_manifest.json").exists()


def test_every_generated_canonical_record_matches_existing_strict_schema(dataset):
    # Structural checks only for final-test files; never compute/print final metrics.
    shops = [dataset / "synthetic"] + sorted(
        (dataset / "synthetic/forecast_eval_shops").iterdir()
    )
    totals = {"transactions": 0, "days": 0}
    for shop in shops:
        rows = read_csv(shop / "all_120d_canonical.csv")
        observed = read_csv(shop / "observed_90d.csv")
        future = read_csv(shop / "future_30d_ground_truth.csv")
        assert rows == observed + future
        assert len({r["business_date"] for r in observed}) == 90
        assert len({r["business_date"] for r in future}) == 30
        for r in rows:
            Transaction(**r)
        for r in read_csv(shop / "categories.csv"):
            Category(**r)
        for r in read_csv(shop / "counterparties.csv"):
            Counterparty(**r)
        for name, cls in [
            ("obligations.csv", Obligation),
            ("payment_links.csv", PaymentLink),
            ("entry_voids.csv", EntryVoid),
            ("evaluation_only/all_120d_obligations.csv", Obligation),
            ("evaluation_only/all_120d_payment_links.csv", PaymentLink),
        ]:
            for r in read_csv(shop / name):
                cls(**r)
        OpeningBalance(**read_json(shop / "opening_balance.json"))
        observed_ids = {r["transaction_id"] for r in observed}
        assert all(
            r["origin_transaction_id"] in observed_ids
            for r in read_csv(shop / "obligations.csv")
        )
        assert all(
            r["payment_transaction_id"] in observed_ids
            for r in read_csv(shop / "payment_links.csv")
        )
        totals["transactions"] += len(rows)
        totals["days"] += 120
    assert totals["days"] == 480
    for path in (dataset / "fixtures").glob("*.obligations.csv"):
        stem = path.name.removesuffix(".obligations.csv")
        for r in read_csv(path.with_name(stem + ".csv")):
            Transaction(**r)
        for suffix, cls in [
            (".obligations.csv", Obligation),
            (".payment_links.csv", PaymentLink),
            (".entry_voids.csv", EntryVoid),
            (".categories.csv", Category),
        ]:
            for r in read_csv(path.with_name(stem + suffix)):
                cls(**r)


def test_generator_fixture_labels_reference_real_rows_and_mapping_is_lossless(dataset):
    labels = read_json(dataset / "synthetic/planted_anomalies.json")
    for label in labels["anomalies"]:
        if "fixture" not in label:
            continue
        with (dataset / "fixtures" / label["fixture"]).open(
            encoding="utf-8", newline=""
        ) as stream:
            ids = {r["source_id"] for r in csv.DictReader(stream)}
        assert set(label["source_ids"]) <= ids
    mapping = read_json(dataset / "fixtures/unfamiliar_column_order.mapping.json")
    with (dataset / "fixtures/unfamiliar_column_order.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        mapped = [
            {mapping[k]: v for k, v in row.items()} for row in csv.DictReader(stream)
        ]
    with (dataset / "fixtures/small_happy_path.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        assert mapped == list(csv.DictReader(stream))
    assert not (
        dataset / "fixtures/missing_opening_balance.opening_balance.json"
    ).exists()


def test_development_truth_behaviors_match_specs(dataset):
    answers = read_json(dataset / "evaluation/development_expected.json")["answers"]
    questions = [
        json.loads(line)
        for line in (dataset / "evaluation/development_questions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    for question in questions:
        answer = answers[question["id"]]
        assert answer["behavior"] == question["spec"]["expected_behavior"]
        if "error_code" in question["spec"]:
            assert answer["error_code"] == question["spec"]["error_code"]


def test_generated_audit_fixtures_satisfy_existing_sqlite_guards(dataset):
    # A schema probe, not an importer implementation or a reimport claim.
    from contextlib import closing

    from app.db.connection import connect_database
    from app.db.migrations import apply_migrations
    from app.schemas.ledger import DifferenceReview, DifferenceReviewRequest
    from app.services.errors import FinancialRuleError
    from app.services.ledger_audit import resolve_difference

    mechanics = read_json(ROOT / "data/generation/business_mechanics.json")
    for name in ("three_instalments_void", "cash_difference_review"):
        folder = dataset / "fixtures"
        rows = [Transaction(**r) for r in read_csv(folder / f"{name}.csv")]
        with closing(connect_database(":memory:")) as connection:
            apply_migrations(connection)
            with connection:
                for p in mechanics["customers"] + mechanics["suppliers"]:
                    connection.execute(
                        "INSERT INTO counterparties VALUES (?, ?, ?)",
                        (p["counterparty_id"], p["display_name"], p["kind"]),
                    )
                for category in mechanics["categories"]:
                    connection.execute(
                        "INSERT INTO categories VALUES (?, ?, ?, ?)",
                        tuple(
                            category[k]
                            for k in (
                                "category_id",
                                "name",
                                "buy_price_iqd",
                                "sell_price_iqd",
                            )
                        ),
                    )
                batches = {}
                for r in rows:
                    batches.setdefault(r.import_batch_id, []).append(r)
                for batch_id, events in batches.items():
                    connection.execute(
                        """INSERT INTO import_batches VALUES
                        (?, ?, 'aggregate_cash', ?, ?, ?, ?, 0, 0, 'completed')""",
                        (
                            batch_id,
                            events[0].source_system,
                            "0" * 64,
                            "2026-09-28T21:00:00+00:00",
                            len(events),
                            len(events),
                        ),
                    )
                    for event in events:
                        connection.execute(
                            "INSERT INTO raw_import_rows VALUES "
                            "(?, ?, ?, ?, '[]', 'accepted')",
                            (
                                event.transaction_id + "-RAW",
                                batch_id,
                                event.source_row,
                                event.model_dump_json(),
                            ),
                        )
                origins = {
                    r["origin_transaction_id"]: r
                    for r in read_csv(folder / f"{name}.obligations.csv")
                }

                def insert(table, payload):
                    columns = ",".join(payload)
                    parameters = ",".join("?" for _ in payload)
                    connection.execute(
                        f"INSERT INTO {table} ({columns}) VALUES ({parameters})",
                        tuple(payload.values()),
                    )

                for event in rows:
                    insert("transactions", event.model_dump(mode="json"))
                    if event.transaction_id in origins:
                        insert(
                            "obligations",
                            Obligation(**origins[event.transaction_id]).model_dump(
                                mode="json"
                            ),
                        )
                audits = [
                    (r["created_at"], "payment_links", PaymentLink(**r))
                    for r in read_csv(folder / f"{name}.payment_links.csv")
                ]
                audits += [
                    (r["voided_at"], "entry_voids", EntryVoid(**r))
                    for r in read_csv(folder / f"{name}.entry_voids.csv")
                ]
                for _, table, record in sorted(audits, key=lambda r: r[0]):
                    insert(table, record.model_dump(mode="json"))
                for review in read_json(folder / f"{name}.difference_reviews.json"):
                    insert(
                        "difference_reviews",
                        DifferenceReview(**review).model_dump(mode="json"),
                    )
                if name == "cash_difference_review":
                    before = connection.total_changes
                    with pytest.raises(
                        FinancialRuleError, match="DIFFERENCE_SIGN_MISMATCH"
                    ):
                        resolve_difference(
                            connection,
                            DifferenceReviewRequest(
                                client_entry_id="T34-REJECT",
                                resolution="expense_unrecorded",
                                amount_iqd=25000,
                            ),
                            business_date=date(2026, 9, 28),
                            recorded_at="2026-09-28T20:02:00+03:00",
                        )
                    assert connection.total_changes == before
                    replay = resolve_difference(
                        connection,
                        DifferenceReviewRequest(
                            client_entry_id="T28-CAPITAL",
                            resolution="capital_injection",
                            amount_iqd=25000,
                        ),
                        business_date=date(2026, 9, 28),
                        recorded_at="2026-09-28T20:06:00+03:00",
                    )
                    assert replay.duplicate is True
                assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_sealing_inputs_exclude_future_labels_unseen_shops_and_answers(dataset):
    package = read_json(dataset / "evaluation/sealing_input_manifest.json")
    for name, digest in package["file_sha256"].items():
        assert hashlib.sha256((dataset / name).read_bytes()).hexdigest() == digest
        assert not any(
            x in name
            for x in (
                "future_",
                "all_120d",
                "forecast_eval_shops",
                "_expected",
                "planted_anomalies",
                "cash_difference_labels",
                "generation_manifest",
            )
        )
    assert "evaluation/QUESTION_SPEC.md" in package["file_sha256"]
    assert "synthetic/payment_links.csv" in package["file_sha256"]
    assert "synthetic/entry_voids.csv" in package["file_sha256"]


def test_late_collection_labels_exclude_on_time_partial_and_early_payments(dataset):
    rows = read_csv(dataset / "synthetic/observed_90d.csv")
    by_id = {r["transaction_id"]: r for r in rows}
    origins = {r["obligation_id"]: r for r in rows if r["type"] == "CREDIT_SALE"}
    late = next(
        a
        for a in read_json(dataset / "synthetic/planted_anomalies.json")["anomalies"]
        if a["label"] == "late_collection"
    )
    assert len(late["source_ids"]) >= 2
    for source in late["source_ids"]:
        payment = by_id[source]
        assert payment["business_date"] > origins[payment["obligation_id"]]["due_date"]


def test_generation_inventory_preserves_and_excludes_existing_unowned_files(
    dataset, tmp_path
):
    (tmp_path / "synthetic").mkdir()
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "synthetic/.gitkeep").touch()
    unrelated = tmp_path / "fixtures/unrelated_existing.json"
    unrelated.write_text('{"preserve": true}\n', encoding="utf-8")
    actual = generate(seed=20260701, output_root=tmp_path)
    expected = read_json(dataset / "synthetic/generation_manifest.json")
    assert actual == expected
    assert unrelated.read_text(encoding="utf-8") == '{"preserve": true}\n'
