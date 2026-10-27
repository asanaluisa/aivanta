"""AI-assisted versus non-AI workflow comparison.

For each use case the engine compares the two arms on cost per completed task
(total cost of ownership, i.e. labour *plus* AI costs for the AI arm),
completion time, throughput, quality, error and rework rates and customer
satisfaction, with sample sizes, observation periods and 95 % intervals.

It then returns exactly one of five decisions. The rules never assume AI is
better: the default when evidence is weak is to run an experiment.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional, Sequence

from . import stats
from .domain import ZERO, Assumptions, StudyDesign, TaskArm, TaskRecord
from .roi import ROIResult, ROIStatus

SIXTY = Decimal(60)


class Decision(str, Enum):
    CONTINUE = "continue"  # 1. measured value is positive
    OPTIMIZE = "optimize"  # 2. optimize model or workflow
    SELECTIVE = "selective"  # 3. use AI only for selected task types
    EXPERIMENT = "experiment"  # 4. evidence inconclusive: run a controlled experiment
    STOP = "stop"  # 5. costs or quality trade-offs outweigh benefits


@dataclass
class ArmStats:
    arm: str
    n: int
    first_day: Optional[date]
    last_day: Optional[date]
    mean_minutes: Optional[float]
    mean_total_minutes: Optional[float]  # duration + review + rework
    success_rate: Optional[float]
    error_rate: Optional[float]
    rework_rate: Optional[float]
    mean_quality: Optional[float]
    mean_csat: Optional[float]
    tasks_per_hour: Optional[float]
    labour_cost: Decimal
    ai_cost: Decimal
    successes: int

    @property
    def total_cost(self) -> Decimal:
        return self.labour_cost + self.ai_cost

    @property
    def cost_per_completed_task(self) -> Optional[Decimal]:
        return self.total_cost / self.successes if self.successes else None


@dataclass
class Difference:
    """AI minus non-AI, with a 95 % interval when computable."""

    estimate: Optional[float]
    low: Optional[float]
    high: Optional[float]

    @property
    def significant(self) -> bool:
        return self.low is not None and self.high is not None and (self.low > 0 or self.high < 0)

    @classmethod
    def of(cls, interval: Optional[stats.Interval]) -> "Difference":
        if interval is None:
            return cls(None, None, None)
        return cls(interval.estimate, interval.low, interval.high)


@dataclass
class SegmentResult:
    task_type: str
    n_ai: int
    n_non_ai: int
    minutes: Difference
    quality: Difference
    favourable: bool


@dataclass
class ComparisonResult:
    use_case_id: str
    study_design: str
    causal: bool
    ai: ArmStats
    non_ai: ArmStats
    minutes: Difference
    quality: Difference
    success_rate: Difference
    error_rate: Difference
    cost_per_task_delta: Optional[Decimal]  # AI − non-AI, TCO per completed task
    estimated_net_benefit: Optional[Decimal]  # estimate: per-task TCO saving × AI successes
    segments: list[SegmentResult]
    decision: str
    reasons: list[str] = field(default_factory=list)


def arm_stats(
    tasks: Sequence[TaskRecord], arm: str, hourly_rate: Decimal, ai_cost: Decimal = ZERO
) -> ArmStats:
    n = len(tasks)
    if n == 0:
        return ArmStats(arm, 0, None, None, None, None, None, None, None, None, None, None,
                        ZERO, ai_cost, 0)
    successes = sum(1 for t in tasks if t.success)
    total_minutes = [t.duration_minutes + t.review_minutes + t.rework_minutes for t in tasks]
    q = [t.quality_score for t in tasks if t.quality_score is not None]
    cs = [t.customer_satisfaction for t in tasks if t.customer_satisfaction is not None]
    mean_total = sum(total_minutes) / n
    labour = Decimal(str(sum(total_minutes))) / SIXTY * hourly_rate
    return ArmStats(
        arm=arm,
        n=n,
        first_day=min(t.completed_on for t in tasks),
        last_day=max(t.completed_on for t in tasks),
        mean_minutes=sum(t.duration_minutes for t in tasks) / n,
        mean_total_minutes=mean_total,
        success_rate=successes / n,
        error_rate=sum(1 for t in tasks if t.had_error) / n,
        rework_rate=sum(1 for t in tasks if t.rework_minutes > 0) / n,
        mean_quality=stats.mean(q),
        mean_csat=stats.mean(cs),
        tasks_per_hour=60 / mean_total if mean_total > 0 else None,
        labour_cost=labour,
        ai_cost=ai_cost,
        successes=successes,
    )


def _quality(tasks: Sequence[TaskRecord]) -> list[float]:
    return [t.quality_score for t in tasks if t.quality_score is not None]


def _segments(
    ai: Sequence[TaskRecord], non_ai: Sequence[TaskRecord], a: Assumptions
) -> list[SegmentResult]:
    types = sorted({t.task_type for t in ai} | {t.task_type for t in non_ai})
    out = []
    for tt in types:
        sa = [t for t in ai if t.task_type == tt]
        sb = [t for t in non_ai if t.task_type == tt]
        minutes = Difference.of(stats.welch_difference(
            [t.duration_minutes + t.review_minutes + t.rework_minutes for t in sa],
            [t.duration_minutes + t.review_minutes + t.rework_minutes for t in sb],
        ))
        quality = Difference.of(stats.welch_difference(_quality(sa), _quality(sb)))
        enough = len(sa) >= a.min_sample_size and len(sb) >= a.min_sample_size
        faster = minutes.significant and (minutes.estimate or 0) < 0
        quality_ok = quality.estimate is None or quality.estimate >= -a.quality_tolerance
        out.append(SegmentResult(tt, len(sa), len(sb), minutes, quality,
                                 favourable=enough and faster and quality_ok))
    return out


def compare(
    *,
    use_case_id: str,
    study_design: str,
    tasks: Sequence[TaskRecord],
    hourly_rate: Decimal,
    ai_cost: Decimal,
    roi: Optional[ROIResult],
    assumptions: Assumptions,
) -> ComparisonResult:
    """Compare arms for one use case and decide what to do.

    ``ai_cost`` is the use case's total AI-related cost *excluding* human
    review and rework (those are labour and already in the arm's minutes).
    """
    ai_tasks = [t for t in tasks if t.arm == TaskArm.AI.value]
    base_tasks = [t for t in tasks if t.arm == TaskArm.NON_AI.value]
    a_stats = arm_stats(ai_tasks, TaskArm.AI.value, hourly_rate, ai_cost)
    b_stats = arm_stats(base_tasks, TaskArm.NON_AI.value, hourly_rate)

    minutes = Difference.of(stats.welch_difference(
        [t.duration_minutes + t.review_minutes + t.rework_minutes for t in ai_tasks],
        [t.duration_minutes + t.review_minutes + t.rework_minutes for t in base_tasks],
    ))
    quality = Difference.of(stats.welch_difference(_quality(ai_tasks), _quality(base_tasks)))
    success = Difference.of(stats.proportion_difference(
        a_stats.successes, a_stats.n, b_stats.successes, b_stats.n))
    errors = Difference.of(stats.proportion_difference(
        sum(t.had_error for t in ai_tasks), a_stats.n,
        sum(t.had_error for t in base_tasks), b_stats.n))

    cpt_a, cpt_b = a_stats.cost_per_completed_task, b_stats.cost_per_completed_task
    delta = cpt_a - cpt_b if cpt_a is not None and cpt_b is not None else None
    est_net = -delta * a_stats.successes if delta is not None else None
    segments = _segments(ai_tasks, base_tasks, assumptions)
    design = StudyDesign(study_design)

    decision, reasons = decide(
        a=assumptions, ai=a_stats, non_ai=b_stats, minutes=minutes, quality=quality,
        cost_delta=delta, roi=roi, design=design, segments=segments,
    )
    return ComparisonResult(
        use_case_id=use_case_id,
        study_design=design.value,
        causal=design.supports_causal_claim,
        ai=a_stats,
        non_ai=b_stats,
        minutes=minutes,
        quality=quality,
        success_rate=success,
        error_rate=errors,
        cost_per_task_delta=delta,
        estimated_net_benefit=est_net,
        segments=segments,
        decision=decision.value,
        reasons=reasons,
    )


def decide(
    *,
    a: Assumptions,
    ai: ArmStats,
    non_ai: ArmStats,
    minutes: Difference,
    quality: Difference,
    cost_delta: Optional[Decimal],
    roi: Optional[ROIResult],
    design: StudyDesign,
    segments: Sequence[SegmentResult],
) -> tuple[Decision, list[str]]:
    reasons: list[str] = []

    # 1. Not enough data in either arm: we cannot say anything yet.
    if ai.n < a.min_sample_size or non_ai.n < a.min_sample_size or minutes.estimate is None:
        reasons.append("sample_too_small")
        if not design.supports_causal_claim:
            reasons.append("no_control_group")
        return Decision.EXPERIMENT, reasons

    quality_worse = (
        quality.estimate is not None
        and quality.estimate < -a.quality_tolerance
        and quality.significant
    )
    cheaper = cost_delta is not None and cost_delta < 0
    roi_ok = roi is not None and roi.status == ROIStatus.OK.value
    roi_positive = roi_ok and roi.net_benefit is not None and roi.net_benefit > 0
    favourable = [s.task_type for s in segments if s.favourable]

    if quality_worse:
        reasons.append("quality_declined")
        if favourable and len(favourable) < len(segments):
            reasons.append("favourable_segments:" + ",".join(favourable))
            return Decision.SELECTIVE, reasons
        if not cheaper or (roi_ok and not roi_positive):
            reasons.append("costs_or_quality_outweigh_benefits")
            return Decision.STOP, reasons
        reasons.append("cheaper_but_lower_quality")
        return Decision.OPTIMIZE, reasons

    if not design.supports_causal_claim and not (roi_ok and roi.benefits.verified_component > 0):
        # Association only and nothing reconciled to the ledger.
        reasons.append("association_only")
        return Decision.EXPERIMENT, reasons

    if roi_positive and cheaper:
        reasons.append("positive_measured_value")
        return Decision.CONTINUE, reasons

    if roi is not None and roi.status == ROIStatus.INSUFFICIENT_EVIDENCE.value and cheaper:
        reasons.append("benefits_not_yet_evidenced")
        return Decision.EXPERIMENT, reasons

    if not cheaper and not (minutes.significant and (minutes.estimate or 0) < 0):
        reasons.append("no_time_or_cost_advantage")
        return Decision.STOP, reasons

    reasons.append("cost_exceeds_value" if not cheaper else "roi_not_positive")
    return Decision.OPTIMIZE, reasons
