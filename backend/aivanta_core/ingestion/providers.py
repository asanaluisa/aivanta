"""Vendor-specific adapters.

These parse *files* exported from each vendor. Field names follow each
vendor's publicly documented usage shape as understood when this module was
written (mid-2026); vendors change these APIs, so every adapter is covered by
fixture tests in ``tests/fixtures`` and unknown fields are ignored rather than
trusted. Live pulls from vendor APIs are **not implemented** — see
``LIVE_SYNC_STATUS``.

* OpenAI — organization Usage API, completions endpoint (bucketed JSON).
  ``input_tokens`` already includes ``input_cached_tokens``.
* Anthropic — Admin API messages usage report (bucketed JSON).
  Prompt size = ``uncached_input_tokens`` + cache creation + ``cache_read_input_tokens``.
  The report does not carry a request count, so each result row counts as 1.
  Cache *writes* are priced at the normal input rate (a documented simplification).
* Google Gemini — JSON Lines of ``usageMetadata`` captured from
  ``generateContent`` responses by your gateway (Gemini has no organization
  usage endpoint equivalent to the two above). ``thoughtsTokenCount`` is billed
  as output and is added to ``output_tokens``.
"""
from __future__ import annotations

import json
from typing import Any, Iterable, Optional

from ..domain import RequestStatus, UsageEvent
from .base import (
    AttributionMap,
    IngestionError,
    IngestionResult,
    RejectedRow,
    non_negative_int,
    parse_timestamp,
    stable_id,
)

LIVE_SYNC_STATUS = {
    "openai": "not_implemented",
    "anthropic": "not_implemented",
    "google": "not_implemented",
}


def _load_json(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise IngestionError(f"invalid JSON: {exc.msg} at line {exc.lineno}") from exc


def _check_model(provider: str, model: Optional[str], known: Optional[set[tuple[str, str]]]) -> str:
    if not model:
        raise ValueError("model is missing (export grouped without group_by=model?)")
    if known is not None and (provider, model) not in known:
        raise ValueError(f"model '{provider}/{model}' has no pricing")
    return model


def parse_openai(content: str, attribution: AttributionMap,
                 known_models: Optional[set[tuple[str, str]]] = None) -> IngestionResult:
    doc = _load_json(content)
    pages: Iterable[dict] = doc if isinstance(doc, list) else [doc]
    result = IngestionResult(provider="openai", format="openai_usage_completions")
    for p_i, page in enumerate(pages):
        buckets = page.get("data")
        if not isinstance(buckets, list):
            raise IngestionError("expected an object with a 'data' list of buckets")
        for b_i, bucket in enumerate(buckets):
            for r_i, r in enumerate(bucket.get("results", [])):
                ref = f"page {p_i} bucket {b_i} result {r_i}"
                try:
                    model = _check_model("openai", r.get("model"), known_models)
                    inp = non_negative_int(r.get("input_tokens"), "input_tokens")
                    cached = non_negative_int(r.get("input_cached_tokens"), "input_cached_tokens")
                    if cached > inp:
                        raise ValueError("input_cached_tokens exceeds input_tokens")
                    req = max(1, non_negative_int(r.get("num_model_requests"), "num_model_requests"))
                    att = attribution.resolve(("api_key", r.get("api_key_id")),
                                              ("project", r.get("project_id")))
                    result.events.append(UsageEvent(
                        event_id=stable_id("openai", bucket.get("start_time"), model,
                                           r.get("project_id"), r.get("api_key_id"),
                                           r.get("user_id"), r.get("batch")),
                        occurred_at=parse_timestamp(bucket["start_time"]),
                        provider="openai", model=model,
                        input_tokens=inp,
                        output_tokens=non_negative_int(r.get("output_tokens"), "output_tokens"),
                        cached_input_tokens=cached,
                        request_count=req,
                        status=RequestStatus.SUCCESS.value,
                        user_id=r.get("user_id"),
                        department_id=att.department_id,
                        use_case_id=att.use_case_id,
                        source="openai_usage_api_export",
                    ))
                except (ValueError, KeyError) as exc:
                    result.rejected.append(RejectedRow(ref, str(exc)))
    return result


def parse_anthropic(content: str, attribution: AttributionMap,
                    known_models: Optional[set[tuple[str, str]]] = None) -> IngestionResult:
    doc = _load_json(content)
    pages: Iterable[dict] = doc if isinstance(doc, list) else [doc]
    result = IngestionResult(provider="anthropic", format="anthropic_usage_report_messages")
    for p_i, page in enumerate(pages):
        buckets = page.get("data")
        if not isinstance(buckets, list):
            raise IngestionError("expected an object with a 'data' list of buckets")
        for b_i, bucket in enumerate(buckets):
            for r_i, r in enumerate(bucket.get("results", [])):
                ref = f"page {p_i} bucket {b_i} result {r_i}"
                try:
                    model = _check_model("anthropic", r.get("model"), known_models)
                    uncached = non_negative_int(r.get("uncached_input_tokens"), "uncached_input_tokens")
                    creation = r.get("cache_creation") or {}
                    created = sum(non_negative_int(v, k) for k, v in creation.items())
                    read = non_negative_int(r.get("cache_read_input_tokens"), "cache_read_input_tokens")
                    att = attribution.resolve(("api_key", r.get("api_key_id")),
                                              ("workspace", r.get("workspace_id")))
                    result.events.append(UsageEvent(
                        event_id=stable_id("anthropic", bucket.get("starting_at"), model,
                                           r.get("workspace_id"), r.get("api_key_id"),
                                           r.get("service_tier")),
                        occurred_at=parse_timestamp(bucket["starting_at"]),
                        provider="anthropic", model=model,
                        input_tokens=uncached + created + read,
                        output_tokens=non_negative_int(r.get("output_tokens"), "output_tokens"),
                        cached_input_tokens=read,
                        request_count=1,
                        status=RequestStatus.SUCCESS.value,
                        department_id=att.department_id,
                        use_case_id=att.use_case_id,
                        source="anthropic_usage_report_export",
                    ))
                except (ValueError, KeyError) as exc:
                    result.rejected.append(RejectedRow(ref, str(exc)))
    return result


def parse_gemini(content: str, attribution: AttributionMap,
                 known_models: Optional[set[tuple[str, str]]] = None) -> IngestionResult:
    result = IngestionResult(provider="google", format="gemini_usage_metadata_jsonl")
    for line_no, line in enumerate(content.splitlines(), start=1):
        if not line.strip():
            continue
        ref = f"line {line_no}"
        try:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON: {exc.msg}") from exc
            model = rec.get("modelVersion") or rec.get("model")
            model = _check_model("google", model, known_models)
            meta = rec.get("usageMetadata")
            if not isinstance(meta, dict):
                raise ValueError("usageMetadata is missing")
            prompt = non_negative_int(meta.get("promptTokenCount"), "promptTokenCount")
            cached = non_negative_int(meta.get("cachedContentTokenCount"), "cachedContentTokenCount")
            if cached > prompt:
                raise ValueError("cachedContentTokenCount exceeds promptTokenCount")
            output = (non_negative_int(meta.get("candidatesTokenCount"), "candidatesTokenCount")
                      + non_negative_int(meta.get("thoughtsTokenCount"), "thoughtsTokenCount"))
            labels = rec.get("labels") or {}
            att = attribution.resolve(("label", labels.get("use_case")),
                                      ("api_key", rec.get("api_key_id")))
            status = (RequestStatus.ERROR.value if rec.get("error")
                      else RequestStatus.SUCCESS.value)
            latency = rec.get("latencyMs")
            result.events.append(UsageEvent(
                event_id=rec.get("responseId") or stable_id("google", line),
                occurred_at=parse_timestamp(rec["timestamp"]),
                provider="google", model=model,
                input_tokens=prompt, output_tokens=output, cached_input_tokens=cached,
                request_count=1 + non_negative_int(rec.get("retries"), "retries"),
                retries=non_negative_int(rec.get("retries"), "retries"),
                status=status,
                latency_ms=non_negative_int(latency, "latencyMs") if latency is not None else None,
                user_id=labels.get("user"),
                department_id=att.department_id,
                use_case_id=att.use_case_id,
                source="gemini_response_log",
            ))
        except (ValueError, KeyError) as exc:
            result.rejected.append(RejectedRow(ref, str(exc)))
    return result
