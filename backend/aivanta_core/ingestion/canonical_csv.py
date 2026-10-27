"""Aivanta canonical CSV — the primary, fully documented ingestion format.

Use it to load usage from any gateway, proxy or provider export you have
already normalized. Columns (header row required, order free):

=====================  ========  ==================================================
column                 required  notes
=====================  ========  ==================================================
occurred_at            yes       ISO-8601 or unix seconds, UTC
provider               yes       ``openai`` | ``anthropic`` | ``google``
model                  yes       must exist in the pricing schedule
input_tokens           yes       full prompt tokens (cached tokens included)
output_tokens          yes
cached_input_tokens    no        subset of input_tokens served from cache
request_count          no        API calls incl. retries (default 1)
retries                no        default 0
status                 no        ``success`` | ``error`` (default success)
latency_ms             no
user_id                no
department_id          no        blank = unallocated
use_case_id            no        blank = unallocated
task_id                no
event_id               no        your own idempotency key; hashed from the row if absent
=====================  ========  ==================================================
"""
from __future__ import annotations

import csv
import io

from ..domain import Provider, RequestStatus, UsageEvent
from .base import IngestionError, IngestionResult, RejectedRow, non_negative_int, parse_timestamp, stable_id

REQUIRED = ("occurred_at", "provider", "model", "input_tokens", "output_tokens")
PROVIDERS = {p.value for p in Provider}
STATUSES = {s.value for s in RequestStatus}


def parse(content: str, *, known_models: set[tuple[str, str]] | None = None) -> IngestionResult:
    reader = csv.DictReader(io.StringIO(content.lstrip("﻿")))
    if reader.fieldnames is None:
        raise IngestionError("empty file")
    missing = [c for c in REQUIRED if c not in reader.fieldnames]
    if missing:
        raise IngestionError(f"missing required columns: {', '.join(missing)}")
    result = IngestionResult(provider="mixed", format="aivanta_csv")
    for line_no, row in enumerate(reader, start=2):
        try:
            provider = (row.get("provider") or "").strip().lower()
            if provider not in PROVIDERS:
                raise ValueError(f"unknown provider '{provider}'")
            model = (row.get("model") or "").strip()
            if not model:
                raise ValueError("model is required")
            if known_models is not None and (provider, model) not in known_models:
                raise ValueError(f"model '{provider}/{model}' has no pricing")
            status = (row.get("status") or "success").strip().lower()
            if status not in STATUSES:
                raise ValueError(f"unknown status '{status}'")
            inp = non_negative_int(row.get("input_tokens"), "input_tokens")
            cached = non_negative_int(row.get("cached_input_tokens"), "cached_input_tokens")
            if cached > inp:
                raise ValueError("cached_input_tokens exceeds input_tokens")
            req = non_negative_int(row.get("request_count") or 1, "request_count")
            if req < 1:
                raise ValueError("request_count must be >= 1")
            occurred = parse_timestamp(row["occurred_at"])
            latency = row.get("latency_ms")
            ev = UsageEvent(
                event_id=(row.get("event_id") or "").strip()
                or stable_id("csv", *(row.get(k) for k in sorted(row))),
                occurred_at=occurred,
                provider=provider,
                model=model,
                input_tokens=inp,
                output_tokens=non_negative_int(row.get("output_tokens"), "output_tokens"),
                cached_input_tokens=cached,
                request_count=req,
                retries=non_negative_int(row.get("retries"), "retries"),
                status=status,
                latency_ms=non_negative_int(latency, "latency_ms") if latency else None,
                user_id=(row.get("user_id") or "").strip() or None,
                department_id=(row.get("department_id") or "").strip() or None,
                use_case_id=(row.get("use_case_id") or "").strip() or None,
                task_id=(row.get("task_id") or "").strip() or None,
                source="aivanta_csv",
            )
        except (ValueError, KeyError) as exc:
            result.rejected.append(RejectedRow(f"line {line_no}", str(exc)))
            continue
        result.events.append(ev)
    return result
