"""FINANCIAL_RULES §1: symbolic periods resolved without the server clock."""

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta

from app.config import Settings
from app.services.errors import FinancialRuleError

DEFAULT_BUSINESS_AS_OF = date(2026, 9, 28)
_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date
    partial: bool = False


@dataclass(frozen=True)
class BusinessClock:
    as_of: date = DEFAULT_BUSINESS_AS_OF

    def __post_init__(self) -> None:
        if type(self.as_of) is not date:
            raise FinancialRuleError("VALIDATION_ERROR")

    @classmethod
    def from_settings(cls, settings: Settings) -> "BusinessClock":
        return cls(settings.business_as_of or DEFAULT_BUSINESS_AS_OF)

    @property
    def today(self) -> date:
        return self.as_of

    def resolve(
        self,
        period: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        dates_from_user: bool = False,
    ) -> DateRange:
        if not isinstance(period, str):
            raise FinancialRuleError("VALIDATION_ERROR")
        if period == "explicit":
            if (
                dates_from_user is not True
                or type(start_date) is not date
                or type(end_date) is not date
                or start_date > end_date
            ):
                raise FinancialRuleError("VALIDATION_ERROR")
            return DateRange(start_date, end_date)
        if start_date is not None or end_date is not None or dates_from_user:
            raise FinancialRuleError("VALIDATION_ERROR")
        today = self.today
        if period == "today":
            return DateRange(today, today)
        if period == "yesterday":
            yesterday = today - timedelta(days=1)
            return DateRange(yesterday, yesterday)
        week_start = today - timedelta(days=(today.weekday() - 5) % 7)
        if period == "this_week":
            return DateRange(week_start, today, partial=today.weekday() != 4)
        if period == "last_week":
            return DateRange(
                week_start - timedelta(days=7), week_start - timedelta(days=1)
            )
        month_start = today.replace(day=1)
        if period == "this_month":
            last_day = calendar.monthrange(today.year, today.month)[1]
            return DateRange(month_start, today, partial=today.day != last_day)
        if period == "last_month":
            end = month_start - timedelta(days=1)
            return DateRange(end.replace(day=1), end)
        if match := re.fullmatch(r"last_n_days:([1-9][0-9]?)", period):
            days = int(match[1])
            if days <= 90:
                return DateRange(today - timedelta(days=days - 1), today)
        if period.startswith("next_weekday:"):
            weekday = period.removeprefix("next_weekday:")
            if weekday in _WEEKDAYS:
                offset = (_WEEKDAYS[weekday] - today.weekday()) % 7
                if offset == 0:
                    raise FinancialRuleError(
                        "AMBIGUOUS_DATE", details={"weekday": weekday}
                    )
                target = today + timedelta(days=offset)
                return DateRange(target, target)
        raise FinancialRuleError("VALIDATION_ERROR")
