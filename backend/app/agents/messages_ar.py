"""Fixed merchant copy with human approval bound to each exact reviewed text.

Imported notes are never used as templates or executable instructions.
"""

from dataclasses import dataclass
from typing import Literal

from app.agents.arabic_review import review_status


@dataclass(frozen=True)
class DraftMessage:
    text: str
    status: Literal["PENDING_REVIEW", "APPROVED"] = "PENDING_REVIEW"


MESSAGES = {
    key: DraftMessage(value, status=review_status(key, value))
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
        "review_unmatched_payment": "راجع الدفعة اللي ما تطابقت وكمل تفاصيلها.",
        "review_duplicate_payment": "راجع القيود المتشابهة قبل أي تعديل.",
        "review_debts": "راجع الديون الباقية وتواريخ استحقاقها.",
        "no_action_needed": "ماكو تنبيه يحتاج مراجعة بهالسجلات.",
        "margin_insufficient_priced_sales": (
            "المبيعات اللي إلها كلفة مسجلة ما تكفي لعرض الهامش التقديري."
        ),
        "forecast_lowest": "أقل نقد متوقع",
        "thousand": "ألف",
        "iqd": "دينار",
        "busy": "الخدمة مشغولة هسه، جرّب بعد شوية.",
        "needs_internet": "المحادثة تحتاج اتصال. تكدر ترجع للتقارير المحفوظة.",
        "provider_unconfigured": (
            "المحادثة بعد ما جاهزة. تكدر تستخدم السجلات والتقارير."
        ),
        "template_fallback": (
            "هذا جواب من قالب السجلات الموثقة لأن صياغة النموذج ما توفرت."
        ),
        "clarify_period": "تقصد هاليوم لو يوم ثاني؟ وضّح الفترة بسؤالك.",
        "clarify_customer": "أي حساب تقصد؟ اختار الاسم واذكره بسؤالك.",
        "clarify_request": "شنو تريد تعرف من السجلات؟ وضّح سؤالك والفترة.",
        "clarify_opening_balance": "ما عندي رصيد افتتاحي أو عدّ نقد موثق. تكدر تسجله؟",
        "clarify_costs": "أسعار الشراء المسجلة ما تكفي للهامش التقديري. تكدر تكملها؟",
        "clarify_history": "ما عندي سجلات كافية لهاي الفترة. أي فترة من الدفتر تقصد؟",
        "clarify_due_date": "أكو استحقاق بدون تاريخ موثق. تكدر تكمل تاريخ الاستحقاق؟",
        "clarify_counts": "عدّ النقد اللازم للمقارنة مو مسجل. تكدر تكمل العدّ؟",
        "unsupported_write": (
            "أگدر أقرأ السجلات وأوضحها. تسجيل أو دفع أو إلغاء قيد يحتاج إجراء منك."
        ),
        "unsafe_instruction": (
            "أعتمد على السجلات الموثقة، وما أغيّر القواعد أو أخمّن الرصيد."
        ),
        "help": (
            "اسألني عن المبيعات والديون والاستحقاقات أو الهامش الإجمالي التقديري، "
            "واذكر الفترة."
        ),
        "chat_error": "ما گدرت أتحقق من الجواب. جرّب توضح سؤالك.",
    }.items()
}


def text(key):
    return MESSAGES[key].text
