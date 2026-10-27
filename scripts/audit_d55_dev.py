"""Public dev-only fake-provider reproduction; original D55 grades stay intact.

D55 retained grades rather than provider recordings. These fabricated slot
drafts reproduce its six trace counts, not its unretained original answers.
This script is never called by the measured evaluator or on a held-out split.
"""

import argparse
import asyncio
import hashlib
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for source in (ROOT, ROOT / "backend"):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

from scripts.evaluation_clients import ReplayClient  # noqa: E402
from scripts.evaluation_evidence import METHOD_V2  # noqa: E402
from scripts.evaluation_metrics import compare_claim  # noqa: E402
from scripts.evaluation_reports import git, now, write_new  # noqa: E402
from scripts.evaluation_runtime import (  # noqa: E402
    PromptInput,
    observe,
    observed_history,
    production_database,
    reference_parties,
)
from scripts.evaluation_truth import claim_catalogue  # noqa: E402
from scripts.run_evaluation import load_questions  # noqa: E402

SALES = {
    "DEV-002": ("this_week", "credit", ["credit_sales"]),
    "DEV-003": (
        "yesterday",
        "all",
        ["cash_sales", "credit_sales", "total_sales", "unexplained_cash_difference"],
    ),
    "DEV-019": (
        "today",
        "cash",
        ["cash_sales", "credit_sales", "total_sales", "unexplained_cash_difference"],
    ),
}
WANTED = set(SALES) | {"DEV-013", "DEV-014", "DEV-017"}


def run_audit():
    started = now()
    original_path = ROOT / "results/evaluation_dev_live_POST_D55.json"
    original_bytes = original_path.read_bytes()
    original = json.loads(original_bytes)
    native = {row["id"]: row for row in original["cases"]}
    questions, _ = load_questions("dev")
    results = []
    before_total = after_total = count_total = 0
    classes = Counter(a=0, b=0, c=0)
    for question in questions:
        identity = question["id"]
        if identity not in WANTED:
            continue
        spec = question["spec"]
        day = date.fromisoformat(question["business_as_of"])
        history = observed_history(question["dataset"], day, ROOT / "data")
        if identity in SALES:
            period, kind, keys = SALES[identity]
            turns = [
                dict(
                    calls=[
                        dict(name="get_sales", arguments=dict(period=period, kind=kind))
                    ]
                )
            ]
            draft = " ".join("{{fig:" + key + "}}" for key in keys)
        else:
            turns = []
            # Explicitly fabricate fallback for 014: the real template includes
            # the reconciler's sourced partial balance. No historical draft exists.
            keys = ["total_sales", "weekly.owner_drawings", "weekly.operating_expenses"]
            draft = (
                "{{fig:unavailable_slot}}"
                if identity == "DEV-014"
                else " ".join("{{fig:" + key + "}}" for key in keys)
            )
        turns.append(dict(action=dict(status="answered", draft_ar=draft)))
        client = ReplayClient()
        client.begin_question(dict(intent=spec["intent"], turns=turns))
        with production_database(
            history, reference_parties(ROOT / "data"), as_of=day
        ) as db:
            observed = asyncio.run(
                observe(
                    PromptInput(question["question_ar"], str(day)),
                    client=client,
                    connection=db,
                )
            )
        period = spec["resolved_period"]
        arguments = (
            history,
            day,
            date.fromisoformat(period["start"]),
            date.fromisoformat(period["end"]),
        )
        kwargs = dict(parties=spec["counterparty_ids"], parameters=spec["parameters"])
        old = claim_catalogue(*arguments, **kwargs)
        new = claim_catalogue(*arguments, **kwargs, method=METHOD_V2)
        unsupported = []
        before = after = 0
        for claim in observed["claims"]:
            _, supported_before = compare_claim(old.get(claim["field"]), claim)
            _, supported_after = compare_claim(
                new.get(claim["field"]), claim, method=METHOD_V2
            )
            before += supported_before
            after += supported_after
            if not supported_before:
                category = (
                    "a"
                    if supported_after and claim.get("query_evidence")
                    else "b"
                    if supported_after and claim["source_ids"]
                    else "c"
                )
                classes[category] += 1
                unsupported.append(
                    dict(
                        field=claim["field"],
                        classification=category,
                        value=claim["value"],
                        source_ids=claim["source_ids"],
                        query_evidence=claim.get("query_evidence"),
                        formula=claim["formula"],
                    )
                )
        count = len(observed["claims"])
        retained = native[identity]["traceability"]
        results.append(
            dict(
                id=identity,
                classes=dict(Counter(c["classification"] for c in unsupported)),
                claims_before=dict(numerator=before, denominator=count),
                claims_after=dict(numerator=after, denominator=count),
                retained_counts_match_reproduction=(
                    before == retained["numerator"] and count == retained["denominator"]
                ),
                unsupported_reproduction_claims=unsupported,
            )
        )
        before_total += before
        after_total += after
        count_total += count
        assert client.receipt()["provider_requests"] == 0
    return dict(
        kind="re-graded replay, not a new measurement",
        scope="six_public_development_fake_provider_reproductions",
        started_at=started,
        executed_at=now(),
        code_commit=git("rev-parse", "HEAD"),
        model_id="synthetic-format-sentinel",
        provider_requests=0,
        original_claim_identities_recovered=False,
        limitations=[
            "original_provider_outputs_drafts_arguments_and_claims_not_retained",
            "matching_counts_do_not_prove_original_claim_identities",
            "remaining_43_original_claims_not_replayed_or_rescored",
        ],
        original_report_sha256=hashlib.sha256(original_bytes).hexdigest(),
        original_claims_unchanged=original["metrics"]["traceability"],
        evidence_method=METHOD_V2,
        cases=results,
        totals=dict(
            classes=dict(classes),
            replay_claims_before=dict(numerator=before_total, denominator=count_total),
            replay_claims_after=dict(numerator=after_total, denominator=count_total),
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("RESULT_ALREADY_EXISTS")
    result = run_audit()
    write_new(args.output, json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(
        json.dumps(
            dict(kind=result["kind"], totals=result["totals"], provider_requests=0)
        )
    )
    return int(bool(result["totals"]["classes"]["c"]))


if __name__ == "__main__":
    raise SystemExit(main())
