"""D61 morning brief: deterministic endpoint equality and typed missing cash."""

import pytest


def test_brief_matches_primary_endpoints_and_proves_empty_counts(api):
    assert api.post("/api/demo/reset").status_code == 200
    response = api.get("/api/brief")
    assert response.status_code == 200, response.text
    body = response.json()
    upcoming = api.get("/api/obligations/upcoming?days=5").json()
    assert body["as_of"] == "2026-09-28"
    assert body["week"] == {"start": "2026-09-28", "end": "2026-10-02"}
    assert (
        body["cash_on_hand"]["amount_iqd"]
        == upcoming["cash_on_hand"]["amount_iqd"]
        == 420000
    )
    assert (
        body["dues_week"]["amount_iqd"]
        == upcoming["dues_total"]["amount_iqd"]
        == 650000
    )
    assert body["dues_today"]["amount_iqd"] == 0
    assert body["dues_today"]["query_evidence"]["matching_obligations"] == 0
    assert body["overdue_total"]["amount_iqd"] == 0
    assert body["overdue_total"]["query_evidence"]["matching_obligations"] == 0
    assert body["overdue_customer_count"]["value"] == 0
    assert body["overdue_customer_count"]["query_evidence"]
    assert body["top_customers"] == []


def test_missing_opening_balance_clarifies_never_zero(api):
    response = api.get("/api/brief")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MISSING_OPENING_BALANCE"


def test_brief_flags_current_week_and_collection_top_three(
    api, ledger, j1_shop, debt_factory
):
    for index in range(3, 7):
        ledger.execute(
            "INSERT INTO counterparties VALUES (?,?,?)",
            (f"CUST-{index:02}", f"زبون تجريبي {index}", "customer"),
        )
        debt_factory(
            f"LATE-{index}", index * 10000, "2026-09-20", party=f"CUST-{index:02}"
        )
    ledger.commit()
    before = tuple(ledger.iterdump())
    body = api.get("/api/brief").json()
    ranked = api.get("/api/collections").json()
    assert body["top_customers"] == ranked["items"][:3]
    assert body["overdue_total"]["amount_iqd"] == ranked["total_overdue"]["amount_iqd"]
    assert body["overdue_customer_count"]["value"] == 4
    assert body["open_flags_count"]["value"] == 4
    assert body["open_flags_count"]["source_ids"]
    assert tuple(ledger.iterdump()) == before


def test_empty_flag_count_has_explicit_verified_query(api, j1_shop):
    body = api.get("/api/brief").json()
    assert body["open_flags_count"]["value"] == 0
    proof = body["open_flags_count"]["query_evidence"]
    assert proof["tool"] == "reconcile" and proof["matching_flags"] == 0
    assert proof["period"] == {"start": "2026-09-26", "end": "2026-09-28"}


@pytest.mark.pipeline("interpretation")
def test_brief_chat_has_same_values_no_narration_completion(ledger, j1_shop):
    from test_collection_routing import CLOCK, KNOWN, Scripted, ask

    from app.services.morning_brief import morning_brief

    client = Scripted("daily_brief")
    result = ask(ledger, "شنو عندي اليوم؟", client)
    assert result.status == "answered"
    assert result.brief == morning_brief(ledger, clock=CLOCK, known_at=KNOWN)
    assert {f.key: f.amount_iqd for f in result.figures} == {
        "cash_on_hand": 420000,
        "dues_today": 0,
        "dues_week": 650000,
        "overdue_total": 0,
    }
    assert len(client.calls) == 1
    assert (
        result.model_dump(mode="json")["metrics"][0]["query_evidence"][
            "matching_obligations"
        ]
        == 0
    )


def test_brief_new_response_models_and_provenance_openapi(api, j1_shop):
    from app.schemas.collections import MorningBrief

    body = api.get("/api/brief")
    assert MorningBrief.model_validate_json(body.content)
    spec = api.get("/openapi.json").json()
    for method, path, model, status in (
        ("get", "/api/collections", "CollectionsReport", "200"),
        ("post", "/api/collections/draft", "CollectionDraft", "200"),
        ("post", "/api/reminders", "ReminderReceipt", "201"),
        ("get", "/api/brief", "MorningBrief", "200"),
    ):
        assert spec["paths"][path][method]["responses"][status]["content"][
            "application/json"
        ]["schema"]["$ref"].endswith("/" + model)


def test_brief_renderer_rejects_forgery_and_mutated_figures(ledger, j1_shop):
    from test_collection_routing import CLOCK, KNOWN

    from app.schemas.collections import MorningBrief
    from app.services.errors import FinancialRuleError
    from app.services.morning_brief import morning_brief, require_brief_verified

    report = morning_brief(ledger, clock=CLOCK, known_at=KNOWN)
    forged = MorningBrief.model_validate_json(report.model_dump_json())
    with pytest.raises(FinancialRuleError):
        require_brief_verified(forged)
    report = report.model_copy(
        update={"dues_today": report.dues_today.model_copy(update={"amount_iqd": 99})}
    )
    with pytest.raises(FinancialRuleError):
        require_brief_verified(report)


def test_collection_drafting_uses_chat_rate_limit(api):
    for _ in range(10):
        assert (
            api.post(
                "/api/collections/draft",
                json={"counterparty_id": "UNKNOWN", "tone": "gentle"},
            ).status_code
            == 404
        )
    blocked = api.post(
        "/api/collections/draft", json={"counterparty_id": "UNKNOWN", "tone": "gentle"}
    )
    assert blocked.status_code == 429 and blocked.headers["retry-after"] == "60"
