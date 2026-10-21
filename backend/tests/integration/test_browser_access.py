"""The local web client can reach the API without allowing arbitrary origins."""

from fastapi.testclient import TestClient

from app.main import app


def test_local_browser_preflight_and_read():
    with TestClient(app) as client:
        response = client.options(
            "/api/entries",
            headers={
                "origin": "http://127.0.0.1:8125",
                "access-control-request-method": "POST",
                "access-control-request-headers": "content-type",
            },
        )
        assert response.status_code == 200
        assert (
            response.headers["access-control-allow-origin"] == "http://127.0.0.1:8125"
        )
        assert (
            client.get("/health", headers={"origin": "http://localhost:8125"}).headers[
                "access-control-allow-origin"
            ]
            == "http://localhost:8125"
        )


def test_unrelated_browser_origin_is_not_allowed():
    with TestClient(app) as client:
        for origin in ("https://example.invalid", "http://localhost.attacker.invalid"):
            response = client.get("/health", headers={"origin": origin})
            assert "access-control-allow-origin" not in response.headers
