# Shgad (شكد)

An Iraqi Arabic cash-flow assistant for a neighbourhood merchant who tracks cash sales,
customer credit and supplier payments. Shgad aims to turn those records into clear answers
with figures that can be traced back to their source rows.

Built for the Agentic AI Challenge Iraq, Topic 02 (SME & Merchant Assistant).

> **Available now:** a tested backend for synthetic CSV import, merchant entries,
> partial payments, voids/corrections, ledger evidence and daily-close review.
> Source-linked sales/debt queries and a next-days obligations HTTP view separate
> confirmed cash from expected collections, with missing balances kept unavailable.
> Five read-only tools, margin/weekly reports, deterministic Arabic figure rendering,
> reconciliation and cutoff-safe cash-estimate HTTP routes are tested. Chat and CSV
> mapping use a configurable provider client with bounded retries and failover;
> their integration is verified with recorded provider responses. Flutter remains a
> static localized shell; merchant screens and frontend chat integration are planned.
> Gemini, Groq and OpenAI completed bounded development routing screens. With
> larger time/token limits, Gemini 3.8 Flash scored 9/10 and GPT-6 Luna 7/10.
> Full live chat validation and human review of new Arabic copy remain pending.

## Capabilities and planned interface

- Import fictional CSVs into a validated SQLite ledger with replay-safe batch receipts.
- Record debts, partial payments, expenses, drawings, capital and cash counts through HTTP endpoints.
- Keep recorded cash sales separate from signed unexplained cash differences.
- Preserve immutable evidence through merchant voids and explicit corrections.
- Identify unmatched/candidate payments, partial balances, overdue debts and suspected duplicates.
- Query sales, debts, reconciliation, estimated gross margin and cash estimates through five validated tools.
- Return deterministic weekly totals and a secondary cash estimate with base, conservative and stress scenarios.
- Render sourced figures and dates in Arabic, with validation and deterministic template fallback.
- Planned merchant screens will put today's cash, debts, entry and daily close first.
- Answer chat requests through a bounded, read-only agent with verified figures and source evidence.

## Merchant questions

These examples describe the intended experience:

| Question | Intended answer |
|---|---|
| عندي فلوس تكفي أدفع للمجهز الخميس؟ | Cash available for a supplier payment, separating confirmed cash from expected collections. |
| منو بعده بذمته فلوس؟ | Outstanding customer debts and their due dates. |
| أكو دفعات ما تطابقت؟ | Unmatched payments and possible duplicates, with explanations. |
| شلون كان شغلنا هالأسبوع؟ | A week-to-date summary of sales, collections, spending and estimated gross margin coverage. |
| الشهر الجاي أكدر أوفي التزاماتي؟ | A secondary cash estimate with base, conservative and stress scenarios. |

## Planned architecture

```mermaid
flowchart LR
    CSV[Synthetic CSV] --> API[Python / FastAPI]
    UI[Flutter interface] <--> API
    API <--> Ledger[(SQLite ledger)]
    API <--> Agent[Single LLM agent]
    Agent --> Tools[Read-only financial tools]
    Tools --> Ledger
    Tools --> Renderer[Verified figure rendering]
    Renderer --> API
```

Financial calculations use integer IQD in Python. The tools and renderer work without
an LLM. The agent requests these tools and drafts explanations with symbolic slots;
the backend fills figures and dates from verified results. Provider calls and API
keys stay in the backend. Integration tests use recorded provider responses;
live model selection and quality checks remain pending.

## Development status

The backend requires Python 3.11+ and was verified locally with Python 3.14.7.
From the repository root, create an environment and install the pinned dependencies:

```sh
python -m venv backend/.venv
# Windows PowerShell:
backend/.venv/Scripts/python -m pip install -e 'backend[dev]'
# macOS / Linux: use backend/.venv/bin/python in place of the Windows path.
```

Then, from `backend/`, use that environment's Python:

```sh
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m uvicorn app.main:app --reload
```

Activate the environment first (`.venv/Scripts/Activate.ps1` in PowerShell or
`source .venv/bin/activate` on macOS/Linux). `GET http://127.0.0.1:8000/health`
returns `{"status":"ok","version":"0.1.0"}` without configuration values.
For local development, copy `.env.example` to a repository-root `.env` if it does
not already exist, then edit it locally. The backend loads that exact file from
either the root or `backend/` working directory. Non-empty process environment
variables override file values; blank optional values use defaults. Keep `.env`
out of Git and chat. Set `APP_ENV=test` or `APP_ENV=production` in the launching
process to use environment variables without reading the local file. Restart the
backend after changing configuration.
No `.env` file or provider credentials are needed for health checks. `BUSINESS_AS_OF`
stays unset in raw settings until configured. The domain `BusinessClock.from_settings`
uses the configured date, or **2026-09-28** (synthetic day 90) when absent; it never
uses the server date. Weeks run Saturday–Friday, and naming today's weekday requires
clarification. Baghdad business dates are derived from offset-aware timestamps;
storage uses UTC.

The backend foundation includes strict integer-IQD records, digit/IQD parsing,
and deterministic cash, sales and settlement primitives. Recorded cash sales stay
separate from signed unexplained differences; missing consecutive counts remain
unavailable. Capital injections add cash without sales, revenue or collections.
Drawings remain separate from business expenses.

SQLite schema version 4 has sixteen STRICT tables, with foreign keys, unique
idempotency keys, guarded partial-payment allocations and immutable source evidence.
`POST /api/entries/{source_id}/void` supports merchant undo with client idempotency
and cutoff-aware calculations. Voiding a collection restores outstanding
debt while retaining original transactions, raw rows and linked reason/timestamp audits.
For a correction, void the original and send its ID as `correction_of_source_id`
on the replacement entry. It retains the original event time and an immutable link,
so correcting a pre-count payment does not add cash again. New entries follow the
last known event on their supplied business date. `GET /api/ledger/transactions` supports
date/type/customer/source-ID filters and cursor pagination; its source-ID detail
route returns raw cells, flags and the original amount with any linked void audit.
Versioned migrations preserve earlier ledger/mapping records and roll back atomically. Unknown opening cash
raises a typed error.

Migrations use the standard-library SQLite driver and require SQLite **3.37+**
(STRICT tables); local verification used SQLite 3.50.4. To create an empty schema,
run this Python from `backend/` with its environment activated:

```python
from contextlib import closing
from app.db.connection import connect_database
from app.db.migrations import apply_migrations

with closing(connect_database("shgad.db")) as connection:
    apply_migrations(connection)
```

This creates the schema only. Preload fictional reference and opening records
before importing or recording debts. Demo reset and automatic demo-data loading
remain planned.

`POST /api/entries` records cash/credit sales, supplier invoices, explicit partial
collections/payments, expenses, drawings, capital and daily cash counts. Amounts
are strict positive integer IQD; invalid references and overpayments are rejected
atomically. Retry with the same `client_entry_id` and payload to receive the saved
source ID without another financial effect. A changed payload under that key fails.

The Python service `app.services.ingest.import_csv` imports explicitly fictional
canonical CSV files into a migrated SQLite connection. Preload verified categories,
counterparties and opening records separately. It validates UTF-8/BOM files up to
5 MiB / 10,000 rows, normalizes Arabic-Indic amounts, preserves raw cells and errors,
and commits validated rows and quarantine evidence atomically. Explicit compatible
obligation references and unique strong matches create payment allocations. Strong
matches require the exact party, a sufficient outstanding balance and a due date
within 30 days. Candidate/unmatched payments and suspected
duplicates remain flagged for review. Exact file replay adds no transactions,
cash, revenue, obligations or allocations; receipts distinguish accepted, rejected,
exact-duplicate and flagged rows. `POST /api/imports/csv` accepts a multipart `file`;
`GET /api/imports/{batch_id}` retrieves its receipt and row errors. Files must be
fictional. No reference data is created automatically.
Uploads retain real audit times; late knowledge stays excluded from earlier cutoffs.

Unfamiliar CSV layouts have mapping preview and confirmation endpoints at
`POST /api/imports/csv/mapping` and `POST /api/imports/csv/mapping/{mapping_id}/confirm`.
The proposer interface receives only the header and three sample rows. Code validates
its mapping and previews up to five parsed rows without financial writes. Confirmation
uses saved immutable input/mapping metadata and the normal importer; retries are safe.
The proposer uses the same configurable client as chat. An unconfigured client
returns `LLM_UNAVAILABLE`. Recorded-response integration tests cover the HTTP
proposal, preview and explicit confirmation flow; live mapping quality is unverified.

`app.services.reconcile.reconciliation_report` reads cutoff-bounded SQLite and
returns definite/strong/candidate/unmatched status, reasons, source IDs and current
partial/overdue flags. It creates no links. Similar names and ambiguous obligations
remain candidates for merchant review. Ledger detail includes these flags.

`app.services.forecast.forecast` reads only a cutoff-filtered SQLite snapshot and
returns 30 integer-IQD daily estimates for base, conservative and stress scenarios.
Recorded sales and signed unexplained differences remain separate drivers; conservative
collections use observed settlement lateness, stress collections are zero, and overdue
receivables are excluded. Unknown starting cash, essential history or due dates produce
typed clarification errors. Later entries, payment links and voids cannot change an
earlier forecast. The service enforces the observed calendar boundary and loads no
files or evaluation answers. `GET /api/reports/forecast` exposes the service;
forecast UI integration and accuracy evaluation remain pending.

Seeded fictional data and offline development truth are available. From the
repository root (standard library only):

```sh
python scripts/generate_synthetic_data.py --seed 20260701
python scripts/make_ground_truth.py
```

The generator writes 90 observed days and 30 separate future days for one
fictional shop, plus three shops reserved for frozen final forecast testing.
It constructs daily counts, recorded sales, signed unexplained differences,
capital, credit and supplier settlements, and isolated review/void fixtures.
The independent calculator imports no backend financial services. Its
development expectations include sales, debts, estimated gross margin,
seven-day positions and three forecast scenarios at historical cutoffs.
These are offline reference values; the separate production forecast service uses
the financial specification and SQLite history. The five read-only tools query
that ledger without a provider. Development score windows stop at day 90.

See [data/README.md](data/README.md) for file boundaries and generation
metadata. Same-seed regeneration was byte-identical in a fresh process,
including the manifest. The development questions and generation mechanics have
recorded human review, including all twelve note phrases and four scenarios.
The historical test set has 60 human-reviewed questions and a
[hash/count manifest](data/evaluation/heldout_60_manifest.json); the questions
remain outside the repository. Generation used a separate session of the same
tool used during development. Memory controls were requested; isolation was not
independently verified and the exact generator model ID was not exposed.
No held-out model evaluation has run.

`scripts/model_smoke_test.py` prepares a provider comparison using ten fixed,
reviewed development questions and the existing five read-only tool schemas.
With the backend development environment installed, run from the repository root:

```sh
python scripts/model_smoke_test.py
python scripts/model_smoke_test.py --help
```

The default is a dry run with no provider requests. Live use requires `--live`,
exact provider model IDs through `--gemini-model` and `--groq-model`, their
`--model-ids-checked-on` date, and the selected provider keys in local `.env` or
process environment variables. `--provider gemini` or `--provider groq` runs one
candidate and requires only its key; the default compares Gemini and Groq.
An explicit `--provider openai --openai-model gpt-6-luna` comparison uses a local
`OPENAI_API_KEY`. This comparison-only path uses Responses with medium reasoning,
no temperature override and optional response storage disabled. It preserves the
same logical prompts, tool parameter schemas and scoring. API/reasoning differences
limit comparisons with the compatible-chat providers. OpenAI is not an application
provider in this implementation.
Only an explicit live run loads credentials; the default
dry run leaves `.env` untouched. Never paste keys into chat. It compares interpretation
and native tool selection against development labels, including customer and period.
It executes no proposed tools and measures no financial-answer accuracy. The hard
cap is 40 requests, with no retries and at least ten seconds between a provider's
requests. Provider errors stop that candidate. The default HTTP timeout is 20s
and output limit is 768 tokens; explicit `--timeout-seconds` (1–300) and
`--max-tokens` (1–32,768) support slower reasoning models. Reports record these
limits, known finish reasons and available token-usage counters, without retaining
model prose or tool arguments. Per-request elapsed times include pacing waits.
Scores from different limit settings are not controlled model comparisons.
Full application quality remains unverified.

`--minimum-interval-seconds` selects 10-60 seconds between a provider's requests
(default 10); `--progress` prints aggregate case/request counts to stderr.
For `qwen/qwen3.8-27b` on Groq, the comparator defaults to medium reasoning;
`--qwen-reasoning-effort none|low|medium|high` selects an explicit profile.
Hidden reasoning format, temperature 1 and top_p 0.95 preserve the same prompts
and tool parameter schemas. Its documented output cap of 16,384 tokens is checked
before loading credentials or sending requests. Model-specific overrides and
actual pacing are recorded in the report; this profile does not change the app.
Quota failures retain only recognized error codes and bounded numeric limit,
remaining-token, requested-token and retry/reset counters. Provider messages,
organization names and secret values are not retained.
Distinct quota counters from headers and provider messages are preserved separately,
along with an allowlisted metric label when the provider identifies one unambiguously.

NVIDIA-hosted candidates are available explicitly through `--provider nvidia
--nvidia-model ...`, using the optional local `BUILD_NVIDIA_API_KEY`. Supported
comparison IDs are `z-ai/glm-5.3`, `moonshotai/kimi-k3`,
`stepfun-ai/step-5-preview` and `z-ai/glm-5.3-flash`. GLM and Kimi profiles request
Max reasoning; Step keeps native reasoning enabled. Reports record their sampling
and chat-template options. Optional `--nvidia-stream` assembles native SSE content
and function-call fragments, discards separate reasoning, and rejects incomplete
or truncated responses. NVIDIA comparisons allow up to 900s HTTP timeouts;
other providers retain the 300s ceiling. Streams bound decoded bytes and retained
output, including unterminated lines, with no automatic retries. The default comparison remains Gemini/Groq and the
application's provider selection is unchanged. NVIDIA model access and quality
must be measured separately; a catalog listing alone is not an inference result.

On 19 October, clean source `b72908f` completed two NVIDIA screens using the
same ten development questions, logical prompts, five schemas and scorer:

| Candidate | Jointly correct | Correct native tool set |
|---|---|---|
| `z-ai/glm-5.3-flash` (Max) | 6/10 | 10/10 |
| `stepfun-ai/step-5-preview` | 0/10 | 10/10 |

Both completed 20 requests without provider errors, retries or reported
truncation, using 32,768 output tokens, 300s HTTP timeouts and 30s pacing.
Flash reported 37,479 total tokens; Step reported 41,622. Step failed every
separate interpretation check while passing every native tool/context check.
One additional unscored format probe returned separate reasoning without final
text; it does not establish the cause of every original failure or change scores.
These are strict routing/format screens, not application or Arabic-language
quality scores. Their reasoning and resource profiles differ from earlier runs.

`moonshotai/kimi-k3` returned HTTP 410 on its first attempt; NVIDIA's
[deployment page](https://build.nvidia.com/moonshotai/kimi-k3?section=deploy)
marks its free endpoint deprecated. All ten cases remain unscored.
`z-ai/glm-5.3` (Max) has no completed case yet: two nonstreaming attempts
at 300s and two at 900s produced two unpaired interpretations, one timeout and
one HTTP 504. A separate unscored streaming probe then returned one well-formed
native tool call after 405s, using 4,387 reported tokens. The full streaming
development screen remains pending; no score is assigned yet.

Measured locally on 18 October 2026 at source commit `ca62b01`: both candidates
completed the ten-question development screen using 40 requests total, with no
provider errors or retries. Joint correctness requires intent, behavior, tool
choice, customer and period to agree with the development labels.

| Candidate | Jointly correct | Correct tool set |
|---|---|---|
| `gemini-3.1-flash-lite` | 6/10 | 9/10 |
| `openai/gpt-oss-120b` on Groq | 4/10 | 5/10 |

This first comparison requested temperature 0, a 768-token output limit and a
20s HTTP timeout. This small development screen uses a separate routing
prompt; it does not measure application answers, financial accuracy or held-out
performance. Development tuning and human acceptance remain pending.

An additional check on 18 October at clean source `54a7382` used the same ten
questions, prompts, gold labels and tool schemas with `gemini-3.8-flash`:
**9/10 jointly correct and 9/10 correct tool sets**, with intent, behavior,
customer and period each correct on all ten. All 20 requests completed with no
provider errors, retries or reported truncation. This run allowed 180s per HTTP
request and 32,768 output tokens, with at least ten seconds between requests.
The API reported 34,829 total tokens across the run. Its larger time/token limits
differ from the first comparison, so the score difference cannot be attributed
solely to model choice. Application model selection and live answer quality
remain pending.

A further check on 18 October at clean source `937d180` used `gpt-6-luna`:
**7/10 jointly correct and 9/10 correct tool sets**, with all 20 requests
completed and no provider errors, retries or truncation. This screen used the
same ten questions, logical prompts, tool parameter schemas and scorer, with
180s HTTP timeouts and 32,768 output tokens. Luna used Responses with medium
reasoning, no temperature override and optional response storage disabled.
The API reported **23,919 total tokens**, including **2,095 reasoning tokens**.
The failed checks concerned one interpreted period, the reconciliation tool set
for conflicting records, and one unsupported-write interpretation. These are
single development screens with different API/reasoning profiles, not controlled
model rankings or live application/financial-answer accuracy.

The `qwen/qwen3.8-27b` screen on Groq completed on 19 October at clean source
`7da09ec` with a recorded local operational adapter: **2/10 jointly correct,
8/10 correct tool sets and 9/10 valid tool selections**. All 20 requests completed
without provider errors, retries or reported truncation, using 29,937 reported
tokens. The profile used **reasoning none**, hidden format, temperature 1/top_p
0.95, 768 output tokens, 180s HTTP timeouts and at least 65s actual spacing
(60s CLI setting). No separate reasoning-token counters were reported.

Sanitized provider metadata identified a separate 1,000 output-token-per-minute
limit alongside the 8,000 combined-token limit. Earlier setup/diagnostics are
retained separately: 12 attempts, six successful responses, five HTTP 429
rejections and one HTTP 400; interrupted answers are not extra scored questions.
The complete Qwen check therefore used 32 generation attempts within its 40-attempt
recovery cap. Logical prompts, development questions, schemas and scoring stayed
unchanged. Different reasoning/resource profiles prevent a controlled model
ranking; application model choice and live answer quality remain pending.

The frontend was verified with Flutter 3.44.9 stable and Dart 3.12.2. It contains a static
chat shell, defaults to Arabic RTL, and also supports English LTR. Cairo is bundled with
its license. Backend requests use one Dio client configured with `API_BASE_URL`;
the static shell does not call the backend or any model provider.

From `frontend/`:

```sh
flutter pub get --enforce-lockfile
flutter gen-l10n
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
flutter run -d chrome --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

To build the web shell with runtime assets served locally:

```sh
flutter build web --release --no-web-resources-cdn --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

The Android target is scaffolded as `com.aw.shgad`, display name «شكد»; Android builds
and release signing have not been verified. Arabic copy is awaiting Iraqi Arabic review.
Flutter merchant screens and model integration remain planned. CSV import/receipts,
merchant entries and deterministic reports have HTTP interfaces, documented at `/docs`.
`GET /api/daily-close/{date}` compares consecutive counts against recorded cash
flows and shows the signed unexplained difference. Missing counts remain missing.
`POST /api/daily-close/{date}/resolve` accepts a merchant-chosen explanation or
`leave_unexplained`. Sign/amount guards and client idempotency prevent a second
financial effect; a voided explanation stays in review history. No cause is inferred.
`GET /api/obligations/upcoming?days=7` lists supplier dues, non-overdue expected
collections and separate overdue receivables. It returns signed confirmed-only
and with-expected positions, daily running balances and first negative dates,
without projected sales. The window accepts 1–30 days; missing cash retains known
obligations with unavailable positions. `GET /api/debts` provides receivable totals,
aging and exact-party evidence. The read-only sales/debts tool wrappers validate
arguments and resolve symbolic periods on the server. `GET /api/reports/margin`
returns estimated gross margin, recorded-sales coverage, unpriced-sale count,
buy-price evidence and an after-recorded-expenses figure with excluded-cost notes.
`GET /api/reports/weekly` returns deterministic weekly totals and shows estimated
margin only at the configured coverage threshold (80% by default;
`MARGIN_MIN_COVERAGE_PCT`). Voided sales and expenses are excluded using the query's
audit knowledge. All five tools validate arguments and verify source references,
integer units and arithmetic before a protected renderer handoff.
`GET /api/flags` exposes reconciliation flags; `GET /api/reports/forecast`
exposes the existing cutoff-safe scenarios. `/api/meta` reports whether a provider,
model ID and local key are configured; this does not probe network availability.

`POST /api/chat` accepts `message` and a correlation `conversation_id`. Each request
starts a fresh tool context. The agent can use only the existing five read-only
tools, with validated arguments, at most four completion turns and eight tool
calls. Responses include the resolved customer and period, sourced figures and
dates, verification evidence and renderer status. Missing balances and ambiguous
names or periods produce fixed clarification messages. Provider failure after a
verified result can return the deterministic template with a fallback notice.

Configure `LLM_PROVIDER` (`gemini` or `groq`), `LLM_MODEL_ID` and that provider's
API key in the root `.env` or process environment. `.env.example` lists optional
fallback and timeout settings. `GEMINI_API_KEY` and `GROQ_API_KEY` authenticate
provider access; model IDs select models separately. Use exact console model IDs;
keep keys local and never paste them into chat. Without configuration, chat
returns the typed `llm_unavailable` response without a provider request.

`app.agents.renderer` fills `{{fig:key}}` and `{{date:key}}` only from verified
tool output. Raw numeric characters, unknown keys and unsourced values are rejected.
It supports one retry callback and then deterministic templates, with server-resolved
customer/period context, margin coverage and estimate assumptions. Exact user-typed
quotes stay quoted data. Money uses Arabic-Indic digits and exact abbreviations;
evidence retains full integers. New fixed Arabic copy is pending Iraqi Arabic review.
The agent retries an invalid draft once before using these templates. Imported
text remains quoted data and gives the agent no ledger-write capability.

Verified locally: **654 backend tests passed, one opt-in live test skipped**,
including real HTTP/SQLite financial, mapping, reconciliation, immutable-correction
and cutoff regressions, recorded provider integration, and offline synthetic-data
and model-comparison harness checks. Ruff lint/format and Python 3.11 grammar
checks pass for **110 backend/script files**; dependency checks pass.
A running-server smoke passed **20 check groups across 19 OpenAPI paths**, using
only a temporary fictional database.
Every implemented endpoint has a response-model contract test, including daily close,
voids and standard error responses. Financial-rule
regressions were observed failing before their implementation or fix.
To include offline scripts in lint/format checks from backend/, run
`python -m ruff check --config pyproject.toml . ../scripts` and
`python -m ruff format --check --config pyproject.toml . ../scripts`.
Checks include recorded sales and signed differences, capital, review validation,
void-adjusted balances and knowledge cutoffs, v1 upgrades, replay and atomic rollback.
Concurrent review requests cannot explain the same cash twice. The live routing
screen above does not validate complete chat/mapping answers or failover behavior.

The default suite makes no live provider requests. A single development routing
probe requires both `SHGAD_RUN_LIVE=1` and `python -m pytest -m live`; it has a
four-request transport cap. The separate development comparison above retains
its forty-request cap. Neither check accesses held-out questions.

Flutter verification: 4 widget tests
(360×800, Arabic/English, text scales 1.0/1.3), Dart formatting and Flutter analysis.
The health endpoint also returned HTTP 200 from a separate clean checkout. The release
web shell launched in headless Chrome without runtime exceptions; RTL screenshots at
normal and enlarged text sizes were inspected. A separate Dio smoke check reached the
running health endpoint using `--dart-define`.

[GitHub Actions](https://github.com/abdulwahed-s/Shgad/actions/workflows/test.yml)
runs backend lint/format/tests and Flutter localization, formatting, analysis and tests
on pushes and pull requests. Its linked run history shows the measured CI results.
No financial benchmark or held-out model evaluation has run.

Synthetic CSV generation, ledger import, financial tools and deterministic reports are available;
a merchant-facing demo remains pending. No forecast accuracy is claimed; the
small development routing results above are the only measured model results.

## Data and scope

All datasets must be fictional. Real customer and transaction records are outside the scope
of this project. The demo will cover one merchant; payment execution and formal tax/accounting
services are outside the planned MVP.

GPT-6.1 Sol drafted the fictional scenario templates. Deterministic seeded Python
generated all numeric records.
The scenario manifest records the drafting brief and the user-confirmed model
display name; the exact provider model ID/settings remain unavailable and are
not guessed. No model-provider API call was used for this dataset.
Application integration is tested with recorded responses. Live development
screening used the candidates above; production selection, complete application
checks and human approval of the new Arabic messages remain pending.
