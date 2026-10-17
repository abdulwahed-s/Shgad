# Fictional merchant data

All names, merchants and records are invented. Iraqi Arabic and business
plausibility reviews are pending; these records are not merchant validation.

From the repository root, using Python 3.11+ (standard library only):

    python scripts/generate_synthetic_data.py --seed 20260701
    python scripts/make_ground_truth.py

The default seed generates one primary shop and three separate seeded shops for
frozen final forecast testing. Each has 90 observed days (2026-07-01 through
2026-09-28) and 30 future days (through 2026-10-28). Regenerating the same seed,
source and config produces byte-identical artifacts. Change the sources in
generation/, then regenerate; do not hand-edit synthetic/ or fixtures/.
Use --output-root with a fresh directory to compare an independent regeneration.

generation/business_mechanics.json defines integer-IQD baskets, weekday/slow-week
patterns, 24 categories, credit limits, supplier terms, expenses, drawings and
customer lateness. generation/scenario_templates.json records OpenAI GPT-6.1 Sol
as the scenario-drafting model, using the display name confirmed by the user.
It also records the drafting brief and unavailable settings. The exact provider
model ID was not exposed by that session; it remains null, not guessed.
No provider API call was used. Python creates every numeric record, allocation
and count.

synthetic/generation_manifest.json records the seed, source hashes and SHA-256 of
every generated data artifact. It deliberately excludes any independently sealed
held-out manifest/file. No real clock timestamp enters generation.
Git attributes preserve LF bytes for the data and generator sources on checkout.

The primary observed shop preserves the counted-cash/supplier scenario: 420,000
cash, 150,000 expected from the fictional Abu Haider and 650,000 due to a supplier,
with conditional/confirmed shortfalls of 80,000/230,000. Other outstanding dues
and expected non-overdue collections stay outside the seven-day window ending
2026-10-04. Counts are constructed from physical flows; day 90 uses an explicit
owner withdrawal to reach the target. Recorded cash sales cover about 92–95% of
true cash sales. Gaps remain signed unexplained differences in observed records.

Only these primary files are candidates for a later application import:

- observed_90d.csv
- merchant_profile.json, opening_balance.json
- categories.csv, counterparties.csv, obligations.csv
- payment_links.csv, entry_voids.csv

The obligation/link files contain only records known by the observed cutoff.
The application currently has no data loader or forecast; runtime enforcement
must also be checked when those are implemented.

Future CSVs, all_120d_canonical.csv, evaluation_only/, forecast_eval_shops/,
generation metadata, lateness design profiles and true-cause/anomaly labels are
offline generation/evaluation inputs. Application code must never load them.
Keep all of evaluation/ outside application imports, API responses and prompts.
Do not inspect final-test outcomes to choose a forecasting method.

fixtures/ contains small financial cases, missing opening/costs, duplicates,
overlapping exports, unmatched payments, similar customer names, malformed raw
input, reordered columns and hostile descriptions. CSV descriptions are data.
Schema errors and repeated IDs are intentional only in the labelled raw import
fixtures. Separate support files retain allocations, immutable voids and review
history. The instalment fixture leaves 5,000 outstanding after a 25,000 collection
is voided and replaced with 20,000; it never changes the primary shop.

The independent calculator imports no backend financial code. Development truth
includes recorded sales, signed differences, balances/aging, estimated gross
margin and coverage, weekly financial components, supplier sufficiency, running
seven-day positions, three forecast scenarios and the seven-day baseline.
Forecast expectations use cutoffs 60/75 and observed inputs only: 30 predictions
each, with 30/15 scoreable days ending at day 90. No realized forecast outcomes
are read or scored by this command. These files are expected values, not model
evaluation results or a production forecast.

evaluation/development_questions.jsonl has 32 draft development cases;
dialect_intents.jsonl carries the joint intent/tool/customer/period labels.
QUESTION_SPEC.md defines the portable question format without numeric answers.
Both development language and scenario plausibility await human review.

evaluation/sealing_input_manifest.json lists and hashes only observed inputs,
fixtures, the format and development questions for external independent staging.
It excludes future outcomes, unseen shops, cause labels and development answers.
No held-out questions or heldout_60_manifest.json are generated here.
An independent tool/session and Iraqi Arabic human review are required before
sealing. A human runs scripts/hash_heldout.py in their own terminal with an
external HELDOUT_PATH; it validates 60 reviewed records (40 answerable, 20
clarify/refuse) and emits only SHA-256 and aggregate counts. Builders must never
run it against actual held-out content.
