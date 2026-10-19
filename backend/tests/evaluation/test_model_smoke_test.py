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


def test_rate_limit_diagnostics_allow_only_numeric_headers_and_known_error_codes(cases):
    sentinel = "fictional-secret-do-not-print"

    def respond(request):
        return httpx.Response(
            429,
            json={
                "error": {
                    "message": f"Limit 8000, Requested 12000. {sentinel}",
                    "code": "rate_limit_exceeded",
                    "type": "tokens",
                }
            },
            headers={
                "x-ratelimit-limit-tokens": "8000",
                "x-ratelimit-remaining-tokens": "3000",
                "x-ratelimit-limit-requests": sentinel,
                "retry-after": "29.2",
                "x-ratelimit-reset-tokens": "1m2.1s",
                "x-unknown": sentinel,
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        report = smoke.compare(
            {"groq": "recorded-model"},
            sender=lambda provider, payload: smoke.send_request(
                client, provider, payload, sentinel
            ),
            cases=[cases["DEV-001"]],
            max_requests=1,
        )
    detail = report["providers"]["groq"]["requests"][0]
    assert detail["provider_error_code"] == "rate_limit_exceeded"
    assert detail["rate_limits"] == {
        "limit_tokens": 8000,
        "remaining_tokens": 3000,
        "retry_after_seconds": 30,
        "token_reset_seconds": 63,
        "requested_tokens": 12000,
    }
    assert sentinel not in json.dumps(report)


def test_dry_run_never_constructs_provider_transport(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("dry-run constructed a network client")

    monkeypatch.setattr(smoke.httpx, "Client", forbidden)
    monkeypatch.setattr(smoke, "runtime_settings", forbidden, raising=False)
    assert smoke.main([]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "dry_run" and output["maximum_requests"] == 40
    assert output["case_count"] == 10
    assert output["selected_providers"] == ["gemini", "groq"]
    assert output["settings"]["max_tokens"] == 768
    assert output["settings"]["timeout_seconds"] == 20


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


def test_single_candidate_keeps_budget_and_records_safe_response_diagnostics(cases):
    sent = []

    def sender(provider, payload):
        sent.append((provider, payload))
        response = (
            interpretation()
            if len(sent) == 1
            else completion(calls=[call(period="this_week", kind="cash")])
        )
        response["choices"][0]["finish_reason"] = (
            "stop" if len(sent) == 1 else "tool_calls"
        )
        response["usage"] = {
            "prompt_tokens": 1200,
            "completion_tokens": 3000,
            "total_tokens": 4200,
            "completion_tokens_details": {"reasoning_tokens": 2900},
            "untrusted_field": "do-not-persist",
        }
        return response

    report = smoke.compare(
        {"gemini": "recorded-model"},
        sender=sender,
        max_requests=2,
        max_tokens=32768,
        cases=[cases["DEV-001"]],
    )
    assert len(sent) == report["request_attempts"] == 2
    assert all(provider == "gemini" for provider, _ in sent)
    assert all(payload["max_tokens"] == 32768 for _, payload in sent)
    summary = report["providers"]["gemini"]
    assert summary["joint_correct"] == 1
    assert [r["stage"] for r in summary["requests"]] == [
        "interpretation",
        "tool_selection",
    ]
    assert summary["requests"][0]["usage"] == {
        "prompt_tokens": 1200,
        "completion_tokens": 3000,
        "total_tokens": 4200,
        "reasoning_tokens": 2900,
    }
    assert all(type(r["elapsed_ms"]) is int for r in summary["requests"])
    assert "do-not-persist" not in json.dumps(report)


def test_truncation_diagnostics_do_not_retain_model_text_or_untrusted_metadata(cases):
    response = completion(content="do-not-persist")
    response["choices"][0]["finish_reason"] = "length"
    response["usage"] = {
        "prompt_tokens": "do-not-persist",
        "completion_tokens": -1,
        "total_tokens": True,
        "completion_tokens_details": {"reasoning_tokens": 32768},
    }
    report = smoke.compare(
        {"gemini": "recorded-model"},
        sender=lambda provider, payload: response,
        max_requests=2,
        cases=[cases["DEV-001"]],
    )
    requests = report["providers"]["gemini"]["requests"]
    assert all(r["finish_reason"] == "length" for r in requests)
    assert requests[0]["usage"] == {"reasoning_tokens": 32768}
    assert "do-not-persist" not in json.dumps(report)


@pytest.mark.parametrize(
    "arguments",
    [
        ["--max-tokens", "0"],
        ["--max-tokens", "32769"],
        ["--timeout-seconds", "0"],
        ["--timeout-seconds", "301"],
    ],
)
def test_invalid_resource_limits_fail_before_loading_credentials(
    monkeypatch, arguments
):
    def forbidden():
        pytest.fail("invalid profile loaded local credentials")

    monkeypatch.setattr(smoke, "runtime_settings", forbidden)
    with pytest.raises(SystemExit) as caught:
        smoke.main(["--live", *arguments])
    assert caught.value.code == 2


def test_single_provider_live_cli_uses_only_its_key_and_honors_resource_profile(
    monkeypatch, tmp_path, capsys
):
    from app.config import Settings

    monkeypatch.setattr(smoke, "ROOT", tmp_path)
    monkeypatch.setattr(smoke, "provenance", lambda: {"head_commit": "fixture"})
    monkeypatch.setattr(
        smoke, "runtime_settings", lambda: Settings(gemini_api_key="fictional-gemini")
    )
    monkeypatch.setattr(smoke.time, "sleep", lambda delay: None)
    seen = []

    def respond(request):
        assert request.url.host == "generativelanguage.googleapis.com"
        assert request.headers["Authorization"] == "Bearer fictional-gemini"
        assert json.loads(request.content)["max_tokens"] == 32768
        assert request.extensions["timeout"]["read"] == 180
        seen.append(request.url.host)
        return httpx.Response(200, json=interpretation())

    client_type = httpx.Client
    monkeypatch.setattr(
        smoke.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(respond), **kwargs),
    )
    result = smoke.main(
        [
            "--live",
            "--provider",
            "gemini",
            "--gemini-model",
            "recorded-model",
            "--model-ids-checked-on",
            "2026-10-18",
            "--max-requests",
            "20",
            "--max-tokens",
            "32768",
            "--timeout-seconds",
            "180",
        ]
    )
    assert result == 0 and len(seen) == 20
    output = capsys.readouterr()
    assert "fictional-gemini" not in output.out + output.err
    report_path = next((tmp_path / "docs/model_comparison").glob("*.json"))
    report = json.loads(report_path.read_text())
    assert report["live_provider_requests"] == report["maximum_requests"] == 20
    assert set(report["providers"]) == {"gemini"}
    assert report["settings"]["max_tokens"] == 32768
    assert report["settings"]["timeout_seconds"] == 180


def responses_body(*, text=None, calls=(), status="completed"):
    output = [{"type": "reasoning", "summary": []}]
    if text is not None:
        output.append(
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": text}],
            }
        )
    for native in calls:
        output.append(
            {
                "type": "function_call",
                "status": "completed",
                "call_id": native["id"],
                **native["function"],
            }
        )
    return {
        "model": "gpt-6-luna",
        "status": status,
        "output": output,
        "usage": {
            "input_tokens": 1200,
            "output_tokens": 500,
            "total_tokens": 1700,
            "output_tokens_details": {"reasoning_tokens": 450},
        },
    }


def test_luna_responses_adapter_preserves_questions_schemas_and_native_scoring(cases):
    sent = []
    parsed = interpretation()["choices"][0]["message"]["content"]

    def respond(request):
        assert request.url == "https://api.openai.com/v1/responses"
        assert request.headers["Authorization"] == "Bearer fictional-openai"
        body = json.loads(request.content)
        assert body["store"] is False
        assert body["reasoning"] == {"effort": "medium"}
        assert body["max_output_tokens"] == 32768
        assert "temperature" not in body and "max_tokens" not in body
        original = smoke.payloads(cases["DEV-001"], "gpt-6-luna", max_tokens=32768)
        assert body["input"] == original[len(sent)]["messages"]
        sent.append(body)
        if len(sent) == 1:
            assert body["text"]["format"] == {"type": "json_object"}
            assert "tools" not in body
            response = responses_body(text=parsed)
        else:
            assert body["tools"] == [
                {"type": "function", **tool["function"], "strict": False}
                for tool in smoke.definitions()
            ]
            assert body["tool_choice"] == "auto"
            response = responses_body(calls=[call(period="this_week", kind="cash")])
        return httpx.Response(200, json=response)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        report = smoke.compare(
            {"openai": "gpt-6-luna"},
            sender=lambda provider, payload: smoke.send_request(
                client, provider, payload, "fictional-openai"
            ),
            max_requests=2,
            max_tokens=32768,
            cases=[cases["DEV-001"]],
        )
    assert len(sent) == report["request_attempts"] == 2
    summary = report["providers"]["openai"]
    assert summary["joint_correct"] == 1
    assert summary["requests"][0]["usage"]["reasoning_tokens"] == 450
    assert summary["requests"][1]["finish_reason"] == "tool_calls"
    assert "fictional-openai" not in json.dumps(report)


@pytest.mark.parametrize(
    "body",
    [
        responses_body(),
        {"status": "completed", "output": []},
        {"status": "completed", "output": [{"type": "web_search_call"}]},
        {"status": "completed", "output": [None]},
    ],
)
def test_bad_responses_outputs_cannot_pass_as_valid_no_tool_answers(body):
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    ) as client:
        with pytest.raises(smoke.ProviderFailure, match="INVALID_RESPONSE"):
            smoke.send_request(
                client,
                "openai",
                smoke.payloads(smoke.development_cases()[0], "gpt-6-luna")[1],
                "fictional-openai",
            )


def test_incomplete_responses_preserve_usage_without_passing_refusal_scoring(cases):
    body = responses_body(text="partial", status="incomplete")
    body["incomplete_details"] = {"reason": "max_output_tokens"}
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    ) as client:
        result = smoke.send_request(
            client,
            "openai",
            smoke.payloads(cases["DEV-028"], "gpt-6-luna")[1],
            "fictional-openai",
        )
    assert smoke.response_diagnostics(result)["finish_reason"] == "length"
    assert smoke.response_diagnostics(result)["usage"]["reasoning_tokens"] == 450
    score = smoke.score(
        cases["DEV-028"],
        interpretation(intent="unsupported_write", behavior="refuse", period=None),
        result,
    )
    assert not score["tool_arguments_valid"] and not score["joint_correct"]


def test_openai_candidate_dry_run_is_explicit_and_never_loads_credentials(
    monkeypatch, capsys
):
    def forbidden(*args, **kwargs):
        pytest.fail("dry run accessed credentials or network")

    monkeypatch.setattr(smoke, "runtime_settings", forbidden)
    monkeypatch.setattr(smoke.httpx, "Client", forbidden)
    assert smoke.main(["--provider", "openai", "--openai-model", "gpt-6-luna"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["selected_providers"] == ["openai"]
    assert report["settings"]["temperature"] is None
    assert report["settings"]["api_protocol"] == "responses"
    assert report["settings"]["reasoning_effort"] == "medium"


@pytest.mark.parametrize("interval", ["0", "9", "61"])
def test_invalid_comparison_pacing_fails_before_credentials(monkeypatch, interval):
    def forbidden():
        pytest.fail("invalid pacing loaded credentials")

    monkeypatch.setattr(smoke, "runtime_settings", forbidden)
    with pytest.raises(SystemExit) as caught:
        smoke.main(["--live", "--minimum-interval-seconds", interval])
    assert caught.value.code == 2


def test_qwen_output_cap_is_checked_before_credentials_or_requests(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("unsupported Qwen output cap accessed credentials or transport")

    monkeypatch.setattr(smoke, "runtime_settings", forbidden)
    with pytest.raises(SystemExit) as caught:
        smoke.main(
            [
                "--live",
                "--provider",
                "groq",
                "--groq-model",
                "qwen/qwen3.8-27b",
                "--max-tokens",
                "16385",
            ]
        )
    assert caught.value.code == 2
    with pytest.raises(ValueError, match="INVALID_MODEL_TOKEN_BUDGET"):
        smoke.compare({"groq": "qwen/qwen3.8-27b"}, sender=forbidden, max_tokens=16385)


def test_qwen_cli_preserves_tools_and_records_profile_pacing_and_safe_progress(
    monkeypatch, tmp_path, capsys
):
    from app.config import Settings

    monkeypatch.setattr(smoke, "ROOT", tmp_path)
    monkeypatch.setattr(smoke, "provenance", lambda: {"head_commit": "fixture"})
    monkeypatch.setattr(
        smoke, "runtime_settings", lambda: Settings(groq_api_key="fictional-qwen")
    )
    elapsed = [0]
    delays, sent = [], []

    def sleep(seconds):
        delays.append(seconds)
        elapsed[0] += seconds

    monkeypatch.setattr(smoke.time, "monotonic", lambda: elapsed[0])
    monkeypatch.setattr(smoke.time, "sleep", sleep)

    def respond(request):
        assert request.url.host == "api.groq.com"
        assert request.headers["Authorization"] == "Bearer fictional-qwen"
        body = json.loads(request.content)
        assert body["model"] == "qwen/qwen3.8-27b"
        assert body["max_tokens"] == 16384
        assert body["temperature"] == 1
        assert body["top_p"] == 0.95
        assert body["reasoning_effort"] == "medium"
        assert body["reasoning_format"] == "hidden"
        assert request.extensions["timeout"]["read"] == 180
        if "tools" in body:
            assert body["tools"] == list(smoke.definitions())
        sent.append(body)
        result = (
            interpretation()
            if "tools" not in body
            else completion(calls=[call(period="this_week", kind="cash")])
        )
        return httpx.Response(200, json=result)

    client_type = httpx.Client
    monkeypatch.setattr(
        smoke.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(respond), **kwargs),
    )
    result = smoke.main(
        [
            "--live",
            "--provider",
            "groq",
            "--groq-model",
            "qwen/qwen3.8-27b",
            "--model-ids-checked-on",
            "2026-10-18",
            "--max-requests",
            "20",
            "--max-tokens",
            "16384",
            "--timeout-seconds",
            "180",
            "--minimum-interval-seconds",
            "30",
            "--progress",
        ]
    )
    assert result == 0 and len(sent) == 20 and delays == [30] * 19
    report = json.loads(
        next((tmp_path / "docs/model_comparison").glob("*.json")).read_text()
    )
    assert report["settings"]["temperature"] == 1
    assert report["settings"]["reasoning_effort"] == "medium"
    assert report["settings"]["minimum_request_interval_seconds"] == 30
    assert report["request_attempts"] == report["maximum_requests"] == 20
    output = capsys.readouterr()
    assert "fictional-qwen" not in output.out + output.err
    progress = [json.loads(line) for line in output.err.splitlines()]
    assert [item["completed"] for item in progress] == list(range(1, 11))
    assert progress[-1] == {
        "provider": "groq",
        "completed": 10,
        "case_count": 10,
        "request_attempts": 20,
    }
