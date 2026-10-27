"""Explainable, rule-based recommendations and alerts.

Each rule is a small function that inspects the dataset and returns zero or
more :class:`Recommendation` objects. Every recommendation carries the metrics
that triggered it (so the UI can show *why*) and any projected benefit is
flagged as an estimate. Messages are localization keys, not prose.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Callable, Optional

from . import stats
from .analytics import (
    UNALLOCATED,
    Filters,
    anomalies,
    budget_status,
    filter_events,
    usage_totals,
    use_case_analysis,
)
from .comparison import Decision
from .domain import ZERO, Dataset, TaskArm
from .pricing import PricingSchedule, cheaper_alternative, token_cost
from .roi import DAYS_PER_MONTH, ROIStatus

SEVERITY_ORDER = {"critical": 0, "warning": 1, "opportunity": 2, "info": 3}
QUALITY_FLOOR = 0.75


@dataclass
class Recommendation:
    rule_id: str
    severity: str  # critical | warning | opportunity | info
    scope_type: str  # organization | department | use_case | budget
    scope_id: str
    metrics: dict[str, Any] = field(default_factory=dict)
    projected_monthly_saving: Optional[Decimal] = None
    is_estimate: bool = True  # projections are always estimates

    @property
    def message_key(self) -> str:
        return f"recommendation.{self.rule_id}"


Rule = Callable[[Dataset, Filters, PricingSchedule], list[Recommendation]]


def _windows(ds: Dataset, f: Filters, days: int = 30) -> tuple[tuple[date, date], tuple[date, date]]:
    _, end = f.period(ds)
    recent = (end - timedelta(days=days - 1), end)
    prior = (recent[0] - timedelta(days=days), recent[0] - timedelta(days=1))
    return prior, recent


def rule_spend_without_improvement(ds, f, schedule):
    out = []
    (p0, p1), (r0, r1) = _windows(ds, f)
    for dep in ds.departments:
        deps = frozenset({dep.department_id})
        prior = usage_totals(filter_events(ds, Filters(p0, p1, deps))).spend
        recent = usage_totals(filter_events(ds, Filters(r0, r1, deps))).spend
        if prior <= 0:
            continue
        growth = float((recent - prior) / prior)
        if growth < ds.assumptions.spend_growth_alert_ratio:
            continue
        uc_ids = {u.use_case_id for u in ds.use_cases if u.department_id == dep.department_id}

        def outcome(a: date, b: date, uc_ids=uc_ids):
            ts = [t for t in ds.tasks if t.use_case_id in uc_ids and t.arm == TaskArm.AI.value
                  and a <= t.completed_on <= b]
            q = stats.mean([t.quality_score for t in ts if t.quality_score is not None])
            s = sum(t.success for t in ts) / len(ts) if ts else None
            return s, q

        s0, q0 = outcome(p0, p1)
        s1, q1 = outcome(r0, r1)
        improved = (s0 is not None and s1 is not None and s1 - s0 > 0.01) or (
            q0 is not None and q1 is not None and q1 - q0 > 0.01)
        if improved:
            continue
        out.append(Recommendation(
            "spend_without_improvement", "warning", "department", dep.department_id,
            {"spend_prior_30d": prior, "spend_recent_30d": recent, "spend_growth": growth,
             "success_rate_prior": s0, "success_rate_recent": s1,
             "quality_prior": q0, "quality_recent": q1},
            is_estimate=False))
    return out


def rule_cheaper_model(ds, f, schedule):
    out = []
    start, end = f.period(ds)
    months = Decimal((end - start).days + 1) / DAYS_PER_MONTH
    for uc in ds.use_cases:
        if uc.task_complexity != "simple":
            continue
        events = filter_events(ds, Filters(start, end, use_case_ids=frozenset({uc.use_case_id})))
        if not events:
            continue
        by_model: dict[tuple[str, str], list] = {}
        for e in events:
            by_model.setdefault((e.provider, e.model), []).append(e)
        (prov, model), evs = max(by_model.items(), key=lambda kv: sum(e.cost or ZERO for e in kv[1]))
        current_rule = schedule.rule_for(prov, model, end)
        if current_rule.tier != "frontier":
            continue
        alt = cheaper_alternative(schedule, prov, model, end)
        if alt is None:
            continue
        current = sum((e.cost or ZERO for e in evs), ZERO)
        repriced = sum((token_cost(alt, input_tokens=e.input_tokens, output_tokens=e.output_tokens,
                                   cached_input_tokens=e.cached_input_tokens) for e in evs), ZERO)
        saving = (current - repriced) / months
        out.append(Recommendation(
            "cheaper_model", "opportunity", "use_case", uc.use_case_id,
            {"current_model": f"{prov}/{model}", "suggested_model": f"{alt.provider}/{alt.model}",
             "current_spend": current, "repriced_spend": repriced,
             "task_complexity": uc.task_complexity,
             "assumption": "same_token_volume_and_quality_to_be_validated"},
            projected_monthly_saving=saving))
    return out


def rule_high_tokens_low_quality(ds, f, schedule):
    start, end = f.period(ds)
    per_uc = []
    for uc in ds.use_cases:
        ai = [t for t in ds.tasks if t.use_case_id == uc.use_case_id and t.arm == TaskArm.AI.value
              and start <= t.completed_on <= end]
        if not ai:
            continue
        tokens = usage_totals(filter_events(
            ds, Filters(start, end, use_case_ids=frozenset({uc.use_case_id})))).total_tokens
        q = stats.mean([t.quality_score for t in ai if t.quality_score is not None])
        per_uc.append((uc.use_case_id, tokens / len(ai), q))
    if len(per_uc) < 2:
        return []
    tpt = sorted(x[1] for x in per_uc)
    mid = len(tpt) // 2
    median = tpt[mid] if len(tpt) % 2 else (tpt[mid - 1] + tpt[mid]) / 2
    return [
        Recommendation("high_tokens_low_quality", "warning", "use_case", uc_id,
                       {"tokens_per_task": t, "org_median_tokens_per_task": median,
                        "quality": q, "quality_floor": QUALITY_FLOOR}, is_estimate=False)
        for uc_id, t, q in per_uc if t >= median and q is not None and q < QUALITY_FLOOR
    ]


def rule_review_erosion(ds, f, schedule):
    out = []
    start, end = f.period(ds)
    for uc in ds.use_cases:
        ts = [t for t in ds.tasks if t.use_case_id == uc.use_case_id
              and start <= t.completed_on <= end]
        ai = [t for t in ts if t.arm == TaskArm.AI.value]
        base = [t for t in ts if t.arm == TaskArm.NON_AI.value]
        if len(ai) < ds.assumptions.min_sample_size or not base:
            continue
        mean = lambda xs, k: sum(k(t) for t in xs) / len(xs)  # noqa: E731
        saved = mean(base, lambda t: t.duration_minutes) - mean(ai, lambda t: t.duration_minutes)
        extra = (mean(ai, lambda t: t.review_minutes + t.rework_minutes)
                 - mean(base, lambda t: t.review_minutes + t.rework_minutes))
        if saved <= 0 or extra <= 0:
            continue
        erosion = extra / saved
        if erosion >= ds.assumptions.review_erosion_ratio:
            out.append(Recommendation(
                "review_erasing_gains", "warning", "use_case", uc.use_case_id,
                {"minutes_saved_per_task": saved, "extra_review_rework_minutes": extra,
                 "erosion_ratio": erosion}, is_estimate=False))
    return out


def rule_budgets(ds, f, schedule):
    _, end = f.period(ds)
    out = []
    for b in budget_status(ds, end):
        if b["status"] == "ok":
            continue
        sev = "critical" if b["status"] in ("exceeded", "forecast_exceeds") else "warning"
        out.append(Recommendation(
            f"budget_{b['status']}", sev, "budget", b["department_id"],
            {"budget": b["budget"], "spent": b["spent"], "utilization": b["utilization"],
             "forecast": b["forecast"], "forecast_utilization": b["forecast_utilization"]},
            is_estimate=b["status"] == "forecast_exceeds"))
    return out


def rule_outcome_tracking(ds, f, schedule):
    out = []
    start, end = f.period(ds)
    events = filter_events(ds, Filters(start, end))
    total = usage_totals(events).spend
    unalloc = usage_totals(e for e in events if e.department_id is None or e.use_case_id is None).spend
    if total and unalloc / total > Decimal("0.05"):
        out.append(Recommendation(
            "unallocated_usage", "warning", "organization", "organization",
            {"unallocated_spend": unalloc, "total_spend": total, "share": unalloc / total},
            is_estimate=False))
    for uc in ds.use_cases:
        s, _ = use_case_analysis(ds, uc.use_case_id, Filters(start, end))
        if s.roi.status == ROIStatus.INSUFFICIENT_EVIDENCE.value and s.roi.costs.total > 0:
            out.append(Recommendation(
                "needs_outcome_tracking", "info", "use_case", uc.use_case_id,
                {"total_cost": s.roi.costs.total, "reasons": list(s.roi.reasons),
                 "ai_tasks": s.tasks_ai}, is_estimate=False))
    return out


def rule_comparison_decisions(ds, f, schedule):
    out = []
    start, end = f.period(ds)
    for uc in ds.use_cases:
        s, cmp = use_case_analysis(ds, uc.use_case_id, Filters(start, end))
        metrics = {"decision": cmp.decision, "reasons": cmp.reasons,
                   "cost_per_task_delta": cmp.cost_per_task_delta,
                   "quality_delta": cmp.quality.estimate, "roi_pct": s.roi.roi_pct}
        if cmp.decision == Decision.CONTINUE.value and s.roi.net_benefit and s.roi.net_benefit > 0:
            months = Decimal(s.roi.period_days) / DAYS_PER_MONTH
            out.append(Recommendation("expansion_candidate", "opportunity", "use_case",
                                      uc.use_case_id, metrics | {"net_benefit": s.roi.net_benefit},
                                      projected_monthly_saving=s.roi.net_benefit / months))
        elif cmp.decision == Decision.STOP.value:
            out.append(Recommendation("stop_workflow", "critical", "use_case", uc.use_case_id,
                                      metrics, is_estimate=False))
        elif cmp.decision == Decision.SELECTIVE.value:
            out.append(Recommendation("restrict_to_task_types", "warning", "use_case",
                                      uc.use_case_id, metrics, is_estimate=False))
    return out


def rule_anomalies(ds, f, schedule):
    return [
        Recommendation("spend_anomaly", "warning", "organization", a["date"].isoformat(),
                       {"date": a["date"], "spend": a["spend"], "zscore": a["zscore"],
                        "typical_daily_spend": a["expected"]}, is_estimate=False)
        for a in anomalies(ds, f)
    ]


RULES: list[Rule] = [
    rule_budgets,
    rule_comparison_decisions,
    rule_spend_without_improvement,
    rule_cheaper_model,
    rule_high_tokens_low_quality,
    rule_review_erosion,
    rule_outcome_tracking,
    rule_anomalies,
]


def generate(ds: Dataset, f: Filters, schedule: PricingSchedule) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for rule in RULES:
        recs.extend(rule(ds, f, schedule))
    recs.sort(key=lambda r: (SEVERITY_ORDER[r.severity], r.rule_id, r.scope_id))
    return recs


__all__ = ["Recommendation", "generate", "RULES", "UNALLOCATED"]
