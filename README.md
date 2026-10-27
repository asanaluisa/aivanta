# Aivanta — AI Business Value & ROI Intelligence

[![CI](https://github.com/asanaluisa/aivanta/actions/workflows/ci.yml/badge.svg)](https://github.com/asanaluisa/aivanta/actions/workflows/ci.yml)

**English** · [Español](README.es.md)

> **Are we getting more value from AI than we are spending on it?**

Aivanta is a full-stack B2B analytics platform that connects AI consumption (tokens, models, providers, requests) with measured business outcomes (time saved, quality, savings, cost avoidance) and evaluates AI with the same rigour as any other investment. It does not stop at an API bill: it decides — with evidence — where AI should be expanded, optimised, restricted, tested or stopped.

![Executive overview](docs/screenshots/dashboard_en.png)

| | |
|---|---|
| ![AI vs. non-AI comparison (Spanish)](docs/screenshots/comparison_es.png) | ![Use case detail](docs/screenshots/use_case_marketing_en.png) |

> All figures in this repository come from a **reproducible synthetic dataset**. Model names (`gpt-demo-large`, `claude-demo-compact`, …) and prices are deliberately fictional placeholders, not vendor list prices.

---

## What it does

| Question | How Aivanta answers it |
|---|---|
| **What are we spending?** | Normalises usage from OpenAI, Anthropic and Google Gemini exports, prices every event against a versioned price schedule (cached-token rates included), and allocates it to departments and use cases. Usage nobody can attribute stays visibly **unallocated**. |
| **What are we getting?** | Captures baselines, AI and non-AI task measurements, quality, review and rework, and benefit claims with a verification status. Only **verified** savings and **supported** (controlled-measurement) contribution / cost avoidance count towards ROI. |
| **Is it worth it?** | A deterministic ROI engine (ROI, net benefit, benefit-to-cost ratio, payback, break-even, scenarios), an AI-vs-non-AI comparison with 95 % intervals, and explainable rule-based recommendations. When evidence is too thin it shows **"Insufficient evidence"** instead of a number. |

### Highlights
- **Evidence-first ROI** — every KPI is tagged *Measured*, *Evidence-backed* or *Estimate*; estimates are shown but never mixed into ROI. Double counting is prevented by collapsing claims that describe the same outcome.
- **AI is never assumed better** — the comparison engine can recommend *continue*, *optimise*, *use only for selected task types*, *run a controlled experiment* or *stop*, and distinguishes causal designs (randomised / control group) from correlational ones.
- **Total cost of ownership** — model usage, subscriptions, infrastructure, implementation, maintenance and *incremental* human review and rework.
- **Fully bilingual (EN/ES)** — structured localisation files, Spain-Spanish business terminology, locale-aware numbers, currency and dates, and localised CSV exports (`;` and decimal comma for Spanish spreadsheets). A test checks key parity, placeholders and that every code the backend can emit is translated.
- **Multi-tenant and governed** — organisation-level data isolation, role-based access (admin, finance, analyst, viewer), editable assumptions, frozen ROI snapshots and an audit log.

## Quick start

Requirements: Docker with Compose.

```bash
cp .env.example .env          # then set AIVANTA_JWT_SECRET to a long random string
docker compose up --build
```

- Web app: <http://localhost:3000>
- API docs (OpenAPI): <http://localhost:8000/docs>

On first start the backend applies migrations and loads the synthetic demo data (two organisations, to demonstrate isolation). Sign in with any demo account; the password is `AIVANTA_DEMO_PASSWORD` (default `aivanta-demo`):

| Account | Role | Can |
|---|---|---|
| `admin@aivanta.demo` | Administrator | everything, incl. audit log |
| `finance@aivanta.demo` | Finance | edit ROI assumptions, freeze ROI snapshots |
| `analyst@aivanta.demo` | Analyst | upload usage files |
| `viewer@aivanta.demo` | Viewer | read only |
| `admin@northwind.demo` | Administrator of a second organisation | sees only its own data |

Reload the demo data with `make seed` (`docker compose exec backend python -m app.seed --reset`).

### Without Docker

```bash
# backend (Python 3.10+, PostgreSQL 14+)
cd backend
pip install -r requirements-dev.txt
export AIVANTA_DATABASE_URL=postgresql+psycopg://aivanta:aivanta@localhost:5432/aivanta
alembic upgrade head && python -m app.seed
uvicorn app.main:app --reload

# frontend (Node 20+)
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## Architecture

```
frontend/  Next.js 15 · React 19 · TypeScript · Tailwind CSS v4 · d3-scale/d3-shape charts
  src/i18n/        messages/en.json, messages/es.json, translation core, provider
  src/features/    one view per page (dashboard, costs, departments, outcomes, comparison, …)
  src/components/  app shell, filter bar, KPI cards, charts, UI primitives
backend/
  aivanta_core/    framework-free domain logic (standard library only)
    pricing.py  roi.py  stats.py  comparison.py  analytics.py  recommendations.py
    ingestion/  synthetic.py  reporting.py  serialize.py  locales/
  app/             FastAPI · SQLAlchemy 2 · Pydantic v2 · JWT auth · RBAC
  migrations/      Alembic (DDL in migrations/sql/0001_initial.sql)
samples/           documented example files for every ingestion format
docs/              architecture, financial definitions, case study (EN/ES)
```

The central design decision: **all business logic lives in `aivanta_core`, a pure-Python package with no framework dependencies.** The API loads an organisation's records into plain dataclasses and hands them to the engines; the same engines feed the exports, the seed script and the tests. Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## ROI methodology (summary)

```
Total AI-related cost = model & API usage + subscriptions + infrastructure + implementation
                      + maintenance + incremental human review + incremental rework
Gross benefit         = verified financial savings + supported incremental contribution
                      + supported cost avoidance                (one claim per outcome)
Net benefit           = gross benefit − total AI-related cost
ROI %                 = (gross benefit − total AI-related cost) / total AI-related cost × 100
```

Hours saved are reported separately and never converted into cash inside ROI. ROI is withheld (status *insufficient evidence*) when there is no verified or supported benefit, fewer than 30 measured AI tasks, or less than 14 days of measurement — all editable assumptions. Full definitions: [docs/FINANCIAL_DEFINITIONS.md](docs/FINANCIAL_DEFINITIONS.md).

## Ingestion

| Format | Endpoint | Status |
|---|---|---|
| Aivanta canonical CSV (any provider) | `POST /api/ingestion/aivanta_csv` | implemented, tested |
| OpenAI organisation usage export (completions buckets, JSON) | `POST /api/ingestion/openai` | implemented, tested against sample |
| Anthropic usage report export (messages, JSON) | `POST /api/ingestion/anthropic` | implemented, tested against sample |
| Gemini `usageMetadata` response log (JSONL) | `POST /api/ingestion/google` | implemented, tested against sample |
| Live pull from vendor APIs | — | **not implemented** (labelled in the UI) |

Vendor adapters follow each provider's publicly documented field names as understood in mid-2026; verify them against your own exports. Uploads are idempotent (deterministic event ids), invalid rows are rejected with a reason, and attribution comes from mapping rules (API key, project, workspace or label → department / use case). See [samples/README.md](samples/README.md).

## Tests and verification status

| Area | What exists | Executed while building this repository? |
|---|---|---|
| Core engine (pricing, ROI, statistics, comparison, recommendations, ingestion, synthetic data, reports, API payloads) | 106 pytest tests incl. reconciliation of every dashboard metric with the raw records | **Yes** — all pass |
| Database schema | `migrations/sql/0001_initial.sql` | **Yes** — applied to PostgreSQL 16 |
| Web API (FastAPI + SQLAlchemy + Alembic) | `tests/api/` — auth, RBAC, organisation isolation, ingestion idempotency, reports, snapshots, audit, and an ORM-vs-migration schema diff | **Yes, in CI** — GitHub Actions against a PostgreSQL 16 service |
| Frontend logic | 14 `node:test` tests: EN/ES key parity and placeholders, terminology, every backend code translated, number/date/currency formatting, filter encoding | **Yes** — all pass |
| Frontend UI | every page rendered in headless Chromium against real API payloads, EN and ES, desktop and mobile (screenshots above) | **Yes** — via a harness with mocked transport |
| `next build`, `tsc --noEmit`, `ruff` | CI workflow in `.github/workflows/ci.yml` | **Yes, in CI** |
| `docker compose up` | `docker-compose.yml` | not run automatically — run locally |

```bash
make test                # backend + frontend tests
cd backend && pytest -q  # API tests run when AIVANTA_TEST_DATABASE_URL is set
```

## Design choices and limitations
- **Charts** use `d3-scale` and `d3-shape` rendered by React instead of Recharts: same role (established library), full control over accessibility (table view for every chart, no colour-only encoding) and a validated colour-blind-safe palette.
- **In-memory analytics.** An organisation's dataset is loaded once per data version and cached; this is ample for tens of thousands of events. Beyond millions of events, the aggregations in `analytics.py` would move to SQL (materialised daily rollups).
- **Token storage** uses `localStorage` for simplicity; a production deployment should use an httpOnly cookie.
- **Anthropic cache writes** are priced at the normal input rate; Gemini thinking tokens are billed as output.
- **Light theme only.**

## Documentation
- [Architecture](docs/ARCHITECTURE.md)
- [Financial definitions](docs/FINANCIAL_DEFINITIONS.md)
- [Case study](docs/CASE_STUDY.md) · [Caso de estudio](docs/CASE_STUDY.es.md)

---

Built by **Andrés Sebastián Analuisa** as a portfolio project in AI engineering, data engineering and AI business systems. Licensed under the MIT License.
