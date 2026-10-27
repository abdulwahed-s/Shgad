"""LABEL_RULES_V2 §4/§5: structured time expressions resolve without model dates."""

from datetime import date

import pytest

from app.schemas.interpretation import TimeExpression
from app.services.business_clock import BusinessClock
from app.services.errors import FinancialRuleError
from app.services.time_expressions import resolve_time

MONDAY = BusinessClock(date(2026, 9, 28))
THURSDAY = BusinessClock(date(2026, 9, 3))


def span(clock, scope, **expression):
    resolved = resolve_time(TimeExpression(**expression), clock, scope=scope)
    return resolved.start.isoformat(), resolved.end.isoformat()


def code(clock, scope, **expression):
    with pytest.raises(FinancialRuleError) as error:
        resolve_time(TimeExpression(**expression), clock, scope=scope)
    return error.value.code


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ({"type": "none"}, ("2026-09-28", "2026-09-28")),
        ({"type": "today"}, ("2026-09-28", "2026-09-28")),
        ({"type": "yesterday"}, ("2026-09-27", "2026-09-27")),
        ({"type": "day_before_yesterday"}, ("2026-09-26", "2026-09-26")),
        ({"type": "this_week"}, ("2026-09-26", "2026-09-28")),
        ({"type": "last_week"}, ("2026-09-19", "2026-09-25")),
        ({"type": "this_month"}, ("2026-09-01", "2026-09-28")),
        ({"type": "last_month"}, ("2026-08-01", "2026-08-31")),
        ({"type": "month", "month": 8}, ("2026-08-01", "2026-08-31")),
        ({"type": "month", "month": 9}, ("2026-09-01", "2026-09-28")),
        ({"type": "month", "month": 7, "year": 2026}, ("2026-07-01", "2026-07-31")),
        ({"type": "last_n_days", "n": 10}, ("2026-09-19", "2026-09-28")),
        ({"type": "since_day", "day": 15}, ("2026-09-15", "2026-09-28")),
        ({"type": "since_day", "day": 29}, ("2026-08-29", "2026-09-28")),
        ({"type": "day", "day": 20}, ("2026-09-20", "2026-09-20")),
        ({"type": "day", "day": 30}, ("2026-08-30", "2026-08-30")),
        ({"type": "day", "day": 5, "month": 8}, ("2026-08-05", "2026-08-05")),
        ({"type": "day_range", "day": 10, "day_end": 15}, ("2026-09-10", "2026-09-15")),
        (
            {"type": "day_range", "day": 10, "day_end": 15, "month": 8},
            ("2026-08-10", "2026-08-15"),
        ),
        ({"type": "weekday_past", "weekday": "thu"}, ("2026-09-24", "2026-09-24")),
        ({"type": "weekday_past", "weekday": "sun"}, ("2026-09-27", "2026-09-27")),
    ],
)
def test_historical_rows_of_label_rules(expression, expected):
    assert span(MONDAY, "historical", **expression) == expected


def test_week_rules_follow_saturday_to_friday_from_any_as_of():
    assert span(THURSDAY, "historical", type="this_week") == (
        "2026-08-29",
        "2026-09-03",
    )
    assert span(THURSDAY, "historical", type="last_week") == (
        "2026-08-22",
        "2026-08-28",
    )
    assert span(THURSDAY, "historical", type="day", day=20) == (
        "2026-08-20",
        "2026-08-20",
    )


def test_summary_defaults_to_this_week():
    assert span(MONDAY, "summary", type="none") == ("2026-09-26", "2026-09-28")
    assert span(MONDAY, "summary", type="last_week") == ("2026-09-19", "2026-09-25")


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ({"type": "weekday_past", "weekday": "mon"}, "AMBIGUOUS_DATE"),
        ({"type": "day", "day": 30, "month": 2}, "VALIDATION_ERROR"),
        ({"type": "day", "day": 31, "month": 9}, "VALIDATION_ERROR"),
        ({"type": "month", "month": 6}, "NO_HISTORICAL_DATA"),
        ({"type": "month", "month": 10}, "NO_HISTORICAL_DATA"),
        ({"type": "month", "month": 8, "year": 2025}, "NO_HISTORICAL_DATA"),
        ({"type": "last_n_days", "n": 120}, "NO_HISTORICAL_DATA"),
        ({"type": "tomorrow"}, "NO_HISTORICAL_DATA"),
        ({"type": "next_n_days", "n": 7}, "NO_HISTORICAL_DATA"),
        ({"type": "day_range", "day": 15, "day_end": 10}, "VALIDATION_ERROR"),
    ],
)
def test_historical_clarifications(expression, expected):
    assert code(MONDAY, "historical", **expression) == expected


def test_week_starting_before_the_ledger_has_no_history():
    early = BusinessClock(date(2026, 7, 2))
    assert code(early, "historical", type="this_week") == "NO_HISTORICAL_DATA"
    assert span(early, "historical", type="yesterday") == ("2026-07-01", "2026-07-01")


def test_balances_are_snapshots_and_past_balances_are_out_of_scope():
    for kind in ("none", "today"):
        assert span(MONDAY, "snapshot", type=kind) == ("2026-09-28", "2026-09-28")
    assert code(MONDAY, "snapshot", type="yesterday") == "OUT_OF_SCOPE"
    assert code(MONDAY, "snapshot", type="month", month=8) == "OUT_OF_SCOPE"


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ({"type": "none"}, ("2026-09-28", "2026-10-04")),
        ({"type": "next_n_days", "n": 3}, ("2026-09-28", "2026-09-30")),
        ({"type": "next_n_days", "n": 30}, ("2026-09-28", "2026-10-27")),
        ({"type": "tomorrow"}, ("2026-09-28", "2026-09-29")),
        ({"type": "weekday_next", "weekday": "thu"}, ("2026-09-28", "2026-10-01")),
        ({"type": "weekday_next", "weekday": "sun"}, ("2026-09-28", "2026-10-04")),
        ({"type": "day", "day": 1, "month": 10}, ("2026-09-28", "2026-10-01")),
        ({"type": "day", "day": 5}, ("2026-09-28", "2026-10-05")),
    ],
)
def test_forward_windows(expression, expected):
    assert span(MONDAY, "forward", **expression) == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ({"type": "weekday_next", "weekday": "mon"}, "AMBIGUOUS_DATE"),
        ({"type": "next_n_days", "n": 31}, "VALIDATION_ERROR"),
        ({"type": "last_week"}, "OUT_OF_SCOPE"),
        ({"type": "day", "day": 1, "month": 12}, "OUT_OF_SCOPE"),
    ],
)
def test_forward_clarifications(expression, expected):
    assert code(MONDAY, "forward", **expression) == expected


def test_target_day_requires_a_future_day():
    assert span(MONDAY, "target", type="weekday_next", weekday="thu") == (
        "2026-09-28",
        "2026-10-01",
    )
    assert span(MONDAY, "target", type="tomorrow") == ("2026-09-28", "2026-09-29")
    assert code(MONDAY, "target", type="none") == "AMBIGUOUS_DATE"
    assert code(MONDAY, "target", type="today") == "AMBIGUOUS_DATE"


def test_expression_schema_is_closed_and_bounded():
    with pytest.raises(ValueError):
        TimeExpression(type="fortnight")
    with pytest.raises(ValueError):
        TimeExpression(type="day", day=0)
    with pytest.raises(ValueError):
        TimeExpression(type="month", month=13)
    with pytest.raises(ValueError):
        TimeExpression(type="day", day=5, unexpected=1)
    with pytest.raises(ValueError):
        TimeExpression(type="last_n_days")


def test_cross_month_ranges():
    assert span(
        MONDAY, "historical", type="date_range", day=25, month=8, day_end=5, month_end=9
    ) == (
        "2026-08-25",
        "2026-09-05",
    )
    early = {"type": "date_range", "day": 28, "month": 6, "day_end": 2, "month_end": 7}
    assert code(MONDAY, "historical", **early) == "NO_HISTORICAL_DATA"
    backwards = {
        "type": "date_range",
        "day": 5,
        "month": 9,
        "day_end": 25,
        "month_end": 8,
    }
    assert code(MONDAY, "historical", **backwards) == "VALIDATION_ERROR"
