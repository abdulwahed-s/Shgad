"""D55 calendar catalogue: general month spellings, never development wording."""

from datetime import date

import pytest

from app.services.business_clock import BusinessClock
from app.services.errors import FinancialRuleError
from app.services.financial_queries import historical_range
from app.services.period_phrases import resolve_period

MONTHS = [
    ("كانون الثاني", 1),
    ("شباط", 2),
    ("آذار", 3),
    ("اذار", 3),
    ("نيسان", 4),
    ("أيار", 5),
    ("ايار", 5),
    ("مايس", 5),
    ("حزيران", 6),
    ("تموز", 7),
    ("آب", 8),
    ("اب", 8),
    ("أيلول", 9),
    ("ايلول", 9),
    ("تشرين الأول", 10),
    ("تشرين الاول", 10),
    ("تشرين الثاني", 11),
    ("كانون الأول", 12),
    ("كانون الاول", 12),
    ("يناير", 1),
    ("فبراير", 2),
    ("مارس", 3),
    ("أبريل", 4),
    ("ابريل", 4),
    ("مايو", 5),
    ("يونيو", 6),
    ("يوليو", 7),
    ("أغسطس", 8),
    ("اغسطس", 8),
    ("سبتمبر", 9),
    ("أكتوبر", 10),
    ("اكتوبر", 10),
    ("نوفمبر", 11),
    ("ديسمبر", 12),
    ("شهر 8", 8),
    ("شهر ٨", 8),
    ("شهر ۸", 8),
    ("بشهر ٨", 8),
    ("شهر ٠٨", 8),
    ("شهر ۰۸", 8),
    ("بآب", 8),
    ("بشهر آب", 8),
    ("بشباط", 2),
    ("وخلال شهر 9", 9),
]


@pytest.mark.parametrize("phrase,month", MONTHS)
def test_month_catalogue(phrase, month):
    result = resolve_period(phrase, weekday=0)
    assert (result.status, result.period, result.month) == (
        "resolved",
        "explicit",
        month,
    )


@pytest.mark.parametrize(
    "phrase",
    [
        "آب 2026",
        "شهر ٨ سنة ٢٠٢٦",
        "آب ۲۰۲۶",
        "آب اليوم",
        "آب هالشهر",
        "آب الشهر الماضي",
        "آب وتموز",
        "شهر 0",
        "شهر ١٣",
        "شهر 2.5",
        "شهر -8",
        "شهر 9999",
        "شهر آب الخميس",
        "كانون",
        "تشرين",
        "سنة ٢٠٢٦",
        "عام ۲۰۲۶",
        "2026",
    ],
)
def test_month_conflicts_never_guess_or_clip(phrase):
    assert resolve_period(phrase, weekday=0).status == "conflict"


@pytest.mark.parametrize(
    "phrase", ["باب المحل", "حساب المجهز", "ما عندي آباء", "شهرية العامل"]
)
def test_month_names_do_not_match_inside_words(phrase):
    assert resolve_period(phrase, weekday=0).status == "none_found"


@pytest.mark.parametrize(
    "as_of,month,start,end,partial",
    [
        ("2026-09-28", 9, "2026-09-01", "2026-09-28", True),
        ("2026-09-28", 8, "2026-08-01", "2026-08-31", False),
        ("2026-09-28", 12, "2025-12-01", "2025-12-31", False),
        ("2026-01-01", 12, "2025-12-01", "2025-12-31", False),
        ("2024-03-01", 2, "2024-02-01", "2024-02-29", False),
        ("2026-09-30", 9, "2026-09-01", "2026-09-30", False),
    ],
)
def test_business_clock_owns_named_month_boundaries(as_of, month, start, end, partial):
    resolved = BusinessClock(date.fromisoformat(as_of)).named_month(month)
    assert (str(resolved.start), str(resolved.end), resolved.partial) == (
        start,
        end,
        partial,
    )


def test_named_month_before_observed_data_is_unavailable():
    clock = BusinessClock(date(2026, 9, 28))
    resolved = clock.named_month(6)
    with pytest.raises(FinancialRuleError, match="NOT_FOUND"):
        historical_range(
            clock,
            "explicit",
            start_date=resolved.start,
            end_date=resolved.end,
            trusted_range=resolved,
        )


def test_explicit_range_does_not_authorize_itself():
    with pytest.raises(FinancialRuleError, match="VALIDATION_ERROR"):
        BusinessClock().resolve(
            "explicit", start_date=date(2026, 8, 1), end_date=date(2026, 8, 31)
        )
