"""Fictional demo lifecycle: no hidden inputs, no provider, atomic replacement."""

from app.config import Settings, get_settings
from app.main import app


def test_demo_reset_seeds_observed_j1_and_restores_after_entry(api):
    result = api.post("/api/demo/reset")
    assert result.status_code == 200
    assert result.json() == {"ok": True, "data_version": "synthetic-ledger-v1"}
    upcoming = api.get("/api/obligations/upcoming").json()
    assert upcoming["cash_on_hand"]["amount_iqd"] == 420000
    assert upcoming["dues_total"]["amount_iqd"] == 650000
    assert upcoming["expected_total"]["amount_iqd"] == 150000
    assert upcoming["position_confirmed"]["amount_iqd"] == -230000
    assert upcoming["position_with_expected"]["amount_iqd"] == -80000
    saved = api.post(
        "/api/entries",
        json={
            "client_entry_id": "added-after-seed",
            "type": "CASH_SALE",
            "business_date": "2026-09-28",
            "amount_iqd": 12000,
        },
    )
    assert saved.status_code == 201
    assert api.post("/api/demo/reset").status_code == 200
    assert (
        api.get("/api/ledger/transactions/" + saved.json()["source_id"]).status_code
        == 404
    )
    assert (
        api.get("/api/obligations/upcoming").json()["cash_on_hand"]["amount_iqd"]
        == 420000
    )


def test_demo_reset_is_disabled_in_production_without_touching_ledger(api, ledger):
    before = tuple(ledger.iterdump())
    app.dependency_overrides[get_settings] = lambda: Settings(app_env="production")
    assert api.post("/api/demo/reset").status_code == 404
    assert tuple(ledger.iterdump()) == before


def test_demo_seed_has_an_explicit_observed_input_allowlist(api, monkeypatch):
    from pathlib import Path

    original = Path.open
    opened = []

    def guarded(path, *args, **kwargs):
        if path.parent.name == "synthetic":
            assert path.name in {
                "observed_90d.csv",
                "opening_balance.json",
                "categories.csv",
                "counterparties.csv",
                "payment_links.csv",
                "entry_voids.csv",
            }
            opened.append(path.name)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    assert api.post("/api/demo/reset").status_code == 200
    assert set(opened) == {
        "observed_90d.csv",
        "opening_balance.json",
        "categories.csv",
        "counterparties.csv",
        "payment_links.csv",
        "entry_voids.csv",
    }


def test_failed_demo_seed_keeps_existing_immutable_database(api, ledger, monkeypatch):
    from app.services import demo_seed

    before = tuple(ledger.iterdump())

    def fail(_):
        raise ValueError("invalid synthetic fixture")

    monkeypatch.setattr(demo_seed, "_typed", fail)
    assert api.post("/api/demo/reset").status_code == 500
    assert tuple(ledger.iterdump()) == before
