"""Every API payload is JSON-serializable and consistent with the engines."""
import json
from datetime import date
from decimal import Decimal

import pytest

from aivanta_core import analytics as A
from aivanta_core import serialize as S
from aivanta_core.domain import Assumptions


def dumps(payload):
    return json.dumps(payload, allow_nan=False)  # raises on Decimal/date/NaN leaks


def test_all_payloads_serialize(demo):
    f = A.Filters()
    dumps(S.all_dashboard(demo, f))
    dumps(S.departments_payload(demo, f))
    dumps(S.use_cases_payload(demo, f))
    dumps(S.recommendations_payload(demo, f))
    dumps(S.meta_payload(demo))
    for uc in demo.use_cases:
        dumps(S.use_case_payload(demo, uc.use_case_id, f))


def test_overview_kpis_have_basis_and_definitions(demo):
    o = S.overview_payload(demo, A.Filters())
    assert o["synthetic"] is True
    for name, k in o["kpis"].items():
        assert k["basis"] in {"measured", "evidence_backed", "estimated"}, name
        assert k["definition_key"].startswith("metric."), name
    assert o["kpis"]["estimated_total_value"]["basis"] == "estimated"
    assert o["kpis"]["roi_pct"]["value"] == o["roi"]["roi_pct"]


def test_model_filter_disables_roi(demo):
    o = S.overview_payload(demo, A.Filters(providers=frozenset({"openai"})))
    assert o["roi_applicable"] is False
    assert o["kpis"]["roi_pct"]["value"] is None and o["roi"] is None
    assert o["roi_status"] == "not_applicable_for_filter"
    assert o["kpis"]["ai_spend"]["value"] > 0


def test_insufficient_use_case_payload(demo):
    p = S.use_case_payload(demo, "invoice_matching", A.Filters())
    assert p["roi"]["status"] == "insufficient_evidence"
    assert p["roi"]["roi_pct"] is None and p["roi"]["net_benefit"] is None
    assert p["comparison"]["decision"] == "experiment"
    assert p["comparison"]["non_ai"]["n"] == 0


def test_unknown_use_case():
    from aivanta_core import synthetic
    with pytest.raises(KeyError):
        S.use_case_payload(synthetic.generate(days=5), "nope", A.Filters())


def test_parse_filters():
    f = S.parse_filters({"start": "2026-09-01", "end": "2026-09-30", "departments": "sales, marketing",
                         "providers": "", "models": None, "use_cases": "sales_outreach"})
    assert f.start == date(2026, 9, 1) and f.department_ids == {"sales", "marketing"}
    assert f.providers == frozenset() and f.use_case_ids == {"sales_outreach"}
    with pytest.raises(ValueError):
        S.parse_filters({"start": "2026-13-01"})
    with pytest.raises(ValueError):
        S.parse_filters({"start": "2026-09-02", "end": "2026-09-01"})


def test_clamp_filters(demo):
    f = S.clamp_filters(demo, A.Filters(start=date(2020, 1, 1), end=date(2030, 1, 1)))
    assert (f.start, f.end) == (demo.period_start, demo.period_end)


def test_apply_assumptions_validates():
    a = S.apply_assumptions(Assumptions(), {"min_sample_size": "50", "conservative_benefit_haircut": 0.5})
    assert a.min_sample_size == 50 and a.conservative_benefit_haircut == Decimal("0.5")
    with pytest.raises(ValueError):
        S.apply_assumptions(Assumptions(), {"unknown": 1})
    with pytest.raises(ValueError):
        S.apply_assumptions(Assumptions(), {"conservative_benefit_haircut": 2})
    with pytest.raises(ValueError):
        S.apply_assumptions(Assumptions(), {"anomaly_sigma": "abc"})


def test_assumptions_change_results(demo):
    import copy
    ds = copy.copy(demo)
    ds.assumptions = S.apply_assumptions(demo.assumptions, {"min_sample_size": 100_000})
    p = S.use_case_payload(ds, "support_triage", A.Filters())
    assert p["roi"]["status"] == "insufficient_evidence"
    assert p["comparison"]["decision"] == "experiment"


def test_recommendation_payloads_label_estimates(demo):
    rows = S.recommendations_payload(demo, A.Filters())["rows"]
    assert rows and all(r["message_key"].startswith("recommendation.") for r in rows)
    for r in rows:
        if r["projected_monthly_saving"] is not None:
            assert r["is_estimate"] is True


def test_single_use_case_keeps_baseline_details(demo):
    p = S.use_case_payload(demo, "marketing_content", A.Filters())
    assert p["roi"]["hours"]["baseline_source"] == "control_group"
    assert p["roi"]["hours"]["baseline_minutes_per_task"] > p["roi"]["hours"]["ai_minutes_per_task"]
    assert S.use_case_payload(demo, "invoice_matching", A.Filters())["roi"]["hours"]["baseline_source"] == "documented_baseline"
