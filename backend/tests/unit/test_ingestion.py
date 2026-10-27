import json
from datetime import datetime

import pytest

from aivanta_core import ingestion
from aivanta_core.ingestion import AttributionMap, IngestionError
from aivanta_core.synthetic import pricing_rules
from tests.conftest import SAMPLES

KNOWN = {(r.provider, r.model) for r in pricing_rules()}


@pytest.fixture(scope="module")
def attribution():
    return AttributionMap.from_dict(json.loads((SAMPLES / "attribution_map.json").read_text()))


def test_openai_sample(attribution):
    r = ingestion.parse("openai", (SAMPLES / "openai_usage_completions.json").read_text(), attribution, KNOWN)
    assert len(r.events) == 2 and len(r.rejected) == 1
    assert "exceeds" in r.rejected[0].reason
    sales, sandbox = r.events
    assert (sales.input_tokens, sales.cached_input_tokens, sales.output_tokens) == (1840000, 420000, 96000)
    assert sales.request_count == 412
    assert sales.occurred_at == datetime(2026, 9, 27)
    assert (sales.department_id, sales.use_case_id) == ("sales", "sales_outreach")
    assert sandbox.department_id is None and sandbox.use_case_id is None  # stays unallocated
    assert r.summary()["unallocated"] == 1


def test_anthropic_sample(attribution):
    r = ingestion.parse("anthropic", (SAMPLES / "anthropic_usage_report.json").read_text(), attribution, KNOWN)
    assert len(r.events) == 2 and len(r.rejected) == 1
    assert "no pricing" in r.rejected[0].reason
    support, eng = r.events
    # prompt = uncached + cache creation + cache read
    assert support.input_tokens == 950000 + 50000 + 1200000
    assert support.cached_input_tokens == 1200000
    assert support.request_count == 1
    assert (support.department_id, support.use_case_id) == ("customer_support", "support_triage")
    assert (eng.department_id, eng.use_case_id) == ("engineering", None)  # partially attributed


def test_gemini_sample(attribution):
    r = ingestion.parse("google", (SAMPLES / "gemini_usage_metadata.jsonl").read_text(), attribution, KNOWN)
    assert len(r.events) == 3 and len(r.rejected) == 2
    first, second, failed = r.events
    assert first.output_tokens == 3900 + 800  # thinking tokens billed as output
    assert first.cached_input_tokens == 6000
    assert first.use_case_id == "marketing_content" and first.user_id == "u_marketing_03"
    assert second.use_case_id is None and second.request_count == 2 and second.retries == 1
    assert failed.status == "error"


def test_canonical_csv_sample():
    r = ingestion.parse("aivanta_csv", (SAMPLES / "aivanta_usage.csv").read_text(), known_models=KNOWN)
    assert [e.event_id for e in r.events] == ["csv-0001", "csv-0002", "csv-0003"]
    assert len(r.rejected) == 2
    assert r.events[2].status == "error" and r.events[2].department_id is None
    assert r.events[1].retries == 1


def test_event_ids_are_idempotent(attribution):
    content = (SAMPLES / "openai_usage_completions.json").read_text()
    a = ingestion.parse("openai", content, attribution, KNOWN)
    b = ingestion.parse("openai", content, attribution, KNOWN)
    assert [e.event_id for e in a.events] == [e.event_id for e in b.events]


@pytest.mark.parametrize("fmt, content", [
    ("openai", "{not json"),
    ("anthropic", '{"nodata": []}'),
    ("aivanta_csv", "a,b\n1,2\n"),
    ("unknown_vendor", ""),
])
def test_whole_file_errors(fmt, content):
    with pytest.raises(IngestionError):
        ingestion.parse(fmt, content)


def test_invalid_attribution_rule():
    with pytest.raises(ValueError):
        AttributionMap.from_dict({"no-colon": {}})


def test_live_sync_is_labelled_not_implemented():
    assert set(ingestion.LIVE_SYNC_STATUS.values()) == {"not_implemented"}
