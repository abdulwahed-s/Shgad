"""Builder smoke through real HTTP routes on isolated synthetic scratch ledgers.

No credentials are loaded without --authorize-paid. A live output directory is
exclusive and durable before any provider call. Never reads evaluation answers,
future data, private questions, or the development check split.
"""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
SMOKE = ROOT / "data/evaluation/collection_smoke_v1.jsonl"
DEMO = ROOT / "data/evaluation/collection_demo_v1.json"
AS_OF = date(2026, 9, 28)
MAX_REQUESTS = 36


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plan():
    smoke = [json.loads(line) for line in SMOKE.read_text("utf-8").splitlines()]
    assert len(smoke) == len({q["id"] for q in smoke}) == 20
    assert all(q["authorship"] == "builder-written, not independent" for q in smoke)
    # The original ten demo checks are packaged unchanged for a fresh checkout.
    questions = json.loads(DEMO.read_text("utf-8"))
    assert len(questions) == 10, "ORIGINAL_DEMO_COUNT_CHANGED"
    assert all(isinstance(question, str) and question.strip() for question in questions)
    return smoke, questions


def write_json(path, value):
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def financial_snapshot(db):
    names = [
        r[0]
        for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name!='reminders' ORDER BY name"
        )
    ]
    return {
        name: [
            tuple(row) for row in db.execute(f'SELECT * FROM "{name}" ORDER BY rowid')
        ]
        for name in names
    }


def evidence(value):
    """Ignore only alias keys and the request's changing wall-clock audit time."""
    if isinstance(value, dict):
        return {
            k: evidence(v) for k, v in value.items() if k not in {"key", "known_at"}
        }
    if isinstance(value, list):
        return [evidence(v) for v in value]
    return value


def same_amount(actual, expected):
    return evidence(actual) == evidence(expected)


def draft_evidence(body, customer):
    figures, metrics = body.get("figures", []), body.get("metrics", [])
    return (
        len(figures) == 1
        and same_amount(figures[0], customer["overdue_amount"])
        and body.get("dates", {}).get("oldest_due") == customer["oldest_due_date"]
        and all(
            m.get("key") == "days_overdue"
            and m.get("value") == customer["days_overdue"]
            and m.get("source_ids") == customer["source_ids"]
            for m in metrics
        )
    )


def check_smoke(case, status, body, expected):
    collection = {
        p["counterparty_id"]: p
        for p in expected.get("collections", {}).get("items", [])
    }
    kind = case["expect"]
    if kind == "missing_cash":
        return (
            status == 422
            and body.get("error", {}).get("code") == "MISSING_OPENING_BALANCE"
        )
    if status not in (200, 201):
        return False
    is_chat = case["surface"] == "chat"
    if (
        is_chat
        and kind not in {"clarification", "refused"}
        and body.get("resolved_range") != {"start": str(AS_OF), "end": str(AS_OF)}
    ):
        return False
    if case["surface"] == "draft":
        if (
            body.get("status") != kind
            or body.get("counterparty", {}).get("id") != case["counterparty_id"]
            or body.get("tone") != case["tone"]
        ):
            return False
        if kind == "drafted":
            return draft_evidence(body, collection[case["counterparty_id"]])
        return not body.get("figures") and (
            kind != "not_due" or body.get("dates", {}).get("next_due") == "2026-09-30"
        )
    if kind == "ranked":
        return evidence(body) == evidence(expected["collections"]) and [
            p["counterparty_id"] for p in body["items"]
        ] == ["CUST-05", "CUST-04"]
    if kind == "empty":
        return not body["items"] and evidence(body) == evidence(expected["collections"])
    if kind == "memory":
        return same_amount(
            body.get("overdue_amount"),
            collection[case["counterparty_id"]]["overdue_amount"],
        ) and body.get("business_date") == str(AS_OF)
    if kind == "brief":
        brief = body.get("brief", body)
        if evidence(brief) != evidence(expected["brief"]):
            return False
        if is_chat:
            figures = {f["key"]: f for f in body.get("figures", [])}
            metrics = {m["key"]: m for m in body.get("metrics", [])}
            return (
                set(figures)
                == {"cash_on_hand", "dues_today", "dues_week", "overdue_total"}
                and all(same_amount(f, brief[k]) for k, f in figures.items())
                and set(metrics) == {"overdue_customer_count", "open_flags_count"}
                and all(evidence(m) == evidence(brief[k]) for k, m in metrics.items())
            )
        return True
    if kind in {"clarification", "refused"}:
        valid = body.get("status") == kind and not body.get("figures")
        if case["id"] == "CS-03":
            return valid and {
                p["value"] for p in (body.get("clarification") or {}).get("options", [])
            } == {"CUST-02", "CUST-03"}
        reason = {
            "CS-04": "UNKNOWN_COUNTERPARTY",
            "CS-10": "MISSING_OPENING_BALANCE",
        }.get(case["id"])
        return valid and (
            reason is None or (body.get("interpretation") or {}).get("reason") == reason
        )
    action = body.get("collection_action") or {}
    if kind == "priorities":
        figures = {f["key"]: f for f in body.get("figures", [])}
        metrics = {m["key"]: m for m in body.get("metrics", [])}
        dates = body.get("dates", {})
        customers = expected["collections"]["items"]
        return (
            body.get("status") == "answered"
            and action.get("kind") == "priorities"
            and len(figures) == len(metrics) == len(customers)
            and all(
                same_amount(
                    figures.get(f"customer_{i}.overdue_amount"), p["overdue_amount"]
                )
                and dates.get(f"customer_{i}.oldest_due") == p["oldest_due_date"]
                and metrics.get(f"customer_{i}.days_overdue", {}).get("value")
                == p["days_overdue"]
                and metrics.get(f"customer_{i}.days_overdue", {}).get("source_ids")
                == p["source_ids"]
                for i, p in enumerate(customers)
            )
        )
    if kind in {"draft", "firm"}:
        return (
            body.get("status") == "answered"
            and (body.get("interpretation") or {}).get("intent") == "draft_reminder"
            and action.get("counterparty_id") == "CUST-04"
            and (body.get("resolved_counterparty") or {}).get("id") == "CUST-04"
            and (kind != "firm" or action.get("tone") == "firm")
            and draft_evidence(body, collection["CUST-04"])
        )
    if kind in {"not_due", "nothing_owed"}:
        return (
            body.get("status") == "answered"
            and not action
            and not body.get("figures")
            and (body.get("interpretation") or {}).get("intent") == "draft_reminder"
            and (body.get("resolved_counterparty") or {}).get("id")
            == ("CUST-01" if kind == "not_due" else "CUST-EMPTY")
            and (
                kind != "not_due"
                or body.get("dates", {}).get("next_due") == "2026-09-30"
            )
        )
    raise AssertionError("UNKNOWN_EXPECTATION")


async def drill(output, client, settings):
    import httpx
    from app.api.dependencies import business_clock, database, llm_client
    from app.config import get_settings
    from app.db.connection import connect_database
    from app.db.migrations import apply_migrations
    from app.main import app
    from app.services.business_clock import BusinessClock
    from app.services.demo_seed import restore_demo

    paths = {
        name: output / f"{name}.sqlite" for name in ("primary", "overdue", "missing")
    }
    active = "primary"
    clock = BusinessClock(AS_OF)
    for name, path in paths.items():
        with connect_database(path) as db:
            apply_migrations(db)
            if name != "missing":
                restore_demo(db, clock=clock)
            if name == "overdue":
                db.execute(
                    "INSERT INTO counterparties VALUES ('CUST-EMPTY', 'أم صفاء', 'customer')"
                )
                db.commit()

    async def db_override():
        db = connect_database(paths[active])
        try:
            yield db
        finally:
            db.close()

    async def model_override():
        yield client

    originals = dict(app.dependency_overrides)
    app.dependency_overrides.update(
        {
            database: db_override,
            business_clock: lambda: clock,
            get_settings: lambda: settings,
            llm_client: model_override,
        }
    )
    last_chat = None
    rows = []
    smoke, questions = plan()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1"
        ) as api:

            async def request(method, path, payload=None):
                nonlocal last_chat
                if path in {"/api/chat", "/api/collections/draft"}:
                    if last_chat is not None:
                        await asyncio.sleep(
                            max(0, 6.1 - (time.monotonic() - last_chat))
                        )
                    last_chat = time.monotonic()
                response = await api.request(method, path, json=payload)
                return response.status_code, response.json()

            async def j1():
                status, report = await request("GET", "/api/obligations/upcoming")
                assert status == 200
                values = [
                    report[k]["amount_iqd"]
                    for k in (
                        "cash_on_hand",
                        "dues_total",
                        "expected_total",
                        "position_confirmed",
                        "position_with_expected",
                    )
                ]
                # Positions are negative; J1's shortfalls are their magnitudes.
                assert values == [420000, 650000, 150000, -230000, -80000], values
                return values

            before_j1 = await j1()
            active = "overdue"
            for party, amount, due in (
                ("CUST-04", 60000, "2026-09-20"),
                ("CUST-05", 90000, "2026-09-19"),
            ):
                status, body = await request(
                    "POST",
                    "/api/entries",
                    {
                        "client_entry_id": "COLLECTION-DRILL-" + party,
                        "type": "CREDIT_SALE",
                        "business_date": str(AS_OF),
                        "amount_iqd": amount,
                        "counterparty_id": party,
                        "due_date": due,
                    },
                )
                assert status == 201, body
            _, ranked = await request("GET", "/api/collections")
            assert [p["counterparty_id"] for p in ranked["items"]] == [
                "CUST-05",
                "CUST-04",
            ]
            snapshots = {}
            for name, path in paths.items():
                with connect_database(path) as db:
                    snapshots[name] = financial_snapshot(db)

            for case in smoke:
                active = case["fixture"]
                _, debts_before = await request("GET", "/api/collections")
                brief_status, brief_before = await request("GET", "/api/brief")
                expected = {"collections": debts_before}
                if brief_status == 200:
                    expected["brief"] = brief_before
                client.begin_question()
                surface = case["surface"]
                if surface == "chat":
                    status, body = await request(
                        "POST",
                        "/api/chat",
                        {"message": case["question_ar"], "conversation_id": case["id"]},
                    )
                elif surface == "draft":
                    status, body = await request(
                        "POST",
                        "/api/collections/draft",
                        {
                            "counterparty_id": case["counterparty_id"],
                            "tone": case["tone"],
                        },
                    )
                elif surface == "reminder":
                    status, body = await request(
                        "POST",
                        "/api/reminders",
                        {
                            "counterparty_id": case["counterparty_id"],
                            "tone": "gentle",
                            "channel": "copy",
                            "edited": True,
                        },
                    )
                    _, memory = await request("GET", "/api/collections")
                    person = next(
                        p
                        for p in memory["items"]
                        if p["counterparty_id"] == case["counterparty_id"]
                    )
                    assert (
                        person["reminder_count"] == 1
                        and person["days_since_last_reminder"] == 0
                    )
                else:
                    status, body = await request("GET", "/api/" + surface)
                row = {
                    "id": case["id"],
                    "fixture": active,
                    "surface": surface,
                    "question_ar": case["question_ar"],
                    "http_status": status,
                    "response": body,
                    "endpoint_projection": expected,
                    "passed": check_smoke(case, status, body, expected),
                }
                rows.append(row)
                write_json(output / "responses.json", rows)
                print(
                    f"{case['id']}: {'PASS' if row['passed'] else 'FAIL'}", flush=True
                )

            active = "primary"
            for index, question in enumerate(questions, 1):
                client.begin_question()
                status, body = await request(
                    "POST",
                    "/api/chat",
                    {"message": question, "conversation_id": f"DEMO-{index}"},
                )
                rows.append(
                    {
                        "id": f"DEMO-{index:02}",
                        "fixture": active,
                        "surface": "chat",
                        "question_ar": question,
                        "http_status": status,
                        "response": body,
                    }
                )
                write_json(output / "responses.json", rows)
                print(
                    f"DEMO-{index:02}: HTTP {status}, {body.get('status', 'error')}",
                    flush=True,
                )
            after_j1 = await j1()
            for name, path in paths.items():
                with connect_database(path) as db:
                    assert financial_snapshot(db) == snapshots[name], (
                        "FINANCIAL_LEDGER_CHANGED"
                    )
            return {
                "builder_smoke_passed": sum(r["passed"] for r in rows[:20]),
                "builder_smoke_total": 20,
                "demo_questions": 10,
                "j1_before": before_j1,
                "j1_after": after_j1,
                "all_financial_tables_unchanged": True,
                "requests": client.receipt(),
            }
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(originals)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorize-paid", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    smoke, questions = plan()
    if not args.authorize_paid:
        print(
            json.dumps(
                {
                    "smoke": len(smoke),
                    "original_demo": len(questions),
                    "max_requests": MAX_REQUESTS,
                    "provider_calls": 0,
                    "credentials_loaded": False,
                }
            )
        )
        return 0
    assert (
        args.output
        and args.output.resolve().parent
        == (ROOT / "docs/mvp_session/collection_agent").resolve()
    ), "OUTPUT_OUTSIDE_LOCAL_RECEIPTS"
    dirty = subprocess.check_output(
        [
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            "backend/app",
            "scripts",
            "data",
        ],
        cwd=ROOT,
    )
    assert not dirty.strip(), "RUNTIME_OR_INPUT_DIRTY"
    runtime = {
        p.relative_to(ROOT).as_posix(): digest(p)
        for folder in (ROOT / "backend/app", ROOT / "scripts")
        for p in sorted(folder.rglob("*.py"))
    }
    observed = {
        "data/synthetic/" + name: digest(ROOT / "data/synthetic" / name)
        for name in (
            "observed_90d.csv",
            "opening_balance.json",
            "categories.csv",
            "counterparties.csv",
            "payment_links.csv",
            "entry_voids.csv",
        )
    }
    args.output.mkdir(parents=True, exist_ok=False)
    head = (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    )
    write_json(
        args.output / "STARTED.json",
        {
            "started_at": datetime.now(UTC).isoformat(),
            "commit": head,
            "business_as_of": str(AS_OF),
            "max_requests": MAX_REQUESTS,
            "smoke_sha256": digest(SMOKE),
            "demo_sha256": digest(DEMO),
            "driver_sha256": digest(Path(__file__)),
            "one_authorized_attempt": True,
            "runtime_sources_sha256": runtime,
            "observed_inputs_sha256": observed,
            "settings": {
                "primary": "gemini/gemini-3.8-flash",
                "fallback": "openai/gpt-6-luna",
                "primary_timeout_seconds": 15,
                "fallback_timeout_seconds": 30,
                "reasoning_effort": "low",
                "max_output_tokens": 8192,
                "per_question_requests": 6,
                "provider_spacing_seconds": 2,
                "chat_spacing_seconds": 6.1,
            },
            "prompt_source_sha256": {
                name: runtime["backend/app/agents/" + name]
                for name in (
                    "system_instructions.py",
                    "interpreter.py",
                    "collection_agent.py",
                    "csv_mapper.py",
                )
            },
        },
    )
    from app.config import runtime_settings

    from scripts.evaluation_clients import BudgetedClient

    settings = runtime_settings().model_copy(
        update={
            "llm_provider": "gemini",
            "llm_model_id": "gemini-3.8-flash",
            "llm_fallback_provider": "openai",
            "llm_fallback_model_id": "gpt-6-luna",
            "business_as_of": AS_OF,
            "llm_primary_timeout_seconds": 15,
            "llm_timeout_seconds": 30,
            "llm_max_output_tokens": 8192,
            "gemini_reasoning_effort": "low",
        }
    )
    client = BudgetedClient(settings, max_requests=MAX_REQUESTS, spacing_seconds=2)
    assert client.available, "PROVIDER_NOT_CONFIGURED"

    async def run():
        async with client:
            return await drill(args.output, client, settings)

    report = asyncio.run(run())
    report.update(
        finished_at=datetime.now(UTC).isoformat(),
        commit=head,
        kind="builder_smoke_and_demo_not_independent_evaluation",
    )
    write_json(args.output / "aggregate.json", report)
    print(json.dumps(report), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
