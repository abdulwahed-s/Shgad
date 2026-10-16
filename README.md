# Shgad (شكد)

An Iraqi Arabic cash-flow assistant for a neighbourhood merchant who tracks cash sales,
customer credit and supplier payments. Shgad aims to turn those records into clear answers
with figures that can be traced back to their source rows.

Built for the Agentic AI Challenge Iraq, Topic 02 (SME & Merchant Assistant).

> **Status: Phase 0 in progress.** The backend health endpoint and configuration tests work.
> Merchant features below remain planned; no benchmark results or demo dataset exist yet.

## Planned features

- Import synthetic CSV records into a validated SQLite ledger.
- Answer everyday financial questions in Iraqi Arabic, with source evidence for every figure.
- Keep cash, sales, customer debts, supplier bills and owner drawings separate.
- Flag unmatched payments and suspected duplicates for review.
- Summarise the week, including gross margin when cost data is sufficient.
- Project cash flow over the next 30 days, with explicit collection assumptions.

## Merchant questions

These examples describe the intended experience:

| Question | Intended answer |
|---|---|
| عندي فلوس تكفي أدفع للمجهز الخميس؟ | Cash available for a supplier payment, separating confirmed cash from expected collections. |
| منو بعده بذمته فلوس؟ | Outstanding customer debts and their due dates. |
| أكو دفعات ما تطابقت؟ | Unmatched payments and possible duplicates, with explanations. |
| شلون كان شغلنا هالأسبوع؟ | A week-to-date summary of sales, collections, spending and gross margin coverage. |
| الشهر الجاي أكدر أوفي التزاماتي؟ | A cash-flow projection with base and conservative scenarios. |

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

Financial calculations will use integer IQD in Python. The LLM will request validated,
read-only tools and draft explanations with symbolic slots; the backend will fill figures
and dates from verified results. Provider calls and API keys will stay in the backend.

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
Settings read process environment variables; `.env.example` lists the names.
No `.env` file or provider credentials are needed for health checks. `BUSINESS_AS_OF`
stays unset until explicitly configured; it never defaults to the server date.

Flutter setup, CI results and demo seed/import instructions remain pending.

## Data and scope

All datasets must be fictional. Real customer and transaction records are outside the scope
of this project. The demo will cover one merchant; payment execution and formal tax/accounting
services are outside the planned MVP.

Application
model/API integration and synthetic data generation remain planned.
