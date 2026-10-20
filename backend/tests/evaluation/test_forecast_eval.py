"""Offline harness boundaries; toy history only, no final run or unseen-shop I/O."""

from datetime import date, timedelta

import pytest


def test_dev_plan_never_grades_past_day_ninety_but_generates_thirty_rows():
    from scripts.run_forecast_eval import evaluation_plan

    plan = evaluation_plan("dev")
    assert [(p.cutoff_day, p.prediction_days, p.scored_days) for p in plan] == [
        (60, 30, 30),
        (75, 30, 15),
    ]
    assert all(p.scored_end == date(2026, 9, 28) for p in plan)
    assert all(p.shop == "primary" for p in plan)


def test_final_plan_requires_explicit_authorization_before_any_dataset_io(tmp_path):
    from scripts.run_forecast_eval import require_final_authorization

    with pytest.raises(ValueError, match="FINAL_TEST_NOT_AUTHORIZED"):
        require_final_authorization(allow_final=False, freeze_path=tmp_path / "absent")


def test_cutoff_history_removes_future_entries_link_knowledge_and_later_voids():
    from scripts.make_ground_truth import TruthLedger
    from scripts.run_forecast_eval import cutoff_history

    def row(key, day, recorded=None):
        return dict(
            transaction_id=key,
            source_id=key,
            business_date=day,
            occurred_at=f"{day}T12:00:00+03:00",
            recorded_at=recorded or f"{day}T12:00:00+03:00",
        )

    truth = TruthLedger(
        [
            row("known", "2026-08-29"),
            row("future", "2026-08-30"),
            row("backfill", "2026-08-28", "2026-08-30T12:00:00+03:00"),
        ],
        links=[
            dict(payment_transaction_id="known", created_at="2026-08-30T12:00:00+03:00")
        ],
        voids=[dict(transaction_id="known", voided_at="2026-08-30T12:00:00+03:00")],
    )
    history = cutoff_history(truth, date(2026, 8, 29))
    assert [r["source_id"] for r in history.rows] == ["known"]
    assert history.links == history.voids == []


def test_grading_truncates_before_lookup_so_day_ninety_one_is_never_requested():
    from scripts.run_forecast_eval import EvaluationCase, score_case

    cutoff = date(2026, 9, 13)
    case = EvaluationCase("primary", 75, 15)
    predictions = [
        dict(date=str(cutoff + timedelta(days=i)), closing_iqd=100)
        for i in range(1, 31)
    ]
    requested = []

    class ObservedTruth:
        def cash(self, day):
            assert day <= date(2026, 9, 28)
            requested.append(day)
            return {"amount_iqd": 90}

        def visible(self, day):
            assert day <= date(2026, 9, 28)
            return []

        links = []

    bundle = {
        "scenarios": {
            s: {"days": predictions} for s in ("base", "conservative", "stress")
        },
        "baseline": {"days": predictions},
        "invoices": [],
        "seven_day": {"days": []},
        "j1": None,
    }
    result = score_case(case, bundle, ObservedTruth())
    assert max(requested) == date(2026, 9, 28)
    for scenario in result["scenarios"].values():
        assert scenario["scored_days"] == 15
        assert scenario["mae_iqd"] == scenario["baseline_mae_iqd"] == 10
        assert scenario["false_ok"]["rate"] is None


def test_development_input_loader_opens_only_named_observed_files(
    monkeypatch, tmp_path
):
    from pathlib import Path

    from scripts.run_forecast_eval import load_observed_inputs

    attempted = []

    def deny(path, *args, **kwargs):
        attempted.append(Path(path).name)
        raise OSError("missing toy input")

    monkeypatch.setattr(Path, "open", deny)
    with pytest.raises(OSError):
        load_observed_inputs(tmp_path)
    assert attempted == ["observed_90d.csv"]


def test_final_plan_is_four_full_horizons_without_loading_any_shop():
    from scripts.run_forecast_eval import evaluation_plan

    plan = evaluation_plan("test", final_shops=("toy-a", "toy-b", "toy-c"))
    assert len(plan) == 4
    assert all(
        (p.cutoff_day, p.scored_days, p.prediction_days) == (90, 30, 30) for p in plan
    )


@pytest.fixture
def toy_history():
    from scripts.make_ground_truth import TruthLedger

    start = date(2026, 7, 1)
    rows = []

    def row(key, kind, amount, offset, hour="12:00", **extra):
        day = start + timedelta(days=offset)
        return dict(
            transaction_id=key,
            source_id=key,
            source_system="synthetic_csv",
            source="synthetic_csv",
            import_batch_id="TOY",
            source_row=len(rows) + 1,
            idempotency_key=f"synthetic_csv:{key}",
            type=kind,
            amount_iqd=amount,
            business_date=str(day),
            occurred_at=f"{day}T{hour}:00+03:00",
            recorded_at=f"{day}T{hour}:00+03:00",
            status="valid",
            **extra,
        )

    for offset in range(90):
        rows.extend(
            [
                row(f"SALE-{offset}", "CASH_SALE", 1000, offset),
                row(f"EXP-{offset}", "OPERATING_EXPENSE", 50, offset),
                row(
                    f"COUNT-{offset}",
                    "DAILY_CASH_COUNT",
                    100000 + offset * 950,
                    offset,
                    "21:00",
                ),
            ]
        )
    rows.extend(
        [
            row(
                "OLD",
                "CREDIT_SALE",
                100,
                1,
                counterparty_id="C",
                obligation_id="OLD-R",
                due_date=str(start + timedelta(days=9)),
            ),
            row(
                "PAID",
                "CREDIT_COLLECTION",
                100,
                11,
                counterparty_id="C",
                obligation_id="OLD-R",
            ),
            row(
                "OPEN",
                "CREDIT_SALE",
                200,
                50,
                counterparty_id="C",
                obligation_id="OPEN-R",
                due_date=str(start + timedelta(days=61)),
            ),
            row(
                "BILL",
                "SUPPLIER_INVOICE",
                400,
                50,
                counterparty_id="S",
                obligation_id="BILL-P",
                due_date=str(start + timedelta(days=62)),
            ),
        ]
    )
    link = dict(
        payment_link_id="L-PAID",
        payment_transaction_id="PAID",
        obligation_id="OLD-R",
        amount_iqd=100,
        match_basis="definite",
        created_at=rows[-3]["recorded_at"],
    )
    return TruthLedger(rows, links=[link])


def test_real_sqlite_adapter_matches_independent_drivers_on_inline_history(toy_history):
    from scripts.forecast_inputs import cutoff_history, production_predictions

    day = date(2026, 8, 29)
    history = cutoff_history(toy_history, day)
    parties = [
        dict(counterparty_id="C", display_name="Fictional customer", kind="customer"),
        dict(counterparty_id="S", display_name="Fictional supplier", kind="supplier"),
    ]
    result = production_predictions(history, parties, day)
    assert result["forecast_metadata"]["assumption_keys"] == [
        "collections_expected_not_guaranteed",
        "sales_from_weekday_averages",
        "unlinked_cash_projected_from_counts",
    ]
    for name in ("base", "conservative", "stress"):
        assert result["scenarios"][name]["days"] == history.forecast(day, name)["days"]
        assert len(result["scenarios"][name]["days"]) == 30
    assert result["seven_day"]["position_with_expected"]["amount_iqd"] == 155850
    # The adapter discards later records even when accidentally handed full history.
    assert production_predictions(toy_history, parties, day) == result


def test_harness_safety_uses_cutoff_unpaid_invoices_and_realized_own_allocations(
    toy_history,
):
    from scripts.forecast_inputs import cutoff_history, production_predictions
    from scripts.run_forecast_eval import EvaluationCase, score_case

    day = date(2026, 8, 29)
    history = cutoff_history(toy_history, day)
    result = production_predictions(
        history,
        [
            dict(
                counterparty_id="C", display_name="Fictional customer", kind="customer"
            ),
            dict(
                counterparty_id="S", display_name="Fictional supplier", kind="supplier"
            ),
        ],
        day,
    )
    result.update(
        baseline=history.baseline(day),
        invoices=[
            r for r in history.debts(day, direction="payable") if r["outstanding_iqd"]
        ],
    )
    # A hand-planted development-only due-day cash shortage. No payment occurred.
    for row in toy_history.rows:
        if (
            row["type"] == "DAILY_CASH_COUNT"
            and row["business_date"] == result["invoices"][0]["due_date"]
        ):
            row["amount_iqd"] = 300
    scored = score_case(EvaluationCase("toy", 60, 30), result, toy_history)
    for value in scored["scenarios"].values():
        assert value["false_ok"] == {
            "numerator": 1,
            "denominator": 1,
            "rate": 1.0,
            "eligible_invoices": 1,
        }
    assert scored["seven_day_with_expected_false_ok"]["numerator"] == 1
    # No invoice was due on the next Thursday; this is inapplicable, not a success.
    assert scored["j1_with_expected_false_ok"]["rate"] is None


def test_changed_method_settings_cannot_pass_a_freeze_check(monkeypatch):
    from scripts import run_forecast_eval as evaluator

    monkeypatch.setattr(
        evaluator,
        "read_json",
        lambda path: {
            "method_settings": {},
            "source_hashes": {},
        },
    )
    with pytest.raises(ValueError, match="METHOD_CHANGED_SINCE_FREEZE"):
        evaluator.verify_freeze("unused-toy-path", {"source_hashes": {"toy": "digest"}})


def test_missing_production_history_is_reported_without_fabricated_metrics(toy_history):
    from scripts.forecast_inputs import production_predictions
    from scripts.run_forecast_eval import EvaluationCase, score_case

    toy_history.rows = [
        r
        for r in toy_history.rows
        if r["type"] != "DAILY_CASH_COUNT" or r["business_date"] > "2026-08-29"
    ]
    result = production_predictions(
        toy_history,
        [
            dict(
                counterparty_id="C", display_name="Fictional customer", kind="customer"
            ),
            dict(
                counterparty_id="S", display_name="Fictional supplier", kind="supplier"
            ),
        ],
        date(2026, 8, 29),
    )
    assert {r["error_code"] for r in result["scenarios"].values()} == {
        "MISSING_OPENING_BALANCE"
    }
    result.update(baseline={"error_code": "MISSING_COUNT"}, invoices=[])
    scored = score_case(EvaluationCase("toy", 60, 30), result, toy_history)
    for value in scored["scenarios"].values():
        assert value["status"] == "missing_data" and value["scored_days"] == 0
        assert "mae_iqd" not in value


def test_unapproved_final_run_cannot_call_the_outcome_loader(monkeypatch):
    from scripts import run_forecast_eval as evaluator

    def forbidden(*args, **kwargs):
        pytest.fail("unauthorized final path reached data I/O")

    monkeypatch.setattr(evaluator, "load_observed_inputs", forbidden)
    monkeypatch.setattr(evaluator, "_final_truth", forbidden)
    with pytest.raises(ValueError, match="FINAL_TEST_NOT_AUTHORIZED"):
        evaluator.run("test")


def test_development_runner_end_to_end_on_toy_csvs_only(
    tmp_path, monkeypatch, toy_history
):
    from pathlib import Path

    from scripts import run_forecast_eval as evaluator
    from scripts.data_contract import (
        LINK_FIELDS,
        TRANSACTION_FIELDS,
        VOID_FIELDS,
        write_csv,
        write_json,
    )

    folder = tmp_path / "data/synthetic"
    folder.mkdir(parents=True)
    write_csv(folder / "observed_90d.csv", toy_history.rows, TRANSACTION_FIELDS)
    write_json(
        folder / "opening_balance.json",
        dict(
            opening_balance_id="TOY-OPEN",
            source_id="TOY-OPEN",
            source_system="synthetic_csv",
            source_row=1,
            import_batch_id="TOY-OPEN-BATCH",
            business_date="2026-07-01",
            amount_iqd=100000,
        ),
    )
    write_csv(
        folder / "categories.csv",
        [],
        ["category_id", "name", "buy_price_iqd", "sell_price_iqd"],
    )
    write_csv(
        folder / "counterparties.csv",
        [
            dict(
                counterparty_id="C", display_name="Fictional customer", kind="customer"
            ),
            dict(
                counterparty_id="S", display_name="Fictional supplier", kind="supplier"
            ),
        ],
        ["counterparty_id", "display_name", "kind"],
    )
    write_csv(folder / "payment_links.csv", toy_history.links, LINK_FIELDS)
    write_csv(folder / "entry_voids.csv", [], VOID_FIELDS)
    monkeypatch.setattr(evaluator, "ROOT", tmp_path)
    # Only external Git metadata is faked; all CSV, SQLite, forecast and scoring run.
    monkeypatch.setattr(
        evaluator,
        "source_provenance",
        lambda: {
            "code_commit": "0" * 40,
            "source_hashes": {},
            "method_settings": evaluator.METHOD_SETTINGS,
        },
    )
    original_open = Path.open
    attempted = []

    def guarded(path, *args, **kwargs):
        assert Path(path).parent == folder
        assert Path(path).name in {
            "observed_90d.csv",
            "opening_balance.json",
            "categories.csv",
            "counterparties.csv",
            "payment_links.csv",
            "entry_voids.csv",
        }
        attempted.append(Path(path).name)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    report = evaluator.run("dev")
    assert len(attempted) >= 6 and report["case_count"] == 2
    assert [c["scored_days"] for c in report["cases"]] == [30, 15]
    for case in report["cases"]:
        for scenario in case["predictions"]["scenarios"].values():
            assert len(scenario["days"]) == 30
    assert all(report["summary"][s]["scored_days"] == 45 for s in evaluator.SCENARIOS)
