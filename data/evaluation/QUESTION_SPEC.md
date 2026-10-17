# Synthetic question JSONL format

Version: shgad-question-v1. This describes development and independently sealed
historical Q&A. It contains no held-out questions or numeric answers. Development
examples are exclusively in development_questions.jsonl; their Arabic is pending
human review. The sealed file is authored and edited outside the repository by a
tool and session independent of every Shgad builder.

Each nonempty line is one UTF-8 JSON object. No duplicate IDs, blank lines, NaN,
comments or trailing commas. Amounts, when calculated later, are integer IQD.
Never put an answer or a figure in the question specification.

| Field | Required value |
|---|---|
| id | Unique string; development uses DEV-...; independent generator chooses its own sealed IDs. |
| category | One category from the list below. |
| question_ar | Nonempty Iraqi Arabic merchant question; synthetic records only. |
| business_as_of | ISO Baghdad business date in 2026-07-01..2026-09-28; normally 2026-09-28. |
| dataset | primary or a fixture selector from the list below; never a filesystem path. |
| arabic_review | pending or approved; only a human may change to approved. |
| spec | Structured gold labels in the table below. No calculated answers. |

| spec field | Meaning |
|---|---|
| intent | sales, debts, supplier_sufficiency, upcoming_obligations, weekly_summary, estimated_gross_margin, reconciliation, unsupported_write, or unsafe_instruction. |
| expected_tools | List without duplicates, using only get_sales, get_debts, reconcile, forecast, get_margin. For refusal or clarification before a tool, use []. Treat order as a set unless a later evaluation explicitly measures ordering. |
| counterparty_ids | Exact relevant customer/supplier IDs, or []. For an ambiguous name list all candidates; do not merge them. |
| resolved_period | {"start":"YYYY-MM-DD","end":"YYYY-MM-DD"} inclusive, or null when no unique period is resolved. Historical sales/summary/margin stay inside observed dates. Known scheduled obligations may end after today (J1 or upcoming); this does not authorize future realized sales. |
| expected_behavior | answer, clarify, or refuse. |
| calculation | sales, cash, debts, margin, weekly_summary, j1, upcoming, or none. |
| parameters | Object containing only parameters for that calculation, below. |
| error_code | Optional typed clarification label. Missing opening cash/costs use MISSING_OPENING_BALANCE / MISSING_COSTS; ambiguous names/dates use AMBIGUOUS_COUNTERPARTY / AMBIGUOUS_DATE. Evaluation-only labels NO_HISTORICAL_DATA / REVIEW_REQUIRED do not define API endpoints or add API error codes. |

sales: optional kind: cash/credit/all (default all). Independent truth retains
both sale components and their separate signed unexplained difference; the grader
uses the selected kind. debts: optional direction: receivable/payable/both
(default receivable), overdue_only: boolean (default false). Customer filtering
uses counterparty_ids. upcoming: days: 1..30 (default 7), period today through
today+days-1. j1: period starts today and ends on the requested supplier date.
Other calculations use {}. none carries no numeric truth; the action is the
behavior/intent/tool/customer/period label. cash supports missing-cash fixture
checks, not a sixth application tool. Only the five tools above are planned.

Categories (all have development cases):

sales, debt_balance, supplier_dues, weekly_summary, cash_sufficiency,
margin, drawings_expenses, relative_dates, reconciliation, missing_data,
ambiguous_customer, ambiguous_date, invalid_date, contradictory_records,
unsupported_request, injection.

Fixtures usable as selectors: small_happy_path, three_instalments_void,
cash_difference_review, seven_day_overdue, missing_opening_balance,
missing_costs, ambiguous_customers, malicious_descriptions,
forecast_scenarios. A fixture must actually be present in the independent staging
package before referring to it. File basenames are selectors, not question text.
Fixture support files use <selector>.opening_balance.json,
<selector>.categories.csv, <selector>.obligations.csv,
<selector>.payment_links.csv, <selector>.entry_voids.csv. Missing opening cash
is represented by an absent opening file, not zero. The canonical primary shop's
support files omit that prefix. Never read cause labels to answer a question.

scripts/make_ground_truth.py computes separate development answers from these
structured inputs, independent of backend financial code. It preserves knowledge
time for entries, allocations and voids. A later measured evaluator can use the
same independent calculator after verifying the sealed hash. This development
script never reads HELDOUT_PATH or discovers question files.

The historical sealed contract is exactly 60 questions: 40 answer, and 20
clarify/refuse, referring only to observed records and known obligations.
The helper validates this shape and prints only SHA-256, total and counts per
category/behavior. The helper is run by the human in their own terminal.
No sealed questions, answers, paths or snippets are printed.

Joint dialect scoring requires correct intent, expected tool set, exact relevant
counterparty IDs and resolved period together, alongside expected behavior.
An amount match with a wrong customer or period fails. Development accuracy is
never reported as held-out accuracy.

Forecast protocol is separate: dev cutoffs 60 and 75 produce 30 predictions, with
30/15 scored days ending at day 90; all future outcomes stay inaccessible during
development. Final day-90/extra-shop scoring requires a prior method/code freeze.
