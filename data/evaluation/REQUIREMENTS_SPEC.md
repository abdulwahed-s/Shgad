# Independent required-figure annotations

Version: `shgad-requirements-v1` (D50). This public format contains no private
questions, answers or annotations. An independent generator/human selects figures
from the question's meaning before measurements, followed by actual human review.
Builders may define this contract and handmade format fixtures only. Do not infer
selectors from model answers or evaluation outcomes. Original question files and
their seals remain unchanged.

Registry revision: `2026-10-28-period-movements` (D58 adds `weekly.supplier_payments`
and `weekly.capital_injections`, already computed by the independent catalogue since
D55; earlier revision `2026-10-23-cash-on-hand`). The JSONL/manifest schema is unchanged;
the refreshed contract hash binds this additive selector revision.

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

Scalar fields: `cash_on_hand`, `cash_sales`, `credit_sales`, `total_sales`, `selected_sales`,
`unexplained_cash_difference`, `gross_margin`, `coverage_pct`,
`unpriced_sales_count`, `priced_sales`, `cost_of_goods`,
`after_recorded_expenses`.

`cash_on_hand` is standalone confirmed cash at `business_as_of`, independent of
the requested historical sales period or future obligation window. Follow
FINANCIAL_RULES §2: latest active count plus subsequent recorded cash inflows
minus outflows known at that cutoff, or opening balance plus subsequent flows
when no count exists. Its unit is integer IQD and its evidence is that count/
opening source plus all contributing subsequent cash rows. Missing opening cash
and counts mean unavailable, never zero. No projected sales or expected
collections enter it. The existing `upcoming.cash_on_hand` and `j1.cash_on_hand`
views satisfy this selector only when the independent catalogue proves the same
cutoff fact, value, unit, label and complete source set. Other cash positions,
projections or equally valued facts are not interchangeable.

Sales use the resolved inclusive historical period and recorded rows only.
`selected_sales` follows the original spec's kind (cash/credit/all).
`unexplained_cash_difference` remains a separate signed residual, never sales
or a causal claim. Margin is estimated gross margin; coverage is a percentage
of recorded sales, with cost basis and unpriced count as defined by the financial
specification. `after_recorded_expenses` never means net profit.

| Allowed selector family | Meaning |
|---|---|
| `weekly.owner_drawings`, `weekly.operating_expenses`, `weekly.collections`, `weekly.supplier_payments`, `weekly.capital_injections` | Separate totals for the resolved historical period; drawings are not business expenses, collections are not new sales, supplier payments settle payables, and capital injections add cash but are not revenue. |
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

---

## Additive historical and closing registry revision

Registry revision: `2026-10-23-historical-closing-v1-candidate`.
The JSONL and manifest schemas remain `shgad-requirements-v1`.
This candidate preserves all original definitions above and adds the ten selectors
defined below. It is not active until the receiving contract owner explicitly
adopts the actual new LF-normalized hash of this full document and its public
input-manifest update. The original registry hash identifies the original
registry only; it cannot be reused for this candidate. No original question,
structured parameter, expected behavior, seal or financial rule is changed.

## Shared economic, knowledge, evidence, and availability rules

All amounts are exact integer IQD. All business dates and day boundaries use
Asia/Baghdad. Let `S..E` be the original resolved inclusive historical period and
`K` the original question's `business_as_of` knowledge cutoff. A period-end
target is the end of `E`; a closing-comparison target is the designated closing
count on `E`. Require a uniquely resolved historical target with `S <= E <= K`
within the observed record range. Never substitute the current date for an
unresolved target or silently change an original resolved period.

Economic time determines whether an event belongs to the target or period.
Knowledge time determines whether its record, verification/allocation link, or
void/correction may be used at `K`. Include only material known by that cutoff.
A settlement economically after `E` cannot reduce an `E` debt balance even if
known by `K`. A correction recorded later may affect the reconstruction only
when known by `K` and economically in scope. Apply the financial rules' immutable
void/re-entry chains and retained original economic ordering. Do not fabricate
earlier knowledge or count a corrected pre-count cash event twice.

An earlier target reconstructed with later knowledge must be labelled
"historical, reconstructed using records known by the question cutoff." It is
not a claim about what was known at the target date. Nothing known only after
`K`, projected sales, expected collections, or future realized activity enters
these historical facts.

Each independent catalogue fact must bind its exact selector, economic target
or period, knowledge cutoff, integer IQD unit, financial label, value, complete
contributing source set, and relevant void/correction provenance. Track
availability prerequisites separately from numerical inputs where needed. Use
only accepted, valid observed records. A candidate match alone is not a verified
debt settlement. Missing, ambiguous, invalid, or incomplete prerequisites make a
fact unavailable; they never establish zero. An empty, demonstrably complete
and valid in-scope set can establish a zero movement or debt total.

For an opening source supplied as observed baseline metadata without an explicit
`recorded_at`, retain that absence; do not invent a record timestamp or substitute
the file modification time. Eligibility must follow an explicitly adopted
observed-baseline policy: the source must be bound to the authorized observed
input package, have an applicable opening economic date, and be designated by
that package's cutoff policy as available for `K`. Its baseline role is not an
assertion of a nonexistent historical audit timestamp. If these eligibility
conditions cannot be established, the opening fallback is unavailable. Apply the
same rule to every selector using an opening baseline.

The cash-event sets remain those in FINANCIAL_RULES sections 2 and 3:

| Direction | Recorded event types | Treatment |
|---|---|---|
| Inflow | `CASH_SALE`, `CREDIT_COLLECTION`, `CAPITAL_INJECTION` | Collections and capital are not new sales. |
| Outflow | `SUPPLIER_PAYMENT`, `OPERATING_EXPENSE`, `OWNER_DRAWING` | Drawings are not operating expenses. |
| Neither | `CREDIT_SALE`, `SUPPLIER_INVOICE` | Do not move cash. |
| Internal transfer | `INTERNAL_TRANSFER` | Zero net effect; do not inflate either external movement total. |

Cash-event acceptance and allocation to a particular obligation are separate
facts. A valid recorded collection/payment can move cash without a verified
allocation; it cannot reduce a particular debt until its settlement allocation
is valid and verified. Exclude unaccepted candidate cash records and voided
events. This does not relax any existing ingestion or verification rule.

## Eight core additions

### 1. `period_end.cash_on_hand`

Meaning: confirmed cash at the end of `E`, reconstructed with knowledge limited
to `K`. Use the latest active, unambiguous physical count economically at or
before that target, plus the valid cash inflows and minus the valid cash outflows
economically after that count through the target. Retain event ordering so
pre-count events already reflected in the physical amount are not added again.
If no applicable count exists, use the known applicable opening balance plus
subsequent in-scope cash movements.

Evidence: the baseline count or opening source, every contributing subsequent
cash event, and relevant void/correction provenance. Availability: require that
baseline and complete subsequent cash coverage; missing both count and opening
balance is unavailable, never zero. Sign: preserve the exact signed position;
do not clamp a negative reconstruction. A target count can establish confirmed
cash but cannot establish its own independent expected comparison.

### 2. `period_end.receivables.total_outstanding`

Meaning: the sum of positive remaining receivable obligations economically
existing at the end of `E`, after valid verified settlements economically
effective by `E` and known by `K`. Remaining principal is original principal less
those settlements. Apply the original counterparty filter and any requested
overdue filter at `E`. Overdue means a positive balance with a known due date
strictly before `E`; an unknown due date is not zero overdue days.

Evidence: all in-scope obligation origins, verified settlement allocations and
their cash/source links, and applicable void/correction records, sufficient to
establish the complete filtered total. Availability: require the complete valid
obligation and settlement set and the attributes needed for the requested
filters. Flag invalid overpayment; do not offset another obligation. Sign:
nonnegative remaining receivables, never netted against payables. This is neither
original principal nor debt originated during the period nor a customer list.

### 3. `period_end.payables.total_outstanding`

Meaning: the corresponding sum of positive remaining payable obligations
economically existing at the end of `E`, less valid verified supplier-payment
allocations effective by `E` and known by `K`. Apply the original counterparty
and overdue filters at `E`, with the same unknown-due-date treatment.

Evidence and availability: the complete filtered obligation origins, verified
supplier-payment allocations and cash/source links, required filter attributes,
and applicable void/correction provenance. Invalid overpayment is flagged, not
netted elsewhere. Sign: nonnegative remaining payables. A request for both debt
directions needs both separately labelled totals; do not subtract one from the
other or substitute a requested customer/obligation list with an aggregate.

### 4. `period.cash_inflows_iqd`

Meaning: the total valid recorded cash inflows economically within `S..E` and
known by `K`, using exactly the inflow event types above. Evidence: every
contributing accepted cash event and relevant void/correction provenance, with
complete period coverage. Availability: no opening balance or count is needed
for a movement total, but incomplete movement records do not establish zero.
Sign: a nonnegative amount received, added when forming a balance. It is not
net movement, total sales, a closing balance, or collections alone.

### 5. `period.cash_outflows_iqd`

Meaning: the total valid recorded cash outflows economically within `S..E` and
known by `K`, using exactly the outflow event types above. Evidence: every
contributing accepted cash event and relevant void/correction provenance, with
complete period coverage. Availability: the same complete-record requirement as
for inflows, independently of opening cash. Sign: a nonnegative amount paid
out, subtracted when forming a balance; do not store this total as a negative
number. Supplier invoices alone do not count as payments.

For either movement field, select only the requested totals or breakdown. A
request for movement does not by itself require each component or an additional
cash-versus-credit sales breakdown. Movement totals do not satisfy a separately
requested period-end cash balance.

### 6. `closing.expected_cash_iqd`

Meaning: the strict FINANCIAL_RULES section 3 expected closing cash on `E`:

```text
active physical closing count on E-1
+ valid recorded cash inflows on E
- valid recorded cash outflows on E
```

`E-1` means the immediately preceding Baghdad calendar date, not the most recent
date with a count. Economic scope is that exact target day and knowledge is
limited to `K`. Evidence used in the expected amount is the prior-day count,
the complete valid target-day cash events, and their correction provenance.
The target count is not a numerical input or source of this expected amount.

Availability for the strict closing comparison requires active, unambiguous
counts on both `E-1` and `E`, known by `K`, and complete valid target-day cash
movement. Record the target count as a comparison prerequisite rather than an
expected-value input. An older count, opening balance, cumulative book position,
expected collection, or current confirmed cash cannot replace the prior-day
count. Sign: an exact signed expected position; negative values are not clamped.

### 7. `closing.counted_cash_iqd`

Meaning: the actual active physical closing count on the exact target `E`, known
by `K`, with the target count's label. It is not an expected value or a count
updated with subsequent cash events. Evidence: that exact count source and its
relevant correction/void provenance. Availability: the target count must be
valid, active, and unambiguous. It can be available on its own even when the
prior-day count is missing. Sign: preserve the validated physical count amount
without sign inversion or conversion into a residual.

### 8. `closing.unexplained_difference_iqd`

Meaning: the exact signed target-date residual:

```text
closing.counted_cash_iqd - closing.expected_cash_iqd
```

Evidence: both consecutive-date counts, all contributing valid target-day cash
events, and relevant void/correction provenance. Availability: require all the
strict comparison prerequisites above. Positive means actual counted cash is
above expected; negative means it is below expected. Preserve a neutral
"unexplained difference" label. The amount is not sales, profit, a collection,
theft, or proof of any cause.

## Two distinct book-comparison additions

These two fields represent a separately labelled comparison to a book position
when that comparison is requested and an independent baseline is available.
They were unaccepted in the earlier revision contract. This proposal includes
them in the ten-field amendment for explicit human and recipient adoption; it
does not assert that the earlier contract already allowed them. They do not
amend the strict daily comparison or make an unavailable daily residual
available.

### 9. `closing.pre_count_book_cash_iqd`

Meaning: the independently reconstructed ledger/book position immediately
before incorporating the designated target count on `E`, with knowledge limited
to `K`. Exclude that target count from the baseline and formula. Use the latest
active, unambiguous count strictly before it in economic event order, plus valid
cash inflows minus outflows after that earlier count through the target count's
pre-count boundary. If no earlier applicable count exists, use the applicable
known opening balance and subsequent cash movement through that boundary.

Evidence: the earlier baseline count or opening source, complete subsequent
cash movement through the pre-count boundary, and applicable void/correction
provenance. Corrections retain their original economic ordering. Availability:
require a uniquely defined target/count boundary, an independent baseline, and
complete valid movement coverage; missing those inputs is unavailable, not zero.
For a comparison also require the active target count, recorded as a separate
prerequisite. Sign: an exact signed book position; do not clamp it. Label it
"book cash before target count," with the baseline and reconstruction cutoff.
An older count or opening fallback is allowed only for this book view, never as
a replacement for the strict daily view's immediately preceding-date count.

### 10. `closing.book_to_count_difference_iqd`

Meaning: the signed designated target count minus the independently established
pre-count book position:

```text
closing.counted_cash_iqd - closing.pre_count_book_cash_iqd
```

Evidence: the union of the target count, independent book baseline, contributing
cash events, and correction/void provenance. Availability: both constituent
facts, an identical target/pre-count boundary, and the same knowledge cutoff
must be established. Sign: positive is counted cash above book, negative is
below book. Label it "book-to-count difference" and identify the baseline; do
not call it the strict daily unexplained difference or infer a cause. An
available book comparison must explicitly retain the need for the missing
prior-calendar-date count before a strict daily difference can be given.

## Existing meanings and aliases remain intact

The existing standalone `cash_on_hand`, `receivables.total_outstanding`, and
`payables.total_outstanding` remain snapshots at `business_as_of`. Existing sales
fields retain their recorded cash/credit/all meanings. `selected_sales` still
follows the original resolved sales kind. Collections, capital, and unexplained
differences never become sales.

Existing `unexplained_cash_difference` remains the requested range's signed
residual under the existing consecutive-date coverage rule. Missing coverage is
unavailable, never zero. A range residual does not become a single closing
comparison merely because its range ends on the comparison date.

Existing proven sales and singleton-debt aliases remain subject to their
original scope, ordering, and same-fact proofs. Existing J1/upcoming cash views
can satisfy standalone `cash_on_hand` only under the existing full identity
proof. No blanket alias is created between an old and a proposed field or
between proposed fields. Any later consumer must independently prove identical
economic target/period, knowledge cutoff, value, unit, financial label, and
complete evidence before using a same-fact alias. Equal amounts alone are
insufficient. Confirmed cash normally incorporates a target count; expected or
pre-count book cash excludes it. Neither is automatically an alias for the other.

Original counterparty identities, customer/obligation list ordering, filters,
and aggregate-versus-list distinctions remain unchanged. No added selector
replaces an explicitly requested list, debt direction, or sales breakdown.
