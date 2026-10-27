"""Analytics service: filters, aggregations, scoped ROI and budgets.

Every figure the dashboard shows is produced here from a :class:`Dataset`, so
the API, the exports and the reconciliation tests all read the same numbers.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, Optional

from . import stats
from .comparison import ComparisonResult, compare
from .domain import (
    ZERO,
    BenefitClaim,
    CostItem,
    Dataset,
    RequestStatus,
    TaskArm,
    TaskRecord,
    UsageEvent,
)
from .roi import (
    CostBreakdown,
    HoursSaved,
    ROIResult,
    ROIStatus,
    build_cost_breakdown,
    compute_hours_saved,
    compute_roi,
    overlap_days,
    select_benefits,
    time_value,
)

UNALLOCATED = "unallocated"
DIMENSIONS = ("department", "provider", "model", "use_case")


@dataclass(frozen=True)
class Filters:
    start: Optional[date] = None
    end: Optional[date] = None
    department_ids: frozenset[str] = frozenset()
    providers: frozenset[str] = frozenset()
    models: frozenset[str] = frozenset()
    use_case_ids: frozenset[str] = frozenset()

    def period(self, ds: Dataset) -> tuple[date, date]:
        start = self.start or ds.period_start
        end = self.end or ds.period_end
        if end < start:
            raise ValueError("end date precedes start date")
        return start, end

    @property
    def model_level(self) -> bool:
        """Provider/model filters only make sense for usage, not for benefits."""
        return bool(self.providers or self.models)


# ------------------------------------------------------------------ selection


def _dept_key(dep: Optional[str]) -> str:
    return dep or UNALLOCATED


def filter_events(ds: Dataset, f: Filters) -> list[UsageEvent]:
    start, end = f.period(ds)
    out = []
    for e in ds.usage_events:
        d = e.occurred_at.date()
        if d < start or d > end:
            continue
        if f.department_ids and _dept_key(e.department_id) not in f.department_ids:
            continue
        if f.use_case_ids and (e.use_case_id or UNALLOCATED) not in f.use_case_ids:
            continue
        if f.providers and e.provider not in f.providers:
            continue
        if f.models and e.model not in f.models:
            continue
        out.append(e)
    return out


def scoped_use_case_ids(ds: Dataset, f: Filters) -> list[str]:
    ids = []
    for uc in ds.use_cases:
        if f.use_case_ids and uc.use_case_id not in f.use_case_ids:
            continue
        if f.department_ids and _dept_key(uc.department_id) not in f.department_ids:
            continue
        ids.append(uc.use_case_id)
    return ids


def filter_tasks(ds: Dataset, f: Filters, use_case_ids: Iterable[str]) -> list[TaskRecord]:
    start, end = f.period(ds)
    wanted = set(use_case_ids)
    return [t for t in ds.tasks if t.use_case_id in wanted and start <= t.completed_on <= end]


def _cost_items_in_scope(ds: Dataset, f: Filters, use_case_ids: set[str], org_scope: bool
                         ) -> list[CostItem]:
    out = []
    for c in ds.cost_items:
        if c.use_case_id is not None:
            if c.use_case_id in use_case_ids:
                out.append(c)
        elif c.department_id is not None:
            if (not f.department_ids or c.department_id in f.department_ids) and not f.use_case_ids:
                out.append(c)
        elif org_scope:
            out.append(c)  # shared organization-wide cost
    return out


def _rate_for_use_case(ds: Dataset, use_case_id: Optional[str]) -> Decimal:
    uc = ds.use_case(use_case_id) if use_case_id else None
    dep = ds.department(uc.department_id) if uc and uc.department_id else None
    if dep:
        return dep.loaded_hourly_rate
    rates = sorted(d.loaded_hourly_rate for d in ds.departments)
    return rates[len(rates) // 2] if rates else ZERO


# ------------------------------------------------------------------ KPIs


@dataclass
class ScopeROI:
    roi: ROIResult
    use_case_ids: list[str]
    insufficient_use_cases: list[str]
    tasks_ai: int
    tasks_ai_successful: int
    quality_ai: Optional[float]
    success_rate_ai: Optional[float]


def scope_roi(ds: Dataset, f: Filters, *, org_scope: bool) -> ScopeROI:
    """ROI for the use cases selected by the filters (provider/model filters ignored).

    ``org_scope`` includes organization-wide shared costs and unallocated usage,
    which is the honest denominator for the whole organization.
    """
    start, end = f.period(ds)
    uc_ids = scoped_use_case_ids(ds, f)
    uc_set = set(uc_ids)
    base = Filters(start, end, f.department_ids, frozenset(), frozenset(), f.use_case_ids)
    events = [
        e for e in filter_events(ds, base)
        if org_scope or (e.use_case_id in uc_set) or (
            e.use_case_id is None and f.department_ids and e.department_id in f.department_ids
        )
    ]
    tasks = filter_tasks(ds, base, uc_ids)
    ai_tasks = [t for t in tasks if t.arm == TaskArm.AI.value]
    costs = build_cost_breakdown(
        events=events,
        cost_items=_cost_items_in_scope(ds, base, uc_set, org_scope),
        ai_tasks=ai_tasks,
        hourly_rate_for=lambda t: _rate_for_use_case(ds, t.use_case_id),
        period_start=start,
        period_end=end,
        baseline_review_rework=_baselines(tasks),
    )
    claims = [b for b in ds.benefits if b.use_case_id in uc_set]
    benefits = select_benefits(claims, start, end)

    hours_parts: list[HoursSaved] = []
    est_value = ZERO
    insufficient: list[str] = []
    for uc_id in uc_ids:
        uc = ds.use_case(uc_id)
        uc_tasks = [t for t in tasks if t.use_case_id == uc_id]
        h = compute_hours_saved(
            [t for t in uc_tasks if t.arm == TaskArm.AI.value],
            [t for t in uc_tasks if t.arm == TaskArm.NON_AI.value],
            uc.baseline_minutes if uc else None,
        )
        hours_parts.append(h)
        est_value += time_value(h, _rate_for_use_case(ds, uc_id)) or ZERO
        uc_sel = select_benefits([b for b in claims if b.use_case_id == uc_id], start, end)
        n_ai = sum(1 for t in uc_tasks if t.arm == TaskArm.AI.value)
        if not uc_sel.counted or n_ai < ds.assumptions.min_sample_size:
            insufficient.append(uc_id)
    hours = combine_hours(hours_parts)
    successes = sum(1 for t in ai_tasks if t.success)
    single = len(uc_ids) == 1 and not org_scope
    roi = compute_roi(
        costs=costs,
        benefits=benefits,
        hours=hours,
        successful_tasks=successes,
        period_start=start,
        period_end=end,
        assumptions=ds.assumptions,
        estimated_time_value=est_value if hours.gross_hours is not None else None,
        outcome_sample_size=len(ai_tasks) if single else None,
        partial_evidence=bool(insufficient) and not single,
    )
    q = [t.quality_score for t in ai_tasks if t.quality_score is not None]
    return ScopeROI(
        roi=roi,
        use_case_ids=uc_ids,
        insufficient_use_cases=insufficient,
        tasks_ai=len(ai_tasks),
        tasks_ai_successful=successes,
        quality_ai=stats.mean(q),
        success_rate_ai=successes / len(ai_tasks) if ai_tasks else None,
    )


def _baselines(tasks: list[TaskRecord]):
    """Mean review and rework minutes of the non-AI arm, per use case."""
    sums: dict[str, list[float]] = {}
    for t in tasks:
        if t.arm == TaskArm.NON_AI.value:
            acc = sums.setdefault(t.use_case_id, [0.0, 0.0, 0])
            acc[0] += t.review_minutes
            acc[1] += t.rework_minutes
            acc[2] += 1
    means = {k: (v[0] / v[2], v[1] / v[2]) for k, v in sums.items()}
    return means.get


def combine_hours(parts: list[HoursSaved]) -> HoursSaved:
    if len(parts) == 1:
        return parts[0]
    with_base = [p for p in parts if p.gross_hours is not None]
    n = sum(p.ai_tasks for p in parts)
    if not with_base:
        return HoursSaved(n, None, None, None, None, None)
    return HoursSaved(
        ai_tasks=n,
        baseline_minutes_per_task=None,
        ai_minutes_per_task=None,
        gross_hours=sum(p.gross_hours for p in with_base),  # type: ignore[misc]
        net_hours=sum(p.net_hours for p in with_base),  # type: ignore[misc]
        baseline_source="mixed",
    )


@dataclass
class UsageTotals:
    spend: Decimal = ZERO
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    requests: int = 0
    events: int = 0
    errors: int = 0
    retries: int = 0
    latency_sum: int = 0
    latency_n: int = 0
    users: set[str] = field(default_factory=set)
    departments: set[str] = field(default_factory=set)

    def add(self, e: UsageEvent) -> None:
        self.spend += e.cost or ZERO
        self.input_tokens += e.input_tokens
        self.output_tokens += e.output_tokens
        self.cached_input_tokens += e.cached_input_tokens
        self.requests += e.request_count
        self.events += 1
        self.retries += e.retries
        if e.status == RequestStatus.ERROR.value:
            self.errors += 1
        if e.latency_ms is not None:
            self.latency_sum += e.latency_ms
            self.latency_n += 1
        if e.user_id:
            self.users.add(e.user_id)
        if e.department_id:
            self.departments.add(e.department_id)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def error_rate(self) -> Optional[float]:
        return self.errors / self.events if self.events else None

    @property
    def avg_latency_ms(self) -> Optional[float]:
        return self.latency_sum / self.latency_n if self.latency_n else None


def usage_totals(events: Iterable[UsageEvent]) -> UsageTotals:
    t = UsageTotals()
    for e in events:
        t.add(e)
    return t


def overview(ds: Dataset, f: Filters) -> dict:
    events = filter_events(ds, f)
    u = usage_totals(events)
    scope = scope_roi(ds, f, org_scope=not (f.department_ids or f.use_case_ids))
    r = scope.roi
    roi_applicable = not f.model_level
    est_total_value = None
    if r.estimated_time_value is not None or r.benefits.estimated:
        est_total_value = r.gross_benefit + r.benefits.estimated + (r.estimated_time_value or ZERO)
    return {
        "period": f.period(ds),
        "usage": u,
        "scope": scope,
        "roi_applicable": roi_applicable,
        "estimated_total_value": est_total_value,
    }


# ------------------------------------------------------------------ breakdowns


def _dimension_key(e: UsageEvent, dimension: str) -> str:
    if dimension == "department":
        return _dept_key(e.department_id)
    if dimension == "provider":
        return e.provider
    if dimension == "model":
        return f"{e.provider}/{e.model}"
    if dimension == "use_case":
        return e.use_case_id or UNALLOCATED
    raise ValueError(f"Unknown dimension '{dimension}'")


def breakdown(ds: Dataset, f: Filters, dimension: str) -> list[dict]:
    if dimension not in DIMENSIONS:
        raise ValueError(f"Unknown dimension '{dimension}'")
    groups: dict[str, UsageTotals] = defaultdict(UsageTotals)
    events = filter_events(ds, f)
    for e in events:
        groups[_dimension_key(e, dimension)].add(e)
    total = sum((g.spend for g in groups.values()), ZERO)
    rows = []
    for key, g in groups.items():
        rows.append({
            "key": key,
            "spend": g.spend,
            "share": (g.spend / total) if total else ZERO,
            "input_tokens": g.input_tokens,
            "output_tokens": g.output_tokens,
            "cached_input_tokens": g.cached_input_tokens,
            "requests": g.requests,
            "error_rate": g.error_rate,
            "avg_latency_ms": g.avg_latency_ms,
            "retries": g.retries,
            "active_users": len(g.users),
            "cost_per_request": g.spend / g.requests if g.requests else None,
        })
    rows.sort(key=lambda r: (-r["spend"], r["key"]))
    return rows


def daily_trend(ds: Dataset, f: Filters) -> list[dict]:
    start, end = f.period(ds)
    days: dict[date, UsageTotals] = {start + timedelta(d): UsageTotals()
                                     for d in range((end - start).days + 1)}
    for e in filter_events(ds, f):
        days[e.occurred_at.date()].add(e)
    return [
        {"date": d, "spend": t.spend, "requests": t.requests, "tokens": t.total_tokens,
         "active_users": len(t.users), "errors": t.errors}
        for d, t in sorted(days.items())
    ]


def adoption(ds: Dataset, f: Filters) -> list[dict]:
    """Weekly active users as a share of licensed users, per ISO week."""
    eligible = {u for u, dep in ds.users.items()
                if not f.department_ids or _dept_key(dep) in f.department_ids}
    weeks: dict[date, set[str]] = defaultdict(set)
    for e in filter_events(ds, f):
        if e.user_id and e.user_id in eligible:
            d = e.occurred_at.date()
            weeks[d - timedelta(days=d.weekday())].add(e.user_id)
    total = len(eligible)
    return [
        {"week_start": w, "active_users": len(us), "eligible_users": total,
         "adoption_rate": len(us) / total if total else None}
        for w, us in sorted(weeks.items())
    ]


def anomalies(ds: Dataset, f: Filters) -> list[dict]:
    trend = daily_trend(ds, f)
    values = [float(r["spend"]) for r in trend]
    z = stats.zscores(values)
    m = stats.mean(values) or 0.0
    return [
        {"date": r["date"], "spend": r["spend"], "zscore": zz, "expected": m}
        for r, zz in zip(trend, z, strict=True) if zz >= ds.assumptions.anomaly_sigma
    ]


# ------------------------------------------------------------------ departments & use cases


def department_summaries(ds: Dataset, f: Filters) -> list[dict]:
    rows = []
    for dep in ds.departments:
        if f.department_ids and dep.department_id not in f.department_ids:
            continue
        df = Filters(f.start, f.end, frozenset({dep.department_id}), f.providers, f.models,
                     f.use_case_ids)
        u = usage_totals(filter_events(ds, df))
        s = scope_roi(ds, df, org_scope=False)
        r = s.roi
        rows.append({
            "department_id": dep.department_id,
            "usage": u,
            "total_cost": r.costs.total,
            "active_users": len(u.users),
            "tasks_completed": s.tasks_ai_successful,
            "hours_saved": r.hours.gross_hours,
            "net_hours_saved": r.hours.net_hours,
            "quality": s.quality_ai,
            "success_rate": s.success_rate_ai,
            "gross_benefit": r.gross_benefit,
            "estimated_time_value": r.estimated_time_value,
            "roi": r,
            "insufficient_use_cases": s.insufficient_use_cases,
        })
    # Explicitly unallocated usage
    if not f.department_ids or UNALLOCATED in f.department_ids:
        uf = Filters(f.start, f.end, frozenset({UNALLOCATED}), f.providers, f.models)
        u = usage_totals(filter_events(ds, uf))
        if u.events:
            rows.append({"department_id": UNALLOCATED, "usage": u, "total_cost": u.spend,
                         "active_users": len(u.users), "tasks_completed": None,
                         "hours_saved": None, "net_hours_saved": None, "quality": None,
                         "success_rate": None, "gross_benefit": ZERO,
                         "estimated_time_value": None, "roi": None,
                         "insufficient_use_cases": []})
    return rows


def use_case_analysis(ds: Dataset, use_case_id: str, f: Filters) -> tuple[ScopeROI, ComparisonResult]:
    uc = ds.use_case(use_case_id)
    if uc is None:
        raise KeyError(use_case_id)
    uf = Filters(f.start, f.end, frozenset(), frozenset(), frozenset(), frozenset({use_case_id}))
    s = scope_roi(ds, uf, org_scope=False)
    tasks = filter_tasks(ds, uf, [use_case_id])
    c = s.roi.costs
    ai_cost = c.total - c.human_review - c.rework
    cmp = compare(
        use_case_id=use_case_id,
        study_design=uc.study_design,
        tasks=tasks,
        hourly_rate=_rate_for_use_case(ds, use_case_id),
        ai_cost=ai_cost,
        roi=s.roi,
        assumptions=ds.assumptions,
    )
    return s, cmp


# ------------------------------------------------------------------ budgets


def budget_status(ds: Dataset, as_of: date, trailing_days: int = 14) -> list[dict]:
    """Month-to-date model spend against monthly budgets, with a linear forecast.

    Forecast = MTD spend + (average daily spend over the trailing window)
    × remaining days in the month. Budgets cover model & API usage.
    """
    month_start = as_of.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    month_end = next_month - timedelta(days=1)
    remaining = (month_end - as_of).days
    rows = []
    for b in ds.budgets:
        if b.month != month_start:
            continue
        deps = frozenset({b.department_id}) if b.department_id else frozenset()
        mtd = sum((e.cost or ZERO for e in filter_events(
            ds, Filters(month_start, as_of, deps))), ZERO)
        win_start = max(ds.period_start, as_of - timedelta(days=trailing_days - 1))
        win = sum((e.cost or ZERO for e in filter_events(
            ds, Filters(win_start, as_of, deps))), ZERO)
        win_days = (as_of - win_start).days + 1
        daily = win / win_days if win_days > 0 else ZERO
        forecast = mtd + daily * remaining
        util = mtd / b.amount if b.amount else None
        fut = forecast / b.amount if b.amount else None
        if util is not None and util >= 1:
            status = "exceeded"
        elif fut is not None and fut >= 1:
            status = "forecast_exceeds"
        elif util is not None and util >= ds.assumptions.budget_warning_ratio:
            status = "warning"
        else:
            status = "ok"
        rows.append({"budget_id": b.budget_id, "department_id": b.department_id or "organization",
                     "month": month_start, "budget": b.amount, "spent": mtd,
                     "utilization": util, "forecast": forecast,
                     "forecast_utilization": fut, "status": status})
    return rows


def claims_in_period(claims: Iterable[BenefitClaim], start: date, end: date) -> list[BenefitClaim]:
    return [c for c in claims if overlap_days(c.period_start, c.period_end, start, end)]


__all__ = [
    "Filters", "UNALLOCATED", "overview", "breakdown", "daily_trend", "adoption", "anomalies",
    "department_summaries", "use_case_analysis", "budget_status", "scope_roi", "usage_totals",
    "filter_events", "CostBreakdown", "ROIStatus",
]
