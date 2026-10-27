from __future__ import annotations

import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from aivanta_core import synthetic  # noqa: E402
from aivanta_core.domain import PricingRule, TaskRecord, UsageEvent  # noqa: E402

SAMPLES = REPO / "samples"


@pytest.fixture(scope="session")
def demo():
    """The full synthetic dataset (generated once per test session)."""
    return synthetic.generate()


@pytest.fixture
def rule():
    return PricingRule("openai", "m", date(2026, 1, 1), Decimal("2"), Decimal("8"), Decimal("0.5"))


def make_event(**kw) -> UsageEvent:
    base = dict(event_id="e1", occurred_at=datetime(2026, 9, 1, 12), provider="openai", model="m",
                input_tokens=1000, output_tokens=100)
    base.update(kw)
    return UsageEvent(**base)


def make_task(i: int, arm: str = "ai", minutes: float = 10.0, **kw) -> TaskRecord:
    base = dict(task_id=f"t{arm}{i}", use_case_id="uc", arm=arm, completed_on=date(2026, 9, 1),
                duration_minutes=minutes, success=True, quality_score=0.9)
    base.update(kw)
    return TaskRecord(**base)
