# Independent required-figure annotations

Version: `shgad-requirements-v1` (D50). This public format contains no private
questions, answers or annotations. An independent generator/human selects figures
from the question's meaning before measurements, followed by actual human review.
Builders may define this contract and handmade format fixtures only. Do not infer
selectors from model answers or evaluation outcomes. Original question files and
their seals remain unchanged.

Each UTF-8 JSONL line has exactly two fields:

```json
{"id":"FORMAT-ONLY-ID","required_fields":["total_sales"]}
```

The example is fabricated format data, not a requirement for an existing question.
IDs join exactly to every original question, without missing/extra/duplicate IDs.
`required_fields` is a unique list of at most1000 allowed field names. Every
answerable question requires a nonempty list; clarify/refuse questions require
`[]`. No numeric answer, value/unit override, date, source ID, prompt, response,
filesystem path or free text is allowed. No blank lines, duplicate JSON keys,
NaN or extra fields. **All selected facts are required together.** Select the
facts actually requested, plus information essential to label them correctly;
do not require every field merely because it is available in a tool response.

The evaluator calculates values independently from observed ledger records and
known obligations. An approved selector must exist in that question's independent
catalogue; otherwise preparation aborts before credentials/provider clients.
Selectors replace legacy heuristic requirements in live scoring. Every additional
displayed historical claim is still checked. The existing proven same-fact sales
and singleton-debt aliases remain equivalent; equal numeric values alone do not
create an alias. Unknown fields or projected series are never silently ignored.

## Field registry and semantics

Scalar fields: `cash_sales`, `credit_sales`, `total_sales`, `selected_sales`,
`unexplained_cash_difference`, `gross_margin`, `coverage_pct`,
`unpriced_sales_count`, `priced_sales`, `cost_of_goods`,
`after_recorded_expenses`.

Sales use the resolved inclusive historical period and recorded rows only.
`selected_sales` follows the original spec's kind (cash/credit/all).
`unexplained_cash_difference` remains a separate signed residual, never sales
or a causal claim. Margin is estimated gross margin; coverage is a percentage
of recorded sales, with cost basis and unpriced count as defined by the financial
specification. `after_recorded_expenses` never means net profit.

| Allowed selector family | Meaning |
|---|---|
| `weekly.owner_drawings`, `weekly.operating_expenses`, `weekly.collections` | Separate totals for the resolved historical period; drawings are not business expenses and collections are not new sales. |
| `receivables.total_outstanding`, `payables.total_outstanding` | Positive remaining balances at the business cutoff after original customer/direction/overdue filters. |
| `<direction>.aging.<bucket>` | Outstanding balances in `not_due`, `d1_7`, `d8_30`, `d31_60`, `d60_plus`; direction is receivables/payables. Missing due dates do not become zero overdue days. |
| `<direction>.customers.<i>.outstanding` | A customer's/supplier's subtotal in that filtered direction. Zero-based groups sort by descending maximum days overdue, descending outstanding amount, then exact counterparty ID. Never merge similar names. |
| `<direction>.customers.<i>.days_overdue` | That group's maximum days overdue, only when all relevant due dates are known. |
| `<direction>.customers.<i>.obligations.<j>.original` or `.outstanding` | Original or remaining balance of an obligation; within each group sort by due date (unknown last), then obligation ID. |
| `price_basis.<i>.buy_price` | Category buy price, with priced categories in exact category-ID order. |
| `j1.cash_on_hand`, `j1.supplier_due`, `j1.expected_collection`, `j1.shortfall_with_collection`, `j1.shortfall_without_collection` | Confirmed-cash/known-obligation J1 view for the resolved supplier date; projections never enter these facts. Expected collections exclude already-overdue receivables. |
| `upcoming.cash_on_hand`, `upcoming.dues_total`, `upcoming.expected_total`, `upcoming.position_confirmed`, `upcoming.position_with_expected` | Known obligations and non-overdue expected collections in the original spec's next-N-day window, including overdue payables due now. |
| `upcoming.days.<i>.dues_iqd`, `.expected_iqd`, `.running_confirmed_iqd`, `.running_with_expected_iqd` | Daily known obligations/expected collections and running positions. Zero-based date index starts at business_as_of; i is0–29, and must exist in the requested window. |

Indices in other indexed families are nonnegative decimal integers with canonical
spelling (`0`, `1`, ...). All names are exact, case-sensitive and catalogue-bound.
This registry describes slots, not calculated answers or a model prompt. Contract
hash: SHA-256 of this file's UTF-8 bytes with CRLF converted to LF. This binds
registry version and ordering/scope semantics in each annotation manifest.

## Separate public manifests

Development: public `data/evaluation/development_requirements.jsonl`, with public
`data/evaluation/dev_requirements_manifest.json`. Both must be supplied by the
independent annotator/human, not authored by builders. Development question bytes
and their original SHA stay unchanged.

Held-out: keep the private sidecar next to the external question file. Its exact
filename is the resolved question filename plus `.requirements.jsonl`. The only
path input remains `HELDOUT_PATH`; no other private path flag or environment
variable exists. Resolve it, append that suffix, and require the sibling to stay
in the same external directory without a symlink/junction escape. Do not copy the
private file into this repository or expose its records to a builder. Only the
public `data/evaluation/heldout_requirements_manifest.json` is returned here.

Each manifest has exactly these fields:

| Field | Value |
|---|---|
| `schema_version` | `shgad-requirements-v1` |
| `split` | `dev` or `heldout` |
| `question_sha256` | Exact original question-file byte SHA; held-out must match the existing Track C seal. |
| `sha256` | Exact reviewed sidecar byte SHA, with no newline/encoding normalization. |
| `selector_spec_sha256` | LF-normalized hash of this public registry document. |
| `total_count`, `answer_count` | Integer question counts matching the original split. |
| `counts_by_behavior` | Exact aggregate counts for answer/clarify/refuse (zero categories may be omitted). |
| `reviewed_count` | Exactly total_count, after actual human review of every annotation. |
| `human_reviewed` | true only after that review. |
| `independent_of_build` | Actual provenance attestation, not an automatically proven isolation claim. |
| `generator_tool` | Actual tool label or `human`; do not invent identity. |
| `generator_model_id` | Exact exposed model ID, or `not_exposed`/`not_applicable`. |
| `reviewed_at` | Actual ISO timestamp with timezone; never a scheduled Git date. |

Public manifest inventory/receipt hashes normalize CRLF to LF for portability.
Private sidecar and question hashes always cover exact raw bytes. Annotators must
write public development sidecars with LF before sealing, matching repository
attributes. No existing question bytes are rewritten.

Plans inspect only public metadata; missing seals produce
`REQUIREMENTS_SEAL_REQUIRED`. Live access requires explicit paid authorization,
separate held-out authorization when applicable, a matching freeze containing
the supplied public manifests and all independent-reference preflight checks.
The model receives only the question/business cutoff and normal verified tool
outputs, never selectors/specs/reference answers. Held-out reports contain public
global hashes/counts/provenance only, never private IDs/selectors/paths/examples.

Changing annotations after a run changes the benchmark. Preserve original files,
seals and reports, disclose any later annotation/scorer change as post-run, and
never use held-out/final outcomes for tuning. This contract does not authorize
provider calls, actual held-out access or final/unseen forecast evaluation.
