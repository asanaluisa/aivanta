"""Write-side operations: ingestion, assumptions, snapshots, alerts, audit."""
from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from aivanta_core import analytics as A
from aivanta_core import ingestion
from aivanta_core.pricing import PricingError, PricingSchedule
from aivanta_core.serialize import apply_assumptions, assumptions_payload, roi_payload

from . import models as M
from .errors import ApiError
from .repository import (
    attribution_map,
    bump_data_version,
    event_rows,
    existing_event_ids,
    key_maps,
    load_dataset,
)
from .security import Principal

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def audit(db: Session, p: Principal, action: str, entity_type: str, entity_id: Optional[str],
          before: Optional[dict] = None, after: Optional[dict] = None) -> None:
    db.add(M.AuditEvent(organization_id=p.organization_id, user_id=p.user_id, action=action,
                        entity_type=entity_type, entity_id=entity_id, before=before, after=after))


def ingest_file(db: Session, p: Principal, fmt: str, filename: str, raw: bytes) -> dict[str, Any]:
    if fmt not in ingestion.FORMATS:
        raise ApiError(404, "unknown_format", {"format": fmt})
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ApiError(413, "file_too_large", {"max_bytes": MAX_UPLOAD_BYTES})
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ApiError(422, "file_not_utf8") from None

    ds = load_dataset(db, p.organization_id)
    schedule = PricingSchedule(ds.pricing)
    known = set(schedule.models())
    try:
        result = ingestion.parse(fmt, content, attribution_map(db, p.organization_id), known)
    except ingestion.IngestionError as exc:
        raise ApiError(422, "ingestion_failed", {"detail": str(exc)}) from None

    priced = []
    for e in result.events:
        try:
            schedule.cost_of(e)
        except (PricingError, ValueError) as exc:
            result.rejected.append(ingestion.RejectedRow(e.event_id, str(exc)))
            continue
        e.cost = schedule.cost_of(e)
        priced.append(e)

    seen = existing_event_ids(db, p.organization_id, [e.event_id for e in priced])
    fresh, dup_in_file = [], set()
    for e in priced:
        if e.event_id in seen or e.event_id in dup_in_file:
            continue
        dup_in_file.add(e.event_id)
        fresh.append(e)
    duplicates = len(priced) - len(fresh)

    summary = result.summary() | {"accepted": len(fresh), "duplicates": duplicates,
                                  "rejected": len(result.rejected),
                                  "unallocated": sum(1 for e in fresh
                                                     if e.department_id is None or e.use_case_id is None)}
    batch = M.IngestionBatch(organization_id=p.organization_id, format=fmt, filename=filename[:255],
                             accepted=len(fresh), duplicates=duplicates, rejected=len(result.rejected),
                             unallocated=summary["unallocated"], summary=summary, created_by=p.user_id)
    db.add(batch)
    db.flush()
    if fresh:
        db.execute(insert(M.UsageEvent), event_rows(p.organization_id, fresh,
                                                    key_maps(db, p.organization_id), batch.id))
        org = db.get(M.Organization, p.organization_id)
        days = [e.occurred_at.date() for e in fresh]
        if org.data_start is None or min(days) < org.data_start:
            org.data_start = min(days)
        if org.data_end is None or max(days) > org.data_end:
            org.data_end = max(days)
        bump_data_version(db, p.organization_id)
    audit(db, p, "ingest", "ingestion_batch", str(batch.id), after=summary)
    db.commit()
    return summary | {"batch_id": batch.id}


def update_assumptions(db: Session, p: Principal, changes: dict[str, Any]) -> dict[str, Any]:
    row = db.scalar(select(M.AssumptionSet).where(M.AssumptionSet.organization_id == p.organization_id))
    before = dict(row.values) if row else {}
    current = apply_assumptions(apply_assumptions(_defaults(), before), {})
    try:
        updated = apply_assumptions(current, changes)
    except ValueError as exc:
        raise ApiError(422, "invalid_assumption", {"detail": str(exc)}) from None
    values = assumptions_payload(updated)
    if row is None:
        row = M.AssumptionSet(organization_id=p.organization_id, values=values, updated_by=p.user_id)
        db.add(row)
    else:
        row.values = values
        row.updated_by = p.user_id
        row.updated_at = dt.datetime.now(dt.timezone.utc)
    bump_data_version(db, p.organization_id)
    audit(db, p, "update", "assumptions", None, before=before, after=values)
    db.commit()
    return values


def _defaults():
    from aivanta_core.domain import Assumptions

    return Assumptions()


def create_snapshot(db: Session, p: Principal, scope_type: str, scope_key: str,
                    f: A.Filters) -> M.ROISnapshot:
    ds = load_dataset(db, p.organization_id)
    if scope_type == "organization":
        r = A.scope_roi(ds, A.Filters(f.start, f.end), org_scope=True).roi
    elif scope_type == "department":
        if ds.department(scope_key) is None:
            raise ApiError(404, "not_found")
        r = A.scope_roi(ds, A.Filters(f.start, f.end, frozenset({scope_key})), org_scope=False).roi
    elif scope_type == "use_case":
        if ds.use_case(scope_key) is None:
            raise ApiError(404, "not_found")
        r = A.use_case_analysis(ds, scope_key, A.Filters(f.start, f.end))[0].roi
    else:
        raise ApiError(422, "invalid_scope")
    start, end = f.period(ds)
    org = db.get(M.Organization, p.organization_id)
    snap = M.ROISnapshot(
        organization_id=p.organization_id, scope_type=scope_type, scope_key=scope_key,
        period_start=start, period_end=end, status=r.status, total_cost=r.costs.total,
        gross_benefit=r.gross_benefit, net_benefit=r.net_benefit,
        roi_pct=round(r.roi_pct, 2) if r.roi_pct is not None else None,
        data_version=org.data_version, assumptions=assumptions_payload(ds.assumptions),
        payload=roi_payload(r), created_by=p.user_id)
    db.add(snap)
    db.flush()
    audit(db, p, "create", "roi_snapshot", str(snap.id), after={"scope": f"{scope_type}:{scope_key}",
                                                                  "status": r.status})
    db.commit()
    return snap


def acknowledge_alert(db: Session, p: Principal, rule_id: str, scope_type: str, scope_key: str,
                      metrics: dict) -> M.Alert:
    row = db.scalar(select(M.Alert).where(
        M.Alert.organization_id == p.organization_id, M.Alert.rule_id == rule_id,
        M.Alert.scope_type == scope_type, M.Alert.scope_key == scope_key))
    now = dt.datetime.now(dt.timezone.utc)
    if row is None:
        row = M.Alert(organization_id=p.organization_id, rule_id=rule_id, severity=metrics.get("severity", ""),
                      scope_type=scope_type, scope_key=scope_key, metrics=metrics)
        db.add(row)
    row.acknowledged_by = p.user_id
    row.acknowledged_at = now
    audit(db, p, "acknowledge", "alert", f"{rule_id}:{scope_type}:{scope_key}")
    db.commit()
    return row


def acknowledged_keys(db: Session, org_id: int) -> set[tuple[str, str, str]]:
    rows = db.execute(select(M.Alert.rule_id, M.Alert.scope_type, M.Alert.scope_key)
                      .where(M.Alert.organization_id == org_id, M.Alert.acknowledged_at.is_not(None))).all()
    return {(r[0], r[1], r[2]) for r in rows}
