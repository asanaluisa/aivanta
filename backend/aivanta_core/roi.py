"""Deterministic cost and ROI engine.

Definitions (see docs/FINANCIAL_DEFINITIONS.md for the full narrative):

* Total AI-related cost = model usage + subscriptions + infrastructure
  + implementation + maintenance + human review + rework + other operating.
  Review and rework are charged incrementally over the non-AI baseline when
  one exists (see :func:`build_cost_breakdown`).
* Gross benefit = verified financial savings
                + supported incremental contribution
                + supported cost avoidance.
  ("Supported" includes "verified".) Estimated and unverified claims never
  enter gross benefit; they are reported separately as estimates.
* Net benefit = gross benefit − total AI-related cost.
* ROI % = net benefit / total AI-related cost × 100.
* Benefit-to-cost ratio = gross benefit / total AI-related cost.
* Hours saved are reported separately from cash and never added to gross
  benefit. Their monetary value appears only as an *estimate*.

Double counting is prevented by ``evidence_key``: claims that describe the
same underlying outcome are collapsed to the single strongest claim.

When the evidence threshold is not met the engine returns
``status = "insufficient_evidence"`` and leaves ROI, net benefit and the
benefit-to-cost ratio empty instead of inventing a figure.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Callable, Iterable, Optional, Sequence

from .domain import (
    ZERO,
    Assumptions,
    BenefitCategory,
    BenefitClaim,
    CostCategory,
    CostItem,
    TaskArm,
    TaskRecord,
    UsageEvent,
    VerificationStatus,
)

DAYS_PER_MONTH = Decimal("30.4375")
HUNDRED = Decimal(100)
SIXTY = Decimal(60)


class ROIStatus(str, Enum):
    OK = "ok"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NO_COSTS = "no_costs"


class EvidenceReason(str, Enum):
    NO_SUPPORTED_BENEFITS = "no_supported_benefits"
    SAMPLE_TOO_SMALL = "sample_too_small"
    PERIOD_TOO_SHORT = "period_too_short"
    NO_OUTCOME_DATA = "no_outcome_data"
    PARTIAL_EVIDENCE = "partial_evidence"  # informational, does not block


class ExclusionReason(str, Enum):
    DUPLICATE_EVIDENCE = "duplicate_evidence"
    ESTIMATE_ONLY = "estimate_only"
    UNVERIFIED = "unverified"
    SAVINGS_NOT_VERIFIED = "savings_not_verified"
    OUTSIDE_PERIOD = "outside_period"


# --------------------------------------------------------------------------- costs


@dataclass
class CostBreakdown:
    model_usage: Decimal = ZERO
    subscription: Decimal = ZERO
    infrastructure: Decimal = ZERO
    implementation: Decimal = ZERO
    maintenance: Decimal = ZERO
    human_review: Decimal = ZERO
    rework: Decimal = ZERO
    other_operating: Decimal = ZERO

    @property
    def total(self) -> Decimal:
        return (
            self.model_usage
            + self.subscription
            + self.infrastructure
            + self.implementation
            + self.maintenance
            + self.human_review
            + self.rework
            + self.other_operating
        )

    @property
    def one_off(self) -> Decimal:
        return self.implementation

    @property
    def recurring(self) -> Decimal:
        return self.total - self.one_off

    @property
    def variable(self) -> Decimal:
        """Costs that scale with task volume."""
        return self.model_usage + self.human_review + self.rework

    def add(self, category: str, amount: Decimal) -> None:
        attr = CostCategory(category).value
        setattr(self, attr, getattr(self, attr) + amount)

    def as_dict(self) -> dict[str, Decimal]:
        return {c.value: getattr(self, c.value) for c in CostCategory} | {"total": self.total}

    def __add__(self, other: "CostBreakdown") -> "CostBreakdown":
        out = CostBreakdown()
        for c in CostCategory:
            setattr(out, c.value, getattr(self, c.value) + getattr(other, c.value))
        return out


def overlap_days(a_start: date, a_end: date, b_start: date, b_end: date) -> int:
    start, end = max(a_start, b_start), min(a_end, b_end)
    return max(0, (end - start).days + 1)


def prorated_amount(item: CostItem, period_start: date, period_end: date) -> Decimal:
    """Share of a cost item that falls inside the analysis period.

    Recurring items are prorated by calendar days. One-off items (e.g.
    implementation) are counted in full when they are incurred inside the
    period — they are an investment, not a run-rate.
    """
    if item.period_end < item.period_start:
        raise ValueError(f"Cost item {item.cost_id} ends before it starts")
    days = overlap_days(item.period_start, item.period_end, period_start, period_end)
    if days == 0:
        return ZERO
    if item.one_off:
        return item.amount if period_start <= item.period_start <= period_end else ZERO
    total_days = (item.period_end - item.period_start).days + 1
    return item.amount * Decimal(days) / Decimal(total_days)


def build_cost_breakdown(
    *,
    events: Iterable[UsageEvent],
    cost_items: Iterable[CostItem],
    ai_tasks: Iterable[TaskRecord],
    hourly_rate_for: Callable[[TaskRecord], Decimal],
    period_start: date,
    period_end: date,
    baseline_review_rework: Optional[Callable[[str], Optional[tuple[float, float]]]] = None,
) -> CostBreakdown:
    """Sum every AI-related cost for a scope and period.

    Human review and rework are valued at the loaded hourly rate. When a use
    case has a non-AI baseline (``baseline_review_rework`` returns the mean
    review and rework minutes per non-AI task), only the *incremental* review
    and rework caused by AI is charged — review that would have happened anyway
    is not an AI cost. Without a baseline, all review and rework on AI tasks is
    charged (the conservative choice).
    """
    out = CostBreakdown()
    for e in events:
        if e.cost is None:
            raise ValueError(f"Usage event {e.event_id} has not been priced")
        out.model_usage += e.cost
    for item in cost_items:
        if item.category in (
            CostCategory.MODEL_USAGE.value,
            CostCategory.HUMAN_REVIEW.value,
            CostCategory.REWORK.value,
        ):
            # These are derived from measured data; manual entries would double count.
            raise ValueError(
                f"Cost item {item.cost_id}: category '{item.category}' is derived, not entered"
            )
        out.add(item.category, prorated_amount(item, period_start, period_end))

    by_use_case: dict[str, list[TaskRecord]] = {}
    for t in ai_tasks:
        if t.arm == TaskArm.AI.value:
            by_use_case.setdefault(t.use_case_id, []).append(t)
    for uc_id in sorted(by_use_case):
        group = by_use_case[uc_id]
        baseline = baseline_review_rework(uc_id) if baseline_review_rework else None
        review_cost = ZERO
        rework_cost = ZERO
        for t in group:
            rate = hourly_rate_for(t) / SIXTY
            review_cost += Decimal(str(t.review_minutes)) * rate
            rework_cost += Decimal(str(t.rework_minutes)) * rate
        if baseline is not None:
            base_review, base_rework = baseline
            rate = hourly_rate_for(group[0]) / SIXTY
            n = Decimal(len(group))
            review_cost = max(ZERO, review_cost - n * Decimal(str(base_review)) * rate)
            rework_cost = max(ZERO, rework_cost - n * Decimal(str(base_rework)) * rate)
        out.human_review += review_cost
        out.rework += rework_cost
    return out


# ------------------------------------------------------------------------ benefits


@dataclass
class ExcludedBenefit:
    claim: BenefitClaim
    reason: str


@dataclass
class BenefitSelection:
    verified_savings: Decimal = ZERO
    supported_contribution: Decimal = ZERO
    supported_cost_avoidance: Decimal = ZERO
    verified_component: Decimal = ZERO  # part of gross that is ledger-verified
    estimated: Decimal = ZERO  # excluded from gross, shown as estimate
    counted: list[BenefitClaim] = field(default_factory=list)
    excluded: list[ExcludedBenefit] = field(default_factory=list)

    @property
    def gross(self) -> Decimal:
        return self.verified_savings + self.supported_contribution + self.supported_cost_avoidance

    @property
    def supported_component(self) -> Decimal:
        return self.gross - self.verified_component


def select_benefits(
    claims: Iterable[BenefitClaim],
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
) -> BenefitSelection:
    """Apply evidence and de-duplication rules to benefit claims."""
    sel = BenefitSelection()
    in_period: list[BenefitClaim] = []
    seen_ids: set[str] = set()
    for c in claims:
        if c.benefit_id in seen_ids:
            continue
        seen_ids.add(c.benefit_id)
        if c.amount < 0:
            raise ValueError(f"Benefit {c.benefit_id} has a negative amount")
        if period_start and period_end:
            days = overlap_days(c.period_start, c.period_end, period_start, period_end)
            if not days:
                sel.excluded.append(ExcludedBenefit(c, ExclusionReason.OUTSIDE_PERIOD.value))
                continue
            claim_days = (c.period_end - c.period_start).days + 1
            if days < claim_days:
                # Pro-rate claims that only partly overlap the analysis period.
                c = replace(c, amount=c.amount * Decimal(days) / Decimal(claim_days))
        in_period.append(c)

    # One claim per evidence key: strongest verification, then the smaller amount.
    by_key: dict[str, list[BenefitClaim]] = {}
    for c in in_period:
        by_key.setdefault(c.evidence_key, []).append(c)
    winners: list[BenefitClaim] = []
    for key in sorted(by_key):
        group = sorted(
            by_key[key],
            key=lambda c: (VerificationStatus(c.verification_status).rank, c.amount, c.benefit_id),
        )
        winners.append(group[0])
        for dup in group[1:]:
            sel.excluded.append(ExcludedBenefit(dup, ExclusionReason.DUPLICATE_EVIDENCE.value))

    for c in winners:
        status = VerificationStatus(c.verification_status)
        category = BenefitCategory(c.category)
        strong = status in (VerificationStatus.VERIFIED, VerificationStatus.SUPPORTED)
        if category is BenefitCategory.FINANCIAL_SAVINGS:
            if status is VerificationStatus.VERIFIED:
                sel.verified_savings += c.amount
            else:
                reason = (
                    ExclusionReason.SAVINGS_NOT_VERIFIED
                    if strong
                    else _weak_reason(status)
                )
                sel.excluded.append(ExcludedBenefit(c, reason.value))
                sel.estimated += c.amount
                continue
        elif strong and category is BenefitCategory.INCREMENTAL_CONTRIBUTION:
            sel.supported_contribution += c.amount
        elif strong and category is BenefitCategory.COST_AVOIDANCE:
            sel.supported_cost_avoidance += c.amount
        else:
            sel.excluded.append(ExcludedBenefit(c, _weak_reason(status).value))
            sel.estimated += c.amount
            continue
        sel.counted.append(c)
        if status is VerificationStatus.VERIFIED:
            sel.verified_component += c.amount
    return sel


def _weak_reason(status: VerificationStatus) -> ExclusionReason:
    return (
        ExclusionReason.UNVERIFIED
        if status is VerificationStatus.UNVERIFIED
        else ExclusionReason.ESTIMATE_ONLY
    )


# --------------------------------------------------------------------------- hours


@dataclass
class HoursSaved:
    ai_tasks: int
    baseline_minutes_per_task: Optional[float]
    ai_minutes_per_task: Optional[float]
    gross_hours: Optional[float]  # duration only
    net_hours: Optional[float]  # after review and rework, vs. baseline incl. review/rework
    baseline_source: Optional[str]  # "control_group" | "documented_baseline" | None


def time_value(hours: HoursSaved, hourly_rate: Decimal) -> Optional[Decimal]:
    """Estimated labour value of gross hours saved (never part of gross benefit)."""
    if hours.gross_hours is None:
        return None
    return max(ZERO, Decimal(str(hours.gross_hours)) * hourly_rate)


def compute_hours_saved(
    ai_tasks: Sequence[TaskRecord],
    non_ai_tasks: Sequence[TaskRecord],
    documented_baseline_minutes: Optional[float] = None,
) -> HoursSaved:
    n = len(ai_tasks)
    if n == 0:
        return HoursSaved(0, None, None, None, None, None)
    ai_dur = sum(t.duration_minutes for t in ai_tasks) / n
    ai_total = sum(t.duration_minutes + t.review_minutes + t.rework_minutes for t in ai_tasks) / n
    if non_ai_tasks:
        m = len(non_ai_tasks)
        base_dur = sum(t.duration_minutes for t in non_ai_tasks) / m
        base_total = (
            sum(t.duration_minutes + t.review_minutes + t.rework_minutes for t in non_ai_tasks) / m
        )
        source = "control_group"
    elif documented_baseline_minutes is not None:
        base_dur = base_total = float(documented_baseline_minutes)
        source = "documented_baseline"
    else:
        return HoursSaved(n, None, ai_dur, None, None, None)
    return HoursSaved(
        ai_tasks=n,
        baseline_minutes_per_task=base_dur,
        ai_minutes_per_task=ai_dur,
        gross_hours=n * (base_dur - ai_dur) / 60,
        net_hours=n * (base_total - ai_total) / 60,
        baseline_source=source,
    )


# ----------------------------------------------------------------------------- ROI


@dataclass
class Scenario:
    name: str
    gross_benefit: Decimal
    total_cost: Decimal
    includes_estimates: bool

    @property
    def net_benefit(self) -> Decimal:
        return self.gross_benefit - self.total_cost

    @property
    def roi_pct(self) -> Optional[Decimal]:
        if self.total_cost <= 0:
            return None
        return self.net_benefit / self.total_cost * HUNDRED


@dataclass
class ROIResult:
    status: str
    reasons: list[str]
    costs: CostBreakdown
    benefits: BenefitSelection
    hours: HoursSaved
    successful_tasks: int
    period_days: int
    estimated_time_value: Optional[Decimal]
    gross_benefit: Decimal
    net_benefit: Optional[Decimal]
    roi_pct: Optional[Decimal]
    benefit_cost_ratio: Optional[Decimal]
    cost_per_successful_task: Optional[Decimal]
    break_even_tasks: Optional[Decimal]
    payback_months: Optional[Decimal]
    scenarios: dict[str, Scenario]

    @property
    def is_conclusive(self) -> bool:
        return self.status == ROIStatus.OK.value


def compute_roi(
    *,
    costs: CostBreakdown,
    benefits: BenefitSelection,
    hours: HoursSaved,
    successful_tasks: int,
    period_start: date,
    period_end: date,
    assumptions: Assumptions,
    estimated_time_value: Optional[Decimal] = None,
    outcome_sample_size: Optional[int] = None,
    partial_evidence: bool = False,
) -> ROIResult:
    """Combine costs, evidence-filtered benefits and outcomes into an ROI result.

    ``outcome_sample_size`` is the number of AI-arm tasks behind the benefits;
    pass ``None`` to skip the sample-size gate (e.g. ledger-only benefits).
    ``estimated_time_value`` is the labour value of gross hours saved; it is an
    estimate and only ever enters the optimistic scenario.
    """
    period_days = (period_end - period_start).days + 1
    if period_days <= 0:
        raise ValueError("period_end must not precede period_start")
    total = costs.total
    gross = benefits.gross
    reasons: list[str] = []

    if total <= 0:
        status = ROIStatus.NO_COSTS
    else:
        if not benefits.counted:
            reasons.append(EvidenceReason.NO_SUPPORTED_BENEFITS.value)
        if outcome_sample_size is not None:
            if outcome_sample_size == 0:
                reasons.append(EvidenceReason.NO_OUTCOME_DATA.value)
            elif outcome_sample_size < assumptions.min_sample_size:
                reasons.append(EvidenceReason.SAMPLE_TOO_SMALL.value)
        if period_days < assumptions.min_measurement_days:
            reasons.append(EvidenceReason.PERIOD_TOO_SHORT.value)
        status = ROIStatus.INSUFFICIENT_EVIDENCE if reasons else ROIStatus.OK
    if partial_evidence and status is ROIStatus.OK:
        reasons.append(EvidenceReason.PARTIAL_EVIDENCE.value)

    if estimated_time_value is not None:
        estimated_time_value = max(ZERO, estimated_time_value)

    cpst = total / successful_tasks if successful_tasks > 0 and total > 0 else None

    ok = status is ROIStatus.OK
    net = gross - total if ok else None
    roi = (gross - total) / total * HUNDRED if ok else None
    bcr = gross / total if ok else None

    scenarios = _scenarios(costs, benefits, estimated_time_value, assumptions) if ok else {}
    return ROIResult(
        status=status.value,
        reasons=reasons,
        costs=costs,
        benefits=benefits,
        hours=hours,
        successful_tasks=successful_tasks,
        period_days=period_days,
        estimated_time_value=estimated_time_value,
        gross_benefit=gross,
        net_benefit=net,
        roi_pct=roi,
        benefit_cost_ratio=bcr,
        cost_per_successful_task=cpst,
        break_even_tasks=_break_even_tasks(costs, gross, successful_tasks) if ok else None,
        payback_months=_payback_months(costs, gross, period_days) if ok else None,
        scenarios=scenarios,
    )


def _scenarios(
    costs: CostBreakdown,
    benefits: BenefitSelection,
    estimated_time_value: Optional[Decimal],
    a: Assumptions,
) -> dict[str, Scenario]:
    total = costs.total
    conservative_gross = benefits.verified_component + benefits.supported_component * (
        1 - a.conservative_benefit_haircut
    )
    optimistic_extra = (benefits.estimated + (estimated_time_value or ZERO)) * (
        a.optimistic_estimated_benefit_share
    )
    return {
        "conservative": Scenario(
            "conservative", conservative_gross, total * (1 + a.conservative_cost_contingency), False
        ),
        "expected": Scenario("expected", benefits.gross, total, False),
        "optimistic": Scenario(
            "optimistic", benefits.gross + optimistic_extra, total, optimistic_extra > 0
        ),
    }


def _break_even_tasks(
    costs: CostBreakdown, gross: Decimal, successful_tasks: int
) -> Optional[Decimal]:
    """Successful tasks needed for gross benefit to cover total cost.

    Assumes benefit and variable cost scale linearly per successful task and
    fixed costs (subscriptions, infrastructure, implementation, maintenance)
    do not. Returns ``None`` when each task loses money (break-even unreachable).
    """
    if successful_tasks <= 0:
        return None
    benefit_per_task = gross / successful_tasks
    variable_per_task = costs.variable / successful_tasks
    margin = benefit_per_task - variable_per_task
    if margin <= 0:
        return None
    fixed = costs.total - costs.variable
    return fixed / margin


def _payback_months(costs: CostBreakdown, gross: Decimal, period_days: int) -> Optional[Decimal]:
    """Months to recover one-off investment from the observed monthly net run-rate."""
    months = Decimal(period_days) / DAYS_PER_MONTH
    monthly_net = (gross - costs.recurring) / months
    if monthly_net <= 0:
        return None
    if costs.one_off <= 0:
        return ZERO
    return costs.one_off / monthly_net
