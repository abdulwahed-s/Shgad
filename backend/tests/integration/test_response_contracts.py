"""API_CONTRACT: every implemented response has its documented Pydantic model."""

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from app.api.health import HealthResponse
from app.schemas.chat import ChatResponse
from app.schemas.csv_mapping import MappingPreview
from app.schemas.daily_close import DailyCloseView, ResolutionReceipt
from app.schemas.demo import DemoReceipt
from app.schemas.entries import EntryReceipt, VoidReceipt
from app.schemas.evidence import LedgerDetail, LedgerPage
from app.schemas.forecast import ForecastReport
from app.schemas.imports import ImportReceipt
from app.schemas.queries import DebtReport, FlagsReport, MetaReport, UpcomingObligations
from app.schemas.reports import MarginReport, WeeklyReport
from app.schemas.source_evidence import SourceEvidencePage
from app.schemas.tools import ErrorResponse

CONTRACTS = {
    ("get", "/api/evidence/sources"): SourceEvidencePage,
    ("post", "/api/demo/reset"): DemoReceipt,
    ("post", "/api/chat"): ChatResponse,
    ("get", "/health"): HealthResponse,
    ("get", "/api/meta"): MetaReport,
    ("post", "/api/entries"): EntryReceipt,
    ("post", "/api/entries/{source_id}/void"): VoidReceipt,
    ("get", "/api/daily-close/{business_date}"): DailyCloseView,
    ("post", "/api/daily-close/{business_date}/resolve"): ResolutionReceipt,
    ("post", "/api/imports/csv"): ImportReceipt,
    ("get", "/api/imports/{batch_id}"): ImportReceipt,
    ("post", "/api/imports/csv/mapping"): MappingPreview,
    ("post", "/api/imports/csv/mapping/{mapping_id}/confirm"): ImportReceipt,
    ("get", "/api/ledger/transactions"): LedgerPage,
    ("get", "/api/ledger/transactions/{source_id}"): LedgerDetail,
    ("get", "/api/debts"): DebtReport,
    ("get", "/api/obligations/upcoming"): UpcomingObligations,
    ("get", "/api/reports/weekly"): WeeklyReport,
    ("get", "/api/reports/forecast"): ForecastReport,
    ("get", "/api/reports/margin"): MarginReport,
    ("get", "/api/flags"): FlagsReport,
}


def test_every_implemented_success_response_validates(api, tool_history):
    seen = set()

    def check(path, response):
        assert 200 <= response.status_code < 300, response.text
        model = CONTRACTS[path]
        parsed = TypeAdapter(model).validate_json(response.content)
        assert json.loads(parsed.model_dump_json()) == response.json()
        seen.add(path)
        return response.json()

    for path, url in [
        ("/health", "/health"),
        ("/api/meta", "/api/meta"),
        ("/api/ledger/transactions", "/api/ledger/transactions?limit=1"),
        ("/api/ledger/transactions/{source_id}", "/api/ledger/transactions/SALE-8"),
        ("/api/debts", "/api/debts"),
        ("/api/obligations/upcoming", "/api/obligations/upcoming"),
        ("/api/reports/weekly", "/api/reports/weekly"),
        ("/api/reports/forecast", "/api/reports/forecast?scenario=all"),
        ("/api/reports/margin", "/api/reports/margin?period=this_week"),
        ("/api/flags", "/api/flags"),
        ("/api/daily-close/{business_date}", "/api/daily-close/2026-09-28"),
        ("/api/evidence/sources", "/api/evidence/sources?ids=SALE-8,CAT-01"),
    ]:
        check(("get", path), api.get(url))
    check(
        ("post", "/api/chat"),
        api.post(
            "/api/chat", json={"message": "شكد بعت؟", "conversation_id": "contract"}
        ),
    )
    entry_body = {
        "client_entry_id": "contract",
        "type": "CASH_SALE",
        "amount_iqd": 5000,
        "business_date": "2026-09-28",
    }
    saved = check(("post", "/api/entries"), api.post("/api/entries", json=entry_body))
    assert api.post("/api/entries", json=entry_body).status_code == 200
    check(
        ("post", "/api/entries/{source_id}/void"),
        api.post(
            f"/api/entries/{saved['source_id']}/void",
            json={
                "client_entry_id": "contract-v",
                "reason": "fictional contract check",
            },
        ),
    )
    check(
        ("post", "/api/daily-close/{business_date}/resolve"),
        api.post(
            "/api/daily-close/2026-09-28/resolve",
            json={
                "client_entry_id": "contract-review",
                "resolution": "expense_unrecorded",
                "amount_iqd": 1,
            },
        ),
    )
    content = (
        b"source_id,occurred_at,type,amount_iqd,counterparty_id,obligation_id,"
        b"due_date,category_id,quantity,description\n"
        b"CONTRACT-CSV,2026-09-27T12:00:00+03:00,CASH_SALE,1000,,,,,,fictional\n"
    )
    receipt = check(
        ("post", "/api/imports/csv"),
        api.post(
            "/api/imports/csv", files={"file": ("fictional.csv", content, "text/csv")}
        ),
    )
    check(
        ("get", "/api/imports/{batch_id}"),
        api.get(f"/api/imports/{receipt['batch_id']}"),
    )
    from app.api.dependencies import mapping_model
    from app.main import app

    class FakeProposer:
        def propose(self, *, headers, sample_rows):
            return json.dumps(
                {
                    "columns": [
                        {"source_header": source, "target_field": target}
                        for source, target in zip(
                            headers,
                            ("source_id", "occurred_at", "type", "amount_iqd"),
                            strict=True,
                        )
                    ]
                }
            )

    app.dependency_overrides[mapping_model] = FakeProposer
    mapping = check(
        ("post", "/api/imports/csv/mapping"),
        api.post(
            "/api/imports/csv/mapping",
            files={
                "file": (
                    "fictional.csv",
                    b"Ref,At,Kind,IQD\nMAPPED-CONTRACT,2026-09-27T12:00:00+03:00,CASH_SALE,1000\n",
                    "text/csv",
                )
            },
        ),
    )
    check(
        ("post", "/api/imports/csv/mapping/{mapping_id}/confirm"),
        api.post(f"/api/imports/csv/mapping/{mapping['mapping_id']}/confirm"),
    )
    check(("post", "/api/demo/reset"), api.post("/api/demo/reset"))
    assert seen == set(CONTRACTS)


def test_openapi_success_error_models_and_idempotent_entry_response(api):
    spec = api.get("/openapi.json").json()
    assert set(spec["paths"]) == {path for _, path in CONTRACTS}
    for (method, path), model in CONTRACTS.items():
        operation = spec["paths"][path][method]
        status = "201" if path == "/api/entries" else "200"
        assert operation["responses"][status]["content"]["application/json"]["schema"][
            "$ref"
        ].endswith("/" + model.__name__)
        for error_status in ("404", "422", "500", "503"):
            assert operation["responses"][error_status]["content"]["application/json"][
                "schema"
            ]["$ref"].endswith("/ErrorResponse")
    assert spec["paths"]["/api/entries"]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/EntryReceipt")
    assert api.get("/docs").status_code == 200


@pytest.mark.parametrize(
    "path,payload,code",
    [
        (
            "/api/daily-close/2026-09-28/resolve",
            {"resolution": "capital_injection", "amount_iqd": 1},
            "DIFFERENCE_SIGN_MISMATCH",
        ),
        (
            "/api/daily-close/2026-09-28/resolve",
            {"resolution": "expense_unrecorded", "amount_iqd": 40001},
            "DIFFERENCE_EXCEEDED",
        ),
        (
            "/api/daily-close/2026-09-19/resolve",
            {"resolution": "capital_injection", "amount_iqd": 1},
            "MISSING_COUNT",
        ),
        ("/api/entries/missing/void", {"reason": "fictional"}, "NOT_FOUND"),
    ],
)
def test_daily_close_void_errors_use_typed_error_contract(
    api, tool_history, path, payload, code
):
    before = tool_history.total_changes
    response = api.post(path, json={"client_entry_id": "bad-contract", **payload})
    parsed = ErrorResponse.model_validate_json(response.content)
    assert response.status_code == (404 if code == "NOT_FOUND" else 422)
    assert parsed.error.code == code
    assert tool_history.total_changes == before


def test_validation_and_internal_failures_are_sanitized_models(api):
    from app.api.dependencies import database
    from app.db.connection import connect_database
    from app.main import app

    for url in (
        "/api/debts?overdue_only=bad",
        "/api/obligations/upcoming?days=0",
        "/api/reports/forecast?scenario=bad",
    ):
        response = api.get(url)
        assert response.status_code == 422
        assert (
            ErrorResponse.model_validate_json(response.content).error.code
            == "VALIDATION_ERROR"
        )

    async def broken_database():
        connection = connect_database(":memory:")
        connection.close()
        yield connection

    app.dependency_overrides[database] = broken_database
    response = api.get("/api/debts")
    assert response.status_code == 500
    parsed = ErrorResponse.model_validate_json(response.content)
    assert parsed.error.code == "INTERNAL" and parsed.error.details == {}


def test_forecast_schema_enforces_thirty_days(api, tool_history):
    data = api.get("/api/reports/forecast?scenario=base").json()
    data["scenarios"]["base"]["days"].pop()
    with pytest.raises(ValidationError):
        ForecastReport.model_validate(data)
