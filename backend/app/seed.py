"""Load the synthetic demonstration dataset into PostgreSQL.

Usage::

    python -m app.seed            # seed if the demo organization does not exist yet
    python -m app.seed --reset    # drop and recreate the demo organizations

Two organizations are created so data isolation can be demonstrated:
``org_demo`` (90 days, the main story) and ``org_northwind`` (30 days).
Every organization created here is flagged ``is_synthetic``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from aivanta_core import synthetic
from aivanta_core.domain import Dataset

from . import models as M
from .config import get_settings
from .db import session_factory
from .repository import clear_cache, event_rows, key_maps
from .security import hash_password

ATTRIBUTION_SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "attribution_map.json"
CHUNK = 5000

DEMO_ACCOUNTS = [
    # email, role, display name
    ("admin@aivanta.demo", "admin", "Alex Admin"),
    ("finance@aivanta.demo", "finance", "Fran Finance"),
    ("analyst@aivanta.demo", "analyst", "Ana Analyst"),
    ("viewer@aivanta.demo", "viewer", "Victor Viewer"),
]


def _chunks(rows: list[dict], size: int = CHUNK) -> Iterable[list[dict]]:
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def ensure_models(db: Session, ds: Dataset) -> None:
    providers = {p.key: p for p in db.scalars(select(M.AIProvider))}
    for rule in ds.pricing:
        if rule.provider not in providers:
            providers[rule.provider] = M.AIProvider(key=rule.provider)
            db.add(providers[rule.provider])
    db.flush()
    existing = {(m.provider_id, m.key) for m in db.scalars(select(M.AIModel))}
    for rule in ds.pricing:
        pid = providers[rule.provider].id
        if (pid, rule.model) not in existing:
            db.add(M.AIModel(provider_id=pid, key=rule.model, tier=rule.tier))
            existing.add((pid, rule.model))
    db.flush()


def seed_organization(db: Session, ds: Dataset, *, key: str, name: str,
                      accounts: list[tuple[str, str, str]], password: str,
                      attribution: dict | None = None) -> M.Organization:
    ensure_models(db, ds)
    org = M.Organization(key=key, name=name, currency=ds.currency, is_synthetic=ds.is_synthetic,
                         data_start=ds.period_start, data_end=ds.period_end, data_version=1)
    db.add(org)
    db.flush()
    oid = org.id

    deps = {}
    for d in ds.departments:
        deps[d.department_id] = M.Department(organization_id=oid, key=d.department_id, name_key=d.name_key,
                                             loaded_hourly_rate=d.loaded_hourly_rate)
        db.add(deps[d.department_id])
    db.flush()

    ucs = {}
    for u in ds.use_cases:
        ucs[u.use_case_id] = M.UseCase(
            organization_id=oid, key=u.use_case_id, name_key=u.name_key,
            department_id=deps[u.department_id].id if u.department_id else None,
            task_complexity=u.task_complexity, measurement_start=u.measurement_start,
            measurement_end=u.measurement_end, data_source=u.data_source)
        db.add(ucs[u.use_case_id])
    db.flush()
    for u in ds.use_cases:
        db.add(M.Experiment(organization_id=oid, use_case_id=ucs[u.use_case_id].id, design=u.study_design,
                            description=u.data_source, start_date=u.measurement_start,
                            end_date=u.measurement_end))
        if u.baseline_minutes is not None:
            db.add(M.Baseline(organization_id=oid, use_case_id=ucs[u.use_case_id].id,
                              metric="duration_minutes", value=u.baseline_minutes,
                              source="Documented pre-AI process timing (synthetic)"))

    pwd = hash_password(password)
    for email, role, display in accounts:
        db.add(M.User(organization_id=oid, key=email, email=email, display_name=display,
                      password_hash=pwd, role=role, preferred_locale="en"))
    db.execute(insert(M.User), [
        {"organization_id": oid, "key": ukey, "role": "member", "preferred_locale": "en",
         "department_id": deps[dkey].id, "is_active": True, "display_name": ukey}
        for ukey, dkey in sorted(ds.users.items())])
    db.flush()

    models = key_maps(db, oid)["models"]
    for p in ds.pricing:
        db.add(M.ModelPrice(organization_id=oid, model_id=models[(p.provider, p.model)],
                            effective_from=p.effective_from, input_per_mtok=p.input_per_mtok,
                            output_per_mtok=p.output_per_mtok, cached_input_per_mtok=p.cached_input_per_mtok))
    for c in ds.cost_items:
        db.add(M.CostItem(organization_id=oid, external_id=c.cost_id, category=c.category, amount=c.amount,
                          period_start=c.period_start, period_end=c.period_end, one_off=c.one_off,
                          description_key=c.description_key,
                          use_case_id=ucs[c.use_case_id].id if c.use_case_id else None,
                          department_id=deps[c.department_id].id if c.department_id else None))
    for b in ds.benefits:
        db.add(M.BenefitClaim(organization_id=oid, external_id=b.benefit_id, use_case_id=ucs[b.use_case_id].id,
                              category=b.category, amount=b.amount, verification_status=b.verification_status,
                              evidence_key=b.evidence_key, period_start=b.period_start, period_end=b.period_end,
                              confidence=b.confidence, source=b.source))
    for b in ds.budgets:
        db.add(M.Budget(organization_id=oid, external_id=b.budget_id,
                        department_id=deps[b.department_id].id if b.department_id else None,
                        month=b.month, amount=b.amount))
    for identifier, rule in (attribution or {}).items():
        if identifier.startswith("_"):
            continue
        db.add(M.AttributionRule(
            organization_id=oid, identifier=identifier,
            department_id=deps[rule["department_id"]].id if rule.get("department_id") else None,
            use_case_id=ucs[rule["use_case_id"]].id if rule.get("use_case_id") else None))
    db.add(M.AssumptionSet(organization_id=oid, values={}))
    db.flush()

    maps = key_maps(db, oid)
    task_rows = [{
        "organization_id": oid, "external_id": t.task_id, "use_case_id": maps["use_cases"][t.use_case_id],
        "arm": t.arm, "task_type": t.task_type, "completed_on": t.completed_on,
        "duration_minutes": t.duration_minutes, "success": t.success, "quality_score": t.quality_score,
        "had_error": t.had_error, "rework_minutes": t.rework_minutes, "review_minutes": t.review_minutes,
        "customer_satisfaction": t.customer_satisfaction,
        "user_id": maps["users"].get(t.user_id) if t.user_id else None,
    } for t in ds.tasks]
    for chunk in _chunks(task_rows):
        db.execute(insert(M.Task), chunk)
    for chunk in _chunks(event_rows(oid, ds.usage_events, maps)):
        db.execute(insert(M.UsageEvent), chunk)
    db.flush()
    return org


def run(reset: bool = False) -> None:
    settings = get_settings()
    with session_factory()() as db:
        existing = db.scalar(select(M.Organization).where(M.Organization.key == synthetic.ORG_ID))
        if existing and not reset:
            print("Demo organization already present — nothing to do (use --reset to rebuild).")
            return
        db.execute(delete(M.Organization).where(M.Organization.key.in_([synthetic.ORG_ID, "org_northwind"])))
        db.flush()
        attribution = json.loads(ATTRIBUTION_SAMPLE.read_text()) if ATTRIBUTION_SAMPLE.exists() else {}
        main = synthetic.generate()
        seed_organization(db, main, key=synthetic.ORG_ID, name="Aivanta Demo Co. (synthetic)",
                          accounts=DEMO_ACCOUNTS, password=settings.demo_password, attribution=attribution)
        other = synthetic.generate(seed=7, days=30)
        seed_organization(db, other, key="org_northwind", name="Northwind Labs (synthetic)",
                          accounts=[("admin@northwind.demo", "admin", "Northwind Admin")],
                          password=settings.demo_password)
        db.commit()
    clear_cache()
    print(f"Seeded {len(main.usage_events)} usage events and {len(main.tasks)} tasks for {synthetic.ORG_ID}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="drop and recreate the demo organizations")
    run(parser.parse_args().reset)


if __name__ == "__main__":
    main()
