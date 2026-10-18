"""Merchant-only entry contracts; no model has access to these write requests."""

from typing import Literal

from pydantic import StrictBool

from app.schemas.ledger import (
    BusinessDate,
    EventType,
    Identifier,
    LedgerModel,
    PositiveIQD,
)


class EntryRequest(LedgerModel):
    client_entry_id: Identifier
    type: Literal[
        EventType.DAILY_CASH_COUNT,
        EventType.OWNER_DRAWING,
        EventType.CREDIT_SALE,
        EventType.CREDIT_COLLECTION,
        EventType.OPERATING_EXPENSE,
        EventType.CAPITAL_INJECTION,
        EventType.CASH_SALE,
        EventType.SUPPLIER_INVOICE,
        EventType.SUPPLIER_PAYMENT,
    ]
    business_date: BusinessDate
    amount_iqd: PositiveIQD
    counterparty_id: Identifier | None = None
    obligation_id: Identifier | None = None
    due_date: BusinessDate | None = None
    note: str | None = None


class EntryReceipt(LedgerModel):
    transaction_id: Identifier
    source_id: Identifier
    duplicate: StrictBool = False


class VoidReceipt(LedgerModel):
    source_id: Identifier
    status: Literal["voided"] = "voided"
    void_id: Identifier
    reason: str
    duplicate: StrictBool = False
