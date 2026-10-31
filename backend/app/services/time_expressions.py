"""LABEL_RULES_V2 §4: structured time expressions -> trusted DateRange.

Only BusinessClock arithmetic decides dates; the model supplies a closed type
and integers already proven to appear in the merchant's text. Scopes:

snapshot    balances at today (cash, debts); anything else is out of scope
historical  observed ledger days only; default today
summary     historical, default this week
forward     today .. end of a window of at most 30 days; default 7 days
target      today .. a named future day (supplier sufficiency)
"""

import calendar
from datetime import date, timedelta

from app.services.business_clock import DateRange
from app.services.errors import FinancialRuleError
from app.services.observed import OBSERVED_START

_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_PAST_ONLY = {
    "yesterday",
    "day_before_yesterday",
    "this_week",
    "last_week",
    "this_month",
    "last_month",
    "month",
    "last_n_days",
    "since_day",
    "day_range",
    "date_range",
    "weekday_past",
}
_FORWARD_LIMIT_DAYS = 30


def _fail(code):
    raise FinancialRuleError(code)


def _year(expression, today):
    if expression.year is not None and expression.year != today.year:
        _fail("NO_HISTORICAL_DATA")
    return today.year


def _day(year, month, day):
    try:
        return date(year, month, day)
    except ValueError:
        _fail("VALIDATION_ERROR")


def _previous_month(today):
    return (today.year, 12) if today.month == 1 else (today.year, today.month - 1)


def _past_day(expression, today):
    """Day D of month M, or the latest past day D (current month if D <= today)."""
    year = _year(expression, today)
    if expression.month is not None:
        return _day(year, expression.month, expression.day)
    if expression.day <= today.day:
        return _day(today.year, today.month, expression.day)
    year, month = _previous_month(today)
    return _day(year, month, expression.day)


def _historical(expression, today, *, default):
    kind = expression.type
    if kind == "none":
        kind = default
    if kind == "today":
        return DateRange(today, today)
    if kind == "yesterday":
        day = today - timedelta(days=1)
        return DateRange(day, day)
    if kind == "day_before_yesterday":
        day = today - timedelta(days=2)
        return DateRange(day, day)
    week_start = today - timedelta(days=(today.weekday() - 5) % 7)
    if kind == "this_week":
        return DateRange(week_start, today)
    if kind == "last_week":
        return DateRange(week_start - timedelta(days=7), week_start - timedelta(days=1))
    if kind == "this_month":
        return DateRange(today.replace(day=1), today)
    if kind == "last_month":
        end = today.replace(day=1) - timedelta(days=1)
        return DateRange(end.replace(day=1), end)
    if kind == "month":
        year = _year(expression, today)
        start = date(year, expression.month, 1)
        last = calendar.monthrange(year, expression.month)[1]
        return DateRange(start, min(date(year, expression.month, last), today))
    if kind == "last_n_days":
        return DateRange(today - timedelta(days=expression.n - 1), today)
    if kind == "since_day":
        return DateRange(_past_day(expression, today), today)
    if kind == "day":
        day = _past_day(expression, today)
        return DateRange(day, day)
    if kind == "day_range":
        if expression.day_end < expression.day:
            _fail("VALIDATION_ERROR")
        start = _past_day(expression, today)
        end = _day(start.year, start.month, expression.day_end)
        return DateRange(start, end)
    if kind == "date_range":
        year = _year(expression, today)
        start = _day(year, expression.month, expression.day)
        end = _day(year, expression.month_end, expression.day_end)
        if end < start:
            _fail("VALIDATION_ERROR")
        return DateRange(start, end)
    if kind == "weekday_past":
        offset = (today.weekday() - _WEEKDAYS[expression.weekday]) % 7
        if offset == 0:
            _fail("AMBIGUOUS_DATE")
        day = today - timedelta(days=offset)
        return DateRange(day, day)
    # tomorrow / next_n_days / weekday_next point into the future.
    _fail("NO_HISTORICAL_DATA")


def _future_day(expression, today):
    kind = expression.type
    if kind == "tomorrow":
        return today + timedelta(days=1)
    if kind == "weekday_next":
        offset = (_WEEKDAYS[expression.weekday] - today.weekday()) % 7
        if offset == 0:
            _fail("AMBIGUOUS_DATE")
        return today + timedelta(days=offset)
    if kind == "day":
        year = _year(expression, today) if expression.year else today.year
        if expression.month is not None:
            target = _day(year, expression.month, expression.day)
        elif expression.day > today.day:
            target = _day(today.year, today.month, expression.day)
        else:
            month = today.month % 12 + 1
            target = _day(today.year + (month == 1), month, expression.day)
        if target <= today:
            _fail("NO_HISTORICAL_DATA")
        return target
    return None


def _forward(expression, today):
    if expression.type == "this_week":
        # D59 / FINANCIAL_RULES §7a: remaining business week, Friday inclusive.
        return DateRange(today, today + timedelta(days=(4 - today.weekday()) % 7))
    if expression.type in {"none", "next_n_days"}:
        days = 7 if expression.type == "none" else expression.n
        if days > _FORWARD_LIMIT_DAYS:
            _fail("VALIDATION_ERROR")
        return DateRange(today, today + timedelta(days=days - 1))
    if expression.type in _PAST_ONLY:
        _fail("OUT_OF_SCOPE")
    target = _future_day(expression, today)
    if target is None:
        _fail("OUT_OF_SCOPE")
    if (target - today).days >= _FORWARD_LIMIT_DAYS:
        _fail("OUT_OF_SCOPE")
    return DateRange(today, target)


def resolve_time(expression, clock, *, scope):
    today = clock.today
    if scope == "snapshot":
        if expression.type not in {"none", "today"}:
            _fail("OUT_OF_SCOPE")
        return DateRange(today, today)
    if scope == "forward":
        return _forward(expression, today)
    if scope == "target":
        if expression.type in {"today", "none"}:
            return DateRange(today, today)
        if expression.type not in {"tomorrow", "weekday_next", "day"}:
            _fail("AMBIGUOUS_DATE")
        return _forward(expression, today)
    if scope not in {"historical", "summary"}:
        _fail("VALIDATION_ERROR")
    resolved = _historical(
        expression, today, default="this_week" if scope == "summary" else "today"
    )
    if not OBSERVED_START <= resolved.start <= resolved.end <= today:
        _fail("NO_HISTORICAL_DATA")
    return resolved
