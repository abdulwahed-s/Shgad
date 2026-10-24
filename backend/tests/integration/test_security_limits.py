"""Post-evaluation security regressions; synthetic input and local ASGI only."""

import logging

import pytest
from test_import_api import csv_bytes

from app.services.errors import FinancialRuleError
from app.services.ingest import MAX_FILE_BYTES, MAX_ROWS, read_csv_content


@pytest.mark.parametrize("path", ["/api/imports/csv", "/api/imports/csv/mapping"])
@pytest.mark.parametrize("mime", ["application/zip", "text/html", "image/png"])
def test_upload_rejects_false_mime_before_provider_or_write(api, ledger, path, mime):
    response = api.post(path, files={"file": ("sample.csv", csv_bytes([{}]), mime)})
    assert response.status_code == 422
    assert response.json()["error"]["details"] == {"reason": "FILE_TYPE"}
    assert ledger.execute("SELECT count(*) FROM raw_import_rows").fetchone()[0] == 0


@pytest.mark.parametrize(
    "content",
    [b"name\na\x00b\n", b"<!doctype html>\n<script>evil</script>", b"PK\x03\x04zip"],
)
def test_upload_rejects_non_csv_content(api, ledger, content):
    response = api.post(
        "/api/imports/csv/mapping", files={"file": ("sample.csv", content, "text/csv")}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "IMPORT_REJECTED"
    assert ledger.execute("SELECT count(*) FROM csv_mappings").fetchone()[0] == 0


def test_csv_row_boundary():
    assert len(read_csv_content(b"a\n" + b"b\n" * MAX_ROWS)[1]) == MAX_ROWS
    with pytest.raises(FinancialRuleError) as error:
        read_csv_content(b"a\n" + b"b\n" * (MAX_ROWS + 1))
    assert error.value.details == {"reason": "ROW_LIMIT"}


def test_csv_byte_boundary():
    content = b"a\n" + (b"x" * 1023 + b"\n") * 5119 + b"x" * 1021 + b"\n"
    assert len(content) == MAX_FILE_BYTES
    assert len(read_csv_content(content)[1]) == 5120
    with pytest.raises(FinancialRuleError) as error:
        read_csv_content(content + b"x")
    assert error.value.details == {"reason": "FILE_SIZE"}


@pytest.mark.parametrize(
    "mime", ["text/csv; charset=utf-8", "application/octet-stream", "text/plain"]
)
def test_generic_csv_media_still_requires_content_validation(api, ledger, mime):
    response = api.post(
        "/api/imports/csv",
        files={
            "file": (
                "sample.csv",
                csv_bytes([{"description": "=fictional_formula()"}]),
                mime,
            )
        },
    )
    assert response.status_code == 200 and response.json()["accepted"] == 1
    assert (
        ledger.execute("SELECT description FROM transactions").fetchone()[0]
        == "=fictional_formula()"
    )


def test_import_deadline_rolls_back_prior_rows(api, ledger, monkeypatch):
    from app.services import import_limits, ingest

    real_parse = ingest._parse
    now = [0.0]
    monkeypatch.setattr(import_limits, "monotonic", lambda: now[0])

    def advancing_parse(*args, **kwargs):
        result = real_parse(*args, **kwargs)
        now[0] += 6
        return result

    monkeypatch.setattr(ingest, "_parse", advancing_parse)
    response = api.post(
        "/api/imports/csv",
        files={"file": ("sample.csv", csv_bytes([{}, {}, {}]), "text/csv")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"] == {"reason": "PROCESSING_TIMEOUT"}
    assert ledger.execute("SELECT count(*) FROM transactions").fetchone()[0] == 0
    assert ledger.execute("SELECT count(*) FROM raw_import_rows").fetchone()[0] == 0


@pytest.mark.parametrize("nested", [False, True])
def test_import_sql_deadline_preserves_transaction_ownership(
    ledger, monkeypatch, nested
):
    from datetime import datetime

    from app.services import import_limits, ingest
    from app.services.business_clock import BusinessClock

    ledger.execute("CREATE TABLE caller_work (value INTEGER)")
    ledger.execute("""CREATE TRIGGER slow_insert BEFORE INSERT ON transactions BEGIN
        SELECT (WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL
        SELECT x+1 FROM n WHERE x<10000) SELECT sum(x) FROM n);
        END""")
    ledger.commit()
    if nested:
        ledger.execute("INSERT INTO caller_work VALUES (7)")
    now = [0.0]
    monkeypatch.setattr(import_limits, "monotonic", lambda: now[0])
    real_parse = ingest._parse

    def expired_parse(*args, **kwargs):
        row = real_parse(*args, **kwargs)
        now[0] = 11
        return row

    monkeypatch.setattr(ingest, "_parse", expired_parse)
    with pytest.raises(FinancialRuleError) as error:
        ingest.import_csv_bytes(
            ledger,
            csv_bytes([{}]),
            filename="synthetic.csv",
            clock=BusinessClock(),
            imported_at=datetime.fromisoformat("2026-09-28T23:59:59+03:00"),
        )
    assert error.value.details == {"reason": "PROCESSING_TIMEOUT"}
    assert ledger.execute("SELECT count(*) FROM transactions").fetchone()[0] == 0
    assert ledger.execute("SELECT count(*) FROM raw_import_rows").fetchone()[0] == 0
    assert ledger.execute("SELECT count(*) FROM caller_work").fetchone()[0] == int(
        nested
    )


def test_async_mapping_has_total_deadline(api, ledger, monkeypatch):
    import asyncio

    from app.api import imports
    from app.api.dependencies import mapping_model
    from app.main import app

    class StalledMapper:
        async def propose(self, **kwargs):
            await asyncio.sleep(1)

    monkeypatch.setattr(imports, "MAPPING_TIMEOUT_SECONDS", 0.001)
    app.dependency_overrides[mapping_model] = lambda: StalledMapper()
    response = api.post(
        "/api/imports/csv/mapping",
        files={"file": ("sample.csv", csv_bytes([{}]), "text/csv")},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "LLM_UNAVAILABLE"
    assert ledger.execute("SELECT count(*) FROM csv_mappings").fetchone()[0] == 0


def test_request_logging_is_sanitized_and_trace_ids_are_server_generated(api, caplog):
    with caplog.at_level(logging.INFO, logger="shgad.requests"):
        response = api.get(
            "/api/imports/secret-path?key=secret-query",
            headers={"x-request-id": "secret-header"},
        )
    trace = response.headers["x-request-id"]
    assert len(trace) == 32 and trace != "secret-header"
    assert "secret-" not in caplog.text
    assert trace in caplog.text
    assert "status=404" in caplog.text


def test_wrong_origin_cannot_trigger_a_write(api, ledger):
    response = api.post(
        "/api/imports/csv",
        headers={"origin": "https://evil.invalid"},
        files={"file": ("sample.csv", csv_bytes([{}]), "text/csv")},
    )
    assert response.status_code == 403
    assert ledger.execute("SELECT count(*) FROM transactions").fetchone()[0] == 0


def test_local_access_request_bounds_and_rate_limit(monkeypatch):
    import asyncio

    import httpx

    from app.api import request_safety
    from app.main import app

    async def drill():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app, client=("198.51.100.2", 12)),
            base_url="http://localhost",
        ) as client:
            response = await client.get(
                "/health", headers={"x-forwarded-for": "127.0.0.1"}
            )
            assert response.status_code == 403
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://127.0.0.1"
        ) as client:
            assert (
                await client.get("/health", headers={"host": "rebound.invalid"})
            ).status_code == 403
            assert (
                await client.post("/api/chat", headers={"content-length": "65537"})
            ).status_code == 413
            cors_error = await client.post(
                "/api/chat",
                headers={"origin": "http://localhost:5000", "content-length": "65537"},
            )
            assert cors_error.status_code == 413
            assert (
                cors_error.headers["access-control-allow-origin"]
                == "http://localhost:5000"
            )
            assert (
                await client.post("/api/chat", headers={"content-length": "bogus"})
            ).status_code == 400

            async def chunks():
                yield b"x" * 40000
                yield b"x" * 40000

            assert (await client.post("/api/chat", content=chunks())).status_code == 413
            request_safety._windows.clear()
            for _ in range(3):
                assert (await client.get("/health")).status_code == 200
            limited = await client.get(
                "/health", headers={"origin": "http://localhost:5000"}
            )
            assert limited.status_code == 429 and limited.headers["retry-after"] == "60"
            assert (
                limited.headers["access-control-allow-origin"]
                == "http://localhost:5000"
            )
            assert "x-request-id" in limited.headers

    monkeypatch.setitem(request_safety.LIMITS, "other", 3)
    asyncio.run(drill())


def test_slow_request_body_times_out_without_dispatch(monkeypatch):
    import asyncio

    from app.api import request_safety

    dispatched, sent = [], []

    async def downstream(*args):
        dispatched.append(True)

    async def receive():
        await asyncio.sleep(0.05)
        return {"type": "http.request", "body": b"{}"}

    async def send(message):
        sent.append(message)

    monkeypatch.setattr(request_safety, "BODY_TIMEOUT_SECONDS", 0.001)
    asyncio.run(
        request_safety.RequestSafety(downstream)(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/chat",
                "client": ("127.0.0.1", 5),
                "headers": [(b"host", b"localhost")],
            },
            receive,
            send,
        )
    )
    assert dispatched == []
    assert sent[0]["status"] == 408
