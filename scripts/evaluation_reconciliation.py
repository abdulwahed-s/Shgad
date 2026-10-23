"""Labelled development reconciliation, independent from question/model context."""

from datetime import date
from pathlib import Path

from scripts.data_contract import read_csv, read_json
from scripts.evaluation_metrics import reconciliation_metrics
from scripts.evaluation_runtime import production_database, reference_parties
from scripts.make_ground_truth import TruthLedger, cutoff


def evaluate(data_root):
    from app.services.business_clock import BusinessClock
    from app.services.ingest import import_csv
    from app.services.reconcile import reconciliation_report

    data_root = Path(data_root)
    gold = read_json(data_root / "evaluation/reconciliation_expected.json")
    fixtures = ("duplicate_rows.csv", "unmatched_payment.csv")
    expected, predicted = (
        {key: set() for key in ("suspected_duplicate", "unmatched")} for _ in range(2)
    )
    receipts = {}
    day = date(2026, 9, 28)
    for fixture in fixtures:
        # The model never receives fixtures or labels. Import through the actual
        # production importer, so duplicate detection is not pre-labelled by us.
        history = TruthLedger(
            [], categories=read_csv(data_root / "synthetic/categories.csv")
        )
        with production_database(
            history, reference_parties(data_root), as_of=day
        ) as db:
            db.execute("PRAGMA query_only=OFF")
            context = None
            if fixture == "duplicate_rows.csv":
                # This export is a slice of small_happy_path. Its HAPPY-R
                # origin must exist before importing the repeated collections.
                context = import_csv(
                    db,
                    data_root / "fixtures/small_happy_path.csv",
                    clock=BusinessClock(day),
                    imported_at=cutoff(day),
                )
                if context.rejected:
                    raise ValueError("RECONCILIATION_CONTEXT_IMPORT_FAILED")
            receipt = import_csv(
                db,
                data_root / "fixtures" / fixture,
                clock=BusinessClock(day),
                imported_at=cutoff(day),
            )
            if receipt.rejected:
                raise ValueError("RECONCILIATION_FIXTURE_IMPORT_FAILED")
            db.execute("PRAGMA query_only=ON")
            flags = reconciliation_report(
                db, clock=BusinessClock(day), known_at=cutoff(day)
            ).flags
            receipts[fixture] = dict(
                accepted=receipt.accepted,
                exact_duplicates=receipt.exact_duplicates,
                flagged_for_review=receipt.flagged_for_review,
                context_fixture="small_happy_path.csv" if context else None,
                context_accepted=context.accepted if context else 0,
            )
            for flag in flags:
                if flag.type in predicted:
                    predicted[flag.type].add((fixture, *sorted(flag.source_ids)))
        for label in gold["labels"]:
            if label["fixture"] == fixture and label["label"] in expected:
                expected[label["label"]].add((fixture, *sorted(label["source_ids"])))
    return dict(
        scope="seeded_development_fixtures_not_heldout_questions",
        fixture_count=2,
        metrics=reconciliation_metrics(expected, predicted),
        import_counts=receipts,
    )
