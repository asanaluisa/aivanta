"""Shared ingestion types.

Every provider adapter turns a vendor export into normalized
:class:`~aivanta_core.domain.UsageEvent` objects with these conventions:

* ``input_tokens`` is the full prompt size; ``cached_input_tokens`` is the part
  served from cache (a subset of ``input_tokens``).
* Attribution to a department and use case comes from an
  :class:`AttributionMap` keyed by whatever identifier the vendor exposes
  (API key, project, workspace, request label). Unknown identifiers stay
  ``None`` — the record is kept and reported as *unallocated*, never guessed.
* ``event_id`` is a deterministic hash of the source row so re-uploading the
  same file is idempotent.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Optional

from ..domain import UsageEvent


class IngestionError(ValueError):
    """The file as a whole could not be parsed."""


@dataclass(frozen=True)
class Attribution:
    department_id: Optional[str] = None
    use_case_id: Optional[str] = None


@dataclass
class AttributionMap:
    """Maps vendor identifiers (``"api_key:key_abc"``, ``"project:proj_1"``…) to scope."""

    rules: dict[str, Attribution] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "AttributionMap":
        rules = {}
        for key, value in data.items():
            if key.startswith("_"):
                continue
            if ":" not in key or not isinstance(value, dict):
                raise ValueError(f"invalid attribution rule '{key}'")
            rules[key] = Attribution(value.get("department_id"), value.get("use_case_id"))
        return cls(rules)

    def resolve(self, *identifiers: tuple[str, Optional[str]]) -> Attribution:
        for kind, value in identifiers:
            if value is None:
                continue
            hit = self.rules.get(f"{kind}:{value}")
            if hit is not None:
                return hit
        return Attribution()


@dataclass
class RejectedRow:
    row: str
    reason: str


@dataclass
class IngestionResult:
    provider: str
    format: str
    events: list[UsageEvent] = field(default_factory=list)
    rejected: list[RejectedRow] = field(default_factory=list)

    @property
    def unallocated(self) -> int:
        return sum(1 for e in self.events if e.department_id is None or e.use_case_id is None)

    def summary(self) -> dict:
        return {
            "provider": self.provider,
            "format": self.format,
            "accepted": len(self.events),
            "rejected": len(self.rejected),
            "unallocated": self.unallocated,
            "rejections": [{"row": r.row, "reason": r.reason} for r in self.rejected[:50]],
        }


def stable_id(*parts: object) -> str:
    raw = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def parse_timestamp(value: object) -> datetime:
    """Accept unix seconds or ISO-8601 (with ``Z``); return a naive UTC datetime."""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc).replace(tzinfo=None)
    if isinstance(value, str):
        s = value.strip()
        if s.isdigit():
            return parse_timestamp(int(s))
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    raise ValueError(f"unrecognised timestamp {value!r}")


def non_negative_int(value: object, name: str) -> int:
    if value is None or value == "":
        return 0
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if n < 0:
        raise ValueError(f"{name} must be >= 0")
    return n


def known_models(pairs: Iterable[tuple[str, str]]) -> set[tuple[str, str]]:
    return set(pairs)
