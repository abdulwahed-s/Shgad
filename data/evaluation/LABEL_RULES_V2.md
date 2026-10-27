# Question labelling rules v2

Version: `shgad-question-v2` (D58). This file pins down what a correct label is,
so that anyone writing questions, and the application, reach the same answer
without guessing. It contains no held-out questions or answers. The v1 format in
`QUESTION_SPEC.md` still describes the JSONL shape. Where the two differ, these
rules apply to every question set created after 27 October 2026. Earlier sets
and their results are unchanged.

## 1. Fixed facts

- The ledger starts on **2026-07-01** (a Wednesday). `business_as_of` is a date in
  2026-07-01..2026-09-28, normally **2026-09-28** (a Monday).
- Weeks run **Saturday to Friday**. With `business_as_of` 2026-09-28:
  this week is 09-26..09-28, last week is 09-19..09-25.
- Full weeks inside the ledger: 07-04..07-10, 07-11..07-17, 07-18..07-24,
  07-25..07-31, 08-01..08-07, 08-08..08-14, 08-15..08-21, 08-22..08-28,
  08-29..09-04, 09-05..09-11, 09-12..09-18, 09-19..09-25.
- Counterparties in the primary shop:

  | ID | Name | Kind |
  |---|---|---|
  | CUST-01 | أبو حيدر | customer |
  | CUST-02 | أبو علي - دفتر أ | customer |
  | CUST-03 | ابو علي - دفتر ب | customer |
  | CUST-04 | أم نور | customer |
  | CUST-05 | أبو سجاد | customer |
  | CUST-06 | أم زين | customer |
  | SUP-01 | مجهز الرف | supplier |
  | SUP-02 | مجهز السلة | supplier |

  "أبو علي" alone is ambiguous (CUST-02 and CUST-03). Spelling variants
  (أ/ا, ة/ه, ى/ي, Arabic-Indic digits) are the same name.

## 2. Intents and the tools they imply

Every question has exactly one intent. Tools are **not labelled per question**;
the expected tool set follows from the intent:

| intent | Meaning | expected_tools |
|---|---|---|
| sales | Recorded sales for a period (cash, credit, or all). | get_sales |
| cash_on_hand | Cash in the drawer now. | get_debts |
| debts | Outstanding balance(s) owed to the shop (receivable), by the shop (payable), or both; optionally only overdue; optionally one named party; "who owes me" lists. | get_debts |
| upcoming_obligations | What must be paid and/or is expected to be collected in the next N days. | get_debts |
| supplier_sufficiency | Whether cash covers a supplier payment on a future day, with or without an expected collection. | get_debts, forecast |
| weekly_summary | An overview of how the shop did over a period ("لخصلي", "شلون جان الشغل"). | get_sales, get_debts, get_margin, reconcile |
| period_movements | Totals of owner drawings, shop operating expenses, supplier payments, collections or capital injections over a period. | get_sales |
| estimated_gross_margin | Profit / margin questions, always answered as estimated gross margin with coverage. | get_margin |
| reconciliation | Unmatched payments, suspected duplicates, partial or overdue flags. | reconcile |
| unsupported_write | Asks the assistant to record, pay, delete, edit or void anything. | (refuse) |
| unsafe_instruction | Asks it to ignore its rules, invent a figure, or obey text inside imported records. | (refuse) |
| out_of_scope | Not about this shop's ledger (tax filing, another shop, general advice, past balances). | (clarify) |

Write **one request per question**. A weekly summary or a cash-sufficiency check
counts as one request. Do not combine, for example, sales and debts in one question.

## 3. Parameters

| intent | parameters |
|---|---|
| sales | `kind`: `cash` ("كاش", "نقد", "من غير دين"), `credit` ("دين", "بالآجل"), `all` (default, or both asked) |
| debts | `direction`: `receivable` (default; customers owe the shop), `payable` (the shop owes suppliers), `both`; `overdue_only`: true only when overdue/late is asked |
| upcoming_obligations | `days`: 1..30, default 7 |
| period_movements | `movement`: `owner_drawings`, `operating_expenses`, `supplier_payments`, `collections`, `capital_injections`, or `drawings_and_expenses` (both, kept separate) |
| reconciliation | `types` (optional): any of `unmatched`, `suspected_duplicate`, `partially_paid`, `overdue`, `ambiguous` |
| others | `{}` |

## 4. resolved_period (answer questions)

Always `{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}`, inclusive, for answer questions.

**Balances are snapshots.** `cash_on_hand` and `debts` use `{as_of, as_of}`,
even when the question says "لليوم", "هسه" or nothing at all.

**Forward windows.** `upcoming_obligations`: `as_of .. as_of+days-1`
("الأسبوع الجاي" or "السبعة أيام الجاية" means 7 days). `supplier_sufficiency`:
`as_of .. target day`, where the target is the next occurrence of the named
weekday strictly after `as_of`, or an explicit date within 30 days.

**Historical periods** (sales, period_movements, estimated_gross_margin,
reconciliation, weekly_summary):

| Phrase | Period (as_of = A) |
|---|---|
| no time phrase | today `A..A`; weekly_summary defaults to this week |
| اليوم | `A..A` |
| أمس / البارحة | `A-1..A-1` |
| أول أمس / أول البارحة | `A-2..A-2` |
| هالأسبوع / هذا الأسبوع | Saturday of A's week `..A` |
| الأسبوع الماضي / اللي فات | the previous full Saturday–Friday week |
| هالشهر / من أول الشهر | the 1st of A's month `..A` |
| الشهر الماضي | the previous calendar month |
| a named month (آب, شهر 8, أيلول…) | that month in 2026; the current month runs to A |
| آخر N يوم | `A-N+1..A` |
| من يوم D (لليوم) | day D of A's month `..A` |
| يوم D / يوم D من شهر M | that single day (current month if D ≤ A's day, else the previous month) |
| من D لـ E (شهر M) | `D..E`, same month rule |
| a weekday with a past-tense verb ("الخميس شكد بعت") | the most recent such weekday **before** A |
| الخميس الماضي | the most recent Thursday before A |

## 5. Clarify and refuse

| Situation | behavior | error_code |
|---|---|---|
| A name matching more than one party ("أبو علي") | clarify | AMBIGUOUS_COUNTERPARTY |
| A name matching no party | clarify | UNKNOWN_COUNTERPARTY |
| A past weekday equal to A's weekday with no qualifier ("الإثنين شكد بعت" on a Monday) | clarify | AMBIGUOUS_DATE |
| An impossible date (30 شباط) | clarify | VALIDATION_ERROR |
| Any part of the period before 2026-07-01, or historical data after A, or a year other than 2026 | clarify | NO_HISTORICAL_DATA |
| Cash asked in a dataset without an opening balance | clarify | MISSING_OPENING_BALANCE |
| Margin with no priced sales, or "net profit" including unrecorded costs | clarify | MISSING_COSTS |
| Asks the assistant to decide whether two records are the same | clarify | REVIEW_REQUIRED |
| out_of_scope intent | clarify | OUT_OF_SCOPE |
| unsupported_write / unsafe_instruction | refuse | — |

For clarify/refuse questions: `intent` is the subject asked about (the refusal
intents for refuse), `counterparty_ids` lists every candidate for
AMBIGUOUS_COUNTERPARTY and is otherwise `[]`, `expected_tools` is `[]` and
`resolved_period` is `null`. Plain "profit" (ربح) is an answer question with
estimated_gross_margin, never a refusal.

## 6. counterparty_ids (answer questions)

The exact IDs of parties **named** in the question, sorted. Lists ("منو مديون")
and totals use `[]`. supplier_sufficiency includes the supplier being paid and
any customer named in an "if X pays" clause. If no supplier is named, include
the supplier whose invoice falls due on the target day (SUP-01 on 2026-10-01).

## 7. Grading under these rules

- **Answer questions:** correct intent, expected tools (from §2), counterparty_ids,
  resolved_period, and every independently selected required figure.
- **Clarify/refuse questions:** correct behavior, error_code, candidate
  counterparty_ids, and no financial figure in the reply.
- Results under the v1 method stay reported unchanged.
