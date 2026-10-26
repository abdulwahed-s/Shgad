"""D53 / FINANCIAL_RULES §1: general Iraqi period phrases, never date arithmetic.

Catalogue: اليوم→today; البارحة/امس→yesterday; هذا/هال week/month→current;
الماضي/الفات/اللي فات→previous; اخر N يوم→last_n_days:1–90;
N ايام الجاية→next_n_days:1–30; named weekday→next_weekday; باچر→the
next weekday name, using only an injected business weekday. BusinessClock alone
calculates dates. Unsupported/conflicting spans are never clipped or guessed.
D55 named calendar months return an explicit marker plus a month ordinal;
BusinessClock alone binds that marker to a trusted range. Years clarify.
No evaluation questions, labels, expected answers, or data files enter this module.
"""

import re
from dataclasses import dataclass
from typing import Literal

from app.schemas.tools import Period
from app.services.reconcile import normalize_name
from app.services.validation import normalize_digits

_NAMED = (
    (r"اليوم", "today"),
    (r"البارحه|بارحه|امس", "yesterday"),
    (r"هالاسبوع|هلاسبوع|هذا\s+الاسبوع|الاسبوع\s+هذا", "this_week"),
    (
        r"(?:ال)?اسبوع\s+(?:الماضي|الفات|الفايت|السابق|(?:اللي|الي)\s+فات)",
        "last_week",
    ),
    (r"هالشهر|هذا\s+الشهر|الشهر\s+هذا", "this_month"),
    (r"الشهر\s+(?:الماضي|الفات|السابق|(?:اللي|الي)\s+فات)", "last_month"),
)
_WEEKDAYS = {
    "الاثنين": "mon",
    "الثلاثاء": "tue",
    "الاربعاء": "wed",
    "الخميس": "thu",
    "الجمعه": "fri",
    "السبت": "sat",
    "الاحد": "sun",
}
_WEEKDAY_CODES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_MONTHS = (
    (r"كانون\s+الثاني|يناير", 1),
    (r"شباط|فبراير", 2),
    (r"اذار|مارس", 3),
    (r"نيسان|ابريل", 4),
    (r"ايار|مايس|مايو", 5),
    (r"حزيران|يونيو", 6),
    (r"تموز|يوليو", 7),
    (r"اغسطس", 8),
    (r"ايلول|سبتمبر", 9),
    (r"تشرين\s+الاول|اكتوبر", 10),
    (r"تشرين\s+الثاني|نوفمبر", 11),
    (r"كانون\s+الاول|ديسمبر", 12),
)


@dataclass(frozen=True)
class PeriodResolution:
    status: Literal["resolved", "none_found", "conflict"]
    period: Period | None = None
    month: int | None = None

    def resolve(self, clock):
        return (
            clock.named_month(self.month) if self.month else clock.resolve(self.period)
        )

    def arguments(self, clock):
        if self.month is None:
            return {"period": self.period}
        resolved = self.resolve(clock)
        return {
            "period": "explicit",
            "start_date": str(resolved.start),
            "end_date": str(resolved.end),
        }


def _phrase(pattern, text):
    return re.search(r"(?<!\w)(?:و)?(?:" + pattern + r")(?!\w)", text)


def _days(raw, maximum):
    if not re.fullmatch(r"[0-9]+", raw):
        return None
    digits = raw.lstrip("0")
    if not digits or len(digits) > 2:
        return None
    value = int(digits)
    return value if 1 <= value <= maximum else None


def resolve_period(message: str, *, weekday: int | None = None) -> PeriodResolution:
    """Pure text/weekday input; no ledger, wall clock, dates, or provider access."""
    text = normalize_name(normalize_digits(message))
    if re.fullmatch(r"[0-9]{4}", text.strip()) or re.search(
        r"(?:سنه|عام)\s+[0-9]{4}(?![0-9])", text
    ):
        return PeriodResolution("conflict")
    periods = {period for pattern, period in _NAMED if _phrase(pattern, text)}
    unsupported = _phrase(
        r"(?:الاسبوع|الشهر)\s+(?:الجاي|القادم|المقبل)|"
        r"السنه\s+(?:الماضيه|الفاتت|القادمه)",
        text,
    )
    if unsupported:
        return PeriodResolution("conflict")
    for pattern, prefix, maximum in (
        (r"اخر\s+(\S+)\s+(?:يوم|ايام)", "last_n_days", 90),
        (
            r"(?:خلال\s+)?(?:ال\s*)?(\S+)\s+(?:يوم|ايام)\s+"
            r"(?:الجايه|الجايات|القادمه|القادم)",
            "next_n_days",
            30,
        ),
    ):
        for match in re.finditer(r"(?<!\w)(?:و)?" + pattern + r"(?!\w)", text):
            if not re.search(r"[0-9]", match[1]):
                continue  # Written quantities stay with the existing model flow.
            days = _days(match[1], maximum)
            if days is None:
                return PeriodResolution("conflict")
            periods.add(f"{prefix}:{days}")
    if _phrase(r"باچر|باجر|بكره|بكرا|غدا", text):
        if weekday is None or not 0 <= weekday <= 6:
            return PeriodResolution("conflict")
        periods.add("next_weekday:" + _WEEKDAY_CODES[(weekday + 1) % 7])
    for name, code in _WEEKDAYS.items():
        if not _phrase(name, text):
            continue
        if _phrase(name + r"\s+(?:الماضي|الفات|السابق)", text):
            return PeriodResolution("conflict")
        if weekday is not None and code == _WEEKDAY_CODES[weekday]:
            if periods == {"today"}:
                continue
            return PeriodResolution("conflict")
        periods.add("next_weekday:" + code)
    months = set()
    # Hamza normalization makes بآب identical to باب (door); retain that raw
    # distinction rather than treating ordinary words as a month request.
    if _phrase(r"اب", text) or re.search(r"(?<!\w)(?:و)?بآب(?!\w)", message):
        months.add(8)
    for pattern, month in _MONTHS:
        if re.search(r"(?<!\w)(?:و)?(?:ب)?(?:شهر\s+)?(?:" + pattern + r")(?!\w)", text):
            months.add(month)
    for match in re.finditer(r"(?<!\w)(?:و)?(?:ب)?شهر\s+([0-9.+-]+)(?!\w)", text):
        month = _days(match[1], 12)
        if month is None:
            return PeriodResolution("conflict")
        months.add(month)
    if months:
        if (
            len(months) != 1
            or periods
            or re.search(r"(?<![0-9])[0-9]{4}(?![0-9])", text)
        ):
            return PeriodResolution("conflict")
        return PeriodResolution("resolved", "explicit", months.pop())
    if _phrase(r"كانون|تشرين", text):
        return PeriodResolution("conflict")
    if len(periods) > 1:
        return PeriodResolution("conflict")
    return (
        PeriodResolution("resolved", periods.pop())
        if periods
        else PeriodResolution("none_found")
    )
