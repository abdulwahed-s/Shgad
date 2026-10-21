"""Every figure source kind can be inspected without a financial write."""


def test_browser_source_lookup_transaction_category_and_unknown(
    api, insert_event, ledger
):
    insert_event(source_id="SOURCE-1", amount_iqd=12345)
    ledger.commit()
    response = api.get("/api/evidence/sources?ids=CAT-01,SOURCE-1")
    assert response.status_code == 200
    category, transaction = response.json()["items"]
    assert category["kind"] == "category"
    assert category["category"]["buy_price_iqd"] == 1000
    assert category["transaction"] is None
    assert transaction["transaction"]["amount_iqd"] == 12345
    assert api.get("/api/evidence/sources?ids=UNKNOWN").status_code == 404
    assert api.get("/api/evidence/sources?ids=CAT-01,CAT-01").status_code == 422


def test_browser_source_lookup_retains_void_and_correction(api, insert_event, ledger):
    insert_event(source_id="ORIGINAL", amount_iqd=12000)
    ledger.commit()
    receipt = api.post(
        "/api/entries/ORIGINAL/void",
        json={"client_entry_id": "void-browser", "reason": "wrong amount"},
    )
    assert receipt.status_code == 200
    row = api.get("/api/evidence/sources?ids=ORIGINAL").json()["items"][0][
        "transaction"
    ]
    assert row["status"] == "voided"
    assert row["void"]["reason"] == "wrong amount"
    assert row["amount_iqd"] == 12000


def test_browser_source_lookup_opening_respects_audit_cutoff(api, ledger):
    ledger.execute(
        """INSERT INTO raw_import_rows VALUES
        ('OPEN-RAW',
        'BATCH-001',
        900,
        '{}',
        '[]',
        'accepted')"""
    )
    ledger.execute(
        """INSERT INTO opening_balances VALUES
        ('OPEN',
        'OPEN-SOURCE',
        'synthetic_csv',
        900,
        'BATCH-001',
        '2026-07-01',
        'aggregate_cash',
        230000)"""
    )
    ledger.commit()
    result = api.get("/api/evidence/sources?ids=OPEN-SOURCE")
    assert result.status_code == 200
    assert result.json()["items"][0]["opening_balance"]["amount_iqd"] == 230000
    ledger.execute(
        """INSERT INTO import_batches VALUES
        ('LATE',
        'synthetic_csv',
        'aggregate_cash',
        ?,
        '2026-10-01T00:00:00+00:00',
        1,
        0,
        0,
        0,
        'pending')""",
        ("1" * 64,),
    )
    ledger.execute(
        "INSERT INTO raw_import_rows VALUES ('LATE-RAW','LATE',1,'{}','[]','accepted')"
    )
    ledger.execute(
        """INSERT INTO opening_balances VALUES
        ('LATE-OPEN',
        'LATE-SOURCE',
        'synthetic_csv',
        1,
        'LATE',
        '2026-07-02',
        'aggregate_cash',
        999999)"""
    )
    ledger.commit()
    assert api.get("/api/evidence/sources?ids=LATE-SOURCE").status_code == 404
