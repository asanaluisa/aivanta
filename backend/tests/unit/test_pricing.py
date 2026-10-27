from datetime import date, datetime
from decimal import Decimal

import pytest

from aivanta_core.domain import PricingRule
from aivanta_core.pricing import PricingError, PricingSchedule, cheaper_alternative, token_cost
from tests.conftest import make_event

D = Decimal


def test_token_cost_with_cache(rule):
    # 1,000,000 input of which 400,000 cached, 100,000 output
    cost = token_cost(rule, input_tokens=1_000_000, output_tokens=100_000, cached_input_tokens=400_000)
    # 600k * 2 + 400k * 0.5 + 100k * 8, per million = 1.2 + 0.2 + 0.8
    assert cost == D("2.2")


def test_cached_price_falls_back_to_input_price():
    r = PricingRule("openai", "m", date(2026, 1, 1), D("2"), D("8"))
    assert token_cost(r, input_tokens=1_000_000, output_tokens=0, cached_input_tokens=1_000_000) == D("2")


@pytest.mark.parametrize("kw", [
    dict(input_tokens=-1, output_tokens=0),
    dict(input_tokens=10, output_tokens=0, cached_input_tokens=11),
])
def test_invalid_token_counts_rejected(rule, kw):
    with pytest.raises(ValueError):
        token_cost(rule, **kw)


def test_schedule_uses_price_effective_on_event_date():
    s = PricingSchedule([
        PricingRule("openai", "m", date(2026, 1, 1), D("10"), D("0")),
        PricingRule("openai", "m", date(2026, 8, 15), D("5"), D("0")),
    ])
    before = make_event(occurred_at=datetime(2026, 8, 14, 23, 59), input_tokens=1_000_000, output_tokens=0)
    after = make_event(occurred_at=datetime(2026, 8, 15, 0, 0), input_tokens=1_000_000, output_tokens=0)
    assert s.cost_of(before) == D("10")
    assert s.cost_of(after) == D("5")


def test_missing_pricing_raises():
    s = PricingSchedule([PricingRule("openai", "m", date(2026, 6, 1), D("1"), D("1"))])
    with pytest.raises(PricingError):
        s.cost_of(make_event(model="other"))
    with pytest.raises(PricingError):
        s.cost_of(make_event(occurred_at=datetime(2026, 1, 1)))


def test_negative_price_rejected():
    with pytest.raises(ValueError):
        PricingSchedule([PricingRule("openai", "m", date(2026, 1, 1), D("-1"), D("1"))])


def test_request_count_must_be_positive(rule):
    s = PricingSchedule([rule])
    with pytest.raises(ValueError):
        s.cost_of(make_event(request_count=0))


def test_cheaper_alternative_same_provider_economy_only():
    d = date(2026, 1, 1)
    s = PricingSchedule([
        PricingRule("openai", "big", d, D("5"), D("15"), tier="frontier"),
        PricingRule("openai", "mid", d, D("1"), D("4"), tier="standard"),
        PricingRule("openai", "small", d, D("0.3"), D("1.2"), tier="economy"),
        PricingRule("google", "tiny", d, D("0.01"), D("0.01"), tier="economy"),
    ])
    alt = cheaper_alternative(s, "openai", "big", d)
    assert alt is not None and alt.model == "small"
    assert cheaper_alternative(s, "openai", "small", d) is None
