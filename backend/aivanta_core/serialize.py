"""JSON payloads for the API, built from core results.

Kept framework-free so every response shape the frontend consumes is unit
tested without a web server. Conventions:

* Money is a JSON number rounded to 2 dp (``unit_cost`` fields to 6 dp).
* ``null`` means "not available / not computable", never zero.
* Each KPI carries ``basis`` — ``measured`` (from usage or task records),
  ``evidence_backed`` (benefits that passed the evidence rules) or
  ``estimated`` (never part of ROI) — plus ``definition_key`` for its tooltip.
* ``synthetic`` at the top level says whether the whole dataset is demo data.
"""
from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable, Mapping, Optional

from . import analytics as A
from .comparison import ArmStats, ComparisonResult, Difference
from .domain import Assumptions, Dataset
from .pricing import PricingSchedule
from .recommendations import Recommendation, generate
from .roi import ROIResult, Scenario

# ------------------------------------------------------------------ primitives

def money(v: Optional[Decimal], places: int = 2) -> Optional[float]:
    if v is None:
        return None
    return float(Decimal(v).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def num(v: Optional[float], places: int = 4) -> Optional[float]:
    if v is None:
        return None
    return round(float(v), places)


def iso(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None


def kpi(value: Any, basis: str, definition_key: str, unit: str, **extra) -> dict:
    return {"value": value, "basis": basis, "definition_key": definition_key, "unit": unit, **extra}


# ------------------------------------------------------------------ filters

def _split(value: Optional[str]) -> frozenset[str]:
    if not value:
        return frozenset()
    return frozenset(v.strip() for v in value.split(",") if v.strip())


def parse_filters(params: Mapping[str, Optional[str]]) -> A.Filters:
    """Build filters from query parameters (comma-separated lists, ISO dates)."""

    def _date(key: str) -> Optional[date]:
        raw = params.get(key)
        if not raw:
            return None
        try:
            return date.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError(f"invalid date for '{key}': {raw}") from exc

    f = A.Filters(
        start=_date("start"),
        end=_date("end"),
        department_ids=_split(params.get("departments")),
        providers=_split(params.get("providers")),
        models=_split(params.get("models")),
        use_case_ids=_split(params.get("use_cases")),
    )
    if f.start and f.end and f.end < f.start:
        raise ValueError("end date precedes start date")
    return f


def clamp_filters(ds: Dataset, f: A.Filters) -> A.Filters:
    """Keep the requested window inside the dataset period."""
    start = max(f.start or ds.period_start, ds.period_start)
    end = min(f.end or ds.period_end, ds.period_end)
    if end < start:
        end = start
    return A.Filters(start, end, f.department_ids, f.providers, f.models, f.use_case_ids)


# ------------------------------------------------------------------ ROI

def scenario_payload(s: Scenario) -> dict:
    return {"name": s.name, "gross_benefit": money(s.gross_benefit), "total_cost": money(s.total_cost),
            "net_benefit": money(s.net_benefit), "roi_pct": money(s.roi_pct, 1),
            "includes_estimates": s.includes_estimates}


def roi_payload(r: ROIResult) -> dict:
    b = r.benefits
    return {
        "status": r.status,
        "reasons": r.reasons,
        "period_days": r.period_days,
        "costs": {k: money(v) for k, v in r.costs.as_dict().items()},
        "one_off_cost": money(r.costs.one_off),
        "recurring_cost": money(r.costs.recurring),
        "benefits": {
            "verified_savings": money(b.verified_savings),
            "supported_contribution": money(b.supported_contribution),
            "supported_cost_avoidance": money(b.supported_cost_avoidance),
            "verified_component": money(b.verified_component),
            "supported_component": money(b.supported_component),
            "gross": money(b.gross),
            "estimated_excluded": money(b.estimated),
            "counted": [_claim(c) for c in b.counted],
            "excluded": [_claim(e.claim) | {"reason": e.reason} for e in b.excluded],
        },
        "gross_benefit": money(r.gross_benefit),
        "net_benefit": money(r.net_benefit),
        "roi_pct": money(r.roi_pct, 1),
        "benefit_cost_ratio": money(r.benefit_cost_ratio),
        "cost_per_successful_task": money(r.cost_per_successful_task),
        "successful_tasks": r.successful_tasks,
        "break_even_tasks": money(r.break_even_tasks, 0),
        "payback_months": money(r.payback_months, 1),
        "hours": {
            "gross": num(r.hours.gross_hours, 1),
            "net": num(r.hours.net_hours, 1),
            "baseline_source": r.hours.baseline_source,
            "baseline_minutes_per_task": num(r.hours.baseline_minutes_per_task, 2),
            "ai_minutes_per_task": num(r.hours.ai_minutes_per_task, 2),
        },
        "estimated_time_value": money(r.estimated_time_value),
        "scenarios": {k: scenario_payload(v) for k, v in r.scenarios.items()},
    }


def _claim(c) -> dict:
    return {"id": c.benefit_id, "use_case": c.use_case_id, "category": c.category,
            "amount": money(c.amount), "verification_status": c.verification_status,
            "evidence_key": c.evidence_key, "period_start": iso(c.period_start),
            "period_end": iso(c.period_end), "confidence": c.confidence, "source": c.source}


# ------------------------------------------------------------------ dashboard

def overview_payload(ds: Dataset, f: A.Filters) -> dict:
    o = A.overview(ds, f)
    u: A.UsageTotals = o["usage"]
    s: A.ScopeROI = o["scope"]
    r = s.roi
    start, end = o["period"]
    applicable = o["roi_applicable"]
    roi_val = money(r.roi_pct, 1) if applicable else None
    return {
        "synthetic": ds.is_synthetic,
        "currency": ds.currency,
        "period": {"start": iso(start), "end": iso(end), "days": (end - start).days + 1},
        "roi_applicable": applicable,
        "roi_status": r.status if applicable else "not_applicable_for_filter",
        "roi_reasons": r.reasons,
        "insufficient_use_cases": s.insufficient_use_cases,
        "kpis": {
            "ai_spend": kpi(money(u.spend), "measured", "metric.ai_spend", "currency"),
            "total_ai_cost": kpi(money(r.costs.total), "measured", "metric.total_ai_cost", "currency"),
            "input_tokens": kpi(u.input_tokens, "measured", "metric.input_tokens", "count"),
            "output_tokens": kpi(u.output_tokens, "measured", "metric.output_tokens", "count"),
            "cached_input_tokens": kpi(u.cached_input_tokens, "measured", "metric.cached_input_tokens", "count"),
            "requests": kpi(u.requests, "measured", "metric.requests", "count"),
            "active_users": kpi(len(u.users), "measured", "metric.active_users", "count"),
            "active_departments": kpi(len(u.departments), "measured", "metric.active_departments", "count"),
            "error_rate": kpi(num(u.error_rate), "measured", "metric.error_rate", "ratio"),
            "gross_benefit": kpi(money(r.gross_benefit) if applicable else None, "evidence_backed",
                                 "metric.gross_benefit", "currency"),
            "estimated_total_value": kpi(money(o["estimated_total_value"]) if applicable else None,
                                         "estimated", "metric.estimated_total_value", "currency"),
            "net_benefit": kpi(money(r.net_benefit) if applicable else None, "evidence_backed",
                               "metric.net_benefit", "currency"),
            "roi_pct": kpi(roi_val, "evidence_backed", "metric.roi", "percent"),
            "verified_savings": kpi(money(r.benefits.verified_savings) if applicable else None,
                                    "evidence_backed", "metric.verified_savings", "currency"),
            "hours_saved": kpi(num(r.hours.gross_hours, 1), "measured", "metric.hours_saved", "hours",
                               net=num(r.hours.net_hours, 1)),
            "cost_per_successful_task": kpi(money(r.cost_per_successful_task) if applicable else None,
                                            "measured", "metric.cost_per_successful_task", "currency"),
        },
        "roi": roi_payload(r) if applicable else None,
    }


def breakdown_payload(ds: Dataset, f: A.Filters, dimension: str) -> dict:
    rows = A.breakdown(ds, f, dimension)
    return {"dimension": dimension, "rows": [
        {"key": r["key"], "spend": money(r["spend"]), "share": num(r["share"]),
         "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
         "cached_input_tokens": r["cached_input_tokens"], "requests": r["requests"],
         "error_rate": num(r["error_rate"]), "avg_latency_ms": num(r["avg_latency_ms"], 0),
         "retries": r["retries"], "active_users": r["active_users"],
         "cost_per_request": money(r["cost_per_request"], 6)}
        for r in rows]}


def trend_payload(ds: Dataset, f: A.Filters) -> dict:
    return {"rows": [{"date": iso(r["date"]), "spend": money(r["spend"]), "requests": r["requests"],
                      "tokens": r["tokens"], "active_users": r["active_users"], "errors": r["errors"]}
                     for r in A.daily_trend(ds, f)],
            "anomalies": [{"date": iso(a["date"]), "spend": money(a["spend"]), "zscore": num(a["zscore"], 2),
                           "typical": money(Decimal(str(a["expected"])))} for a in A.anomalies(ds, f)]}


def adoption_payload(ds: Dataset, f: A.Filters) -> dict:
    return {"rows": [{"week_start": iso(w["week_start"]), "active_users": w["active_users"],
                      "eligible_users": w["eligible_users"], "adoption_rate": num(w["adoption_rate"])}
                     for w in A.adoption(ds, f)]}


def budgets_payload(ds: Dataset, as_of: date) -> dict:
    return {"as_of": iso(as_of), "basis": "model_usage", "rows": [
        {"budget_id": b["budget_id"], "department": b["department_id"], "month": iso(b["month"]),
         "budget": money(b["budget"]), "spent": money(b["spent"]), "utilization": num(b["utilization"]),
         "forecast": money(b["forecast"]), "forecast_utilization": num(b["forecast_utilization"]),
         "status": b["status"]} for b in A.budget_status(ds, as_of)]}


def departments_payload(ds: Dataset, f: A.Filters) -> dict:
    rows = []
    for d in A.department_summaries(ds, f):
        u: A.UsageTotals = d["usage"]
        r: Optional[ROIResult] = d["roi"]
        rows.append({
            "department": d["department_id"],
            "spend": money(u.spend),
            "total_cost": money(d["total_cost"]),
            "tokens": u.total_tokens,
            "requests": u.requests,
            "active_users": d["active_users"],
            "tasks_completed": d["tasks_completed"],
            "hours_saved": num(d["hours_saved"], 1),
            "net_hours_saved": num(d["net_hours_saved"], 1),
            "quality": num(d["quality"]),
            "success_rate": num(d["success_rate"]),
            "gross_benefit": money(d["gross_benefit"]),
            "estimated_time_value": money(d["estimated_time_value"]),
            "roi_status": r.status if r else "unallocated",
            "roi_pct": money(r.roi_pct, 1) if r else None,
            "net_benefit": money(r.net_benefit) if r else None,
            "insufficient_use_cases": d["insufficient_use_cases"],
        })
    return {"rows": rows}


# ------------------------------------------------------------------ comparison

def _diff(d: Difference, places: int = 4) -> dict:
    return {"estimate": num(d.estimate, places), "low": num(d.low, places), "high": num(d.high, places),
            "significant": d.significant}


def _arm(a: ArmStats) -> dict:
    return {"n": a.n, "first_day": iso(a.first_day), "last_day": iso(a.last_day),
            "mean_minutes": num(a.mean_minutes, 2), "mean_total_minutes": num(a.mean_total_minutes, 2),
            "success_rate": num(a.success_rate), "error_rate": num(a.error_rate),
            "rework_rate": num(a.rework_rate), "quality": num(a.mean_quality),
            "csat": num(a.mean_csat, 2), "tasks_per_hour": num(a.tasks_per_hour, 3),
            "labour_cost": money(a.labour_cost), "ai_cost": money(a.ai_cost),
            "total_cost": money(a.total_cost), "cost_per_completed_task": money(a.cost_per_completed_task)}


def comparison_payload(c: ComparisonResult) -> dict:
    return {
        "use_case": c.use_case_id,
        "study_design": c.study_design,
        "causal": c.causal,
        "ai": _arm(c.ai),
        "non_ai": _arm(c.non_ai),
        "differences": {"total_minutes": _diff(c.minutes, 2), "quality": _diff(c.quality),
                        "success_rate": _diff(c.success_rate), "error_rate": _diff(c.error_rate)},
        "cost_per_task_delta": money(c.cost_per_task_delta),
        "estimated_net_benefit": money(c.estimated_net_benefit),
        "segments": [{"task_type": s.task_type, "n_ai": s.n_ai, "n_non_ai": s.n_non_ai,
                      "total_minutes": _diff(s.minutes, 2), "quality": _diff(s.quality),
                      "favourable": s.favourable} for s in c.segments],
        "decision": c.decision,
        "reasons": c.reasons,
    }


def use_case_payload(ds: Dataset, use_case_id: str, f: A.Filters) -> dict:
    uc = ds.use_case(use_case_id)
    if uc is None:
        raise KeyError(use_case_id)
    s, c = A.use_case_analysis(ds, use_case_id, f)
    dep = ds.department(uc.department_id) if uc.department_id else None
    return {
        "use_case": uc.use_case_id,
        "name_key": uc.name_key,
        "department": uc.department_id,
        "task_complexity": uc.task_complexity,
        "study_design": uc.study_design,
        "data_source": uc.data_source,
        "measurement_period": {"start": iso(uc.measurement_start), "end": iso(uc.measurement_end)},
        "documented_baseline_minutes": uc.baseline_minutes,
        "labour_rate": money(dep.loaded_hourly_rate) if dep else None,
        "tasks_ai": s.tasks_ai,
        "quality_ai": num(s.quality_ai),
        "success_rate_ai": num(s.success_rate_ai),
        "roi": roi_payload(s.roi),
        "comparison": comparison_payload(c),
    }


def use_cases_payload(ds: Dataset, f: A.Filters) -> dict:
    rows = []
    for uc in ds.use_cases:
        if f.department_ids and (uc.department_id or A.UNALLOCATED) not in f.department_ids:
            continue
        if f.use_case_ids and uc.use_case_id not in f.use_case_ids:
            continue
        p = use_case_payload(ds, uc.use_case_id, f)
        rows.append({k: p[k] for k in ("use_case", "name_key", "department", "study_design",
                                       "task_complexity", "tasks_ai", "quality_ai", "success_rate_ai")}
                    | {"decision": p["comparison"]["decision"], "roi_status": p["roi"]["status"],
                       "roi_pct": p["roi"]["roi_pct"], "total_cost": p["roi"]["costs"]["total"],
                       "gross_benefit": p["roi"]["gross_benefit"], "net_benefit": p["roi"]["net_benefit"],
                       "hours_saved": p["roi"]["hours"]["gross"],
                       "cost_per_task_delta": p["comparison"]["cost_per_task_delta"],
                       "causal": p["comparison"]["causal"]})
    return {"rows": rows}


# ------------------------------------------------------------------ recommendations

def _jsonable(v: Any) -> Any:
    if isinstance(v, Decimal):
        return money(v, 4)
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return v


def recommendation_payload(r: Recommendation) -> dict:
    return {"rule_id": r.rule_id, "message_key": r.message_key, "severity": r.severity,
            "scope_type": r.scope_type, "scope_id": r.scope_id,
            "metrics": {k: _jsonable(v) for k, v in r.metrics.items()},
            "projected_monthly_saving": money(r.projected_monthly_saving),
            "is_estimate": r.is_estimate}


def recommendations_payload(ds: Dataset, f: A.Filters) -> dict:
    recs = generate(ds, f, PricingSchedule(ds.pricing))
    return {"rows": [recommendation_payload(r) for r in recs]}


# ------------------------------------------------------------------ meta & assumptions

def assumptions_payload(a: Assumptions) -> dict:
    return {
        "min_sample_size": a.min_sample_size,
        "min_measurement_days": a.min_measurement_days,
        "conservative_benefit_haircut": float(a.conservative_benefit_haircut),
        "conservative_cost_contingency": float(a.conservative_cost_contingency),
        "optimistic_estimated_benefit_share": float(a.optimistic_estimated_benefit_share),
        "quality_tolerance": a.quality_tolerance,
        "budget_warning_ratio": float(a.budget_warning_ratio),
        "review_erosion_ratio": a.review_erosion_ratio,
        "spend_growth_alert_ratio": a.spend_growth_alert_ratio,
        "anomaly_sigma": a.anomaly_sigma,
    }


ASSUMPTION_BOUNDS: dict[str, tuple[float, float]] = {
    "min_sample_size": (2, 100_000),
    "min_measurement_days": (1, 3650),
    "conservative_benefit_haircut": (0, 1),
    "conservative_cost_contingency": (0, 5),
    "optimistic_estimated_benefit_share": (0, 1),
    "quality_tolerance": (0, 1),
    "budget_warning_ratio": (0, 1),
    "review_erosion_ratio": (0, 10),
    "spend_growth_alert_ratio": (0, 100),
    "anomaly_sigma": (1, 10),
}


def apply_assumptions(current: Assumptions, changes: Mapping[str, Any]) -> Assumptions:
    """Validate and apply assumption updates; returns a new object."""
    values = assumptions_payload(current)
    for key, raw in changes.items():
        if key not in ASSUMPTION_BOUNDS:
            raise ValueError(f"unknown assumption '{key}'")
        lo, hi = ASSUMPTION_BOUNDS[key]
        try:
            v = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"'{key}' must be a number") from exc
        if not lo <= v <= hi:
            raise ValueError(f"'{key}' must be between {lo} and {hi}")
        values[key] = v
    return Assumptions(
        min_sample_size=int(values["min_sample_size"]),
        min_measurement_days=int(values["min_measurement_days"]),
        conservative_benefit_haircut=Decimal(str(values["conservative_benefit_haircut"])),
        conservative_cost_contingency=Decimal(str(values["conservative_cost_contingency"])),
        optimistic_estimated_benefit_share=Decimal(str(values["optimistic_estimated_benefit_share"])),
        quality_tolerance=float(values["quality_tolerance"]),
        budget_warning_ratio=Decimal(str(values["budget_warning_ratio"])),
        review_erosion_ratio=float(values["review_erosion_ratio"]),
        spend_growth_alert_ratio=float(values["spend_growth_alert_ratio"]),
        anomaly_sigma=float(values["anomaly_sigma"]),
    )


def meta_payload(ds: Dataset) -> dict:
    return {
        "organization": ds.organization_id,
        "currency": ds.currency,
        "synthetic": ds.is_synthetic,
        "period": {"start": iso(ds.period_start), "end": iso(ds.period_end)},
        "departments": [{"id": d.department_id, "name_key": d.name_key,
                         "loaded_hourly_rate": money(d.loaded_hourly_rate)} for d in ds.departments],
        "use_cases": [{"id": u.use_case_id, "name_key": u.name_key, "department": u.department_id}
                      for u in ds.use_cases],
        "providers": sorted({p.provider for p in ds.pricing}),
        "models": [{"provider": p.provider, "model": p.model, "tier": p.tier,
                    "effective_from": iso(p.effective_from),
                    "input_per_mtok": money(p.input_per_mtok, 4),
                    "output_per_mtok": money(p.output_per_mtok, 4),
                    "cached_input_per_mtok": money(p.cached_input_per_mtok, 4)} for p in ds.pricing],
        "assumptions": assumptions_payload(ds.assumptions),
    }


def all_dashboard(ds: Dataset, f: A.Filters, dims: Iterable[str] = A.DIMENSIONS) -> dict:
    """Everything the executive dashboard needs in one call."""
    _, end = f.period(ds)
    return {
        "overview": overview_payload(ds, f),
        "trend": trend_payload(ds, f),
        "adoption": adoption_payload(ds, f),
        "breakdowns": {d: breakdown_payload(ds, f, d) for d in dims},
        "budgets": budgets_payload(ds, end),
    }
