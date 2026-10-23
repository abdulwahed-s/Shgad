"""Separated historical Q&A evaluation. Held-out content is never reportable.

Only an explicitly authorized live run may open HELDOUT_PATH. Plan/replay modes
never load credentials. Independent expected specs/answers stay on the scorer side.
"""

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for source in (ROOT, ROOT / "backend"):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

from scripts.data_contract import CATEGORIES, validate_question  # noqa: E402


class EvaluationError(ValueError):
    """Only fixed public error codes; never include exception/path/question text."""


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError()
            result[key] = value
        return result

    def constant(_):
        raise ValueError()

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def seal_metadata(data_root=ROOT / "data"):
    try:
        path = Path(data_root) / "evaluation/heldout_60_manifest.json"
        if path.resolve() != path.absolute():
            raise ValueError()
        manifest = strict_json(path.read_bytes())
        if not isinstance(manifest, dict) or set(manifest) != {
            "sha256",
            "total_count",
            "counts_by_category",
            "counts_by_behavior",
        }:
            raise ValueError()
        if (
            not isinstance(manifest["sha256"], str)
            or not re.fullmatch("[0-9a-f]{64}", manifest["sha256"])
            or type(manifest["total_count"]) is not int
            or manifest["total_count"] != 60
        ):
            raise ValueError()
        for field, allowed in (
            ("counts_by_category", CATEGORIES),
            ("counts_by_behavior", {"answer", "clarify", "refuse"}),
        ):
            counts = manifest[field]
            if (
                not isinstance(counts, dict)
                or not counts
                or not counts.keys() <= allowed
            ):
                raise ValueError()
            if (
                any(type(n) is not int or n < 0 for n in counts.values())
                or sum(counts.values()) != 60
            ):
                raise ValueError()
        if manifest["counts_by_behavior"].get("answer") != 40:
            raise ValueError()
    except (OSError, ValueError, TypeError, KeyError):
        raise EvaluationError("INVALID_SEAL_MANIFEST") from None
    return manifest


def load_questions(split, *, authorized=False, data_root=ROOT / "data"):
    """Read and hash the same bytes; verify the seal BEFORE decoding private input."""
    data_root = Path(data_root)
    if split not in {"dev", "heldout"}:
        raise EvaluationError("INVALID_SPLIT")
    manifest = None
    if split == "heldout":
        if not authorized:
            raise EvaluationError("HELDOUT_NOT_AUTHORIZED")
        value = os.getenv("HELDOUT_PATH")
        if not value:
            raise EvaluationError("HELDOUT_PATH_REQUIRED")
        path = Path(value).resolve()
        if path.is_relative_to(ROOT):
            raise EvaluationError("HELDOUT_MUST_BE_EXTERNAL")
        manifest = seal_metadata(data_root)
    else:
        path = data_root / "evaluation/development_questions.jsonl"
        if path.resolve() != path.absolute():
            raise EvaluationError("PUBLIC_INPUT_PATH_REQUIRED")
    try:
        if path.stat().st_size > 2_000_000:
            raise EvaluationError("QUESTION_FILE_TOO_LARGE")
        raw = path.read_bytes()
    except OSError:
        raise EvaluationError("QUESTION_INPUT_UNAVAILABLE") from None
    digest = hashlib.sha256(raw).hexdigest()
    if split == "heldout" and digest != manifest["sha256"]:
        raise EvaluationError("HELDOUT_HASH_MISMATCH")
    try:
        rows = [strict_json(line) for line in raw.decode("utf-8-sig").splitlines()]
        if not rows or len({q["id"] for q in rows}) != len(rows):
            raise ValueError()
        for row in rows:
            validate_question(row)
            if row["arabic_review"] != "approved":
                raise ValueError()
        if split == "heldout" and (
            len(rows) != 60
            or manifest["total_count"] != len(rows)
            or dict(Counter(q["category"] for q in rows))
            != manifest["counts_by_category"]
            or dict(Counter(q["spec"]["expected_behavior"] for q in rows))
            != manifest["counts_by_behavior"]
            or sum(q["spec"]["expected_behavior"] == "answer" for q in rows) != 40
        ):
            raise ValueError()
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise EvaluationError("QUESTION_FORMAT_INVALID") from None
    return rows, digest


def plan(split, *, max_requests=None, require_clean=False):
    from scripts.evaluation_reports import frozen_snapshot

    snapshot = frozen_snapshot(require_clean=require_clean)
    if split == "heldout":
        seal = seal_metadata()
        count, digest = seal["total_count"], seal["sha256"]
    else:
        questions, digest = load_questions("dev")
        count = len(questions)
    cap = snapshot["settings"]["request_limits_by_split"][split]
    limit = max_requests if max_requests is not None else cap
    if type(limit) is not int or not 1 <= limit <= min(count * 6, cap):
        raise EvaluationError("INVALID_REQUEST_LIMIT")
    return snapshot | dict(
        split=split,
        question_count=count,
        question_sha256=digest,
        max_requests=limit,
        expected_request_range=[150, 180] if split == "heldout" else [64, 96],
        expected_outputs=[
            "results/evaluation_<actual-UTC-time>.json",
            "matching Markdown summary",
        ],
        heldout_opened=False,
        credentials_loaded=False,
        provider_requests=0,
        authorization_required=["paid_provider_calls"]
        + (["heldout_evaluation"] if split == "heldout" else []),
        measurement_blockers=["REQUIRED_FACT_POLICY_NOT_FROZEN"],
    )


async def evaluate_questions(
    questions, *, client, data_root=ROOT / "data", replay=None
):
    """Specs/truth stay in this scorer; the runtime receives only PromptInput."""
    from datetime import date

    from scripts.evaluation_metrics import grade_question
    from scripts.evaluation_runtime import (
        PromptInput,
        observe,
        observed_history,
        production_database,
        reference_parties,
    )
    from scripts.evaluation_truth import claim_catalogue, required_fields
    from scripts.make_ground_truth import answer_question

    rows = []
    parties = reference_parties(data_root)
    stopped = False
    for question in questions:
        spec = question["spec"]
        observed, catalogue, required = dict(behavior="error"), {}, set()
        if stopped:
            observed["failure"] = "runtime_failure"
        elif hasattr(client, "attempts") and client.attempts >= client.max_requests:
            observed["failure"] = "request_budget_exhausted"
        else:
            try:
                as_of = date.fromisoformat(question["business_as_of"])
                history = observed_history(question["dataset"], as_of, data_root)
                period = spec["resolved_period"] or dict(
                    start=str(as_of), end=str(as_of)
                )
                catalogue = claim_catalogue(
                    history,
                    as_of,
                    date.fromisoformat(period["start"]),
                    date.fromisoformat(period["end"]),
                    parties=spec["counterparty_ids"],
                    parameters=spec["parameters"],
                )
                required = required_fields(spec, catalogue)
                reference = answer_question(question, data_root)
                if (
                    spec["expected_behavior"] == "answer"
                    and reference["behavior"] != "answer"
                ):
                    raise EvaluationError("GROUND_TRUTH_UNAVAILABLE")
                client.begin_question(
                    replay[question["id"]] if replay is not None else None
                )
                with production_database(history, parties, as_of=as_of) as connection:
                    observed = await observe(
                        PromptInput(
                            question["question_ar"], question["business_as_of"]
                        ),
                        client=client,
                        connection=connection,
                    )
            except KeyboardInterrupt:
                stopped = True
                observed["failure"] = "runtime_failure"
            except Exception:
                # Never serialize private specs, provider text or exception values.
                observed["failure"] = "runtime_failure"
        result = grade_question(spec, catalogue, required, observed)
        rows.append(
            dict(
                id=question["id"],
                category=question["category"],
                expected_behavior=spec["expected_behavior"],
                **result,
            )
        )
    return rows


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--split", choices=("dev", "heldout"), required=True)
    result.add_argument(
        "--mode", choices=("plan", "replay", "live", "forecast"), default="plan"
    )
    result.add_argument("--forecast-split", choices=("dev", "test"), default="dev")
    result.add_argument("--authorize-final-forecast", action="store_true")
    result.add_argument("--max-requests", type=int)
    result.add_argument("--output", type=Path)
    result.add_argument(
        "--replay-file",
        type=Path,
        default=ROOT / "backend/tests/evaluation/fixtures/evaluation_replay.json",
    )
    result.add_argument(
        "--freeze-manifest",
        type=Path,
        default=ROOT / "results/evaluation_method_freeze_portable_aliases.json",
    )
    result.add_argument("--write-freeze", action="store_true")
    result.add_argument(
        "--authorize-paid",
        action="store_true",
        help="Use only after explicit user run authorization",
    )
    result.add_argument(
        "--authorize-heldout",
        action="store_true",
        help="Use only after separate explicit held-out authorization",
    )
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    from scripts.data_contract import sha256
    from scripts.evaluation_reports import (
        forecast_archive,
        now,
        public_report,
        verify_freeze,
        write_new,
        write_report,
    )

    try:
        if args.mode == "replay":
            expected = ROOT / "backend/tests/evaluation/fixtures/evaluation_replay.json"
            if (
                args.replay_file.absolute() != expected
                or args.replay_file.resolve() != expected
            ):
                raise EvaluationError("PUBLIC_REPLAY_PATH_REQUIRED")
        if args.mode in {"replay", "live"} or args.write_freeze:
            path = args.freeze_manifest.absolute()
            if (
                path.parent != ROOT / "results"
                or path.resolve() != path
                or not re.fullmatch(
                    r"evaluation_method_freeze(?:_[A-Za-z0-9_-]+)?\.json", path.name
                )
            ):
                raise EvaluationError("PUBLIC_FREEZE_PATH_REQUIRED")
        if args.mode == "forecast":
            if args.split != "dev":
                raise EvaluationError("FORECAST_REQUIRES_SEPARATE_DEV_COMMAND")
            if args.forecast_split == "test" and not args.authorize_final_forecast:
                raise EvaluationError("FINAL_TEST_NOT_AUTHORIZED")
            from scripts.evaluation_forecast import run_and_write

            output = args.output or ROOT / "results" / (
                "evaluation_forecast_"
                + now().replace(":", "").replace("+", "_")
                + ".json"
            )
            result = run_and_write(
                args.forecast_split, output, allow_final=args.authorize_final_forecast
            )
            print(
                json.dumps(
                    dict(
                        split=result["split"],
                        code_commit=result["code_commit"],
                        summary=result["summary"],
                    ),
                    sort_keys=True,
                )
            )
            return 0
        if args.split == "heldout" and args.mode == "replay":
            raise EvaluationError("HELDOUT_REPLAY_PROHIBITED")
        if args.mode == "live" and not args.authorize_paid:
            raise EvaluationError("PAID_CALLS_NOT_AUTHORIZED")
        if (
            args.mode == "live"
            and args.split == "heldout"
            and not args.authorize_heldout
        ):
            raise EvaluationError("HELDOUT_NOT_AUTHORIZED")
        if args.mode == "live":
            raise EvaluationError("REQUIRED_FACT_POLICY_NOT_FROZEN")
        if args.write_freeze and args.mode != "plan":
            raise EvaluationError("FREEZE_REQUIRES_PLAN_MODE")
        prepared = plan(
            args.split,
            max_requests=args.max_requests,
            require_clean=args.mode != "plan" or args.write_freeze,
        )
        if args.mode == "plan":
            from scripts.evaluation_reports import forecast_archive

            prepared["forecast"] = forecast_archive()
            prepared["forecast"]["requested_split"] = args.forecast_split
            prepared["forecast"]["authorization_required"] = (
                args.forecast_split == "test"
            )
            if args.write_freeze:
                write_new(
                    args.freeze_manifest,
                    json.dumps(
                        prepared | dict(frozen_at=now()),
                        sort_keys=True,
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                )
            print(
                json.dumps(
                    {
                        key: value
                        for key, value in prepared.items()
                        if key not in {"source_hashes", "input_hashes"}
                    },
                    sort_keys=True,
                )
            )
            return 0
        output = args.output or ROOT / "results" / (
            "evaluation_" + now().replace(":", "").replace("+", "_") + ".json"
        )
        if (
            output.suffix != ".json"
            or output.exists()
            or output.with_suffix(".md").exists()
        ):
            raise EvaluationError("RESULT_ALREADY_EXISTS_OR_INVALID_PATH")
        frozen = verify_freeze(args.freeze_manifest, prepared)
        questions, question_hash = load_questions(
            args.split, authorized=args.authorize_heldout
        )
        started = now()
        from scripts.evaluation_reconciliation import evaluate

        reconciliation = evaluate(ROOT / "data")
        forecast = forecast_archive()
        settings = prepared["settings"]
        if args.mode == "replay":
            from scripts.evaluation_clients import ReplayClient

            recording = strict_json(args.replay_file.read_bytes())
            if recording["kind"] != "synthetic-format-replay":
                raise EvaluationError("INVALID_REPLAY")
            replay = recording["cases"]
            questions = [q for q in questions if q["id"] in replay]
            if not questions or len(questions) != len(replay):
                raise EvaluationError("INVALID_REPLAY_CASES")
            client = ReplayClient()
            rows = asyncio.run(
                evaluate_questions(questions, client=client, replay=replay)
            )
            provider, model = "synthetic-replay", "synthetic-format-sentinel"
            settings = settings | dict(
                replay_sha256=sha256(args.replay_file),
                full_development_question_count=prepared["question_count"],
            )
        else:
            from app.config import runtime_settings
            from scripts.evaluation_clients import BudgetedClient

            # This is the only credential-loading branch, after authorization,
            # freeze verification and (when required) seal verification.
            live_settings = runtime_settings().model_copy(
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
                live_settings, max_requests=prepared["max_requests"]
            )
            if not client.available:
                raise EvaluationError("PROVIDER_NOT_CONFIGURED")

            async def live():
                async with client:
                    return await evaluate_questions(questions, client=client)

            rows = asyncio.run(live())
            provider, model = "gemini+openai-fallback", "gemini-3.8-flash+gpt-6-luna"
        metadata = prepared | dict(
            started_at=started,
            executed_at=now(),
            question_sha256=question_hash,
            provider=provider,
            model_id=model,
            settings=settings,
            requests=client.receipt(),
            freeze_sha256=sha256(args.freeze_manifest),
            frozen_code_commit=frozen["code_commit"],
        )
        report = public_report(
            split=args.split,
            mode=args.mode,
            rows=rows,
            metadata=metadata,
            reconciliation=reconciliation,
            forecast=forecast,
        )
        write_report(output, report)
        print(
            json.dumps(
                dict(
                    split=report["split"],
                    mode=report["mode"],
                    question_count=report["question_count"],
                    metrics=report["metrics"],
                    requests=report["requests"],
                ),
                sort_keys=True,
            )
        )
        return 0
    except (Exception, KeyboardInterrupt):
        # Even tracebacks from parsers/OS/providers can quote a private row/path.
        # Public errors are fixed codes; never pass through arbitrary exceptions.
        error = sys.exc_info()[1]
        code = (
            str(error)
            if isinstance(error, EvaluationError)
            else "EVALUATION_PREPARATION_OR_REPORT_FAILED"
        )
        print(json.dumps(dict(error=code)), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
