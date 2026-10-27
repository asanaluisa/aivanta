"""Reproducible synthetic demonstration dataset.

**Everything produced here is synthetic.** Model identifiers are deliberately
fictional (``gpt-demo-large``, ``claude-demo-compact`` …) and their prices are
illustrative, not vendor list prices. Labour rates, benefits and costs are
invented to exercise every branch of the engines:

=====================  ==================================================  ===========
use case               story                                               design
=====================  ==================================================  ===========
support_triage         low cost, high value; ledger-verified savings      randomized
code_review            moderate cost, positive verified ROI               control group
sales_outreach         high cost (licence + frontier model), low value    control group
marketing_content      faster, but quality drops on long-form content     control group
invoice_matching       too few tasks, estimates only                      observational
(unallocated)          shared API key with no attribution                 —
=====================  ==================================================  ===========

Also included: a mid-period price change, a runaway-loop spend anomaly, a
budget overrun, a duplicate benefit claim, and an adoption ramp.

The same ``seed`` always yields byte-identical data.
"""
from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from .domain import (
    Assumptions,
    BenefitClaim,
    Budget,
    CostItem,
    Dataset,
    Department,
    PricingRule,
    TaskArm,
    TaskRecord,
    UsageEvent,
    UseCase,
)
from .pricing import PricingSchedule

DEFAULT_SEED = 20260930
DEFAULT_END = date(2026, 9, 30)
DEFAULT_DAYS = 90
ORG_ID = "org_demo"
D = Decimal


def pricing_rules() -> list[PricingRule]:
    start = date(2026, 1, 1)
    return [
        PricingRule("openai", "gpt-demo-large", start, D("5.00"), D("15.00"), D("0.50"), "frontier"),
        # Mid-period price cut: events after 15 Aug use the new rate.
        PricingRule("openai", "gpt-demo-large", date(2026, 8, 15), D("4.00"), D("12.00"), D("0.40"), "frontier"),
        PricingRule("openai", "gpt-demo-mini", start, D("0.30"), D("1.20"), D("0.03"), "economy"),
        PricingRule("anthropic", "claude-demo-advanced", start, D("3.00"), D("15.00"), D("0.30"), "standard"),
        PricingRule("anthropic", "claude-demo-compact", start, D("0.80"), D("4.00"), D("0.08"), "economy"),
        PricingRule("google", "gemini-demo-pro", start, D("2.50"), D("10.00"), D("0.25"), "standard"),
        PricingRule("google", "gemini-demo-flash", start, D("0.30"), D("2.50"), D("0.03"), "economy"),
    ]


DEPARTMENTS = [
    # id, users, loaded hourly rate (EUR, assumption)
    ("engineering", 22, D("75")),
    ("customer_support", 18, D("38")),
    ("sales", 12, D("55")),
    ("marketing", 8, D("50")),
    ("finance_operations", 8, D("48")),
]


class _Arm:
    """Distribution parameters for one arm (and optionally one task type)."""

    def __init__(self, minutes, sd, success, quality, quality_sd, error, review, rework_p,
                 rework, csat=None):
        self.minutes, self.sd, self.success = minutes, sd, success
        self.quality, self.quality_sd, self.error = quality, quality_sd, error
        self.review, self.rework_p, self.rework, self.csat = review, rework_p, rework, csat


class _UseCaseSpec:
    def __init__(self, uc: UseCase, models, ai_per_day, non_ai_per_day, tokens, arms,
                 task_types=(("standard", 1.0),)):
        self.uc = uc
        self.models = models  # list of ((provider, model), weight)
        self.ai_per_day = ai_per_day
        self.non_ai_per_day = non_ai_per_day
        self.tokens = tokens  # (input_mean, cached_share, output_mean, requests_mean)
        self.arms = arms  # {(arm, task_type) | arm: _Arm}
        self.task_types = task_types

    def arm(self, arm: str, task_type: str) -> _Arm:
        return self.arms.get((arm, task_type)) or self.arms[arm]


def _specs(start: date, end: date) -> list[_UseCaseSpec]:
    return [
        _UseCaseSpec(
            UseCase("support_triage", "use_case.support_triage", "customer_support", "simple",
                    "randomized", start, end, "Helpdesk export + randomized routing log"),
            [(("anthropic", "claude-demo-compact"), 1.0)],
            ai_per_day=110, non_ai_per_day=28,
            tokens=(14000, 0.60, 450, 2.0),
            arms={
                "ai": _Arm(6.0, 2.0, 0.95, 0.90, 0.05, 0.03, 0.6, 0.05, 6, csat=4.4),
                "non_ai": _Arm(14.0, 4.0, 0.94, 0.89, 0.05, 0.04, 0.0, 0.05, 8, csat=4.2),
            }),
        _UseCaseSpec(
            UseCase("code_review", "use_case.code_review", "engineering", "complex",
                    "control_group", start, end, "Git provider PR analytics, two matched teams"),
            [(("openai", "gpt-demo-large"), 0.6), (("anthropic", "claude-demo-advanced"), 0.4)],
            ai_per_day=38, non_ai_per_day=12,
            tokens=(95000, 0.45, 3200, 4.0),
            arms={
                "ai": _Arm(34.0, 10.0, 0.93, 0.86, 0.06, 0.05, 4.0, 0.20, 12),
                "non_ai": _Arm(55.0, 15.0, 0.92, 0.85, 0.06, 0.06, 3.0, 0.18, 12),
            }),
        _UseCaseSpec(
            UseCase("sales_outreach", "use_case.sales_outreach", "sales", "simple",
                    "control_group", start, end, "CRM activity log, holdout reps"),
            [(("openai", "gpt-demo-large"), 1.0)],
            ai_per_day=55, non_ai_per_day=18,
            tokens=(42000, 0.05, 1100, 3.0),
            arms={
                "ai": _Arm(9.0, 3.0, 0.90, 0.80, 0.07, 0.04, 2.5, 0.10, 4),
                "non_ai": _Arm(12.0, 3.5, 0.90, 0.81, 0.07, 0.04, 0.0, 0.08, 4),
            }),
        _UseCaseSpec(
            UseCase("marketing_content", "use_case.marketing_content", "marketing", "standard",
                    "control_group", start, end, "CMS workflow timestamps + editor scoring"),
            [(("google", "gemini-demo-pro"), 0.7), (("anthropic", "claude-demo-advanced"), 0.3)],
            ai_per_day=24, non_ai_per_day=10,
            tokens=(38000, 0.15, 3800, 2.5),
            task_types=(("social_post", 0.55), ("long_form_article", 0.45)),
            arms={
                ("ai", "social_post"): _Arm(14.0, 5.0, 0.95, 0.85, 0.05, 0.03, 3.0, 0.10, 5),
                ("non_ai", "social_post"): _Arm(30.0, 8.0, 0.95, 0.84, 0.05, 0.03, 2.0, 0.10, 5),
                ("ai", "long_form_article"): _Arm(70.0, 20.0, 0.82, 0.60, 0.08, 0.12, 22.0, 0.65, 45),
                ("non_ai", "long_form_article"): _Arm(160.0, 35.0, 0.93, 0.84, 0.05, 0.04, 12.0, 0.15, 25),
                "ai": _Arm(14.0, 5.0, 0.95, 0.85, 0.05, 0.03, 3.0, 0.10, 5),
                "non_ai": _Arm(30.0, 8.0, 0.95, 0.84, 0.05, 0.03, 2.0, 0.10, 5),
            }),
        _UseCaseSpec(
            UseCase("invoice_matching", "use_case.invoice_matching", "finance_operations", "standard",
                    "observational", start, end, "Pilot spreadsheet, self-reported",
                    baseline_minutes=20.0),
            [(("anthropic", "claude-demo-advanced"), 1.0)],
            ai_per_day=0.25, non_ai_per_day=0,
            tokens=(11000, 0.0, 700, 2.0),
            arms={"ai": _Arm(12.0, 4.0, 0.88, 0.85, 0.06, 0.06, 2.0, 0.10, 6),
                  "non_ai": _Arm(20.0, 5.0, 0.9, 0.85, 0.05, 0.05, 0.0, 0.1, 5)}),
    ]


def _lognormal(rng: random.Random, mean: float, cv: float = 0.35) -> float:
    sigma = math.sqrt(math.log(1 + cv * cv))
    mu = math.log(mean) - sigma * sigma / 2
    return rng.lognormvariate(mu, sigma)


def _poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    if lam > 30:
        return max(0, int(round(rng.gauss(lam, math.sqrt(lam)))))
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def _weighted(rng: random.Random, options):
    r, acc = rng.random(), 0.0
    for value, w in options:
        acc += w
        if r <= acc:
            return value
    return options[-1][0]


def generate(seed: int = DEFAULT_SEED, end: date = DEFAULT_END, days: int = DEFAULT_DAYS) -> Dataset:
    if days < 1:
        raise ValueError("days must be >= 1")
    rng = random.Random(seed)
    start = end - timedelta(days=days - 1)
    rules = pricing_rules()
    schedule = PricingSchedule(rules)

    departments = [Department(d, f"department.{d}", rate) for d, _, rate in DEPARTMENTS]
    users: dict[str, str] = {}
    activation: dict[str, int] = {}
    for dep, n, _ in DEPARTMENTS:
        for i in range(1, n + 1):
            uid = f"u_{dep}_{i:02d}"
            users[uid] = dep
            # Adoption ramp: most users activate in the first 60 days, a few never do.
            activation[uid] = 10_000 if rng.random() < 0.10 else int(rng.random() ** 1.6 * 60)

    specs = _specs(start, end)
    events: list[UsageEvent] = []
    tasks: list[TaskRecord] = []
    ev_seq = task_seq = 0

    for offset in range(days):
        day = start + timedelta(days=offset)
        weekday = day.weekday() < 5
        load = (1.0 if weekday else 0.2) * (0.55 + 0.45 * min(1.0, offset / 45))
        for spec in specs:
            dep = spec.uc.department_id
            dep_users = [u for u, d in users.items() if d == dep]
            active = [u for u in dep_users if activation[u] <= offset] or dep_users[:1]
            growth = 1.0
            if spec.uc.use_case_id == "sales_outreach" and offset >= days - 30:
                growth = 1.45  # usage grows in the last 30 days without better outcomes
            for arm, per_day in ((TaskArm.AI.value, spec.ai_per_day * load * growth),
                                 (TaskArm.NON_AI.value, spec.non_ai_per_day * (1.0 if weekday else 0.2))):
                for _ in range(_poisson(rng, per_day)):
                    task_seq += 1
                    task_type = _weighted(rng, spec.task_types)
                    p = spec.arm(arm, task_type)
                    user = rng.choice(active if arm == "ai" else dep_users)
                    success = rng.random() < p.success
                    rework = _lognormal(rng, p.rework) if rng.random() < p.rework_p else 0.0
                    quality = min(1.0, max(0.0, rng.gauss(p.quality, p.quality_sd)))
                    task_id = f"t{task_seq:06d}"
                    tasks.append(TaskRecord(
                        task_id=task_id,
                        use_case_id=spec.uc.use_case_id,
                        arm=arm,
                        completed_on=day,
                        duration_minutes=round(max(1.0, rng.gauss(p.minutes, p.sd)), 2),
                        success=success,
                        quality_score=round(quality, 4),
                        had_error=rng.random() < p.error,
                        rework_minutes=round(rework, 2),
                        review_minutes=round(_lognormal(rng, p.review), 2) if p.review else 0.0,
                        customer_satisfaction=(round(min(5.0, max(1.0, rng.gauss(p.csat, 0.6))), 1)
                                               if p.csat else None),
                        task_type=task_type,
                        user_id=user,
                    ))
                    if arm != TaskArm.AI.value:
                        continue
                    ev_seq += 1
                    events.append(_event(rng, ev_seq, day, spec, user, dep, task_id, task_type))

        # Engineering ad-hoc coding assistant: department known, use case unknown.
        eng = [u for u, d in users.items() if d == "engineering" and activation[u] <= offset]
        for _ in range(_poisson(rng, 70 * load)):
            ev_seq += 1
            events.append(_raw_event(rng, ev_seq, day, _weighted(rng, [
                (("anthropic", "claude-demo-advanced"), 0.6), (("openai", "gpt-demo-large"), 0.4)]),
                inp=_lognormal(rng, 60000), cached=0.5, out=_lognormal(rng, 2500),
                requests=1 + _poisson(rng, 2.0), user=rng.choice(eng) if eng else None,
                dep="engineering", uc=None))

        # Shared API key with no attribution (unallocated).
        for _ in range(_poisson(rng, 40 * load)):
            ev_seq += 1
            events.append(_raw_event(rng, ev_seq, day, ("openai", "gpt-demo-large"),
                                     inp=_lognormal(rng, 30000), cached=0.2, out=_lognormal(rng, 1200),
                                     requests=1 + _poisson(rng, 0.6), user=None, dep=None, uc=None))

    # Runaway retry loop in the sales integration: one day, many failed requests.
    anomaly_day = end - timedelta(days=18)
    for _ in range(320):
        ev_seq += 1
        events.append(_raw_event(rng, ev_seq, anomaly_day, ("openai", "gpt-demo-large"),
                                 inp=_lognormal(rng, 120000, 0.1), cached=0.0,
                                 out=_lognormal(rng, 1200, 0.1), requests=4,
                                 user=None, dep="sales", uc="sales_outreach",
                                 status="error", retries=3))

    schedule.price_events(events)
    ds = Dataset(
        organization_id=ORG_ID,
        currency="EUR",
        period_start=start,
        period_end=end,
        departments=departments,
        use_cases=[s.uc for s in specs],
        pricing=rules,
        usage_events=events,
        tasks=tasks,
        cost_items=_cost_items(start, end),
        benefits=_benefits(start, end),
        budgets=_budgets(start, end),
        users=users,
        assumptions=Assumptions(),
        is_synthetic=True,
    )
    return ds


def _event(rng, seq, day, spec: _UseCaseSpec, user, dep, task_id, task_type) -> UsageEvent:
    inp_mean, cached_share, out_mean, req_mean = spec.tokens
    if task_type == "long_form_article":
        inp_mean, out_mean = inp_mean * 1.6, out_mean * 2.4
    model = _weighted(rng, spec.models)
    return _raw_event(rng, seq, day, model, inp=_lognormal(rng, inp_mean), cached=cached_share,
                      out=_lognormal(rng, out_mean), requests=max(1, _poisson(rng, req_mean)),
                      user=user, dep=dep, uc=spec.uc.use_case_id, task_id=task_id)


def _raw_event(rng, seq, day, model, *, inp, cached, out, requests, user, dep, uc,
               task_id: Optional[str] = None, status="success", retries=None) -> UsageEvent:
    inp_i = max(50, int(inp)) * requests
    if retries is None:
        retries = 1 if rng.random() < 0.03 else 0
        if retries:
            requests += 1
    is_error = status == "error" or rng.random() < 0.015
    when = datetime(day.year, day.month, day.day, 8 + int(rng.random() * 10), int(rng.random() * 60))
    return UsageEvent(
        event_id=f"ev{seq:07d}",
        occurred_at=when,
        provider=model[0],
        model=model[1],
        input_tokens=inp_i,
        output_tokens=max(10, int(out)) * requests,
        cached_input_tokens=int(inp_i * cached),
        request_count=requests,
        retries=retries,
        status="error" if is_error else "success",
        latency_ms=int(_lognormal(rng, 2400 if "large" in model[1] or "advanced" in model[1] else 900)),
        user_id=user,
        department_id=dep,
        use_case_id=uc,
        task_id=task_id,
        source="synthetic",
    )


def _month_starts(start: date, end: date) -> list[date]:
    m, out = start.replace(day=1), []
    while m <= end:
        out.append(m)
        m = (m + timedelta(days=32)).replace(day=1)
    return out


def _month_end(m: date) -> date:
    return (m + timedelta(days=32)).replace(day=1) - timedelta(days=1)


def _cost_items(start: date, end: date) -> list[CostItem]:
    items: list[CostItem] = []
    n = 0

    def add(cat, amount, ps, pe, key, uc=None, dep=None, one_off=False):
        nonlocal n
        n += 1
        items.append(CostItem(f"cost_{n:03d}", cat, D(amount), ps, pe, key, uc, dep, one_off))

    for m in _month_starts(start, end):
        me = _month_end(m)
        add("infrastructure", "1800", m, me, "cost.vector_db_observability")
        add("subscription", "1200", m, me, "cost.ai_governance_platform")
        add("subscription", "770", m, me, "cost.coding_assistant_seats", dep="engineering")
        add("maintenance", "900", m, me, "cost.support_bot_maintenance", uc="support_triage")
        add("subscription", "6000", m, me, "cost.sales_ai_platform_licence", uc="sales_outreach")
        add("subscription", "1500", m, me, "cost.content_tool_licence", uc="marketing_content")
        add("infrastructure", "400", m, me, "cost.review_bot_runners", uc="code_review")
    add("implementation", "12000", start + timedelta(days=2), start + timedelta(days=2),
        "cost.implementation", uc="support_triage", one_off=True)
    add("implementation", "8000", start + timedelta(days=7), start + timedelta(days=7),
        "cost.implementation", uc="code_review", one_off=True)
    add("implementation", "25000", start + timedelta(days=5), start + timedelta(days=5),
        "cost.implementation", uc="sales_outreach", one_off=True)
    add("implementation", "6000", start + timedelta(days=20), start + timedelta(days=20),
        "cost.implementation", uc="invoice_matching", one_off=True)
    return items


def _benefits(start: date, end: date) -> list[BenefitClaim]:
    claims: list[BenefitClaim] = []
    n = 0

    def add(uc, cat, amount, status, key, ps, pe, conf, src):
        nonlocal n
        n += 1
        claims.append(BenefitClaim(f"ben_{n:03d}", uc, cat, D(amount), status, key, ps, pe, conf, src))

    for m in _month_starts(start, end):
        ps, pe = max(m, start), min(_month_end(m), end)
        share = D((pe - ps).days + 1) / D((_month_end(m) - m).days + 1)
        tag = m.strftime("%Y-%m")
        amt = lambda x, share=share: str((D(x) * share).quantize(D("0.01")))  # noqa: E731
        # Support: BPO overflow invoices fell (ledger) and outsourcing avoided (RCT).
        add("support_triage", "financial_savings", amt("6000"), "verified",
            f"support_triage:bpo_invoices:{tag}", ps, pe, 0.95, "AP ledger, vendor BPO-01")
        add("support_triage", "cost_avoidance", amt("14000"), "supported",
            f"support_triage:overflow_capacity:{tag}", ps, pe, 0.75, "RCT deflection × contract rate")
        # Duplicate of the same effect booked by another team — must be de-duplicated.
        add("support_triage", "financial_savings", amt("15000"), "estimated",
            f"support_triage:overflow_capacity:{tag}", ps, pe, 0.4, "Team lead estimate")
        # Engineering: fewer contractor review hours, verified on invoices.
        add("code_review", "financial_savings", amt("9500"), "verified",
            f"code_review:contractor_hours:{tag}", ps, pe, 0.9, "Contractor invoices")
        # Sales: small holdout-measured margin uplift + an unverified pipeline claim.
        add("sales_outreach", "incremental_contribution", amt("1500"), "supported",
            f"sales_outreach:holdout_margin:{tag}", ps, pe, 0.6, "Holdout reps, gross margin")
        add("sales_outreach", "incremental_contribution", amt("12000"), "unverified",
            f"sales_outreach:pipeline_influence:{tag}", ps, pe, 0.2, "Vendor dashboard 'influenced pipeline'")
        # Marketing: freelance copywriting spend avoided (supported by PO history).
        add("marketing_content", "cost_avoidance", amt("2500"), "supported",
            f"marketing_content:freelance:{tag}", ps, pe, 0.6, "Purchase orders vs. plan")
        # Finance: only an estimate exists.
        add("invoice_matching", "financial_savings", amt("3000"), "estimated",
            f"invoice_matching:fte_time:{tag}", ps, pe, 0.3, "Pilot owner estimate")
    return claims


def _budgets(start: date, end: date) -> list[Budget]:
    """Monthly model & API usage budgets (EUR)."""
    amounts = {"engineering": "2000", "customer_support": "150", "sales": "1400",
               "marketing": "300", "finance_operations": "50", None: "5000"}
    out = []
    for m in _month_starts(start, end):
        for dep, amount in amounts.items():
            out.append(Budget(f"bud_{m:%Y%m}_{dep or 'org'}", dep, m, D(amount)))
    return out
