"""Explicit fictional sample lifecycle receipt."""

from typing import Literal

from app.schemas.ledger import LedgerModel


class DemoReceipt(LedgerModel):
    ok: Literal[True] = True
    data_version: Literal["synthetic-ledger-v1"] = "synthetic-ledger-v1"
