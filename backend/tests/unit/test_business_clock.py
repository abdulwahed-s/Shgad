"""T25: FINANCIAL_RULES §1; roadmap §5.4; API_CONTRACT §Agent tools."""

from datetime import date

import pytest

from app.config import Settings
from app.services.business_clock import BusinessClock
from app.services.errors import FinancialRuleError


@pytest.mark.parametrize(
    ("period", "start", "end", "partial"),
    [
        ("today", "2026-09-28", "2026-09-28", False),
        ("yesterday", "2026-09-27", "2026-09-27", False),
        ("this_week", "2026-09-26", "2026-09-28", True),
        ("last_week", "2026-09-19", "2026-09-25", False),
        ("this_month", "2026-09-01", "2026-09-28", True),
        ("last_month", "2026-08-01", "2026-08-31", False),
        ("last_n_days:1", "2026-09-28", "2026-09-28", False),
        ("last_n_days:90", "2026-07-01", "2026-09-28", False),
        ("next_weekday:thu", "2026-10-01", "2026-10-01", False),
        ("next_weekday:sat", "2026-10-03", "2026-10-03", False),
    ],
)
def test_t25_fixed_business_periods(period, start, end, partial):
    result = BusinessClock(date(2026, 9, 28)).resolve(period)
    assert result.start == date.fromisoformat(start)
    assert result.end == date.fromisoformat(end)
    assert result.partial is partial


def test_t25_same_weekday_requires_clarification():
    clock = BusinessClock(date(2026, 10, 1))
    with pytest.raises(FinancialRuleError) as error:
        clock.resolve("next_weekday:thu")
    assert error.value.code == "AMBIGUOUS_DATE"
    assert error.value.details["weekday"] == "thu"


def test_t25_business_date_from_environment_and_default(monkeypatch):
    monkeypatch.setenv("BUSINESS_AS_OF", "2026-10-01")
    assert BusinessClock.from_settings(Settings()).today == date(2026, 10, 1)
    monkeypatch.delenv("BUSINESS_AS_OF", raising=False)
    assert Settings().business_as_of is None
    assert BusinessClock.from_settings(Settings()).today == date(2026, 9, 28)


@pytest.mark.parametrize(
    ("as_of", "period", "start", "end", "partial"),
    [
        ("2026-09-26", "this_week", "2026-09-26", "2026-09-26", True),
        ("2026-10-02", "this_week", "2026-09-26", "2026-10-02", False),
        ("2026-01-01", "last_month", "2025-12-01", "2025-12-31", False),
        ("2024-03-01", "last_month", "2024-02-01", "2024-02-29", False),
        ("2026-09-30", "this_month", "2026-09-01", "2026-09-30", False),
    ],
)
def test_calendar_boundaries(as_of, period, start, end, partial):
    result = BusinessClock(date.fromisoformat(as_of)).resolve(period)
    assert (result.start.isoformat(), result.end.isoformat(), result.partial) == (
        start,
        end,
        partial,
    )


@pytest.mark.parametrize(
    "period",
    [
        None,
        True,
        123,
        "last_n_days:0",
        "last_n_days:91",
        "last_n_days:1.5",
        "next_weekday:x",
        "soon",
    ],
)
def test_unknown_or_invalid_period_is_not_guessed(period):
    with pytest.raises(FinancialRuleError, match="VALIDATION_ERROR"):
        BusinessClock().resolve(period)


def test_explicit_dates_need_user_provenance_and_order():
    clock = BusinessClock()
    start, end = date(2026, 9, 1), date(2026, 9, 10)
    result = clock.resolve(
        "explicit", start_date=start, end_date=end, dates_from_user=True
    )
    assert (result.start, result.end) == (start, end)
    for kwargs in (
        {"start_date": start, "end_date": end},
        {"start_date": end, "end_date": start, "dates_from_user": True},
        {"start_date": start, "dates_from_user": True},
    ):
        with pytest.raises(FinancialRuleError, match="VALIDATION_ERROR"):
            clock.resolve("explicit", **kwargs)


def test_symbolic_period_cannot_silently_override_explicit_dates():
    with pytest.raises(FinancialRuleError, match="VALIDATION_ERROR"):
        BusinessClock().resolve("today", start_date=date(2026, 9, 1))
