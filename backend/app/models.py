"""Relational schema.

All rows are scoped by ``organization_id`` (data isolation). Enum-like
columns hold language-neutral identifiers (``"cost_avoidance"``,
``"control_group"`` …); the frontend localizes them. Business keys
(``key`` / ``external_id``) are what the core engine and the API expose;
integer primary keys stay internal.
"""
import datetime as dt
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION as Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

MONEY = Numeric(14, 2)
UNIT_PRICE = Numeric(12, 6)
EVENT_COST = Numeric(18, 8)

ROLES = ("admin", "finance", "analyst", "viewer", "member")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    data_start: Mapped[Optional[dt.date]] = mapped_column(Date)
    data_end: Mapped[Optional[dt.date]] = mapped_column(Date)
    # Incremented on every write that changes analytics inputs; used as a cache key.
    data_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("organization_id", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    name_key: Mapped[str] = mapped_column(String(128))
    loaded_hourly_rate: Mapped[Decimal] = mapped_column(MONEY)


class User(Base):
    """People in the organization. Members with a password can sign in.

    ``role = "member"`` marks someone whose AI usage is tracked but who has no
    application access.
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("organization_id", "key"),
        CheckConstraint(f"role IN {ROLES}", name="ck_users_role"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(128))
    email: Mapped[Optional[str]] = mapped_column(String(254), unique=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(200))
    password_hash: Mapped[Optional[str]] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16), default="member")
    preferred_locale: Mapped[str] = mapped_column(String(5), default="en")
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    department: Mapped[Optional[Department]] = relationship()


class AIProvider(Base):
    __tablename__ = "ai_providers"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(32), unique=True)  # openai | anthropic | google


class AIModel(Base):
    __tablename__ = "ai_models"
    __table_args__ = (UniqueConstraint("provider_id", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("ai_providers.id"))
    key: Mapped[str] = mapped_column(String(128))
    tier: Mapped[str] = mapped_column(String(16), default="standard")
    provider: Mapped[AIProvider] = relationship()


class ModelPrice(Base):
    """Versioned price schedule per organization (contract prices differ)."""

    __tablename__ = "model_prices"
    __table_args__ = (UniqueConstraint("organization_id", "model_id", "effective_from"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("ai_models.id"))
    effective_from: Mapped[dt.date] = mapped_column(Date)
    input_per_mtok: Mapped[Decimal] = mapped_column(UNIT_PRICE)
    output_per_mtok: Mapped[Decimal] = mapped_column(UNIT_PRICE)
    cached_input_per_mtok: Mapped[Optional[Decimal]] = mapped_column(UNIT_PRICE)
    model: Mapped[AIModel] = relationship()


class UseCase(Base):
    __tablename__ = "use_cases"
    __table_args__ = (UniqueConstraint("organization_id", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    name_key: Mapped[str] = mapped_column(String(128))
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"))
    task_complexity: Mapped[str] = mapped_column(String(16), default="standard")
    measurement_start: Mapped[Optional[dt.date]] = mapped_column(Date)
    measurement_end: Mapped[Optional[dt.date]] = mapped_column(Date)
    data_source: Mapped[str] = mapped_column(Text, default="")
    department: Mapped[Optional[Department]] = relationship()


class Experiment(Base):
    """How AI vs. non-AI evidence is collected for a use case (control groups, RCTs)."""

    __tablename__ = "experiments"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    use_case_id: Mapped[int] = mapped_column(ForeignKey("use_cases.id", ondelete="CASCADE"), unique=True)
    design: Mapped[str] = mapped_column(String(32))  # randomized | control_group | before_after | observational
    assignment_unit: Mapped[Optional[str]] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    start_date: Mapped[Optional[dt.date]] = mapped_column(Date)
    end_date: Mapped[Optional[dt.date]] = mapped_column(Date)


class Baseline(Base):
    """A documented pre-AI baseline, used when no concurrent control group exists."""

    __tablename__ = "baselines"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    use_case_id: Mapped[int] = mapped_column(ForeignKey("use_cases.id", ondelete="CASCADE"))
    metric: Mapped[str] = mapped_column(String(32), default="duration_minutes")
    value: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(Text, default="")
    measured_from: Mapped[Optional[dt.date]] = mapped_column(Date)
    measured_to: Mapped[Optional[dt.date]] = mapped_column(Date)


class IngestionBatch(Base):
    __tablename__ = "ingestion_batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    format: Mapped[str] = mapped_column(String(32))
    filename: Mapped[str] = mapped_column(String(255))
    accepted: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    rejected: Mapped[int] = mapped_column(Integer, default=0)
    unallocated: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AttributionRule(Base):
    __tablename__ = "attribution_rules"
    __table_args__ = (UniqueConstraint("organization_id", "identifier"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    identifier: Mapped[str] = mapped_column(String(255))  # e.g. "api_key:key_abc"
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"))
    use_case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("use_cases.id"))


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("organization_id", "external_id"),
        Index("ix_tasks_org_uc_day", "organization_id", "use_case_id", "completed_on"),
        CheckConstraint("arm IN ('ai', 'non_ai')", name="ck_tasks_arm"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    external_id: Mapped[str] = mapped_column(String(64))
    use_case_id: Mapped[int] = mapped_column(ForeignKey("use_cases.id", ondelete="CASCADE"))
    arm: Mapped[str] = mapped_column(String(8))
    task_type: Mapped[str] = mapped_column(String(64), default="standard")
    completed_on: Mapped[dt.date] = mapped_column(Date)
    duration_minutes: Mapped[float] = mapped_column(Float)
    success: Mapped[bool] = mapped_column(Boolean)
    quality_score: Mapped[Optional[float]] = mapped_column(Float)
    had_error: Mapped[bool] = mapped_column(Boolean, default=False)
    rework_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    review_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    customer_satisfaction: Mapped[Optional[float]] = mapped_column(Float)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        UniqueConstraint("organization_id", "external_id"),
        Index("ix_usage_org_time", "organization_id", "occurred_at"),
        CheckConstraint("cached_input_tokens <= input_tokens", name="ck_usage_cached_le_input"),
        CheckConstraint("request_count >= 1", name="ck_usage_requests"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    external_id: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime)  # UTC, naive
    model_id: Mapped[int] = mapped_column(ForeignKey("ai_models.id"))
    input_tokens: Mapped[int] = mapped_column(BigInteger)
    output_tokens: Mapped[int] = mapped_column(BigInteger)
    cached_input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    request_count: Mapped[int] = mapped_column(Integer, default=1)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="success")
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    cost: Mapped[Decimal] = mapped_column(EVENT_COST)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"))  # NULL = unallocated
    use_case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("use_cases.id"))  # NULL = unallocated
    task_external_id: Mapped[Optional[str]] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(64), default="")
    ingestion_batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ingestion_batches.id"))


class CostItem(Base):
    """Non-usage AI costs and their allocation (use case, department or organization)."""

    __tablename__ = "cost_items"
    __table_args__ = (
        UniqueConstraint("organization_id", "external_id"),
        CheckConstraint(
            "category IN ('subscription','infrastructure','implementation','maintenance','other_operating')",
            name="ck_cost_items_category"),
        CheckConstraint("period_end >= period_start", name="ck_cost_items_period"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(32))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    period_start: Mapped[dt.date] = mapped_column(Date)
    period_end: Mapped[dt.date] = mapped_column(Date)
    one_off: Mapped[bool] = mapped_column(Boolean, default=False)
    description_key: Mapped[str] = mapped_column(String(128), default="")
    use_case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("use_cases.id"))
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"))


class BenefitClaim(Base):
    __tablename__ = "benefit_claims"
    __table_args__ = (
        UniqueConstraint("organization_id", "external_id"),
        CheckConstraint(
            "category IN ('financial_savings','incremental_contribution','cost_avoidance')",
            name="ck_benefit_category"),
        CheckConstraint(
            "verification_status IN ('verified','supported','estimated','unverified')",
            name="ck_benefit_status"),
        CheckConstraint("amount >= 0", name="ck_benefit_amount"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(64))
    use_case_id: Mapped[int] = mapped_column(ForeignKey("use_cases.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(32))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    verification_status: Mapped[str] = mapped_column(String(16))
    evidence_key: Mapped[str] = mapped_column(String(255))
    period_start: Mapped[dt.date] = mapped_column(Date)
    period_end: Mapped[dt.date] = mapped_column(Date)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    source: Mapped[str] = mapped_column(Text, default="")
    verified_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("organization_id", "department_id", "month"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(64))
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"))  # NULL = org-wide
    month: Mapped[dt.date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(MONEY)


class Alert(Base):
    """Persisted recommendation/alert instances (acknowledgement workflow)."""

    __tablename__ = "alerts"
    __table_args__ = (UniqueConstraint("organization_id", "rule_id", "scope_type", "scope_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    rule_id: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    scope_type: Mapped[str] = mapped_column(String(32))
    scope_key: Mapped[str] = mapped_column(String(128))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    first_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    acknowledged_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    acknowledged_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True))


class AssumptionSet(Base):
    __tablename__ = "assumption_sets"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), unique=True)
    values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class ROISnapshot(Base):
    """Frozen ROI results, so a reported figure can be reproduced later."""

    __tablename__ = "roi_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    scope_type: Mapped[str] = mapped_column(String(32))  # organization | department | use_case
    scope_key: Mapped[str] = mapped_column(String(128))
    period_start: Mapped[dt.date] = mapped_column(Date)
    period_end: Mapped[dt.date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32))
    total_cost: Mapped[Decimal] = mapped_column(MONEY)
    gross_benefit: Mapped[Decimal] = mapped_column(MONEY)
    net_benefit: Mapped[Optional[Decimal]] = mapped_column(MONEY)
    roi_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    data_version: Mapped[int] = mapped_column(Integer)
    assumptions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_org_time", "organization_id", "created_at"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[Optional[str]] = mapped_column(String(128))
    before: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    after: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
