"""Fixed merchant copy. Every entry is PENDING_REVIEW under decision D3.

Imported notes are never used as templates or executable instructions.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class DraftMessage:
    text: str
    status: Literal["PENDING_REVIEW"] = "PENDING_REVIEW"


MESSAGES = {
    key: DraftMessage(value)
    for key, value in {
        "period": "للفترة من {start} إلى {end}.",
        "customer": "الحساب: {name}.",
        "no_figures": "ما عندي أرقام موثقة كافية لهالجواب.",
        "collections_expected_not_guaranteed": "التحصيل المتوقع مو مضمون.",
        "forecast": "هذا تقدير نقدي، مو مبلغ مؤكد. السيناريو: {scenarios}.",
        "base": "أساسي",
        "conservative": "متحفظ",
        "stress": "ضغط",
        "margin_excludes_unrecorded_costs": (
            "هذا هامش إجمالي تقديري للمبيعات المسجلة المسعّرة؛ "
            "المصاريف غير المسجلة مو مشمولة."
        ),
        "unexplained_difference_excluded": (
            "الفرق غير المفسّر مو داخل بحساب تغطية المبيعات المسجلة."
        ),
        "coverage": "يشمل {value} من المبيعات المسجلة.",
        "difference_note": "الفرق غير مفسّر، وما نحدد سببه من هالسجلات.",
        "recorded_cash_sales": "المبيعات النقدية المسجلة",
        "credit_sales": "المبيعات الآجلة المسجلة",
        "total_recorded_sales": "مجموع المبيعات المسجلة",
        "unexplained_cash_difference": "الفرق غير المفسّر",
        "cash_on_hand": "النقد المتوفر",
        "supplier_due": "المبلغ المستحق للمجهز",
        "supplier_dues": "مستحقات المجهزين",
        "expected_collection": "التحصيل المتوقع",
        "expected_collections": "التحصيل المتوقع",
        "shortfall_with_collection": "النقص إذا صار التحصيل المتوقع",
        "shortfall_without_collection": "النقص بدون التحصيل المتوقع",
        "position_confirmed": "الرصيد بعد المستحقات بالنقد المؤكد",
        "position_with_expected": "الرصيد بعد المستحقات ويا التحصيل المتوقع",
        "receivables": "بذمة الزبائن",
        "payables": "مستحقات المجهزين",
        "estimated_gross_margin": "هامش إجمالي تقديري",
        "after_recorded_expenses": "بعد المصاريف المسجلة",
        "unpriced_sales_count": "عدد المبيعات بدون كلفة مسجلة",
        "reconciliation_amount": "مبلغ يحتاج مراجعة",
        "forecast_lowest": "أقل نقد متوقع",
        "thousand": "ألف",
        "iqd": "دينار",
    }.items()
}


def text(key):
    return MESSAGES[key].text
