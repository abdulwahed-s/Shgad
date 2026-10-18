"""FINANCIAL_RULES §9: display abbreviation is exact and never float-based."""

from datetime import date

import pytest

from app.agents.renderer import format_date, format_iqd


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, "٠ ألف"),
        (420000, "٤٢٠ ألف"),
        (420001, "٤٢٠٬٠٠١ دينار"),
        (1000000, "١٬٠٠٠٬٠٠٠ دينار"),
        (-80000, "−٨٠ ألف"),
        (-1000001, "−١٬٠٠٠٬٠٠١ دينار"),
    ],
)
def test_exact_arabic_money(value, expected):
    assert format_iqd(value) == expected


def test_evidence_never_abbreviates_and_dates_use_exact_server_date():
    assert format_iqd(420000, evidence=True) == "٤٢٠٬٠٠٠ دينار"
    assert format_date(date(2026, 10, 1)) == "٠١/١٠/٢٠٢٦"


@pytest.mark.parametrize("value", [1.5, True, "420000", None])
def test_display_never_coerces_amount(value):
    with pytest.raises((TypeError, ValueError)):
        format_iqd(value)
