"""Localized CSV reports (English and Spanish).

Spanish exports use the conventions a Spanish spreadsheet expects: ``;`` as
the field separator and ``,`` as the decimal separator. Identifiers stay
language-neutral in the data; only headers and enum labels are translated.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from .analytics import Filters, breakdown, use_case_analysis
from .domain import Dataset

LOCALES = ("en", "es")
_DIR = Path(__file__).parent / "locales"


@lru_cache(maxsize=None)
def messages(locale: str) -> dict[str, str]:
    if locale not in LOCALES:
        raise ValueError(f"unsupported locale '{locale}'")
    return json.loads((_DIR / f"{locale}.json").read_text(encoding="utf-8"))


def t(locale: str, key: str) -> str:
    return messages(locale).get(key, key)


def fmt_number(value: Any, locale: str, places: int = 2) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    d = Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    s = f"{d:f}"
    return s.replace(".", ",") if locale == "es" else s


def _writer(locale: str) -> tuple[io.StringIO, Any]:
    buf = io.StringIO()
    return buf, csv.writer(buf, delimiter=";" if locale == "es" else ",", lineterminator="\n")


def _preamble(w, ds: Dataset, f: Filters, locale: str, generated: Optional[datetime]) -> None:
    start, end = f.period(ds)
    if ds.is_synthetic:
        w.writerow([f"# {t(locale, 'report.synthetic_notice')}"])
    w.writerow([f"# {t(locale, 'report.estimate_notice')}"])
    w.writerow([f"# {t(locale, 'report.period')}: {start.isoformat()} – {end.isoformat()}"])
    w.writerow([f"# {t(locale, 'report.currency')}: {ds.currency}"])
    if generated:
        w.writerow([f"# {t(locale, 'report.generated')}: {generated.isoformat(timespec='seconds')}"])


def roi_summary_csv(ds: Dataset, f: Filters, locale: str = "en",
                    generated: Optional[datetime] = None) -> str:
    buf, w = _writer(locale)
    _preamble(w, ds, f, locale, generated)
    cols = ["use_case", "department", "study_design", "decision", "roi_status", "total_cost",
            "model_usage", "gross_benefit", "net_benefit", "roi_pct", "bcr", "hours_saved",
            "net_hours_saved", "estimated_time_value", "cost_per_successful_task", "ai_tasks"]
    w.writerow([t(locale, f"col.{c}") for c in cols])
    for uc in ds.use_cases:
        if f.use_case_ids and uc.use_case_id not in f.use_case_ids:
            continue
        if f.department_ids and (uc.department_id or "unallocated") not in f.department_ids:
            continue
        s, cmp = use_case_analysis(ds, uc.use_case_id, f)
        r = s.roi
        w.writerow([
            t(locale, uc.name_key),
            t(locale, f"department.{uc.department_id or 'unallocated'}"),
            t(locale, f"study_design.{uc.study_design}"),
            t(locale, f"decision.{cmp.decision}"),
            t(locale, f"roi_status.{r.status}"),
            fmt_number(r.costs.total, locale),
            fmt_number(r.costs.model_usage, locale),
            fmt_number(r.gross_benefit, locale),
            fmt_number(r.net_benefit, locale),
            fmt_number(r.roi_pct, locale, 1),
            fmt_number(r.benefit_cost_ratio, locale),
            fmt_number(r.hours.gross_hours, locale, 1),
            fmt_number(r.hours.net_hours, locale, 1),
            fmt_number(r.estimated_time_value, locale),
            fmt_number(r.cost_per_successful_task, locale),
            s.tasks_ai,
        ])
    return buf.getvalue()


def usage_breakdown_csv(ds: Dataset, f: Filters, dimension: str, locale: str = "en",
                        generated: Optional[datetime] = None) -> str:
    buf, w = _writer(locale)
    _preamble(w, ds, f, locale, generated)
    cols = ["key", "spend", "share", "input_tokens", "output_tokens", "cached_input_tokens",
            "requests", "error_rate", "active_users", "cost_per_request"]
    w.writerow([t(locale, f"col.{c}") for c in cols])
    for row in breakdown(ds, f, dimension):
        key = row["key"]
        if dimension == "department":
            label = t(locale, f"department.{key}")
        elif dimension == "use_case":
            uc = ds.use_case(key)
            label = t(locale, uc.name_key if uc else "use_case.unallocated")
        else:
            label = key
        w.writerow([
            label,
            fmt_number(row["spend"], locale),
            fmt_number(row["share"] * 100, locale, 1),
            row["input_tokens"], row["output_tokens"], row["cached_input_tokens"], row["requests"],
            fmt_number((row["error_rate"] or 0) * 100, locale, 2),
            row["active_users"],
            fmt_number(row["cost_per_request"], locale, 6),
        ])
    return buf.getvalue()


def json_default(o: Any) -> Any:
    """Serializer for API/JSON exports: Decimals as strings keep exact precision."""
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if isinstance(o, set):
        return sorted(o)
    raise TypeError(f"not serializable: {type(o)!r}")
