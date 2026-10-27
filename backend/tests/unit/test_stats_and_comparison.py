import random
from decimal import Decimal

import pytest

from aivanta_core import stats
from aivanta_core.comparison import Decision, compare
from aivanta_core.domain import Assumptions, StudyDesign
from aivanta_core.roi import BenefitSelection, CostBreakdown, HoursSaved, ROIResult
from tests.conftest import make_task

D = Decimal


def test_t_critical_values():
    assert stats.t_critical_95(10) == pytest.approx(2.228)
    assert stats.t_critical_95(5000) == pytest.approx(1.96, abs=1e-3)
    assert 2.0 < stats.t_critical_95(50) < 2.021
    with pytest.raises(ValueError):
        stats.t_critical_95(0)


def test_welch_interval_has_nominal_coverage():
    rng = random.Random(1)
    covered = 0
    for _ in range(400):
        a = [rng.gauss(10, 2) for _ in range(40)]
        b = [rng.gauss(12, 3) for _ in range(25)]
        i = stats.welch_difference(a, b)
        covered += i.low < -2 < i.high
    assert 0.92 <= covered / 400 <= 0.98


def test_welch_detects_clear_difference():
    rng = random.Random(1)
    i = stats.welch_difference([rng.gauss(10, 2) for _ in range(400)], [rng.gauss(12, 3) for _ in range(300)])
    assert i.excludes_zero and i.high < 0


def test_welch_needs_two_observations():
    assert stats.welch_difference([1.0], [1.0, 2.0]) is None


def test_proportion_difference():
    i = stats.proportion_difference(90, 100, 50, 100)
    assert i.estimate == pytest.approx(0.4)
    assert i.excludes_zero
    assert stats.proportion_difference(1, 0, 1, 1) is None


def test_study_design_causality():
    assert StudyDesign.RANDOMIZED.supports_causal_claim
    assert StudyDesign.CONTROL_GROUP.supports_causal_claim
    assert not StudyDesign.BEFORE_AFTER.supports_causal_claim
    assert not StudyDesign.OBSERVATIONAL.supports_causal_claim


# ------------------------------------------------------------------ decisions

def _tasks(n_ai, n_base, ai_min, base_min, ai_q=0.9, base_q=0.9, seed=7, task_type="standard"):
    rng = random.Random(seed)
    ai = [make_task(i, "ai", rng.gauss(ai_min, 1), quality_score=rng.gauss(ai_q, 0.02), task_type=task_type)
          for i in range(n_ai)]
    base = [make_task(i, "non_ai", rng.gauss(base_min, 1), quality_score=rng.gauss(base_q, 0.02),
                      task_type=task_type) for i in range(n_base)]
    return ai + base


def _roi(status="ok", net="100", verified="0"):
    sel = BenefitSelection(verified_component=D(verified))
    return ROIResult(status=status, reasons=[], costs=CostBreakdown(), benefits=sel,
                     hours=HoursSaved(0, None, None, None, None, None), successful_tasks=0, period_days=90,
                     estimated_time_value=None, gross_benefit=D(0),
                     net_benefit=D(net) if status == "ok" else None, roi_pct=None,
                     benefit_cost_ratio=None, cost_per_successful_task=None, break_even_tasks=None,
                     payback_months=None, scenarios={})


def run(tasks, *, design="randomized", ai_cost="0", roi=None):
    return compare(use_case_id="uc", study_design=design, tasks=tasks, hourly_rate=D("60"),
                   ai_cost=D(ai_cost), roi=roi, assumptions=Assumptions())


def test_continue_when_value_positive_and_causal():
    r = run(_tasks(100, 100, 10, 20), roi=_roi(net="500"))
    assert r.decision == Decision.CONTINUE.value
    assert r.cost_per_task_delta < 0 and r.estimated_net_benefit > 0


def test_experiment_when_sample_small():
    r = run(_tasks(10, 10, 10, 20), roi=_roi())
    assert r.decision == Decision.EXPERIMENT.value and "sample_too_small" in r.reasons


def test_experiment_when_only_association():
    r = run(_tasks(100, 100, 10, 20), design="before_after", roi=_roi(net="500"))
    assert r.decision == Decision.EXPERIMENT.value and "association_only" in r.reasons
    assert r.causal is False


def test_association_with_ledger_verified_savings_can_continue():
    r = run(_tasks(100, 100, 10, 20), design="observational", roi=_roi(net="500", verified="300"))
    assert r.decision == Decision.CONTINUE.value


def test_stop_when_quality_drops_and_not_cheaper():
    # AI is slower *and* worse; AI cost makes it more expensive per task.
    r = run(_tasks(100, 100, 25, 20, ai_q=0.7, base_q=0.9), ai_cost="500", roi=_roi(net="-100"))
    assert r.decision == Decision.STOP.value


def test_stop_when_no_time_or_cost_advantage():
    r = run(_tasks(100, 100, 20, 20), ai_cost="2000", roi=_roi(net="-100"))
    assert r.decision == Decision.STOP.value
    assert "no_time_or_cost_advantage" in r.reasons


def test_optimize_when_faster_but_too_expensive():
    r = run(_tasks(100, 100, 15, 20), ai_cost="2000", roi=_roi(net="-100"))
    assert r.decision == Decision.OPTIMIZE.value


def test_selective_when_one_task_type_is_favourable():
    good = _tasks(80, 80, 10, 30, ai_q=0.9, base_q=0.9, seed=1, task_type="short")
    bad = _tasks(80, 80, 40, 60, ai_q=0.5, base_q=0.9, seed=2, task_type="long")
    # make ids unique across the two groups
    for i, t in enumerate(bad):
        t.task_id = f"bad{i}"
    r = run(good + bad, roi=_roi(net="-10"))
    assert r.decision == Decision.SELECTIVE.value
    assert any(s.task_type == "short" and s.favourable for s in r.segments)
    assert any(s.task_type == "long" and not s.favourable for s in r.segments)


def test_never_assumes_ai_is_better():
    # Identical arms, no costs, no evidence of benefit: must not recommend continuing.
    r = run(_tasks(100, 100, 20, 20), roi=_roi(status="insufficient_evidence"))
    assert r.decision != Decision.CONTINUE.value
