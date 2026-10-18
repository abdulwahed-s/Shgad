"""Offline model routing comparison, budgets and joint label checks."""

import json
from pathlib import Path

import httpx
import pytest
from scripts import model_smoke_test as smoke


def completion(*, content=None, calls=()):
    return {
        "model": "recorded-model",
        "choices": [{"message": {"content": content, "tool_calls": list(calls)}}],
    }


def call(name="get_sales", **arguments):
    return {
        "id": "recorded-call",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def interpretation(**overrides):
    return completion(
        content=json.dumps(
            {
                "intent": "sales",
                "behavior": "answer",
                "counterparty_queries": [],
                "period": "this_week",
            }
            | overrides
        )
    )


@pytest.fixture
def cases():
    return {q["id"]: q for q in smoke.development_cases()}


def test_d15_joint_requires_intent_tool_customer_and_server_resolved_period(cases):
    question = cases["DEV-006"]
    selection = completion(calls=[call("get_debts", counterparty_query="أبو حيدر")])
    parsed = interpretation(
        intent="debts", counterparty_queries=["أبو حيدر"], period="today"
    )
    good = smoke.score(question, parsed, selection)
    assert good["joint_correct"] and good["resolved_counterparty_ids"] == ["CUST-01"]
    assert good["resolved_range"] == {"start": "2026-09-28", "end": "2026-09-28"}

    for change, failed in [
        ({"intent": "sales"}, "intent_correct"),
        ({"period": "yesterday"}, "period_correct"),
        ({"counterparty_queries": ["أم نور"]}, "customer_correct"),
    ]:
        bad = smoke.score(
            question,
            interpretation(
                **(
                    {
                        "intent": "debts",
                        "counterparty_queries": ["أبو حيدر"],
                        "period": "today",
                    }
                    | change
                )
            ),
            selection,
        )
        assert not bad[failed] and not bad["joint_correct"]
    wrong_tool_party = completion(
        calls=[call("get_debts", counterparty_query="أم نور")]
    )
    assert not smoke.score(question, parsed, wrong_tool_party)["joint_correct"]


@pytest.mark.parametrize(
    "bad_call",
    [
        call("execute_sql", sql="DELETE FROM transactions"),
        call(period="this_week", sql="SELECT 1"),
        call(period="explicit", start_date="2026-09-26", end_date="2026-09-28"),
        call("get_debts", overdue_only="false"),
    ],
)
def test_real_registry_rejects_unknown_extra_coerced_and_computed_arguments(
    cases, bad_call
):
    scored = smoke.score(
        cases["DEV-001"], interpretation(), completion(calls=[bad_call])
    )
    assert not scored["tool_arguments_valid"] and not scored["joint_correct"]


def test_correct_classification_cannot_hide_wrong_native_tool_period(cases):
    scored = smoke.score(
        cases["DEV-001"],
        interpretation(),
        completion(calls=[call(period="last_week", kind="cash")]),
    )
    assert scored["period_correct"]
    assert not scored["tool_context_correct"] and not scored["joint_correct"]


def test_same_weekday_clarifies_without_tools_and_refusal_is_scored(cases):
    clarified = smoke.score(
        cases["DEV-024"], interpretation(behavior="clarify", period=None), completion()
    )
    assert clarified["joint_correct"]
    refused = smoke.score(
        cases["DEV-028"],
        interpretation(intent="unsupported_write", behavior="refuse", period=None),
        completion(),
    )
    assert refused["joint_correct"]
    assert not smoke.score(
        cases["DEV-028"],
        interpretation(intent="unsupported_write", behavior="answer", period=None),
        completion(),
    )["joint_correct"]


@pytest.mark.parametrize(
    "message",
    [None, [], {"tool_calls": 0}, {"tool_calls": {}}, {"tool_calls": ""}],
)
def test_malformed_native_messages_cannot_count_as_valid_refusals(cases, message):
    scored = smoke.score(
        cases["DEV-028"],
        interpretation(intent="unsupported_write", behavior="refuse", period=None),
        {"choices": [{"message": message}]},
    )
    assert not scored["tool_arguments_valid"] and not scored["joint_correct"]


def test_no_expected_labels_are_sent_and_identical_real_schemas_are_used(cases):
    first, second = smoke.payloads(cases["DEV-006"], "recorded-model")
    assert "tools" not in first and second["tools"] == list(smoke.definitions())
    assert len(second["tools"]) == 5
    for payload in (first, second):
        text = json.dumps(payload, ensure_ascii=False)
        for forbidden in (
            "expected_tools",
            "counterparty_ids",
            '"spec"',
            "calculation",
        ):
            assert forbidden not in text
        assert cases["DEV-006"]["question_ar"] in text


def test_hard_budget_counts_every_attempt_and_no_hidden_retry(cases):
    sent = []

    def sender(provider, payload):
        sent.append((provider, payload))
        return (
            interpretation()
            if len(sent) == 1
            else completion(calls=[call(period="this_week", kind="cash")])
        )

    report = smoke.compare(
        {"gemini": "recorded-model", "groq": "recorded-model"},
        sender=sender,
        max_requests=2,
        cases=[cases["DEV-001"]],
        mode="recorded",
    )
    assert len(sent) == report["request_attempts"] == 2
    assert report["live_provider_requests"] == 0
    assert report["providers"]["gemini"]["joint_correct"] == 1
    assert report["providers"]["groq"]["completed"] == 0
    assert report["providers"]["groq"]["stopped_reason"] == "REQUEST_BUDGET"


def test_rate_limit_stops_candidate_without_echoing_provider_body(cases):
    attempted = []

    def sender(provider, payload):
        attempted.append(provider)
        raise smoke.ProviderFailure("HTTP_429")

    result = smoke.compare(
        {"gemini": "recorded-model", "groq": "recorded-model"},
        sender=sender,
        max_requests=40,
        cases=[cases["DEV-001"]],
        mode="recorded",
    )
    assert attempted == ["gemini", "groq"] and result["request_attempts"] == 2
    assert all(p["stopped_reason"] == "HTTP_429" for p in result["providers"].values())


@pytest.mark.parametrize("status", [302, 400, 401, 429, 500])
def test_transport_never_logs_keys_or_provider_error_body(status):
    sentinel = "not-a-real-key-DO-NOT-LOG"

    def respond(request):
        assert request.headers["Authorization"] == f"Bearer {sentinel}"
        assert request.url.host == "api.groq.com"
        return httpx.Response(
            status,
            json={"error": sentinel},
            headers={"Location": "https://invalid.test"},
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(smoke.ProviderFailure) as caught:
            smoke.send_request(client, "groq", {"model": "recorded-model"}, sentinel)
    assert sentinel not in str(caught.value) and str(status) in str(caught.value)


def test_dry_run_never_constructs_provider_transport(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("dry-run constructed a network client")

    monkeypatch.setattr(smoke.httpx, "Client", forbidden)
    monkeypatch.setattr(smoke, "runtime_settings", forbidden, raising=False)
    assert smoke.main([]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "dry_run" and output["maximum_requests"] == 40
    assert output["case_count"] == 10


def test_input_reads_stay_on_the_explicit_development_metadata_allowlist(
    monkeypatch, capsys
):
    allowed = {
        smoke.DEVELOPMENT.resolve(),
        smoke.PARTIES.resolve(),
        (smoke.ROOT / smoke.SEAL).resolve(),
        Path(smoke.__file__).resolve(),
    }
    original = Path.open
    opened = set()

    def guarded(path, *args, **kwargs):
        assert path.resolve() in allowed, f"non-allowlisted read: {path.name}"
        opened.add(path.resolve())
        return original(path, *args, **kwargs)

    monkeypatch.setenv("HELDOUT_PATH", "C:/never-access/questions-private.jsonl")
    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "open", guarded)
        assert smoke.main([]) == 0
    assert opened.issubset(allowed) and smoke.DEVELOPMENT.resolve() in opened
    capsys.readouterr()


def test_live_requires_exact_ids_and_both_local_keys_before_requests(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(SystemExit) as caught:
        smoke.main(
            [
                "--live",
                "--gemini-model",
                "console-id",
                "--groq-model",
                "console-id",
                "--model-ids-checked-on",
                "2026-10-18",
            ]
        )
    assert caught.value.code == 2


def test_explicit_live_command_loads_fake_local_credentials_without_echoing_them(
    monkeypatch, tmp_path, capsys
):
    from app import config

    fake_file = tmp_path / "synthetic-provider-settings.fixture"
    fake_file.write_text(
        "GEMINI_API_KEY=fictional-local-gemini\n"
        "GROQ_API_KEY=fictional-local-groq\nBUSINESS_AS_OF=\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "LOCAL_ENV_FILE", fake_file, raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setattr(smoke, "ROOT", tmp_path)
    monkeypatch.setattr(smoke, "provenance", lambda: {"head_commit": "fixture"})
    seen = []

    def respond(request):
        host = request.url.host
        expected = (
            "fictional-local-groq"
            if host == "api.groq.com"
            else "fictional-local-gemini"
        )
        assert request.headers["Authorization"] == f"Bearer {expected}"
        seen.append(host)
        return httpx.Response(401, json={"error": "recorded rejection"})

    client_type = httpx.Client
    monkeypatch.setattr(
        smoke.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(respond), **kwargs),
    )
    result = smoke.main(
        [
            "--live",
            "--gemini-model",
            "recorded-model",
            "--groq-model",
            "recorded-model",
            "--model-ids-checked-on",
            "2026-10-18",
        ]
    )
    assert result == 1
    assert seen == ["generativelanguage.googleapis.com", "api.groq.com"]
    output = capsys.readouterr()
    assert "fictional-local" not in output.out + output.err
    reports = list((tmp_path / "docs/model_comparison").glob("*.json"))
    assert len(reports) == 1 and "fictional-local" not in reports[0].read_text()


def test_invalid_local_comparison_settings_are_sanitized_before_transport(
    monkeypatch, tmp_path, capsys
):
    from app import config

    fake_file = tmp_path / "synthetic-invalid-settings.fixture"
    fake_file.write_text(
        "LLM_TIMEOUT_SECONDS=fictional-sensitive-value\n", encoding="utf-8"
    )
    monkeypatch.setattr(config, "LOCAL_ENV_FILE", fake_file, raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    with pytest.raises(SystemExit) as caught:
        smoke.main(
            [
                "--live",
                "--gemini-model",
                "recorded-model",
                "--groq-model",
                "recorded-model",
                "--model-ids-checked-on",
                "2026-10-18",
            ]
        )
    assert caught.value.code == 2
    error = capsys.readouterr().err
    assert "invalid local configuration" in error
    assert "fictional-sensitive-value" not in error
