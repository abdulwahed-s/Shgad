"""API_CONTRACT debts: keep receivables and all supplier payables separate."""


def test_browser_debt_directions_use_verified_service(api, j1_shop):
    receivable = api.get("/api/debts").json()
    payable = api.get("/api/debts?direction=payable").json()
    assert receivable["total_outstanding"]["amount_iqd"] == 150000
    assert payable["total_outstanding"]["amount_iqd"] == 650000
    assert payable["customers"][0]["obligations"][0]["obligation_id"] == "OB-J1-P"
    assert api.get("/api/debts?direction=both").status_code == 422
