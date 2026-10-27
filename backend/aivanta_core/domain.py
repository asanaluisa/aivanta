"""Language-neutral domain objects used by every Aivanta calculation.

This module has no framework dependencies on purpose: the cost, ROI, evidence,
comparison and recommendation engines operate on these plain dataclasses so
they can be unit-tested deterministically and reused by the API, the seed
script and offline analysis alike.

Conventions
-----------
* Money is ``decimal.Decimal`` in the organization's reporting currency.
* Durations are minutes (``float``).
* Identifiers and enum values are English snake_case; display labels are
  resolved by the frontend localization files, never stored here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

ZERO = Decimal("0")


class Provider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class RequestStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"


class TaskArm(str, Enum):
    """Which arm of a comparison a task belongs to."""

    AI = "ai"
    NON_AI = "non_ai"


class StudyDesign(str, Enum):
    """How the AI vs. non-AI evidence was collected.

    Only randomized experiments and concurrent control groups support causal
    language. Before/after and observational data are reported as
    associations.
    """

    RANDOMIZED = "randomized"
    CONTROL_GROUP = "control_group"
    BEFORE_AFTER = "before_after"
    OBSERVATIONAL = "observational"

    @property
    def supports_causal_claim(self) -> bool:
        return self in (StudyDesign.RANDOMIZED, StudyDesign.CONTROL_GROUP)


class BenefitCategory(str, Enum):
    FINANCIAL_SAVINGS = "financial_savings"
    INCREMENTAL_CONTRIBUTION = "incremental_contribution"
    COST_AVOIDANCE = "cost_avoidance"


class VerificationStatus(str, Enum):
    """Strength of evidence behind a benefit claim (strongest first)."""

    VERIFIED = "verified"  # reconciled to the general ledger / invoices
    SUPPORTED = "supported"  # backed by a controlled measurement
    ESTIMATED = "estimated"  # modelled from assumptions; never in ROI
    UNVERIFIED = "unverified"  # claimed without evidence; never in ROI

    @property
    def rank(self) -> int:
        return {
            VerificationStatus.VERIFIED: 0,
            VerificationStatus.SUPPORTED: 1,
            VerificationStatus.ESTIMATED: 2,
            VerificationStatus.UNVERIFIED: 3,
        }[self]


class CostCategory(str, Enum):
    MODEL_USAGE = "model_usage"  # derived from usage events, never entered manually
    SUBSCRIPTION = "subscription"
    INFRASTRUCTURE = "infrastructure"
    IMPLEMENTATION = "implementation"  # one-off
    MAINTENANCE = "maintenance"
    HUMAN_REVIEW = "human_review"  # derived from task review minutes
    REWORK = "rework"  # derived from task rework minutes
    OTHER_OPERATING = "other_operating"


class DataOrigin(str, Enum):
    """Provenance shown next to every number in the UI."""

    MEASURED = "measured"
    ESTIMATED = "estimated"
    SYNTHETIC = "synthetic"


@dataclass(frozen=True)
class PricingRule:
    """Price per million tokens for a model, valid from ``effective_from``."""

    provider: str
    model: str
    effective_from: date
    input_per_mtok: Decimal
    output_per_mtok: Decimal
    cached_input_per_mtok: Optional[Decimal] = None
    tier: str = "standard"  # "frontier" | "standard" | "economy"


@dataclass
class UsageEvent:
    """One normalized unit of AI consumption.

    ``request_count`` counts API calls (including retries) that produced the
    reported token totals. ``department_id``/``use_case_id`` are ``None`` when
    the source system could not attribute the usage; such records remain
    explicitly unallocated.
    """

    event_id: str
    occurred_at: datetime
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0
    request_count: int = 1
    retries: int = 0
    status: str = RequestStatus.SUCCESS.value
    latency_ms: Optional[int] = None
    user_id: Optional[str] = None
    department_id: Optional[str] = None
    use_case_id: Optional[str] = None
    task_id: Optional[str] = None
    source: str = "synthetic"
    cost: Optional[Decimal] = None  # filled by the pricing engine

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class TaskRecord:
    """A unit of business work, with or without AI assistance."""

    task_id: str
    use_case_id: str
    arm: str  # TaskArm value
    completed_on: date
    duration_minutes: float
    success: bool
    quality_score: Optional[float] = None  # 0..1
    had_error: bool = False
    rework_minutes: float = 0.0
    review_minutes: float = 0.0
    customer_satisfaction: Optional[float] = None  # 1..5
    task_type: str = "standard"
    user_id: Optional[str] = None


@dataclass
class UseCase:
    use_case_id: str
    name_key: str  # localization key, e.g. "use_case.support_triage"
    department_id: Optional[str]
    task_complexity: str = "standard"  # "simple" | "standard" | "complex"
    study_design: str = StudyDesign.OBSERVATIONAL.value
    measurement_start: Optional[date] = None
    measurement_end: Optional[date] = None
    data_source: str = ""
    baseline_minutes: Optional[float] = None  # documented pre-AI baseline


@dataclass
class Department:
    department_id: str
    name_key: str
    loaded_hourly_rate: Decimal  # fully loaded labour cost assumption


@dataclass
class CostItem:
    """A non-usage AI cost, allocated to a use case, a department, or the org."""

    cost_id: str
    category: str  # CostCategory value
    amount: Decimal
    period_start: date
    period_end: date
    description_key: str = ""
    use_case_id: Optional[str] = None
    department_id: Optional[str] = None
    one_off: bool = False


@dataclass
class BenefitClaim:
    """A financial benefit attributed to AI for a period.

    ``evidence_key`` identifies the underlying business outcome. Two claims
    with the same key describe the same economic effect (for example "tickets
    deflected" booked once as cost avoidance and again as savings) and are
    counted once — the strongest-verified claim wins.
    """

    benefit_id: str
    use_case_id: str
    category: str  # BenefitCategory value
    amount: Decimal
    verification_status: str  # VerificationStatus value
    evidence_key: str
    period_start: date
    period_end: date
    confidence: float = 0.5  # 0..1, analyst judgement
    source: str = ""


@dataclass
class Budget:
    budget_id: str
    department_id: Optional[str]  # None = organization-wide
    month: date  # first day of month
    amount: Decimal


@dataclass
class Assumptions:
    """Editable assumptions that drive scenarios and evidence thresholds."""

    min_sample_size: int = 30
    min_measurement_days: int = 14
    conservative_benefit_haircut: Decimal = Decimal("0.30")
    conservative_cost_contingency: Decimal = Decimal("0.10")
    optimistic_estimated_benefit_share: Decimal = Decimal("0.50")
    quality_tolerance: float = 0.03  # max acceptable absolute quality drop
    budget_warning_ratio: Decimal = Decimal("0.80")
    review_erosion_ratio: float = 0.70
    spend_growth_alert_ratio: float = 0.25
    anomaly_sigma: float = 3.0


@dataclass
class Dataset:
    """Everything the engines need for one organization."""

    organization_id: str
    currency: str
    period_start: date
    period_end: date
    departments: list[Department] = field(default_factory=list)
    use_cases: list[UseCase] = field(default_factory=list)
    pricing: list[PricingRule] = field(default_factory=list)
    usage_events: list[UsageEvent] = field(default_factory=list)
    tasks: list[TaskRecord] = field(default_factory=list)
    cost_items: list[CostItem] = field(default_factory=list)
    benefits: list[BenefitClaim] = field(default_factory=list)
    budgets: list[Budget] = field(default_factory=list)
    users: dict[str, str] = field(default_factory=dict)  # user_id -> department_id
    assumptions: Assumptions = field(default_factory=Assumptions)
    is_synthetic: bool = False

    def department(self, department_id: str) -> Optional[Department]:
        return next((d for d in self.departments if d.department_id == department_id), None)

    def use_case(self, use_case_id: str) -> Optional[UseCase]:
        return next((u for u in self.use_cases if u.use_case_id == use_case_id), None)
