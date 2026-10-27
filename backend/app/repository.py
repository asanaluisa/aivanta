"""Loads an organization's data from PostgreSQL into a core :class:`Dataset`.

Analytics run in memory on the loaded dataset. Results are cached per
``(organization, data_version)``; any write that changes analytics inputs
must call :func:`bump_data_version` in the same transaction.
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session, aliased

from aivanta_core import domain as D
from aivanta_core.ingestion import Attribution, AttributionMap

from . import models as M

_CACHE: "OrderedDict[tuple[int, int], D.Dataset]" = OrderedDict()
_LOCK = threading.Lock()
_CACHE_SIZE = 8


def get_organization(db: Session, org_id: int) -> M.Organization:
    org = db.get(M.Organization, org_id)
    if org is None:
        raise LookupError(f"organization {org_id} not found")
    return org


def bump_data_version(db: Session, org_id: int) -> None:
    db.execute(update(M.Organization).where(M.Organization.id == org_id)
               .values(data_version=M.Organization.data_version + 1))


def load_dataset(db: Session, org_id: int) -> D.Dataset:
    org = get_organization(db, org_id)
    key = (org.id, org.data_version)
    with _LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
    ds = _load(db, org)
    with _LOCK:
        _CACHE[key] = ds
        while len(_CACHE) > _CACHE_SIZE:
            _CACHE.popitem(last=False)
    return ds


def clear_cache() -> None:
    with _LOCK:
        _CACHE.clear()


def _load(db: Session, org: M.Organization) -> D.Dataset:
    oid = org.id
    deps = db.scalars(select(M.Department).where(M.Department.organization_id == oid)).all()
    dep_key = {d.id: d.key for d in deps}
    ucs = db.scalars(select(M.UseCase).where(M.UseCase.organization_id == oid)).all()
    uc_key = {u.id: u.key for u in ucs}
    designs = {e.use_case_id: e.design for e in db.scalars(
        select(M.Experiment).where(M.Experiment.organization_id == oid))}
    baselines = {b.use_case_id: b.value for b in db.scalars(
        select(M.Baseline).where(M.Baseline.organization_id == oid, M.Baseline.metric == "duration_minutes"))}
    users = [tuple(r) for r in db.execute(select(M.User.id, M.User.key, M.User.department_id)
                                          .where(M.User.organization_id == oid))]
    user_key = {uid: ukey for uid, ukey, _ in users}

    model_rows = db.execute(
        select(M.AIModel.id, M.AIModel.key, M.AIModel.tier, M.AIProvider.key)
        .join(M.AIProvider, M.AIModel.provider_id == M.AIProvider.id)).all()
    models = {r[0]: (r[3], r[1], r[2]) for r in model_rows}

    pricing = [
        D.PricingRule(models[p.model_id][0], models[p.model_id][1], p.effective_from, p.input_per_mtok,
                      p.output_per_mtok, p.cached_input_per_mtok, models[p.model_id][2])
        for p in db.scalars(select(M.ModelPrice).where(M.ModelPrice.organization_id == oid))
    ]

    E = M.UsageEvent
    events = [
        D.UsageEvent(
            event_id=r.external_id, occurred_at=r.occurred_at, provider=models[r.model_id][0],
            model=models[r.model_id][1], input_tokens=r.input_tokens, output_tokens=r.output_tokens,
            cached_input_tokens=r.cached_input_tokens, request_count=r.request_count, retries=r.retries,
            status=r.status, latency_ms=r.latency_ms, user_id=user_key.get(r.user_id),
            department_id=dep_key.get(r.department_id), use_case_id=uc_key.get(r.use_case_id),
            task_id=r.task_external_id, source=r.source, cost=Decimal(r.cost))
        for r in db.execute(select(
            E.external_id, E.occurred_at, E.model_id, E.input_tokens, E.output_tokens,
            E.cached_input_tokens, E.request_count, E.retries, E.status, E.latency_ms, E.user_id,
            E.department_id, E.use_case_id, E.task_external_id, E.source, E.cost,
        ).where(E.organization_id == oid).order_by(E.occurred_at, E.id))
    ]

    T = M.Task
    tasks = [
        D.TaskRecord(
            task_id=r.external_id, use_case_id=uc_key[r.use_case_id], arm=r.arm, completed_on=r.completed_on,
            duration_minutes=r.duration_minutes, success=r.success, quality_score=r.quality_score,
            had_error=r.had_error, rework_minutes=r.rework_minutes, review_minutes=r.review_minutes,
            customer_satisfaction=r.customer_satisfaction, task_type=r.task_type,
            user_id=user_key.get(r.user_id))
        for r in db.execute(select(
            T.external_id, T.use_case_id, T.arm, T.completed_on, T.duration_minutes, T.success,
            T.quality_score, T.had_error, T.rework_minutes, T.review_minutes, T.customer_satisfaction,
            T.task_type, T.user_id).where(T.organization_id == oid).order_by(T.completed_on, T.id))
    ]

    cost_items = [
        D.CostItem(c.external_id, c.category, c.amount, c.period_start, c.period_end, c.description_key,
                   uc_key.get(c.use_case_id), dep_key.get(c.department_id), c.one_off)
        for c in db.scalars(select(M.CostItem).where(M.CostItem.organization_id == oid).order_by(M.CostItem.id))
    ]
    benefits = [
        D.BenefitClaim(b.external_id, uc_key[b.use_case_id], b.category, b.amount, b.verification_status,
                       b.evidence_key, b.period_start, b.period_end, b.confidence, b.source)
        for b in db.scalars(select(M.BenefitClaim).where(M.BenefitClaim.organization_id == oid)
                            .order_by(M.BenefitClaim.id))
    ]
    budgets = [
        D.Budget(b.external_id, dep_key.get(b.department_id), b.month, b.amount)
        for b in db.scalars(select(M.Budget).where(M.Budget.organization_id == oid).order_by(M.Budget.id))
    ]
    assumption_row = db.scalar(select(M.AssumptionSet).where(M.AssumptionSet.organization_id == oid))
    assumptions = assumptions_from_values(assumption_row.values if assumption_row else {})

    start = org.data_start or (min((e.occurred_at.date() for e in events), default=None))
    end = org.data_end or (max((e.occurred_at.date() for e in events), default=None))
    if start is None or end is None:
        import datetime as _dt
        start = end = _dt.date.today()

    return D.Dataset(
        organization_id=org.key,
        currency=org.currency,
        period_start=start,
        period_end=end,
        departments=[D.Department(d.key, d.name_key, d.loaded_hourly_rate) for d in deps],
        use_cases=[
            D.UseCase(u.key, u.name_key, dep_key.get(u.department_id), u.task_complexity,
                      designs.get(u.id, D.StudyDesign.OBSERVATIONAL.value), u.measurement_start,
                      u.measurement_end, u.data_source, baselines.get(u.id))
            for u in ucs
        ],
        pricing=pricing,
        usage_events=events,
        tasks=tasks,
        cost_items=cost_items,
        benefits=benefits,
        budgets=budgets,
        users={ukey: dep_key[udep] for _, ukey, udep in users if udep is not None},
        assumptions=assumptions,
        is_synthetic=org.is_synthetic,
    )


def assumptions_from_values(values: dict) -> D.Assumptions:
    from aivanta_core.serialize import apply_assumptions

    return apply_assumptions(D.Assumptions(), values or {})


def attribution_map(db: Session, org_id: int) -> AttributionMap:
    Dep, UC = aliased(M.Department), aliased(M.UseCase)
    rows = db.execute(
        select(M.AttributionRule.identifier, Dep.key, UC.key)
        .outerjoin(Dep, M.AttributionRule.department_id == Dep.id)
        .outerjoin(UC, M.AttributionRule.use_case_id == UC.id)
        .where(M.AttributionRule.organization_id == org_id)).all()
    return AttributionMap({r[0]: Attribution(r[1], r[2]) for r in rows})


def key_maps(db: Session, org_id: int) -> dict[str, dict]:
    """Business-key → primary-key lookups used when writing rows."""
    return {
        "departments": dict(db.execute(select(M.Department.key, M.Department.id)
                                       .where(M.Department.organization_id == org_id)).all()),
        "use_cases": dict(db.execute(select(M.UseCase.key, M.UseCase.id)
                                     .where(M.UseCase.organization_id == org_id)).all()),
        "users": dict(db.execute(select(M.User.key, M.User.id).where(M.User.organization_id == org_id)).all()),
        "models": {(r[0], r[1]): r[2] for r in db.execute(
            select(M.AIProvider.key, M.AIModel.key, M.AIModel.id)
            .join(M.AIProvider, M.AIModel.provider_id == M.AIProvider.id)).all()},
    }


def existing_event_ids(db: Session, org_id: int, ids: list[str]) -> set[str]:
    out: set[str] = set()
    for i in range(0, len(ids), 1000):
        chunk = ids[i:i + 1000]
        out.update(db.scalars(select(M.UsageEvent.external_id).where(
            M.UsageEvent.organization_id == org_id, M.UsageEvent.external_id.in_(chunk))))
    return out


def event_rows(org_id: int, events: list[D.UsageEvent], maps: dict[str, dict],
               batch_id: Optional[int] = None) -> list[dict]:
    """Rows for a bulk insert. Unknown department/use case keys stay NULL (unallocated)."""
    rows = []
    for e in events:
        if e.cost is None:
            raise ValueError(f"event {e.event_id} is not priced")
        rows.append({
            "organization_id": org_id, "external_id": e.event_id, "occurred_at": e.occurred_at,
            "model_id": maps["models"][(e.provider, e.model)], "input_tokens": e.input_tokens,
            "output_tokens": e.output_tokens, "cached_input_tokens": e.cached_input_tokens,
            "request_count": e.request_count, "retries": e.retries, "status": e.status,
            "latency_ms": e.latency_ms, "cost": e.cost,
            "user_id": maps["users"].get(e.user_id) if e.user_id else None,
            "department_id": maps["departments"].get(e.department_id) if e.department_id else None,
            "use_case_id": maps["use_cases"].get(e.use_case_id) if e.use_case_id else None,
            "task_external_id": e.task_id, "source": e.source, "ingestion_batch_id": batch_id,
        })
    return rows
