"""D58 development runner: live interpretation pipeline, grading method v3.

Public development questions only (never HELDOUT_PATH). Per-question detail is
written for train questions; ids with a --aggregate-only prefix (the dev-check
part) contribute to totals but their detail is withheld from the output.

    python scripts/dev_eval_v3.py \
        --questions data/evaluation/development_questions_v2.jsonl \
        --requirements data/evaluation/development_requirements.jsonl \
        --output results/dev_v3_local.json --authorize-paid
"""

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from scripts.evaluation_evidence import METHOD_V2  # noqa: E402
from scripts.evaluation_metrics import aggregate_questions, grade_question_v3  # noqa: E402
from scripts.evaluation_runtime import (  # noqa: E402
    PromptInput,
    observe,
    observed_history,
    production_database,
    reference_parties,
)
from scripts.evaluation_truth import claim_catalogue  # noqa: E402


def read_jsonl(path):
    return [
        json.loads(line) for line in Path(path).read_text("utf-8").splitlines() if line
    ]


def references(question, requirements, data_root):
    spec = question["spec"]
    as_of = date.fromisoformat(question["business_as_of"])
    history = observed_history(question["dataset"], as_of, data_root)
    period = spec["resolved_period"] or dict(start=str(as_of), end=str(as_of))
    catalogue = claim_catalogue(
        history,
        as_of,
        date.fromisoformat(period["start"]),
        date.fromisoformat(period["end"]),
        parties=spec["counterparty_ids"],
        parameters=spec["parameters"],
        method=METHOD_V2,
    )
    required = set(requirements.get(question["id"], ()))
    return as_of, history, catalogue, required


async def run(questions, requirements, client, data_root):
    parties = reference_parties(data_root)
    rows = []
    for question in questions:
        spec = question["spec"]
        observed = dict(behavior="error")
        catalogue, required, error = {}, set(), None
        try:
            as_of, history, catalogue, required = references(
                question, requirements, data_root
            )
            missing = required - catalogue.keys()
            if missing:
                error = "required_selector_unavailable:" + ",".join(sorted(missing))
            client.begin_question()
            with production_database(history, parties, as_of=as_of) as connection:
                observed = await observe(
                    PromptInput(question["question_ar"], question["business_as_of"]),
                    client=client,
                    connection=connection,
                    intent_probe=False,
                )
        except Exception as exc:  # noqa: BLE001 - development diagnostics only
            observed["failure"] = "runtime_failure"
            error = f"{type(exc).__name__}: {exc}"[:300]
        grade = grade_question_v3(spec, catalogue, required, observed, method=METHOD_V2)
        rows.append(
            dict(
                id=question["id"],
                category=question["category"],
                expected_behavior=spec["expected_behavior"],
                **grade,
                detail=dict(
                    question=question["question_ar"],
                    expected=dict(
                        intent=spec["intent"],
                        behavior=spec["expected_behavior"],
                        reason=spec.get("error_code"),
                        parties=spec["counterparty_ids"],
                        period=spec["resolved_period"],
                        required=sorted(required),
                    ),
                    observed=dict(
                        behavior=observed.get("behavior"),
                        interpretation=observed.get("interpretation"),
                        claims=[c.get("field") for c in observed.get("claims", [])],
                        tools=observed.get("tools"),
                        tool_errors=observed.get("tool_errors"),
                        template_fallback=observed.get("template_fallback"),
                    ),
                    error=error,
                ),
            )
        )
        mark = "PASS" if rows[-1]["joint_correct"] else "FAIL"
        print(f"{question['id']} {mark}", flush=True)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ids", default="")
    parser.add_argument("--max-requests", type=int, default=200)
    parser.add_argument("--spacing-seconds", type=float, default=2)
    parser.add_argument("--aggregate-only-prefix", default="DV3C-")
    parser.add_argument("--authorize-paid", action="store_true")
    args = parser.parse_args(argv)
    if not args.authorize_paid:
        raise SystemExit("PAID_CALLS_NOT_AUTHORIZED")
    if args.output.exists():
        raise SystemExit("OUTPUT_EXISTS")
    questions = read_jsonl(args.questions)
    if args.ids:
        wanted = set(args.ids.split(","))
        questions = [q for q in questions if q["id"] in wanted]
    requirements = {
        r["id"]: r["required_fields"] for r in read_jsonl(args.requirements)
    }

    from app.config import runtime_settings
    from scripts.evaluation_clients import BudgetedClient

    settings = runtime_settings().model_copy(
        update=dict(
            llm_provider="gemini",
            llm_model_id="gemini-3.8-flash",
            llm_fallback_provider="openai",
            llm_fallback_model_id="gpt-6-luna",
            llm_timeout_seconds=30,
            llm_max_output_tokens=8192,
        )
    )
    client = BudgetedClient(
        settings,
        max_requests=args.max_requests,
        spacing_seconds=args.spacing_seconds,
    )
    if not client.available:
        raise SystemExit("PROVIDER_NOT_CONFIGURED")

    async def live():
        async with client:
            return await run(questions, requirements, client, ROOT / "data")

    started = datetime.now(UTC).isoformat()
    rows = asyncio.run(live())
    withheld = [r for r in rows if r["id"].startswith(args.aggregate_only_prefix)]
    for row in withheld:
        row.pop("detail")
    report = dict(
        kind="development_v3",
        method="label_rules_v2_grading_v3",
        started_at=started,
        finished_at=datetime.now(UTC).isoformat(),
        questions=args.questions.as_posix(),
        metrics=aggregate_questions(rows),
        requests=client.receipt(),
        withheld_detail_count=len(withheld),
        rows=rows,
    )
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n", "utf-8"
    )
    metrics = report["metrics"]
    print(
        json.dumps(
            {
                key: metrics[key]
                for key in (
                    "historical_accuracy",
                    "safe_handling",
                    "joint_accuracy",
                    "joint_fields",
                    "failure_counts",
                )
            },
            ensure_ascii=False,
        )
    )
    print(
        json.dumps(dict(Counter(r["category"] for r in rows if not r["joint_correct"])))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
