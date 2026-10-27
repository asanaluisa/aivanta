"""Model pricing: turns token counts into money.

Cost of one usage event::

    uncached_input = input_tokens - cached_input_tokens
    cost = ( uncached_input      * input_per_mtok
           + cached_input_tokens * cached_input_per_mtok   # falls back to input price
           + output_tokens       * output_per_mtok ) / 1_000_000

``input_tokens`` is the *total* prompt size reported by the provider, of which
``cached_input_tokens`` were served from the provider's prompt cache. Adapters
are responsible for normalizing vendor fields to that convention.

The schedule is versioned by ``effective_from`` so historical events keep the
price that applied on the day they occurred.
"""
from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Optional

from .domain import PricingRule, UsageEvent

MILLION = Decimal(1_000_000)
EVENT_COST_QUANT = Decimal("0.00000001")  # keep 8 dp per event; round only for display


class PricingError(LookupError):
    """Raised when no price applies to a provider/model on a date."""


class PricingSchedule:
    def __init__(self, rules: Iterable[PricingRule]):
        self._rules: dict[tuple[str, str], list[PricingRule]] = {}
        for rule in rules:
            if rule.input_per_mtok < 0 or rule.output_per_mtok < 0:
                raise ValueError(f"Negative price for {rule.provider}/{rule.model}")
            if rule.cached_input_per_mtok is not None and rule.cached_input_per_mtok < 0:
                raise ValueError(f"Negative cached price for {rule.provider}/{rule.model}")
            self._rules.setdefault((rule.provider, rule.model), []).append(rule)
        for versions in self._rules.values():
            versions.sort(key=lambda r: r.effective_from)

    def rule_for(self, provider: str, model: str, on: date) -> PricingRule:
        versions = self._rules.get((provider, model))
        if not versions:
            raise PricingError(f"No pricing configured for {provider}/{model}")
        applicable: Optional[PricingRule] = None
        for rule in versions:
            if rule.effective_from <= on:
                applicable = rule
            else:
                break
        if applicable is None:
            raise PricingError(
                f"No pricing for {provider}/{model} effective on {on.isoformat()}"
            )
        return applicable

    def models(self) -> list[tuple[str, str]]:
        return sorted(self._rules)

    def cost_of(self, event: UsageEvent) -> Decimal:
        _validate_tokens(event)
        rule = self.rule_for(event.provider, event.model, event.occurred_at.date())
        return token_cost(
            rule,
            input_tokens=event.input_tokens,
            output_tokens=event.output_tokens,
            cached_input_tokens=event.cached_input_tokens,
        )

    def price_events(self, events: Iterable[UsageEvent]) -> list[UsageEvent]:
        """Set ``cost`` on every event in place and return them."""
        priced = []
        for event in events:
            event.cost = self.cost_of(event)
            priced.append(event)
        return priced


def token_cost(
    rule: PricingRule, *, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0
) -> Decimal:
    if min(input_tokens, output_tokens, cached_input_tokens) < 0:
        raise ValueError("Token counts cannot be negative")
    if cached_input_tokens > input_tokens:
        raise ValueError("cached_input_tokens cannot exceed input_tokens")
    cached_price = (
        rule.cached_input_per_mtok
        if rule.cached_input_per_mtok is not None
        else rule.input_per_mtok
    )
    uncached = input_tokens - cached_input_tokens
    raw = (
        Decimal(uncached) * rule.input_per_mtok
        + Decimal(cached_input_tokens) * cached_price
        + Decimal(output_tokens) * rule.output_per_mtok
    ) / MILLION
    return raw.quantize(EVENT_COST_QUANT, rounding=ROUND_HALF_UP)


def _validate_tokens(event: UsageEvent) -> None:
    if event.cached_input_tokens > event.input_tokens:
        raise ValueError(
            f"Event {event.event_id}: cached_input_tokens exceeds input_tokens"
        )
    if event.request_count < 1:
        raise ValueError(f"Event {event.event_id}: request_count must be >= 1")


def cheaper_alternative(
    schedule: PricingSchedule, provider: str, model: str, on: date
) -> Optional[PricingRule]:
    """Cheapest economy-tier model of the same provider, if cheaper than ``model``."""
    current = schedule.rule_for(provider, model, on)
    best: Optional[PricingRule] = None
    for prov, mdl in schedule.models():
        if prov != provider or mdl == model:
            continue
        try:
            candidate = schedule.rule_for(prov, mdl, on)
        except PricingError:
            continue
        if candidate.tier != "economy":
            continue
        blended = candidate.input_per_mtok + candidate.output_per_mtok
        if blended >= current.input_per_mtok + current.output_per_mtok:
            continue
        if best is None or blended < best.input_per_mtok + best.output_per_mtok:
            best = candidate
    return best
