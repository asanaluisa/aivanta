# Case study — Measuring whether AI pays for itself

**English** · [Español](CASE_STUDY.es.md)

*Andrés Sebastián Analuisa · Aivanta portfolio project*

> All numbers below come from Aivanta's reproducible synthetic dataset (seed `20260930`, 3 July – 30 September 2026). They illustrate the method; they do not describe a real company.

## 1. The business problem

Most companies can tell you what they pay their AI providers. Very few can tell you what they get back. The usual dashboards stop at tokens and invoices, while the business case is argued with anecdotes ("the team says it saves hours") and vendor metrics ("influenced pipeline"). The result is predictable: AI spend grows in places where it adds little, and genuinely valuable use cases are never scaled because nobody can prove they work.

Aivanta treats AI like any other investment and answers three questions:

1. **What are we spending?** — not just on tokens, but in total.
2. **What measurable outcomes are we getting?** — with the evidence behind each claim.
3. **Is it enough to justify the cost?** — per organisation, department and use case, with a clear decision.

## 2. The approach

**Normalise and price every AI call.** Usage exports from OpenAI, Anthropic and Gemini differ in shape and in how they report cached and reasoning tokens. Provider adapters convert them to one event model; a versioned price schedule turns tokens into money on the day of use; attribution rules map API keys, projects or labels to departments and use cases. Anything that cannot be attributed is kept, priced and shown as *unallocated* — never guessed.

**Count the full cost.** Model usage is only one line. Aivanta adds subscriptions, infrastructure, implementation, maintenance and the human time AI creates: review and rework, charged only where they exceed what the non-AI process already needed.

**Only evidence counts.** Each benefit claim carries a verification status. Ledger-verified savings and benefits backed by a controlled measurement count; estimates and unverified claims are shown but kept out of ROI; claims describing the same outcome are counted once. If the evidence threshold is not met, the platform says *insufficient evidence* instead of producing a number.

**Compare against the alternative, not against zero.** For each use case, AI-assisted work is compared with the same work done without AI on total cost per completed task, time, quality, errors and rework, with 95 % intervals and per task type. The decision is one of five: continue, optimise, use only for selected task types, run a controlled experiment, or stop.

## 3. Technical decisions

| Decision | Why |
|---|---|
| A **pure-Python core** (`aivanta_core`) with no framework dependencies | Financial rules must be deterministic and auditable. The engine is unit-tested in milliseconds and reused by the API, exports, seed and tests. |
| `Decimal` money, rounding only at presentation | Totals reconcile to the cent; the test suite recomputes every dashboard metric from raw records. |
| **Evidence as data**: verification status + `evidence_key` on every claim | Makes "what counts" a rule, not a judgement buried in a spreadsheet, and makes double counting detectable. |
| Welch and proportion intervals, causal vs. correlational designs | Distinguishes "AI is faster" from "AI looked faster in a before/after comparison". |
| **Rule-based recommendations** returning their triggering metrics | Explainability first; a learned model can come later once outcomes accumulate. |
| Language-neutral identifiers, localised UI and exports | Spanish and English are full first-class experiences without coupling data to a language. |
| FastAPI + SQLAlchemy + PostgreSQL, multi-tenant with RBAC and audit | The shape of a real enterprise product: isolation, roles, assumptions under change control, frozen snapshots. |
| Next.js + d3-based SVG charts with table views | Accessible, colour-blind-safe charts with full control over provenance badges and drill-downs. |

## 4. What the demo organisation learns

**Spend is not where the money goes.** The organisation spent **€8,658** on models and APIs over 90 days — 2.96 billion tokens. That is only **6.5 %** of the **€133.6k** total AI-related cost. Implementation (38 %), subscriptions (21 %) and human review and rework (28 %) dominate. A token dashboard alone would have missed 93 % of the cost.

**Overall, AI did not pay for itself in this window — and the platform shows why.** Evidence-backed gross benefit is **€98.3k** (verified savings €45.5k, supported cost avoidance €48.4k, supported contribution €4.4k), giving **ROI −26.4 %** (benefit-to-cost ratio 0.74). Because most of the cost is one-off implementation, the monthly run-rate is positive and the **payback period is about 9.6 months**. Scenarios range from −43.9 % (conservative) to +50.9 % (optimistic, which includes estimates and is labelled as such).

**Naive accounting would have reported a success.** Counting estimated, unverified and duplicated claims would have turned −26 % into **+6.6 %**; adding the labour value of 3,066 hours "saved" as if it were cash would have produced **+128 %**. The difference between those numbers is the reason the product exists.

**Two use cases carry the portfolio:**

| Use case | Design | Result | Decision |
|---|---|---|---|
| Support ticket triage | randomised | ROI **+238 %**, €2.68 cheaper per ticket, quality unchanged | continue — expansion candidate |
| Code review assistant | control group | ROI **+71 %**, 18 min faster per review, €20.91 cheaper per review | continue — expansion candidate |
| Sales outreach drafting | control group | ROI **−92 %**; AI costs €12.51 *more* per email; review consumes the time saved | optimise (cheaper model saves ~€900/month; the €6k/month licence is the real issue) |
| Marketing content drafting | control group | 32 min faster per piece, but quality −10 points; long-form articles fail, social posts work | use AI only for social posts |
| Invoice matching | observational | 16 tasks, estimates only | run a controlled experiment before spending more |

**Alerts that matter.** The rule engine flags the sales budget overrun (117 % of the September budget), a one-day spend spike caused by a runaway retry loop (7.5 standard deviations above normal), sales spend up 141 % on the previous 30 days (partly the runaway loop) without better outcomes, and 29 % of spend that cannot be attributed to a use case.

## 5. Validation

* 106 backend tests cover pricing, cost allocation, benefit selection, every ROI formula, the evidence gate, scenarios, break-even and payback, the statistics (including interval coverage), each comparison decision, every recommendation rule, ingestion of each vendor sample, reproducibility of the synthetic data and reconciliation of every dashboard total with the raw records.
* The PostgreSQL schema was applied to PostgreSQL 16; an API test suite (auth, roles, isolation between organisations, idempotent ingestion, exports, snapshots, audit, ORM-vs-migration diff) is included for CI.
* Frontend tests check that English and Spanish have identical keys and placeholders, that the agreed Spanish terminology is used and that every code the backend emits is translated. All pages were rendered in a headless browser against real API payloads in both languages, on desktop and mobile.

## 6. What I would build next

1. Live connectors to provider usage APIs and a gateway/SDK that tags requests with use case and task ids at source.
2. Daily roll-up tables for production-scale volumes.
3. Experiment management: assignment, power calculation and sequential monitoring for the "run a controlled experiment" recommendation.
4. Ledger integration so finance can mark benefits verified from the accounting system.
5. Quality evaluation pipelines (LLM-as-judge with human calibration) feeding the quality scores.

## Skills demonstrated

AI systems (token economics, caching, model tiers, multi-provider normalisation) · data engineering (ingestion, idempotency, attribution, relational modelling, migrations) · financial reasoning (TCO, ROI, payback, break-even, scenarios, double counting) · statistics and experimental design · full-stack engineering (FastAPI, PostgreSQL, Next.js, TypeScript) · product design for executives · internationalisation · testing and verification.
