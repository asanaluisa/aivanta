# Financial definitions

Every figure in Aivanta is produced by `backend/aivanta_core`. This document is the specification those modules implement; each rule below is covered by a unit test in `backend/tests/unit/test_roi.py`, `test_pricing.py` or `test_stats_and_comparison.py`.

Money is handled as `Decimal` end to end and rounded only for display. Durations are minutes.

## 1. Cost of a usage event

```
uncached_input = input_tokens − cached_input_tokens
cost = ( uncached_input      × input_price_per_Mtok
       + cached_input_tokens × cached_input_price_per_Mtok   (falls back to the input price)
       + output_tokens       × output_price_per_Mtok ) / 1,000,000
```

* `input_tokens` is the full prompt, of which `cached_input_tokens` were served from the provider cache. Each adapter normalises vendor fields to this convention.
* Prices are versioned by `effective_from`; an event uses the price in force on the day it occurred (the demo includes a mid-period price cut to exercise this).
* Unknown model, negative tokens, cached > input, or `request_count < 1` are rejected, never guessed.

## 2. Total AI-related cost

| Category | Source | Notes |
|---|---|---|
| Model & API usage | sum of priced usage events | derived — cannot be entered manually |
| Subscriptions | cost items | prorated by calendar days |
| Infrastructure & hosting | cost items | prorated |
| Implementation | cost items (one-off) | counted in full if incurred inside the period |
| Maintenance | cost items | prorated |
| Human review | task records | **incremental** over the non-AI baseline |
| Rework | task records | **incremental** over the non-AI baseline |
| Other operating | cost items | prorated |

**Human review and rework.** They are valued at the department's fully loaded hourly rate. When a use case has a non-AI arm, only review and rework *above* the non-AI mean per task is charged — review that would have happened anyway is not an AI cost. Without a baseline, all review and rework on AI tasks is charged (the conservative choice). The increment is floored at zero per use case, never negative.

**Allocation.** Cost items are allocated to a use case, a department or the organisation. Organisation-wide items appear in organisation ROI but are not spread across departments; usage with no department or use case stays *unallocated* and is included in organisation totals.

## 3. Benefits and evidence

Each benefit claim has a category and a verification status:

| Status | Meaning | Counts towards gross benefit? |
|---|---|---|
| `verified` | reconciled to the general ledger or supplier invoices | yes |
| `supported` | backed by a controlled measurement (RCT, control group) | yes — except for *financial savings*, which must be verified |
| `estimated` | modelled from assumptions | no — shown as an estimate |
| `unverified` | claimed without evidence | no |

```
Gross benefit = verified financial savings
              + supported (or verified) incremental contribution
              + supported (or verified) cost avoidance
```

**No double counting.** Claims carry an `evidence_key` naming the underlying outcome (e.g. "overflow support capacity, September"). Claims with the same key describe the same economic effect; only the strongest one counts (verified > supported > estimated > unverified, then the smaller amount). The others are listed as excluded with the reason `duplicate_evidence`. The demo dataset contains such a duplicate on purpose.

Claims that only partly overlap the analysis period are prorated by days.

## 4. ROI and related measures

```
Net benefit              = gross benefit − total AI-related cost
ROI %                    = (gross benefit − total AI-related cost) / total AI-related cost × 100
Benefit-to-cost ratio    = gross benefit / total AI-related cost
Cost per successful task = total AI-related cost / AI-assisted tasks completed successfully
```

**Break-even volume** — successful tasks for gross benefit to cover all costs, assuming benefit and *variable* cost (model usage, review, rework) scale per task and *fixed* cost (subscriptions, infrastructure, implementation, maintenance) does not:

```
break_even = fixed cost / (gross benefit per task − variable cost per task)     (none if the margin ≤ 0)
```

**Payback period** — months to recover the one-off investment from the observed monthly run-rate:

```
monthly net run-rate = (gross benefit − recurring cost) / months in period
payback (months)     = implementation cost / monthly net run-rate   (none if run-rate ≤ 0; 0 if no one-off cost)
```

This is why the demo organisation can show a negative 90-day ROI and still a ~10-month payback: the period absorbs €51k of one-off implementation.

## 5. Evidence threshold

ROI, net benefit, benefit-to-cost ratio, break-even, payback and scenarios are **withheld** (status `insufficient_evidence`, reasons listed) when any of these hold:

* no benefit is verified or supported (`no_supported_benefits`);
* for a single use case, fewer than `min_sample_size` AI-assisted tasks (default 30; `sample_too_small`) or none at all (`no_outcome_data`);
* the period is shorter than `min_measurement_days` (default 14; `period_too_short`).

Costs and hours are still reported. For an organisation or department, use cases that lack evidence add their costs but no benefits, and the result is flagged `partial_evidence`.

When the scope is filtered by provider or model, ROI is not calculated at all (`not_applicable_for_filter`) because business benefits cannot be split by model.

## 6. Time saved

```
gross hours = AI tasks × (baseline minutes − AI minutes) / 60                 (duration only)
net hours   = AI tasks × (baseline total − AI total) / 60                     (total = duration + review + rework)
```

The baseline is the concurrent non-AI arm when one exists, otherwise a documented baseline. Without either, hours are not reported. Hours are **never** added to gross benefit. Their labour value (`gross hours × loaded rate`) is shown only as an *estimate* and only enters the optimistic scenario.

## 7. Scenarios

| Scenario | Gross benefit | Cost |
|---|---|---|
| Conservative | verified + supported × (1 − 30 %) | total × (1 + 10 %) |
| Expected | gross benefit | total |
| Optimistic | gross benefit + 50 % × (estimated claims + labour value of hours) — **flagged as including estimates** | total |

All percentages are editable assumptions (Finance and Administrator roles; every change is audited).

## 8. AI versus non-AI comparison

Both arms are compared on **total cost of ownership per completed task**: labour (duration + review + rework at the loaded rate) for both arms, plus every non-labour AI cost for the AI arm. Differences for time per task and quality use Welch's two-sample interval; success and error rates use a Wald interval for proportions (95 %). Each task type is also compared separately.

Decision rules (`comparison.decide`), in order:

1. Fewer than `min_sample_size` tasks in either arm → **run a controlled experiment**.
2. Quality significantly lower (beyond `quality_tolerance`, default 3 points):
   some task types favourable → **use AI only for those task types**; not cheaper or ROI negative → **stop**; otherwise → **optimise**.
3. Design is not causal and nothing is ledger-verified → **run a controlled experiment** (association is not causation).
4. ROI positive and cheaper per task → **continue**.
5. Cheaper per task but benefits not yet evidenced → **run a controlled experiment**.
6. Neither cheaper nor significantly faster → **stop**.
7. Otherwise → **optimise** the model or workflow.

## 9. Budgets and alerts

```
utilisation = month-to-date model & API spend / monthly budget
forecast    = month-to-date spend + (average daily spend, trailing 14 days) × remaining days
```

Status: `exceeded` (≥ 100 %), `forecast_exceeds` (forecast ≥ 100 %), `warning` (≥ 80 %), `ok`.

Spend anomalies are days whose spend is more than `anomaly_sigma` (default 3) standard deviations above the period mean.
