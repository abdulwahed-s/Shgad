"""T13 groundwork: integer IQD and digits; roadmap §5.2–5.3, Appendix A."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.services.validation import (
    arabic_indic_digits,
    normalize_digits,
    parse_business_date,
    parse_iqd,
    parse_timestamp,
)


def test_t13_digit_normalization_preserves_original_text():
    original = "بذمته ١٢٣٬٤٥٦ و ۷۸۹؟"
    assert normalize_digits(original) == "بذمته 123٬456 و 789؟"
    assert original == "بذمته ١٢٣٬٤٥٦ و ۷۸۹؟"
    assert arabic_indic_digits("123٬456") == "١٢٣٬٤٥٦"
    assert normalize_digits(arabic_indic_digits("0123456789")) == "0123456789"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (100_000, 100_000),
        ("100000", 100_000),
        ("100,000", 100_000),
        ("١٠٠٬٠٠٠", 100_000),
        ("  ۴۲۰٬۰۰۰  ", 420_000),
        ("1,234,567", 1_234_567),
        ("٩٢٢٣٣٧٢٠٣٦٨٥٤٧٧٥٨٠٧", 9_223_372_036_854_775_807),
    ],
)
def test_t13_iqd_parser_accepts_exact_integer_text(value, expected):
    result = parse_iqd(value)
    assert type(result) is int
    assert result == expected


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        100.0,
        100.5,
        Decimal("100"),
        None,
        "",
        "0",
        0,
        -1,
        "-100",
        "+100",
        "100.00",
        "١٠٠٫٥",
        "1,00",
        "1,234٬567",
        "1 000",
        "٤٢٠ ألف",
        "100 USD",
        "100 IQD",
        "1e3",
        "²",
        9_223_372_036_854_775_808,
    ],
)
def test_t13_ambiguous_or_invalid_amounts_need_clarification(value):
    with pytest.raises(ValueError):
        parse_iqd(value)


def test_currency_and_zero_are_explicit():
    with pytest.raises(ValueError):
        parse_iqd("100", currency="USD")
    assert parse_iqd("٠", allow_zero=True) == 0


def test_dates_are_unambiguous_and_timestamps_normalize_to_utc():
    assert parse_business_date("٢٠٢٦-٠٩-٢٨") == date(2026, 9, 28)
    assert parse_timestamp("2026-09-28T00:30:00+03:00") == datetime(
        2026, 9, 27, 21, 30, tzinfo=UTC
    )


@pytest.mark.parametrize(
    "value", ["28/09/2026", "2026-02-30", "2026-09-28T00:00:00", 123, True]
)
def test_invalid_business_dates_are_rejected(value):
    with pytest.raises(ValueError):
        parse_business_date(value)


@pytest.mark.parametrize(
    "value", ["2026-09-28", "2026-09-28T10:00:00", 123, True, datetime(2026, 9, 28)]
)
def test_unknown_timestamp_timezone_is_rejected(value):
    with pytest.raises(ValueError):
        parse_timestamp(value)
