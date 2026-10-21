"""Merchant edits require a new immutable, validated preview; no provider call."""

import json

from app.api.dependencies import mapping_model
from app.main import app


def test_manual_mapping_edits_are_repreviewed_without_calling_provider(api, ledger):
    class ForbiddenProvider:
        def propose(self, **kwargs):
            raise AssertionError("Manual mapping must not call the provider")

    app.dependency_overrides[mapping_model] = ForbiddenProvider
    content = (
        "Ref,At,Kind,IQD\n"
        + "".join(
            f"EDIT-{i},2026-09-27T12:00:00+03:00,CASH_SALE,1000\n" for i in range(7)
        )
    ).encode()
    columns = [
        {"source_header": h, "target_field": t}
        for h, t in [
            ("Ref", "source_id"),
            ("At", "occurred_at"),
            ("Kind", "type"),
            ("IQD", None),
        ]
    ]

    def preview():
        return api.post(
            "/api/imports/csv/mapping",
            files={"file": ("fictional.csv", content, "text/csv")},
            data={"columns_json": json.dumps({"columns": columns})},
        )

    first = preview()
    assert first.status_code == 200
    assert first.json()["can_confirm"] is False
    old_id = first.json()["mapping_id"]
    original = ledger.execute(
        "SELECT preview_json FROM csv_mappings WHERE mapping_id=?", (old_id,)
    ).fetchone()[0]
    columns[-1]["target_field"] = "amount_iqd"
    second = preview()
    assert second.status_code == 200
    assert second.json()["can_confirm"] is True
    assert len(second.json()["preview_rows"]) == 5
    assert second.json()["mapping_id"] != old_id
    assert ledger.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0
    assert (
        ledger.execute(
            "SELECT preview_json FROM csv_mappings WHERE mapping_id=?", (old_id,)
        ).fetchone()[0]
        == original
    )
    result = api.post(
        "/api/imports/csv/mapping/" + second.json()["mapping_id"] + "/confirm"
    )
    assert result.status_code == 200
    assert result.json()["accepted"] + result.json()["flagged_for_review"] == 7


def test_manual_invalid_or_duplicated_target_fails_closed(api, ledger):
    content = b"Ref,Other\nA,B\n"
    for proposal in (
        "not json",
        json.dumps(
            {
                "columns": [
                    {"source_header": "Ref", "target_field": "source_id"},
                    {"source_header": "Other", "target_field": "source_id"},
                ]
            }
        ),
    ):
        response = api.post(
            "/api/imports/csv/mapping",
            files={"file": ("fictional.csv", content, "text/csv")},
            data={"columns_json": proposal},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "MAPPING_UNRESOLVED"
    assert ledger.execute("SELECT COUNT(*) FROM csv_mappings").fetchone()[0] == 0
    assert ledger.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0
