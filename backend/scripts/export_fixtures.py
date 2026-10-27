"""Write API payloads for the synthetic dataset to frontend/tests/fixtures.

The frontend tests use them to check that every enum value, reason code,
rule id and metric name the backend can emit has a translation in both
locales. Run from backend/:  python scripts/export_fixtures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aivanta_core import analytics as A  # noqa: E402
from aivanta_core import serialize as S  # noqa: E402
from aivanta_core import synthetic  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "frontend" / "tests" / "fixtures" / "demo-payloads.json"


def build() -> dict:
    ds = synthetic.generate()
    f = A.Filters()
    sept = A.Filters(start=ds.period_end.replace(day=1), end=ds.period_end)
    return {
        "meta": S.meta_payload(ds) | {"ingestion_formats": ["aivanta_csv", "openai", "anthropic", "google"],
                                      "live_sync": {"openai": "not_implemented", "anthropic": "not_implemented",
                                                    "google": "not_implemented"}},
        "dashboard": S.all_dashboard(ds, f),
        "dashboard_september": S.all_dashboard(ds, sept),
        "dashboard_openai_only": S.all_dashboard(ds, A.Filters(providers=frozenset({"openai"}))),
        "departments": S.departments_payload(ds, f),
        "use_cases": S.use_cases_payload(ds, f),
        "use_case_details": {u.use_case_id: S.use_case_payload(ds, u.use_case_id, f) for u in ds.use_cases},
        "recommendations": S.recommendations_payload(ds, f),
        "assumptions": S.assumptions_payload(ds.assumptions),
    }


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build(), indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KiB)")
