# Linkup API Reference
> Researched 2026-08-27. Source: docs.linkup.so/llms-full.txt + PyPI linkup-sdk.

## Overview
- Base URL: `https://api.linkup.so/v1`
- Auth: `Authorization: Bearer <API_KEY>`
- SDK: `pip install linkup-sdk` (Python 3.10+, uses httpx + pydantic)
- SimpleQA benchmark: **94% F-score** (ranks #1 sub-second search APIs)
- Pricing currency: USD (converted from EUR May 2026, 1:1 parity)
- Free monthly top-up: $20 (eligible accounts)

---

## Endpoints

### 1. POST /v1/search — Main search (sync)
The primary endpoint. Sub-second to ~30s depending on depth.

**Request body (JSON):**

| Parameter | Type | Required | Default | Allowed values |
|-----------|------|----------|---------|----------------|
| `q` | string | yes | — | Any search query |
| `depth` | string | no | `"standard"` | `"fast"` (beta, <1s), `"standard"`, `"deep"` (iterative, ~30s) |
| `outputType` | string | no | `"searchResults"` | `"searchResults"`, `"sourcedAnswer"`, `"structured"` |
| `maxResults` | integer | no | — | Limits returned results |
| `fromDate` | string | no | — | `YYYY-MM-DD` — start of date range |
| `toDate` | string | no | — | `YYYY-MM-DD` — end of date range |
| `includeDomains` | string[] | no | — | Only return results from these domains |
| `excludeDomains` | string[] | no | — | Skip results from these domains |
| `includeImages` | boolean | no | false | Include image results alongside text |
| `structuredOutputSchema` | object | conditional | — | Required when `outputType="structured"` |

**outputType values explained:**
- `"searchResults"` — list of URLs + snippets, no LLM synthesis
- `"sourcedAnswer"` — LLM-synthesized answer with source citations (like Perplexity)
- `"structured"` — JSON matching `structuredOutputSchema`; use for machine-readable extraction

**depth tradeoffs:**
- `"fast"` — sub-second, beta, fewer sources; best for real-time/voice
- `"standard"` — default, good balance; used for TrueBrief news collection
- `"deep"` — iterative search-and-scrape chaining, multi-source synthesis, 30s; best for research

**Pricing per call:**

| depth | outputType | Cost |
|-------|-----------|------|
| fast/standard | searchResults | $0.005 |
| fast/standard | sourcedAnswer / structured | $0.006 |
| deep | searchResults | $0.050 |
| deep | sourcedAnswer / structured | $0.055 |

**Response (sourcedAnswer):**
```json
{
  "answer": "string — synthesized answer",
  "sources": [
    {
      "url": "string",
      "title": "string",
      "snippet": "string"
    }
  ]
}
```

**Response (searchResults):**
```json
{
  "results": [
    {
      "url": "string",
      "title": "string",
      "content": "string",
      "publishedDate": "ISO 8601"
    }
  ]
}
```

**Python SDK:**
```python
from linkup import LinkupClient

client = LinkupClient(api_key="your-key")

response = client.search(
    query="Iran ceasefire negotiations 2025",
    depth="standard",
    output_type="sourcedAnswer",   # snake_case in SDK
    max_results=10,
    from_date="2025-01-01",
    to_date="2025-12-31",
)
print(response.answer)
for src in response.sources:
    print(src.url, src.title)
```

**Raw HTTP:**
```bash
curl -X POST https://api.linkup.so/v1/search \
  -H "Authorization: Bearer $LINKUP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "q": "Iran ceasefire negotiations",
    "depth": "standard",
    "outputType": "sourcedAnswer",
    "maxResults": 10
  }'
```

---

### 2. POST /v1/fetch — Webpage extraction (sync)
Extracts clean markdown/HTML from a URL (no auth-protected pages).

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `url` | string (required) | — | Target URL |
| `mode` | string | `"standard"` | `"standard"` or `"pro"` (higher success rate) |
| `renderJs` | boolean | false | Execute JavaScript before extraction |
| `includeRawHtml` | boolean | false | Return original HTML alongside markdown |
| `extractImages` | boolean | false | Include image URLs in output |

**Constraints:** HTML ≤20MB, PDF ≤100MB. No login-protected pages.

**Pricing:**
| renderJs | standard | pro |
|----------|----------|-----|
| false | $0.001 | $0.005 |
| true | $0.005 | $0.010 |

---

### 3. POST /v1/research — Autonomous research agent (async)
Multi-source investigation, 2–20 minutes. Returns task ID immediately.

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `q` | string (required) | — | Research question |
| `mode` | string | — | `"answer"` (precise), `"investigate"` (single subject), `"research"` (broad) |
| `reasoningDepth` | string | `"L"` | `"S"` ($0.25), `"M"` ($0.50), `"L"` ($1.50), `"XL"` ($2.50) |
| `outputType` | string | `"sourcedAnswer"` | `"sourcedAnswer"` or `"structured"` |
| `structuredOutputSchema` | object | — | Required for structured output |
| `fromDate`, `toDate` | string | — | YYYY-MM-DD date range |
| `includeDomains`, `excludeDomains` | string[] | — | Domain filtering |

**Lifecycle:**
```python
task = client.research.create(q="Compare cloud providers", mode="investigate", reasoning_depth="L")
result = client.research.get(task.id)  # poll until complete
```

---

### 4. POST/GET /v1/tasks — Batch wrapper (async)
Run up to 100 search/fetch/research calls in one request. Same params as individual endpoints.

---

### 5. GET /v1/credits/balance — Account balance
Returns current credit balance. No params required.

---

## Rate Limits
- Poll rate: max 1 req/sec (throttled above this)
- Research polling: initial 2s, then 10s backoff; 30s for long tasks
- Failed tasks: no credits deducted

---

## Error Codes
- `401 UNAUTHORIZED` — missing or invalid Bearer token
- Throttling returns 4xx at >1 req/sec

---

## Use in TrueBrief Collector

**Recommended config for news collection:**
```python
client.search(
    query=f"Latest news: {topic_name}",
    depth="standard",          # fast enough, good coverage
    output_type="sourcedAnswer",  # gives synthesized answer + real source URLs
    from_date=last_run_date,   # date filtering = fresher results
    to_date=today,
    max_results=15,
)
```

**What makes Linkup useful for TrueBrief:**
- Real source URLs (not fabricated) — same guarantee as Gemini grounding
- Date filtering (`fromDate`/`toDate`) lets us replicate the "since last run" window
- `sourcedAnswer` mode gives pre-synthesized text + citations → maps cleanly to Alpha extraction
- `"standard"` depth is $0.006/call — vs Gemini ~$0.014 estimated

**Watch out for:**
- No explicit paywall bypass — same limitation as Brave
- `"deep"` mode costs 10x more and is slow (~30s) — wrong for real-time news
- SDK uses `snake_case` (e.g. `output_type`, `max_results`) not `camelCase` like the HTTP API
