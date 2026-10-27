"""Usage ingestion: adapters from vendor exports to normalized usage events."""
from __future__ import annotations

from typing import Optional

from . import canonical_csv
from .base import Attribution, AttributionMap, IngestionError, IngestionResult, RejectedRow
from .providers import LIVE_SYNC_STATUS, parse_anthropic, parse_gemini, parse_openai

FORMATS = {
    "aivanta_csv": "Aivanta canonical CSV (all providers)",
    "openai": "OpenAI organization usage export (JSON)",
    "anthropic": "Anthropic usage report export (JSON)",
    "google": "Gemini usageMetadata response log (JSONL)",
}


def parse(fmt: str, content: str, attribution: Optional[AttributionMap] = None,
          known_models: Optional[set[tuple[str, str]]] = None) -> IngestionResult:
    """Dispatch to the adapter for ``fmt``.

    The canonical CSV carries its own attribution columns. For vendor exports,
    attribution comes from ``attribution``; anything unmatched stays unallocated.
    """
    att = attribution or AttributionMap()
    if fmt == "aivanta_csv":
        return canonical_csv.parse(content, known_models=known_models)
    if fmt == "openai":
        return parse_openai(content, att, known_models)
    if fmt == "anthropic":
        return parse_anthropic(content, att, known_models)
    if fmt == "google":
        return parse_gemini(content, att, known_models)
    raise IngestionError(f"unsupported format '{fmt}'")


__all__ = [
    "Attribution", "AttributionMap", "IngestionError", "IngestionResult", "RejectedRow",
    "FORMATS", "LIVE_SYNC_STATUS", "parse",
]
