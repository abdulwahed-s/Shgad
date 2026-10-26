"""D53 general phrase catalogue; FINANCIAL_RULES §1, not evaluation wording."""

from datetime import date

import pytest
from pydantic import TypeAdapter

from app.schemas.tools import Period
from app.services.business_clock import BusinessClock
from app.services.period_phrases import resolve_period

CASES = [
    ("اليوم", "resolved", "today"),
    ("هسه اليوم", "resolved", "today"),
    ("هذا اليوم", "resolved", "today"),
    ("  الْيَوْم  ", "resolved", "today"),
    ("اليوم اليوم", "resolved", "today"),
    ("البارحة", "resolved", "yesterday"),
    ("البارحه", "resolved", "yesterday"),
    ("بارحة", "resolved", "yesterday"),
    ("بارحه", "resolved", "yesterday"),
    ("امس", "resolved", "yesterday"),
    ("أمس", "resolved", "yesterday"),
    ("اَمْس", "resolved", "yesterday"),
    ("هالأسبوع", "resolved", "this_week"),
    ("هالاسبوع", "resolved", "this_week"),
    ("هلاسبوع", "resolved", "this_week"),
    ("هذا الأسبوع", "resolved", "this_week"),
    ("هذا الاسبوع", "resolved", "this_week"),
    ("الأسبوع هذا", "resolved", "this_week"),
    ("الاسبوع هذا", "resolved", "this_week"),
    ("هالاسبوع لهسه", "resolved", "this_week"),
    ("الأسبوع الماضي", "resolved", "last_week"),
    ("الاسبوع الماضي", "resolved", "last_week"),
    ("الأسبوع الفات", "resolved", "last_week"),
    ("الاسبوع اللي فات", "resolved", "last_week"),
    ("الاسبوع الي فات", "resolved", "last_week"),
    ("الاسبوع الفايت", "resolved", "last_week"),
    ("اسبوع الماضي", "resolved", "last_week"),
    ("الاسبوع السابق", "resolved", "last_week"),
    ("هالشهر", "resolved", "this_month"),
    ("هذا الشهر", "resolved", "this_month"),
    ("الشهر هذا", "resolved", "this_month"),
    ("الشَّهْر هذا", "resolved", "this_month"),
    ("الشهر الماضي", "resolved", "last_month"),
    ("الشهر الفات", "resolved", "last_month"),
    ("الشهر اللي فات", "resolved", "last_month"),
    ("الشهر السابق", "resolved", "last_month"),
    ("آخر 7 يوم", "resolved", "last_n_days:7"),
    ("اخر 7 أيام", "resolved", "last_n_days:7"),
    ("آخر ٧ أيام", "resolved", "last_n_days:7"),
    ("اخر ۷ ايام", "resolved", "last_n_days:7"),
    ("آخر ١ يوم", "resolved", "last_n_days:1"),
    ("آخر ٩٠ يوم", "resolved", "last_n_days:90"),
    ("اخر 90 ايام", "resolved", "last_n_days:90"),
    ("آخر ٠٧ أيام", "resolved", "last_n_days:7"),
    ("خلال 7 أيام الجاية", "resolved", "next_n_days:7"),
    ("خلال ٧ ايام الجايه", "resolved", "next_n_days:7"),
    ("خلال ۷ ايام القادمه", "resolved", "next_n_days:7"),
    ("خلال 30 يوم الجاية", "resolved", "next_n_days:30"),
    ("الـ ٣ ايام الجاية", "resolved", "next_n_days:3"),
    ("باچر", "resolved", "next_weekday:tue"),
    ("باجر", "resolved", "next_weekday:tue"),
    ("بكرة", "resolved", "next_weekday:tue"),
    ("بكرا", "resolved", "next_weekday:tue"),
    ("الثلاثاء", "resolved", "next_weekday:tue"),
    ("الاربعاء", "resolved", "next_weekday:wed"),
    ("الأربعاء الجاي", "resolved", "next_weekday:wed"),
    ("الخميس", "resolved", "next_weekday:thu"),
    ("الجمعة", "resolved", "next_weekday:fri"),
    ("السبت", "resolved", "next_weekday:sat"),
    ("الأحد", "resolved", "next_weekday:sun"),
    ("الإثنين", "conflict", None),
    ("الاثنين", "conflict", None),
    ("اليوم الاثنين", "resolved", "today"),
    ("اليوم والبارحة", "conflict", None),
    ("هالاسبوع والشهر الماضي", "conflict", None),
    ("هذا الشهر الاسبوع الماضي", "conflict", None),
    ("امس باچر", "conflict", None),
    ("آخر 0 يوم", "conflict", None),
    ("اخر ٠ ايام", "conflict", None),
    ("آخر 91 يوم", "conflict", None),
    ("آخر ۹۱ أيام", "conflict", None),
    ("خلال ٣١ يوم الجاية", "conflict", None),
    ("خلال 0 ايام الجاية", "conflict", None),
    ("اخر 1.5 يوم", "conflict", None),
    ("آخر -3 يوم", "conflict", None),
    ("الاسبوع الجاي", "conflict", None),
    ("الشهر القادم", "conflict", None),
    ("الخميس الماضي", "conflict", None),
    ("السنة الماضية", "conflict", None),
    ("", "none_found", None),
    ("هلا", "none_found", None),
    ("شكد المتبقي؟", "none_found", None),
    ("دين الزبون", "none_found", None),
    ("التحصيلات", "none_found", None),
    ("الكاش", "none_found", None),
    ("مبيعات", "none_found", None),
    ("وريني كشف الحساب", "none_found", None),
    ("2026-09-01 الى 2026-09-02", "none_found", None),
    ("هسه", "none_found", None),
    ("بالسبع ايام الجاية", "none_found", None),
    ("الايام الجاية", "none_found", None),
]


@pytest.mark.parametrize("message,status,period", CASES)
def test_general_period_catalogue(message, status, period):
    result = resolve_period(message, weekday=0)
    assert (result.status, result.period) == (status, period)
    if period:
        assert TypeAdapter(Period).validate_python(period) == period


@pytest.mark.parametrize(
    "as_of,first,last,previous_first,previous_last",
    [
        ("2026-09-25", "2026-09-19", "2026-09-25", "2026-09-12", "2026-09-18"),
        ("2026-09-26", "2026-09-26", "2026-09-26", "2026-09-19", "2026-09-25"),
        ("2026-09-27", "2026-09-26", "2026-09-27", "2026-09-19", "2026-09-25"),
        ("2026-09-28", "2026-09-26", "2026-09-28", "2026-09-19", "2026-09-25"),
    ],
)
def test_saturday_week_boundaries_remain_business_clock_owned(
    as_of, first, last, previous_first, previous_last
):
    clock = BusinessClock(date.fromisoformat(as_of))
    current = clock.resolve(
        resolve_period("هذا الاسبوع", weekday=clock.today.weekday()).period
    )
    previous = clock.resolve(
        resolve_period("الاسبوع الماضي", weekday=clock.today.weekday()).period
    )
    assert (str(current.start), str(current.end)) == (first, last)
    assert (str(previous.start), str(previous.end)) == (previous_first, previous_last)


def test_period_resolver_does_not_guess_a_business_weekday():
    assert resolve_period("باچر").status == "conflict"
    assert resolve_period("الخميس").period == "next_weekday:thu"
