"""D59 mapped CSV values: deterministic normalization, never model conversion."""

import hashlib
import re
from datetime import datetime

from app.schemas.evidence import CounterpartyView
from app.schemas.ledger import EventType
from app.services.identity import candidate_ids
from app.services.reconcile import normalize_name
from app.services.validation import (
    BAGHDAD,
    normalize_digits,
    parse_iqd,
    parse_timestamp,
)

SYNONYMS = {
    "CASH_SALE": ("بيع نقدي", "بيع كاش", "كاش", "cash sale", "cash"),
    "CREDIT_SALE": ("بيع بالدين", "بيع آجل", "credit sale"),
    "CREDIT_COLLECTION": (
        "تسديد دين",
        "تحصيل",
        "credit collection",
        "debt repayment",
        "collection",
    ),
    "SUPPLIER_INVOICE": ("فاتورة مجهز", "supplier invoice"),
    "SUPPLIER_PAYMENT": ("دفعة مجهز", "supplier payment"),
    "OPERATING_EXPENSE": ("مصروف", "operating expense", "expense"),
    "OWNER_DRAWING": ("سحب صاحب المحل", "owner drawing"),
    "CAPITAL_INJECTION": ("إضافة رأس مال", "capital injection"),
    "DAILY_CASH_COUNT": ("عد نقد", "عد النقد", "daily cash count", "cash count"),
}


def _type_form(value):
    return normalize_name(value.replace("_", " "))


def _type_table():
    table = {}
    for kind in EventType:
        for alias in (kind.value, *SYNONYMS.get(kind.value, ())):
            key = _type_form(alias)
            if key in table and table[key] != kind.value:
                raise ValueError("Conflicting import type synonym")
            table[key] = kind.value
    return table


_TYPES = _type_table()


def mapped_type(value):
    try:
        return _TYPES[_type_form(value)]
    except KeyError as exc:
        raise ValueError("Unknown mapped type") from exc


def mapped_date(value):
    value = normalize_digits(value).strip()
    try:
        return parse_timestamp(value).astimezone(BAGHDAD)
    except ValueError:
        pass
    match = re.fullmatch(
        r"(?:(\d{4})-(\d{2})-(\d{2})|(\d{1,2})([/-])(\d{1,2})\5(\d{4}))"
        r"(?:[ T](\d{2}):(\d{2}))?",
        value,
    )
    if match is None:
        raise ValueError("Invalid mapped date")
    year, month, day, local_day, _, local_month, local_year, hour, minute = (
        match.groups()
    )
    return datetime(
        int(year or local_year),
        int(month or local_month),
        int(day or local_day),
        int(hour) if hour is not None else 12,
        int(minute) if minute is not None else 0,
        tzinfo=BAGHDAD,
    )


def mapped_amount(value):
    value = normalize_digits(value).strip()
    value = re.sub(r"\s*(?:دينار|د\.ع|IQD)$", "", value, flags=re.I).strip()
    if not re.fullmatch(r"[0-9]+|[0-9]{1,3}(?:[,٬\s][0-9]{3})+", value):
        raise ValueError("Expected positive integer IQD")
    return parse_iqd(re.sub(r"[,٬\s]", "", value))


def normalize_row(raw, parties):
    """Return canonical text cells plus field/code/candidate errors, without writes."""
    row = dict(raw)
    errors = []

    def convert(field, code, function, *, required=False):
        value = row.get(field, "").strip()
        if not value and not required:
            return
        try:
            row[field] = str(function(value))
        except ValueError:
            errors.append((code, field, ()))

    convert(
        "occurred_at",
        "INVALID_DATE",
        lambda v: mapped_date(v).isoformat(),
        required=True,
    )
    convert("recorded_at", "INVALID_DATE", lambda v: mapped_date(v).isoformat())
    convert(
        "business_date", "INVALID_DATE", lambda v: mapped_date(v).date().isoformat()
    )
    convert("due_date", "INVALID_DATE", lambda v: mapped_date(v).date().isoformat())
    convert("amount_iqd", "INVALID_AMOUNT", mapped_amount, required=True)
    convert("quantity", "INVALID_AMOUNT", parse_iqd)
    convert("type", "UNKNOWN_TYPE", mapped_type, required=True)
    kind = row.get("type")
    value = row.get("counterparty_id", "").strip()
    needs_party = kind in {
        "CREDIT_SALE",
        "CREDIT_COLLECTION",
        "SUPPLIER_INVOICE",
        "SUPPLIER_PAYMENT",
    }
    if value or needs_party:
        if value in parties:
            row["counterparty_id"] = value
        else:
            allowed = (
                {"supplier"}
                if kind in {"SUPPLIER_INVOICE", "SUPPLIER_PAYMENT"}
                else {"customer"}
                if needs_party
                else {"supplier", "customer"}
            )
            matches = candidate_ids(parties, value, allowed)
            if len(matches) == 1:
                row["counterparty_id"] = matches[0]
            else:
                candidates = tuple(
                    CounterpartyView(id=key, display_name=parties[key][0])
                    for key in sorted(matches)
                )
                errors.append(
                    (
                        "AMBIGUOUS_COUNTERPARTY" if matches else "UNKNOWN_COUNTERPARTY",
                        "counterparty_id",
                        candidates,
                    )
                )
    if (
        kind in {"CREDIT_SALE", "SUPPLIER_INVOICE"}
        and not row.get("due_date", "").strip()
    ):
        errors.append(("MISSING_DUE_DATE", "due_date", ()))
    if kind == "CREDIT_SALE" and not row.get("obligation_id", "").strip():
        token = hashlib.sha256(f"synthetic_csv:{row['source_id']}".encode()).hexdigest()
        row["obligation_id"] = f"CSV-CREDIT-{token}"
    return row, tuple(errors)
