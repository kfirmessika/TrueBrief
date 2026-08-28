# Brave Search API Reference
> Researched 2026-08-27. Source: brave.com/search/api + brave.com/search/api documentation pages.
> Note: Full parameter docs are behind auth at api.search.brave.com — some details from public marketing pages.

## Overview
- Base URL: `https://api.search.brave.com/res/v1`
- Auth header: `X-Subscription-Token: <API_KEY>` (NOT Bearer — different from most APIs)
- SimpleQA benchmark: **94.1% F1** (comparable to Linkup)
- V4 already uses this: see `src/truebrief/collector/brave_layer.py`
- Key already in `config/settings.py` as `BRAVE_API_KEY`

---

## Pricing Tiers

| Plan | Cost | Free credit | Rate limit | Notes |
|------|------|------------|------------|-------|
| **Search** | $5 / 1,000 requests | $5/month | 50 req/sec | Standard web/news results |
| **Answers** | $4 / 1,000 req + $5 / M tokens | — | 2 req/sec | AI-grounded answers with citations |
| **Enterprise** | Custom | — | Custom | SLA + volume pricing |

---

## Endpoints

### 1. GET /res/v1/news/search — News search
Used in V4's `BraveLayer`. Returns news articles.

**Query parameters:**

| Parameter | Type | Default | Allowed values / notes |
|-----------|------|---------|----------------------|
| `q` | string (required) | — | Max 400 chars, 50 words |
| `country` | string | `"US"` | ISO 3166-1 alpha-2 country code |
| `search_lang` | string | `"en"` | BCP 47 language tag |
| `ui_lang` | string | — | UI locale |
| `count` | integer | 20 | 1–50 results per page |
| `offset` | integer | 0 | 0–9 (pagination, max 10 pages) |
| `freshness` | string | — | `"pd"` (past day), `"pw"` (past week), `"pm"` (past month), `"py"` (past year), or `"YYYY-MM-DDtoYYYY-MM-DD"` (custom UTC range) |
| `safesearch` | string | `"moderate"` | `"off"`, `"moderate"`, `"strict"` |
| `spellcheck` | boolean | true | Enable spelling correction |
| `text_decorations` | boolean | true | Bold/highlight in snippets |
| `extra_snippets` | boolean | false | Extra text extracts (Search plan only) |

**Response schema:**
```json
{
  "type": "news",
  "news": {
    "type": "news",
    "results": [
      {
        "type": "news_result",
        "url": "string",
        "title": "string",
        "description": "string",
        "age": "string (relative, e.g. '3 hours ago')",
        "page_age": "ISO 8601 timestamp",
        "breaking": true,
        "thumbnail": { "src": "string", "original": "string" },
        "source": "string (domain name)"
      }
    ]
  },
  "query": { "original": "string", "spellcheck_off": false }
}
```

---

### 2. GET /res/v1/web/search — Web search
Full web results. Richer than news search.

**Query parameters:** Same as news search, plus:

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `result_filter` | string | — | Comma-separated: `"discussions"`, `"news"`, `"videos"`, `"web"` |
| `goggles_id` | string | — | Custom ranking/filtering "Goggle" ID |
| `summary` | boolean | false | Request AI summary (triggers Goggles plan) |

**Response:** `web.results[]` with `title`, `url`, `description`, `extra_snippets[]`.

---

### 3. GET /res/v1/llm/context — RAG-optimized extraction
Pre-extracts webpage text for LLM context windows. No separate fetch step needed.

| Parameter | Type | Default | Allowed |
|-----------|------|---------|---------|
| `q` | string (required) | — | Search query |
| `maximum_number_of_urls` | integer | — | 1–50 |
| `maximum_number_of_tokens` | integer | — | 1024–32768 |

**Response:** `results[]` with `url`, `content_type`, `page_content`, `snippet`, `title`.

**Use case for TrueBrief:** Fetch full article text in one API call without separate scraping.

---

### 4. POST /res/v1/chat/completions — AI Answers (OpenAI-compatible)
Grounded answers with citations. Uses Brave's own index for grounding (not model hallucinations).

- OpenAI SDK compatible (swap base URL)
- Supports streaming
- Returns `result.answer` (string) + `result.citations[]` (url, title)
- Rate limit: **2 req/sec** (much lower than Search plan's 50/sec)
- Cost: $4/1k requests + $5/M tokens

**⚠️ Note:** Brave's grounded answer uses verified source URLs from its index — same "no fabrication" guarantee as Gemini grounding.

---

### 5. GET /res/v1/summarizer/summary — Legacy AI summarizer
Direct abstractive summary + entity cards. Older endpoint, less capable than `/chat/completions`.

---

### 6. Other endpoints
- `/images/search` — image results (max 50)
- `/videos/search` — video results (max 50)
- `/suggest/search` — autocomplete suggestions (`rich=true` for thumbnails)
- `/spellcheck/search` — spelling corrections
- `/local/pois` — local places by ID (max 20 IDs)
- `/local/descriptions` — descriptions for local POIs

---

## Freshness / Date Filtering
This is **critical for TrueBrief** — replicate the "since last run" window:

```
# Presets (relative)
freshness=pd   # past day
freshness=pw   # past week
freshness=pm   # past month
freshness=py   # past year

# Custom range (UTC, start ≤ end)
freshness=2025-07-01to2025-07-26

# In-query operators (alternative)
q="Iran ceasefire after:2025-07-01"
q="Iran ceasefire before:2025-07-26"
```

---

## Rate Limits Summary
| Plan | Limit |
|------|-------|
| Search | 50 req/sec |
| Answers | 2 req/sec |

---

## Auth Example

```python
import httpx

resp = httpx.get(
    "https://api.search.brave.com/res/v1/news/search",
    headers={
        "X-Subscription-Token": settings.BRAVE_API_KEY,
        "Accept": "application/json",
    },
    params={
        "q": "Iran ceasefire negotiations",
        "count": 20,
        "freshness": "pw",    # past week
        "country": "US",
        "search_lang": "en",
    },
    timeout=10.0,
)
data = resp.json()
articles = data["news"]["results"]
```

---

## V4 Implementation Reference
`src/truebrief/collector/brave_layer.py` already has a working implementation:
- Uses `/res/v1/news/search`
- Passes `X-Subscription-Token` header
- Maps `age` string → datetime via `_parse_age()` helper
- Returns `RawArticle` objects

**For the V5 BraveCollector:** re-use the HTTP call pattern but return `List[Alpha]` directly (no RawArticle intermediate) to match the `GeminiSearchCollector` interface.

---

## Use in TrueBrief Collector

**Recommended config for news collection:**
```python
# News search — direct, no LLM synthesis
params = {
    "q": topic_name,
    "count": 20,
    "freshness": f"{last_run_date:%Y-%m-%d}to{today:%Y-%m-%d}",  # exact window
    "country": "US",
    "search_lang": "en",
    "extra_snippets": True,  # more text per result (Search plan only)
}

# OR: AI Answers endpoint — pre-synthesized, but 2 req/sec limit
# POST /res/v1/chat/completions with grounding
```

**For the benchmark:** use `/news/search` (same approach as V4) — it's the direct comparison to Gemini grounding. The Answers endpoint is a different product (closer to Perplexity) and should be a separate test.

**What makes Brave useful for TrueBrief:**
- Independent index (not Google) — catches stories Google might de-rank
- `freshness` date range maps cleanly to "since last run"
- Already paid for ($5 free/month credit)
- V4 code is reusable as-is
- `extra_snippets` gives more text without a separate fetch call

**Watch out for:**
- News search returns article metadata + snippets only — NOT full article text (need separate fetch for body)
- No paywall bypass — paywalled articles return snippet only
- V4 had `402` errors in production — check account balance before benchmark
- `age` field is a relative string ("3 hours ago") — need to parse to datetime (V4's `_parse_age()` does this)
