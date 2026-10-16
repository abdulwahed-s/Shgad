"""Explicit text boundaries for roadmap §5.2–5.3 and Appendix A."""

import re
from datetime import UTC, date, datetime, timedelta, timezone

SQLITE_MAX_INTEGER = 2**63 - 1
# The specified synthetic 2026 calendar uses Baghdad's explicit +03:00 offset.
BAGHDAD = timezone(timedelta(hours=3), name="Asia/Baghdad")
_WESTERN = "0123456789"
_ARABIC_INDIC = "٠١٢٣٤٥٦٧٨٩"
_EASTERN_ARABIC_INDIC = "۰۱۲۳۴۵۶۷۸۹"
_TO_WESTERN = str.maketrans(_ARABIC_INDIC + _EASTERN_ARABIC_INDIC, _WESTERN * 2)
_TO_ARABIC_INDIC = str.maketrans(_WESTERN, _ARABIC_INDIC)


def normalize_digits(text: str) -> str:
    """Return a normalized copy; callers retain original text for audit."""
    return text.translate(_TO_WESTERN)


def arabic_indic_digits(text: str) -> str:
    return normalize_digits(text).translate(_TO_ARABIC_INDIC)


def parse_iqd(value: object, *, currency: str = "IQD", allow_zero: bool = False) -> int:
    """Parse an exact IQD magnitude, rejecting ambiguity rather than rounding."""
    if currency != "IQD":
        raise ValueError("Only IQD is supported")
    if type(value) is int:
        amount = value
    elif isinstance(value, str):
        text = normalize_digits(value).strip()
        if not re.fullmatch(
            r"[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+|[0-9]{1,3}(?:٬[0-9]{3})+", text
        ):
            raise ValueError("Expected integer IQD with consistent thousands groups")
        digits = text.replace(",", "").replace("٬", "")
        if len(digits) > 19:
            raise ValueError("IQD exceeds SQLite integer range")
        amount = int(digits)
    else:
        raise ValueError("Expected integer IQD or explicit integer text")
    if not (0 if allow_zero else 1) <= amount <= SQLITE_MAX_INTEGER:
        raise ValueError("IQD outside permitted integer range")
    return amount


def parse_business_date(value: object) -> date:
    if type(value) is date:
        return value
    if isinstance(value, str):
        text = normalize_digits(value)
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
            return date.fromisoformat(text)
    raise ValueError("Expected an unambiguous YYYY-MM-DD business date")


def parse_timestamp(value: object) -> datetime:
    if isinstance(value, str):
        text = normalize_digits(value)
        if not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
            r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})",
            text,
        ):
            raise ValueError("Expected an ISO timestamp with an explicit offset")
        value = datetime.fromisoformat(text)
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("Timestamp timezone is required")
    return value.astimezone(UTC)
