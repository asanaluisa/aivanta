"""Read endpoints. Every handler gets the caller's organization dataset only."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from aivanta_core import analytics as A
from aivanta_core import serialize as S
from aivanta_core.domain import Dataset
from aivanta_core.ingestion import FORMATS, LIVE_SYNC_STATUS

from ..db import get_db
from ..deps import org_dataset, request_filters, require
from ..errors import ApiError
from ..security import Principal
from ..services import acknowledged_keys

router = APIRouter(tags=["analytics"])


@router.get("/meta")
def meta(ds: Dataset = Depends(org_dataset)):
    return S.meta_payload(ds) | {
        "ingestion_formats": list(FORMATS),
        "live_sync": LIVE_SYNC_STATUS,
    }


@router.get("/dashboard")
def dashboard(ds: Dataset = Depends(org_dataset), f: A.Filters = Depends(request_filters)):
    return S.all_dashboard(ds, f)


@router.get("/dashboard/overview")
def overview(ds: Dataset = Depends(org_dataset), f: A.Filters = Depends(request_filters)):
    return S.overview_payload(ds, f)


@router.get("/usage/trend")
def trend(ds: Dataset = Depends(org_dataset), f: A.Filters = Depends(request_filters)):
    return S.trend_payload(ds, f)


@router.get("/usage/breakdown/{dimension}")
def usage_breakdown(dimension: str, ds: Dataset = Depends(org_dataset),
                    f: A.Filters = Depends(request_filters)):
    if dimension not in A.DIMENSIONS:
        raise ApiError(404, "unknown_dimension", {"dimension": dimension})
    return S.breakdown_payload(ds, f, dimension)


@router.get("/adoption")
def adoption(ds: Dataset = Depends(org_dataset), f: A.Filters = Depends(request_filters)):
    return S.adoption_payload(ds, f)


@router.get("/budgets")
def budgets(ds: Dataset = Depends(org_dataset), f: A.Filters = Depends(request_filters)):
    return S.budgets_payload(ds, f.period(ds)[1])


@router.get("/departments")
def departments(ds: Dataset = Depends(org_dataset), f: A.Filters = Depends(request_filters)):
    return S.departments_payload(ds, f)


@router.get("/use-cases")
def use_cases(ds: Dataset = Depends(org_dataset), f: A.Filters = Depends(request_filters)):
    return S.use_cases_payload(ds, f)


@router.get("/use-cases/{key}")
def use_case(key: str, ds: Dataset = Depends(org_dataset), f: A.Filters = Depends(request_filters)):
    if ds.use_case(key) is None:
        raise ApiError(404, "not_found")
    return S.use_case_payload(ds, key, f)


@router.get("/comparison")
def comparison(ds: Dataset = Depends(org_dataset), f: A.Filters = Depends(request_filters)):
    rows = []
    for uc in ds.use_cases:
        if f.use_case_ids and uc.use_case_id not in f.use_case_ids:
            continue
        if f.department_ids and (uc.department_id or A.UNALLOCATED) not in f.department_ids:
            continue
        p = S.use_case_payload(ds, uc.use_case_id, f)
        rows.append(p["comparison"] | {"name_key": p["name_key"], "department": p["department"],
                                       "roi_status": p["roi"]["status"], "roi_pct": p["roi"]["roi_pct"],
                                       "net_benefit": p["roi"]["net_benefit"]})
    return {"rows": rows}


@router.get("/recommendations")
def recommendations(ds: Dataset = Depends(org_dataset), f: A.Filters = Depends(request_filters),
                    p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    acked = acknowledged_keys(db, p.organization_id)
    payload = S.recommendations_payload(ds, f)
    for r in payload["rows"]:
        r["acknowledged"] = (r["rule_id"], r["scope_type"], r["scope_id"]) in acked
    return payload
