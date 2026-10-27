"""End-to-end checks over the full synthetic dataset.

These are the "verify every dashboard metric" tests: every aggregate is
recomputed independently from the raw records and must match exactly.
"""
from datetime import date
from decimal import Decimal

import pytest

from aivanta_core import analytics as A
from aivanta_core import ingestion, recommendations, reporting, synthetic
from aivanta_core.comparison import Decision
from aivanta_core.pricing import PricingSchedule
from aivanta_core.roi import ROIStatus
from tests.conftest import SAMPLES

ZERO = Decimal(0)


# ------------------------------------------------------------- dataset shape

def test_dataset_meets_spec(demo):
    assert (demo.period_end - demo.period_start).days + 1 >= 90
    assert len({e.provider for e in demo.usage_events}) == 3
    assert len({(e.provider, e.model) for e in demo.usage_events}) >= 4
    assert {d.department_id for d in demo.departments} == {
        "engineering", "customer_support", "sales", "marketing", "finance_operations"}
    assert len(demo.use_cases) >= 5
    assert any(t.arm == "ai" for t in demo.tasks) and any(t.arm == "non_ai" for t in demo.tasks)
    assert demo.is_synthetic
    assert all(e.cost is not None for e in demo.usage_events)


def test_generation_is_reproducible():
    a, b = synthetic.generate(seed=42, days=20), synthetic.generate(seed=42, days=20)
    assert [(e.event_id, e.cost, e.input_tokens) for e in a.usage_events] == \
           [(e.event_id, e.cost, e.input_tokens) for e in b.usage_events]
    assert [(t.task_id, t.duration_minutes) for t in a.tasks] == [(t.task_id, t.duration_minutes) for t in b.tasks]
    c = synthetic.generate(seed=43, days=20)
    assert [e.input_tokens for e in a.usage_events] != [e.input_tokens for e in c.usage_events]


def test_mid_period_price_change_is_applied(demo):
    big = [e for e in demo.usage_events if e.model == "gpt-demo-large"]
    sched = PricingSchedule(demo.pricing)
    early = next(e for e in big if e.occurred_at.date() < date(2026, 8, 15))
    late = next(e for e in big if e.occurred_at.date() >= date(2026, 8, 15))
    assert sched.rule_for("openai", "gpt-demo-large", early.occurred_at.date()).input_per_mtok == Decimal("5.00")
    assert sched.rule_for("openai", "gpt-demo-large", late.occurred_at.date()).input_per_mtok == Decimal("4.00")


# ------------------------------------------------------------- reconciliation

def test_totals_reconcile_with_raw_events(demo):
    f = A.Filters()
    o = A.overview(demo, f)
    u = o["usage"]
    assert u.spend == sum((e.cost for e in demo.usage_events), ZERO)
    assert u.input_tokens == sum(e.input_tokens for e in demo.usage_events)
    assert u.output_tokens == sum(e.output_tokens for e in demo.usage_events)
    assert u.requests == sum(e.request_count for e in demo.usage_events)
    assert len(u.users) == len({e.user_id for e in demo.usage_events if e.user_id})


@pytest.mark.parametrize("dimension", A.DIMENSIONS)
def test_breakdowns_sum_to_total(demo, dimension):
    f = A.Filters()
    rows = A.breakdown(demo, f, dimension)
    assert sum((r["spend"] for r in rows), ZERO) == A.overview(demo, f)["usage"].spend
    assert sum(r["requests"] for r in rows) == sum(e.request_count for e in demo.usage_events)
    assert abs(sum(r["share"] for r in rows) - 1) < Decimal("1e-20")


def test_unallocated_usage_is_explicit(demo):
    rows = {r["key"]: r for r in A.breakdown(demo, A.Filters(), "department")}
    raw = sum((e.cost for e in demo.usage_events if e.department_id is None), ZERO)
    assert rows[A.UNALLOCATED]["spend"] == raw > 0
    uc_rows = {r["key"]: r for r in A.breakdown(demo, A.Filters(), "use_case")}
    assert uc_rows[A.UNALLOCATED]["spend"] == sum(
        (e.cost for e in demo.usage_events if e.use_case_id is None), ZERO)


def test_daily_trend_reconciles(demo):
    trend = A.daily_trend(demo, A.Filters())
    assert len(trend) == 90
    assert sum((d["spend"] for d in trend), ZERO) == A.overview(demo, A.Filters())["usage"].spend


def test_filters_partition_spend(demo):
    total = A.overview(demo, A.Filters())["usage"].spend
    by_provider = sum((A.overview(demo, A.Filters(providers=frozenset({p})))["usage"].spend
                       for p in ("openai", "anthropic", "google")), ZERO)
    assert by_provider == total
    sept = A.Filters(start=date(2026, 9, 1), end=date(2026, 9, 30))
    assert A.overview(demo, sept)["usage"].spend == sum(
        (e.cost for e in demo.usage_events if e.occurred_at.date() >= date(2026, 9, 1)), ZERO)


def test_org_roi_equals_formula(demo):
    r = A.overview(demo, A.Filters())["scope"].roi
    assert r.status == ROIStatus.OK.value
    assert r.net_benefit == r.gross_benefit - r.costs.total
    assert r.roi_pct == (r.gross_benefit - r.costs.total) / r.costs.total * 100
    # org cost includes shared org costs and unallocated usage
    assert r.costs.model_usage == A.overview(demo, A.Filters())["usage"].spend
    assert "partial_evidence" in r.reasons


def test_use_case_costs_plus_shared_equal_org_cost(demo):
    f = A.Filters()
    org = A.overview(demo, f)["scope"].roi.costs
    uc_total = sum((A.use_case_analysis(demo, u.use_case_id, f)[0].roi.costs.total for u in demo.use_cases), ZERO)
    start, end = f.period(demo)
    from aivanta_core.roi import prorated_amount
    shared_items = sum((prorated_amount(c, start, end) for c in demo.cost_items if c.use_case_id is None), ZERO)
    no_uc_usage = sum((e.cost for e in demo.usage_events if e.use_case_id is None), ZERO)
    assert uc_total + shared_items + no_uc_usage == org.total


def test_department_costs_reconcile(demo):
    rows = A.department_summaries(demo, A.Filters())
    org = A.overview(demo, A.Filters())["scope"].roi.costs.total
    start, end = A.Filters().period(demo)
    from aivanta_core.roi import prorated_amount
    org_shared = sum((prorated_amount(c, start, end) for c in demo.cost_items
                      if c.use_case_id is None and c.department_id is None), ZERO)
    assert sum((r["total_cost"] for r in rows), ZERO) + org_shared == org


# ------------------------------------------------------------- stories

EXPECTED_DECISIONS = {
    "support_triage": Decision.CONTINUE,
    "code_review": Decision.CONTINUE,
    "sales_outreach": Decision.OPTIMIZE,
    "marketing_content": Decision.SELECTIVE,
    "invoice_matching": Decision.EXPERIMENT,
}


@pytest.mark.parametrize("uc_id, decision", EXPECTED_DECISIONS.items())
def test_use_case_stories(demo, uc_id, decision):
    s, cmp = A.use_case_analysis(demo, uc_id, A.Filters())
    assert cmp.decision == decision.value, cmp.reasons


def test_insufficient_evidence_use_case_has_no_roi(demo):
    s, _ = A.use_case_analysis(demo, "invoice_matching", A.Filters())
    assert s.roi.status == ROIStatus.INSUFFICIENT_EVIDENCE.value
    assert s.roi.roi_pct is None


def test_duplicate_support_claim_is_not_double_counted(demo):
    s, _ = A.use_case_analysis(demo, "support_triage", A.Filters())
    dup = [e for e in s.roi.benefits.excluded if e.reason == "duplicate_evidence"]
    assert len(dup) == 3  # one per month
    assert all(e.claim.verification_status == "estimated" for e in dup)


def test_time_improves_but_quality_drops_in_marketing(demo):
    _, cmp = A.use_case_analysis(demo, "marketing_content", A.Filters())
    assert cmp.minutes.estimate < 0 and cmp.minutes.significant
    assert cmp.quality.estimate < 0 and cmp.quality.significant


def test_budget_and_anomaly(demo):
    budgets = {b["department_id"]: b for b in A.budget_status(demo, demo.period_end)}
    assert budgets["sales"]["status"] == "exceeded"
    assert budgets["customer_support"]["status"] == "ok"
    anomalies = A.anomalies(demo, A.Filters())
    assert [a["date"] for a in anomalies] == [date(2026, 9, 12)]


def test_all_recommendation_rules_explain_themselves(demo):
    recs = recommendations.generate(demo, A.Filters(), PricingSchedule(demo.pricing))
    ids = {r.rule_id for r in recs}
    assert {"budget_exceeded", "cheaper_model", "high_tokens_low_quality", "review_erasing_gains",
            "spend_without_improvement", "unallocated_usage", "needs_outcome_tracking",
            "expansion_candidate", "restrict_to_task_types", "spend_anomaly"} <= ids
    for r in recs:
        assert r.metrics, r.rule_id
        if r.projected_monthly_saving is not None:
            assert r.is_estimate


def test_adoption_trend_grows(demo):
    weeks = A.adoption(demo, A.Filters())
    assert weeks[-2]["adoption_rate"] > weeks[1]["adoption_rate"]
    assert all(0 <= w["adoption_rate"] <= 1 for w in weeks)


# ------------------------------------------------------------- ingestion → analytics

def test_ingested_events_flow_into_analytics(demo):
    import copy
    ds = copy.deepcopy(synthetic.generate(days=10))
    known = {(r.provider, r.model) for r in ds.pricing}
    res = ingestion.parse("aivanta_csv", (SAMPLES / "aivanta_usage.csv").read_text(), known_models=known)
    ds.period_end = date(2026, 9, 30)
    for e in res.events:  # sample is dated 28 Sep, inside the 10-day window
        assert ds.period_start <= e.occurred_at.date() <= ds.period_end
    before = A.overview(ds, A.Filters())["usage"].spend
    PricingSchedule(ds.pricing).price_events(res.events)
    ds.usage_events.extend(res.events)
    after = A.overview(ds, A.Filters())["usage"].spend
    assert after - before == sum((e.cost for e in res.events), ZERO) > 0


# ------------------------------------------------------------- reports

@pytest.mark.parametrize("locale, sep, synthetic_word", [("en", ",", "Synthetic"), ("es", ";", "sintéticos")])
def test_localized_reports(demo, locale, sep, synthetic_word):
    csv_text = reporting.roi_summary_csv(demo, A.Filters(), locale)
    assert synthetic_word in csv_text.splitlines()[0]
    header = next(line for line in csv_text.splitlines() if not line.startswith("#"))
    assert header.count(sep) == 15
    if locale == "es":
        assert "Conciliación de facturas" in csv_text and "Evidencia insuficiente" in csv_text
        assert "," in csv_text.splitlines()[-1]  # decimal comma
    usage = reporting.usage_breakdown_csv(demo, A.Filters(), "department", locale)
    assert ("Sin asignar" if locale == "es" else "Unallocated") in usage


def test_report_locales_have_identical_keys():
    assert reporting.messages("en").keys() == reporting.messages("es").keys()
    with pytest.raises(ValueError):
        reporting.messages("fr")


def test_number_formatting():
    assert reporting.fmt_number(Decimal("1234.567"), "en") == "1234.57"
    assert reporting.fmt_number(Decimal("1234.567"), "es") == "1234,57"
    assert reporting.fmt_number(None, "es") == ""
    assert reporting.fmt_number(7, "es") == "7"
