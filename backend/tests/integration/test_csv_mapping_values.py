"""D59: real mapped-value preview/confirmation on the fictional sample shop."""

import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "arabic_drill_import.csv"
HEADERS = {
    "رقم": "source_id",
    "التاريخ": "occurred_at",
    "النوع": "type",
    "المبلغ": "amount_iqd",
    "الزبون": "counterparty_id",
    "ملاحظات": "description",
    "موعد السداد": "due_date",
}


@pytest.mark.parametrize(
    ("field", "value"), [("business_date", "2026-09-27"), ("due_date", "2026-10-01")]
)
def test_semantic_row_errors_point_to_the_actual_field(api, field, value):
    content = (
        f"source_id,occurred_at,type,amount_iqd,{field}\n"
        f"SEMANTIC,28/09/2026,CASH_SALE,1000,{value}\n"
    ).encode()
    columns = [
        {"source_header": h, "target_field": h}
        for h in ("source_id", "occurred_at", "type", "amount_iqd", field)
    ]
    body = api.post(
        "/api/imports/csv/mapping",
        files={"file": ("synthetic.csv", content, "text/csv")},
        data={"columns_json": json.dumps({"columns": columns})},
    ).json()
    assert not body["can_confirm"]
    assert body["preview_rows"][0]["errors"][0]["field"] == field


def preview(api, content=None):
    columns = [{"source_header": h, "target_field": t} for h, t in HEADERS.items()]
    response = api.post(
        "/api/imports/csv/mapping",
        files={"file": ("synthetic.csv", content or FIXTURE.read_bytes(), "text/csv")},
        data={"columns_json": json.dumps({"columns": columns})},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_same_in_file_credit_sale_without_due_is_rejected_with_named_field(api, ledger):
    content = (
        b"Ref,At,Kind,IQD,Party,Debt,Due\n"
        b"MAP-1,2026-09-27T12:00:00+03:00,CREDIT_SALE,70000,CUST-01,MAPPED-DEBT,\n"
        b"MAP-2,2026-09-27T12:00:00+03:00,CREDIT_COLLECTION,30000,CUST-01,MAPPED-DEBT,\n"
    )
    columns = [
        {"source_header": header, "target_field": field}
        for header, field in (
            ("Ref", "source_id"),
            ("At", "occurred_at"),
            ("Kind", "type"),
            ("IQD", "amount_iqd"),
            ("Party", "counterparty_id"),
            ("Debt", "obligation_id"),
            ("Due", "due_date"),
        )
    ]
    body = api.post(
        "/api/imports/csv/mapping",
        files={"file": ("synthetic.csv", content, "text/csv")},
        data={"columns_json": json.dumps({"columns": columns})},
    ).json()
    assert body["can_confirm"] is False
    assert body["preview_rows"][0]["errors"] == [
        {
            "row": 1,
            "code": "MISSING_DUE_DATE",
            "message": "MISSING_DUE_DATE",
            "field": "due_date",
        }
    ]
    assert ledger.execute("SELECT count(*) FROM transactions").fetchone()[0] == 0
    result = api.post(f"/api/imports/csv/mapping/{body['mapping_id']}/confirm")
    assert result.json()["error"]["code"] == "MAPPING_UNRESOLVED"
    assert ledger.execute("SELECT count(*) FROM transactions").fetchone()[0] == 0


def test_arabic_values_preview_confirm_and_reimport_preserve_evidence(api, ledger):
    assert api.post("/api/demo/reset").status_code == 200
    before = ledger.execute("SELECT count(*) FROM transactions").fetchone()[0]
    body = preview(api)
    assert body["can_confirm"] is True
    assert ledger.execute("SELECT count(*) FROM transactions").fetchone()[0] == before
    assert body["preview_rows"][0]["parsed"]["business_date"] == "2026-09-28"
    assert body["preview_rows"][0]["parsed"]["amount_iqd"] == 75000
    assert body["preview_rows"][1]["parsed"]["counterparty_id"] == "CUST-06"
    assert body["preview_rows"][1]["parsed"]["obligation_id"]
    assert body["preview_rows"][2]["parsed"]["counterparty_id"] == "CUST-05"
    receipt = api.post(f"/api/imports/csv/mapping/{body['mapping_id']}/confirm").json()
    assert (
        receipt["accepted"],
        receipt["flagged_for_review"],
        receipt["rejected"],
    ) == (2, 1, 0)
    assert (
        ledger.execute("SELECT count(*) FROM transactions").fetchone()[0] == before + 3
    )
    original = api.get("/api/ledger/transactions/A-1").json()["raw_row"]
    assert original["original"]["المبلغ"] == "75,000"
    assert original["canonical"]["amount_iqd"] == "75000"
    assert any(
        "A-3" in flag["source_ids"] for flag in api.get("/api/flags").json()["items"]
    )
    again = preview(api)
    assert again["can_confirm"] is True
    replay = api.post(f"/api/imports/csv/mapping/{again['mapping_id']}/confirm").json()
    assert (
        replay["accepted"],
        replay["flagged_for_review"],
        replay["exact_duplicates"],
    ) == (0, 0, 3)


@pytest.mark.parametrize(
    ("old", "new", "code", "field"),
    [
        ("أم زين", "أبو علي", "AMBIGUOUS_COUNTERPARTY", "counterparty_id"),
        ("أم زين", "اسم مجهول", "UNKNOWN_COUNTERPARTY", "counterparty_id"),
        ("05/10/2026", "", "MISSING_DUE_DATE", "due_date"),
        ('"75,000"', "75.5", "INVALID_AMOUNT", "amount_iqd"),
        ("بيع نقدي", "دين", "UNKNOWN_TYPE", "type"),
        ("28/09/2026", "31/09/2026", "INVALID_DATE", "occurred_at"),
    ],
)
def test_mapped_errors_name_the_field_and_ambiguity_candidates(
    api, old, new, code, field
):
    assert api.post("/api/demo/reset").status_code == 200
    content = FIXTURE.read_text(encoding="utf-8").replace(old, new).encode()
    body = preview(api, content)
    assert body["can_confirm"] is False
    errors = [e for r in body["preview_rows"] for e in r["errors"]]
    assert any(e["code"] == code and e["field"] == field for e in errors)
    if code == "AMBIGUOUS_COUNTERPARTY":
        match = next(e for e in errors if e["code"] == code)
        assert {c["id"] for c in match["candidates"]} == {"CUST-02", "CUST-03"}
