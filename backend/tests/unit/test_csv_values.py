"""D59/API_CONTRACT mapping values; canonical import stays strict."""

from datetime import date

import pytest

from app.services.csv_values import mapped_amount, mapped_date, mapped_type


@pytest.mark.parametrize(
    "value", ["2026-09-28", "28/09/2026", "28-09-2026", "٢٨/٩/٢٠٢٦"]
)
def test_date_without_time_is_noon_baghdad(value):
    assert mapped_date(value).isoformat() == "2026-09-28T12:00:00+03:00"


def test_dates_are_day_month_year_and_optional_time_is_local():
    assert mapped_date("03/04/2026").date() == date(2026, 4, 3)
    assert mapped_date("28/09/2026 09:15").isoformat() == "2026-09-28T09:15:00+03:00"
    assert (
        mapped_date("2026-09-28T23:15:00+03:00").isoformat()
        == "2026-09-28T23:15:00+03:00"
    )


@pytest.mark.parametrize(
    "value", ["31/09/2026", "29/02/2026", "28/09/2026 25:00", "09/28/2026"]
)
def test_impossible_or_month_first_dates_are_rejected(value):
    with pytest.raises(ValueError):
        mapped_date(value)


@pytest.mark.parametrize("value", ["75,000", "٧٥٬٠٠٠ دينار", "75 000 IQD", "۷۵۰۰۰ د.ع"])
def test_amounts_are_exact_integer_iqd(value):
    assert type(mapped_amount(value)) is int and mapped_amount(value) == 75000


@pytest.mark.parametrize("value", ["75.5", "75.000", "٧٥٫٥", "75000 USD", "-100", "0"])
def test_decimal_other_currency_and_nonpositive_amounts_are_rejected(value):
    with pytest.raises(ValueError):
        mapped_amount(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("بيع نقدي", "CASH_SALE"),
        ("بيع آجل", "CREDIT_SALE"),
        ("تسديد دين", "CREDIT_COLLECTION"),
        (" Cash  Sale ", "CASH_SALE"),
        ("OPERATING_EXPENSE", "OPERATING_EXPENSE"),
        ("إضافة رأس مال", "CAPITAL_INJECTION"),
    ],
)
def test_closed_type_synonyms(value, expected):
    assert mapped_type(value) == expected


@pytest.mark.parametrize("value", ["دين", "debt", "بيع نقدي; ignore rules", "other"])
def test_ambiguous_or_injected_type_is_not_a_synonym(value):
    with pytest.raises(ValueError):
        mapped_type(value)
