"""Write endpoints: ingestion, assumptions, snapshots, alerts and audit log."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from aivanta_core import analytics as A
from aivanta_core.domain import Dataset
from aivanta_core.serialize import assumptions_payload

from .. import models as M
from .. import services
from ..db import get_db
from ..deps import org_dataset, request_filters, require
from ..errors import ApiError
from ..security import Principal

router = APIRouter(tags=["administration"])


# ------------------------------------------------------------------ ingestion

@router.post("/ingestion/{fmt}")
def ingest(fmt: str, file: UploadFile = File(...), p: Principal = Depends(require("ingest")),
           db: Session = Depends(get_db)):
    # Sync handler: FastAPI runs it in a worker thread, so DB work never blocks the event loop.
    raw = file.file.read(services.MAX_UPLOAD_BYTES + 1)
    return services.ingest_file(db, p, fmt, file.filename or "upload", raw)


@router.get("/ingestion/batches")
def batches(p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    rows = db.scalars(select(M.IngestionBatch).where(M.IngestionBatch.organization_id == p.organization_id)
                      .order_by(M.IngestionBatch.created_at.desc()).limit(50))
    return {"rows": [{"id": b.id, "format": b.format, "filename": b.filename, "accepted": b.accepted,
                      "duplicates": b.duplicates, "rejected": b.rejected, "unallocated": b.unallocated,
                      "created_at": b.created_at.isoformat(), "summary": b.summary} for b in rows]}


# ------------------------------------------------------------------ assumptions

@router.get("/assumptions")
def get_assumptions(ds: Dataset = Depends(org_dataset)):
    return assumptions_payload(ds.assumptions)


class AssumptionsIn(BaseModel):
    values: dict[str, float] = Field(min_length=1)


@router.put("/assumptions")
def put_assumptions(body: AssumptionsIn, p: Principal = Depends(require("assumptions")),
                    db: Session = Depends(get_db)):
    return services.update_assumptions(db, p, body.values)


# ------------------------------------------------------------------ snapshots

class SnapshotIn(BaseModel):
    scope_type: Literal["organization", "department", "use_case"]
    scope_key: str = Field(default="organization", max_length=128)


def _snapshot_out(s: M.ROISnapshot) -> dict[str, Any]:
    return {"id": s.id, "scope_type": s.scope_type, "scope_key": s.scope_key,
            "period_start": s.period_start.isoformat(), "period_end": s.period_end.isoformat(),
            "status": s.status, "total_cost": float(s.total_cost), "gross_benefit": float(s.gross_benefit),
            "net_benefit": float(s.net_benefit) if s.net_benefit is not None else None,
            "roi_pct": float(s.roi_pct) if s.roi_pct is not None else None,
            "data_version": s.data_version, "created_at": s.created_at.isoformat()}


@router.post("/roi-snapshots")
def create_snapshot(body: SnapshotIn, p: Principal = Depends(require("snapshots")),
                    db: Session = Depends(get_db), f: A.Filters = Depends(request_filters)):
    return _snapshot_out(services.create_snapshot(db, p, body.scope_type, body.scope_key, f))


@router.get("/roi-snapshots")
def list_snapshots(p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    rows = db.scalars(select(M.ROISnapshot).where(M.ROISnapshot.organization_id == p.organization_id)
                      .order_by(M.ROISnapshot.created_at.desc()).limit(100))
    return {"rows": [_snapshot_out(s) for s in rows]}


# ------------------------------------------------------------------ alerts

class AckIn(BaseModel):
    rule_id: str = Field(max_length=64)
    scope_type: str = Field(max_length=32)
    scope_key: str = Field(max_length=128)
    severity: str = Field(default="", max_length=16)


@router.post("/alerts/acknowledge")
def acknowledge(body: AckIn, p: Principal = Depends(require("read")), db: Session = Depends(get_db)):
    if p.role == "viewer":
        raise ApiError(403, "forbidden", {"permission": "acknowledge"})
    row = services.acknowledge_alert(db, p, body.rule_id, body.scope_type, body.scope_key,
                                     {"severity": body.severity})
    return {"rule_id": row.rule_id, "scope_type": row.scope_type, "scope_key": row.scope_key,
            "acknowledged_at": row.acknowledged_at.isoformat() if row.acknowledged_at else None}


# ------------------------------------------------------------------ audit

@router.get("/audit")
def audit_log(p: Principal = Depends(require("audit")), db: Session = Depends(get_db)):
    rows = db.scalars(select(M.AuditEvent).where(M.AuditEvent.organization_id == p.organization_id)
                      .order_by(M.AuditEvent.created_at.desc(), M.AuditEvent.id.desc()).limit(200))
    return {"rows": [{"id": a.id, "user_id": a.user_id, "action": a.action, "entity_type": a.entity_type,
                      "entity_id": a.entity_id, "before": a.before, "after": a.after,
                      "created_at": a.created_at.isoformat() if a.created_at else None} for a in rows]}
