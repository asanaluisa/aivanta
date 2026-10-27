from datetime import date
from decimal import Decimal

import pytest

from aivanta_core.domain import Assumptions, BenefitClaim, CostItem
from aivanta_core.roi import (
    BenefitSelection,
    CostBreakdown,
    HoursSaved,
    ROIStatus,
    build_cost_breakdown,
    compute_hours_saved,
    compute_roi,
    prorated_amount,
    select_benefits,
    time_value,
)
from tests.conftest import make_event, make_task

D = Decimal
P0, P1 = date(2026, 7, 1), date(2026, 9, 28)  # 90 days


def claim(i, category, amount, status, key=None, start=P0, end=P1):
    return BenefitClaim(f"b{i}", "uc", category, D(amount), status, key or f"k{i}", start, end)


# ----------------------------------------------------------------- benefits

def test_gross_benefit_formula():
    sel = select_benefits([
        claim(1, "financial_savings", "1000", "verified"),
        claim(2, "incremental_contribution", "500", "supported"),
        claim(3, "cost_avoidance", "300", "supported"),
        claim(4, "cost_avoidance", "200", "verified"),
    ])
    assert sel.verified_savings == D("1000")
    assert sel.supported_contribution == D("500")
    assert sel.supported_cost_avoidance == D("500")
    assert sel.gross == D("2000")
    assert sel.verified_component == D("1200")
    assert sel.supported_component == D("800")


def test_estimates_and_unverified_never_enter_gross():
    sel = select_benefits([
        claim(1, "incremental_contribution", "9000", "estimated"),
        claim(2, "cost_avoidance", "9000", "unverified"),
        claim(3, "financial_savings", "9000", "supported"),  # savings must be verified
    ])
    assert sel.gross == 0
    assert sel.estimated == D("27000")
    assert {e.reason for e in sel.excluded} == {"estimate_only", "unverified", "savings_not_verified"}


def test_double_counting_prevented_by_evidence_key():
    sel = select_benefits([
        claim(1, "cost_avoidance", "14000", "supported", key="same"),
        claim(2, "financial_savings", "15000", "estimated", key="same"),
        claim(3, "financial_savings", "14000", "verified", key="same"),
    ])
    # Only the strongest claim (verified) counts; the others are duplicates.
    assert sel.gross == D("14000")
    assert [c.benefit_id for c in sel.counted] == ["b3"]
    assert sorted(e.reason for e in sel.excluded) == ["duplicate_evidence", "duplicate_evidence"]
    assert sel.estimated == 0


def test_same_claim_id_counted_once():
    c = claim(1, "financial_savings", "100", "verified")
    assert select_benefits([c, c]).gross == D("100")


def test_claims_prorated_and_period_filtered():
    sel = select_benefits(
        [claim(1, "financial_savings", "3000", "verified", start=date(2026, 9, 1), end=date(2026, 9, 30)),
         claim(2, "financial_savings", "999", "verified", start=date(2026, 1, 1), end=date(2026, 1, 31))],
        date(2026, 9, 1), date(2026, 9, 10))
    assert sel.gross == D("1000")  # 10 of 30 days
    assert [e.reason for e in sel.excluded] == ["outside_period"]


def test_negative_benefit_rejected():
    with pytest.raises(ValueError):
        select_benefits([claim(1, "financial_savings", "-1", "verified")])


# ----------------------------------------------------------------- costs

def test_cost_breakdown_all_categories():
    events = [make_event(event_id="a", cost=D("10")), make_event(event_id="b", cost=D("5"))]
    items = [
        CostItem("c1", "subscription", D("3000"), P0, P1),  # whole period
        CostItem("c2", "implementation", D("5000"), P0, P0, one_off=True),
        CostItem("c3", "infrastructure", D("900"), date(2026, 6, 2), date(2026, 7, 1)),  # 1 of 30 days
    ]
    tasks = [make_task(1, review_minutes=30, rework_minutes=60)]
    c = build_cost_breakdown(events=events, cost_items=items, ai_tasks=tasks,
                             hourly_rate_for=lambda t: D("60"), period_start=P0, period_end=P1)
    assert c.model_usage == D("15")
    assert c.subscription == D("3000")
    assert c.implementation == D("5000")
    assert c.infrastructure == D("30")
    assert c.human_review == D("30")
    assert c.rework == D("60")
    assert c.total == D("8135")
    assert c.one_off == D("5000") and c.recurring == D("3135")


def test_review_charged_incrementally_over_baseline():
    tasks = [make_task(i, review_minutes=10, rework_minutes=2) for i in range(3)]
    c = build_cost_breakdown(events=[], cost_items=[], ai_tasks=tasks, hourly_rate_for=lambda t: D("60"),
                             period_start=P0, period_end=P1,
                             baseline_review_rework=lambda uc: (4.0, 5.0))
    assert c.human_review == D("18")  # (10-4) min * 3 tasks * €1/min
    assert c.rework == D("0")  # below baseline → floored at zero, never negative


def test_derived_categories_cannot_be_entered_manually():
    with pytest.raises(ValueError):
        build_cost_breakdown(events=[], cost_items=[CostItem("x", "model_usage", D("1"), P0, P1)],
                             ai_tasks=[], hourly_rate_for=lambda t: D("1"), period_start=P0, period_end=P1)


def test_unpriced_event_rejected():
    with pytest.raises(ValueError):
        build_cost_breakdown(events=[make_event()], cost_items=[], ai_tasks=[],
                             hourly_rate_for=lambda t: D("1"), period_start=P0, period_end=P1)


def test_one_off_outside_period_excluded():
    item = CostItem("c", "implementation", D("100"), date(2026, 6, 1), date(2026, 6, 1), one_off=True)
    assert prorated_amount(item, P0, P1) == 0


# ----------------------------------------------------------------- hours

def test_hours_saved_against_control_group():
    ai = [make_task(i, minutes=10, review_minutes=2) for i in range(6)]
    base = [make_task(i, "non_ai", minutes=30) for i in range(4)]
    h = compute_hours_saved(ai, base)
    assert h.gross_hours == pytest.approx(6 * 20 / 60)
    assert h.net_hours == pytest.approx(6 * 18 / 60)
    assert h.baseline_source == "control_group"
    assert time_value(h, D("60")) == D("120.0")


def test_hours_saved_documented_baseline_and_missing_baseline():
    ai = [make_task(i, minutes=15) for i in range(2)]
    assert compute_hours_saved(ai, [], 20).gross_hours == pytest.approx(2 * 5 / 60)
    assert compute_hours_saved(ai, []).gross_hours is None


# ----------------------------------------------------------------- ROI

def _costs(total="1000", impl="0"):
    c = CostBreakdown(model_usage=D("100"), subscription=D(total) - D("100") - D(impl),
                      implementation=D(impl))
    assert c.total == D(total)
    return c


def _benefits(verified="1500", supported="500"):
    return select_benefits([claim(1, "financial_savings", verified, "verified"),
                            claim(2, "cost_avoidance", supported, "supported")])


def _hours():
    return HoursSaved(100, 30, 10, 33.3, 30.0, "control_group")


def test_roi_formulas():
    r = compute_roi(costs=_costs("1000"), benefits=_benefits(), hours=_hours(), successful_tasks=50,
                    period_start=P0, period_end=P1, assumptions=Assumptions(), outcome_sample_size=100)
    assert r.status == ROIStatus.OK.value
    assert r.gross_benefit == D("2000")
    assert r.net_benefit == D("1000")
    assert r.roi_pct == D("100")
    assert r.benefit_cost_ratio == D("2")
    assert r.cost_per_successful_task == D("20")


def test_roi_negative_is_reported_not_hidden():
    r = compute_roi(costs=_costs("4000"), benefits=_benefits(), hours=_hours(), successful_tasks=50,
                    period_start=P0, period_end=P1, assumptions=Assumptions(), outcome_sample_size=100)
    assert r.roi_pct == D("-50")
    assert r.net_benefit == D("-2000")


@pytest.mark.parametrize("sample, start, benefits, reason", [
    (5, P0, None, "sample_too_small"),
    (0, P0, None, "no_outcome_data"),
    (100, date(2026, 9, 20), None, "period_too_short"),
    (100, P0, BenefitSelection(), "no_supported_benefits"),
])
def test_insufficient_evidence_returns_status_not_a_number(sample, start, benefits, reason):
    r = compute_roi(costs=_costs(), benefits=benefits or _benefits(), hours=_hours(), successful_tasks=5,
                    period_start=start, period_end=P1, assumptions=Assumptions(),
                    outcome_sample_size=sample)
    assert r.status == ROIStatus.INSUFFICIENT_EVIDENCE.value
    assert reason in r.reasons
    assert r.roi_pct is None and r.net_benefit is None and r.benefit_cost_ratio is None
    assert r.scenarios == {}
    assert r.costs.total == D("1000")  # costs are still reported


def test_no_costs_status():
    r = compute_roi(costs=CostBreakdown(), benefits=_benefits(), hours=_hours(), successful_tasks=1,
                    period_start=P0, period_end=P1, assumptions=Assumptions())
    assert r.status == ROIStatus.NO_COSTS.value and r.roi_pct is None


def test_scenarios():
    a = Assumptions()
    r = compute_roi(costs=_costs("1000"), benefits=_benefits("1500", "500"), hours=_hours(),
                    successful_tasks=50, period_start=P0, period_end=P1, assumptions=a,
                    estimated_time_value=D("400"))
    cons, exp, opt = r.scenarios["conservative"], r.scenarios["expected"], r.scenarios["optimistic"]
    assert cons.gross_benefit == D("1500") + D("500") * D("0.70")
    assert cons.total_cost == D("1100")
    assert exp.gross_benefit == D("2000") and exp.roi_pct == r.roi_pct
    assert opt.gross_benefit == D("2000") + D("400") * D("0.5")
    assert opt.includes_estimates and not exp.includes_estimates and not cons.includes_estimates
    assert cons.roi_pct < exp.roi_pct < opt.roi_pct


def test_time_value_is_never_in_gross_benefit():
    r = compute_roi(costs=_costs("1000"), benefits=_benefits(), hours=_hours(), successful_tasks=50,
                    period_start=P0, period_end=P1, assumptions=Assumptions(),
                    estimated_time_value=D("100000"))
    assert r.gross_benefit == D("2000")
    assert r.roi_pct == D("100")


def test_break_even_and_payback():
    costs = CostBreakdown(model_usage=D("200"), subscription=D("300"), implementation=D("500"))
    r = compute_roi(costs=costs, benefits=_benefits("1500", "500"), hours=_hours(), successful_tasks=100,
                    period_start=P0, period_end=P1, assumptions=Assumptions())
    # benefit/task 20, variable/task 2, fixed 800 → 800/18 tasks
    assert r.break_even_tasks == D("800") / D("18")
    # months = 90/30.4375; monthly net run-rate = (2000-500)/months; payback = 500/that
    months = D(90) / D("30.4375")
    assert r.payback_months == D("500") / (D("1500") / months)


def test_payback_none_when_run_rate_negative_and_zero_without_investment():
    neg = compute_roi(costs=_costs("5000"), benefits=_benefits(), hours=_hours(), successful_tasks=5,
                      period_start=P0, period_end=P1, assumptions=Assumptions())
    assert neg.payback_months is None
    pos = compute_roi(costs=_costs("1000"), benefits=_benefits(), hours=_hours(), successful_tasks=5,
                      period_start=P0, period_end=P1, assumptions=Assumptions())
    assert pos.payback_months == 0


def test_break_even_unreachable_when_each_task_loses_money():
    costs = CostBreakdown(model_usage=D("5000"))
    r = compute_roi(costs=costs, benefits=_benefits("1000", "0"), hours=_hours(), successful_tasks=10,
                    period_start=P0, period_end=P1, assumptions=Assumptions())
    assert r.break_even_tasks is None


def test_engine_is_deterministic():
    kw = dict(costs=_costs("1234.56"), benefits=_benefits(), hours=_hours(), successful_tasks=77,
              period_start=P0, period_end=P1, assumptions=Assumptions(), estimated_time_value=D("10"))
    a, b = compute_roi(**kw), compute_roi(**kw)
    assert (a.roi_pct, a.payback_months, a.break_even_tasks) == (b.roi_pct, b.payback_months, b.break_even_tasks)
