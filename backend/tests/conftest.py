"""Inline synthetic records for unit and integration checks."""

from datetime import date, datetime

import pytest

from app.schemas.ledger import OpeningBalance, Transaction


@pytest.fixture(autouse=True)
def offline_provider_environment(request, monkeypatch):
    """Default tests never inherit configured live provider credentials or IDs."""
    if request.node.get_closest_marker("live") is None:
        for name in (
            "LLM_PROVIDER",
            "LLM_MODEL_ID",
            "LLM_FALLBACK_PROVIDER",
            "LLM_FALLBACK_MODEL_ID",
            "GEMINI_API_KEY",
            "GROQ_API_KEY",
        ):
            monkeypatch.delenv(name, raising=False)


@pytest.fixture
def transaction_factory():
    def make(source_id="TX-001", **overrides):
        fields = {
            "transaction_id": source_id,
            "source_id": source_id,
            "source_system": "synthetic_csv",
            "source_row": 1,
            "import_batch_id": "BATCH-001",
            "occurred_at": datetime.fromisoformat("2026-09-28T10:00:00+03:00"),
            "type": "CASH_SALE",
            "amount_iqd": 100_000,
            "idempotency_key": f"synthetic_csv:{source_id}",
        }
        return Transaction(**(fields | overrides))

    return make


@pytest.fixture
def opening_balance():
    return OpeningBalance(
        opening_balance_id="OPEN-001",
        source_id="OPEN-001",
        source_system="synthetic_csv",
        source_row=1,
        import_batch_id="OPEN-BATCH",
        business_date=date(2026, 7, 1),
        amount_iqd=200_000,
    )
