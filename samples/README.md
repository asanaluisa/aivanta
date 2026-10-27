# Ingestion samples

Example files for every supported format. They are small, hand-written and **synthetic**, dated 27–28 September 2026 so they fall inside the demo period. Each file deliberately contains invalid rows to show validation.

| File | Format id | Upload with |
|---|---|---|
| `aivanta_usage.csv` | `aivanta_csv` | `POST /api/ingestion/aivanta_csv` |
| `openai_usage_completions.json` | `openai` | `POST /api/ingestion/openai` |
| `anthropic_usage_report.json` | `anthropic` | `POST /api/ingestion/anthropic` |
| `gemini_usage_metadata.jsonl` | `google` | `POST /api/ingestion/google` |
| `attribution_map.json` | — | loaded by the seed script as attribution rules |

```bash
TOKEN=$(curl -s localhost:8000/api/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"analyst@aivanta.demo","password":"aivanta-demo"}' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s -H "Authorization: Bearer $TOKEN" -F file=@samples/aivanta_usage.csv localhost:8000/api/ingestion/aivanta_csv
```

Expected results: CSV → 3 accepted, 2 rejected (cached > input, unknown provider); OpenAI → 2 accepted (1 unallocated), 1 rejected; Anthropic → 2 accepted, 1 rejected (model without pricing); Gemini → 3 accepted, 2 rejected (invalid JSON, missing `usageMetadata`). Uploading the same file twice reports every row as a duplicate.

## Canonical CSV columns

| Column | Required | Notes |
|---|---|---|
| `occurred_at` | yes | ISO-8601 or Unix seconds, UTC |
| `provider` | yes | `openai`, `anthropic` or `google` |
| `model` | yes | must exist in the organisation's price schedule |
| `input_tokens` | yes | full prompt, cached tokens included |
| `output_tokens` | yes | |
| `cached_input_tokens` | no | subset of `input_tokens` |
| `request_count` | no | API calls including retries (default 1) |
| `retries`, `status` (`success`/`error`), `latency_ms` | no | |
| `user_id`, `department_id`, `use_case_id`, `task_id` | no | blank department or use case = unallocated |
| `event_id` | no | your idempotency key; otherwise a hash of the row |

## Vendor mappings

| Normalised field | OpenAI usage (completions) | Anthropic usage report | Gemini `usageMetadata` |
|---|---|---|---|
| input tokens | `input_tokens` | `uncached_input_tokens` + cache creation + `cache_read_input_tokens` | `promptTokenCount` |
| cached input tokens | `input_cached_tokens` | `cache_read_input_tokens` | `cachedContentTokenCount` |
| output tokens | `output_tokens` | `output_tokens` | `candidatesTokenCount` + `thoughtsTokenCount` |
| requests | `num_model_requests` | not reported → 1 per row | 1 + `retries` |
| attribution keys | `api_key_id`, `project_id` | `api_key_id`, `workspace_id` | `labels.use_case`, `api_key_id` |

These shapes follow the vendors' public documentation as understood in mid-2026; verify against your own exports before relying on them.
