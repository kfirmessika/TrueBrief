# Step 3.19 — Brave Search + Exa

**Complexity:** 15 | **Model:** SONNET

---

## Goal

Add two new search-source plugins to the intelligence pipeline:

1. **BraveLayer** — Brave Search REST API (web search with `freshness=pd`)
2. **ExaLayer** — Exa semantic search SDK (`exa-py`)

Both plug into the existing `SourceLayer` abstraction. The tier model already lists `"brave"` and `"exa"` in PRO/POWER tier source lists — no billing changes needed. The pipeline's `_collect_all()` already handles per-tier source filtering.

---

## Architecture

### Source Plugin Contract (existing)
```python
class SourceLayer(ABC):
    @property
    def name(self) -> str: ...          # "brave" | "exa"
    def search(self, query: SearchQuery) -> List[RawArticle]: ...
```

### Brave Search
- REST API: `GET https://api.search.brave.com/res/v1/web/search`
- Auth: `X-Subscription-Token: {BRAVE_API_KEY}` header
- Params: `q`, `count=5`, `freshness=pd` (past 24 h), `result_filter=web`
- No SDK: use `httpx` (already in requirements)
- Response: `data["web"]["results"][*]` → `url`, `title`, `description`, `page_age`
- Text: `description` (snippet) populated directly; ArticleExtractor handles full fetch if needed

### Exa Search
- SDK: `exa-py` (pip install required)
- Auth: `EXA_API_KEY`
- Call: `exa.search_and_contents(query, num_results=5, text={"max_characters": 1500})`
- Response: `results.results[*]` → `url`, `title`, `text`, `published_date`
- Text: full article text returned by Exa directly (like Tavily)

### Keyword Filter Skip
Brave and Exa are targeted search engines (like Tavily) — they return on-topic results by design. The existing keyword filter in `_collect_all()` currently reads `if source.name != "tavily"`. This must be extended to also skip Brave and Exa.

### Default Source List After This Step
```python
all_sources = [TavilyLayer(), RSSLayer(), GoogleNewsLayer(), BraveLayer(), ExaLayer()]
```

Tier enforcement (already in `models/tier.py`):
- FREE: `["rss", "tavily"]`  
- PRO: `["rss", "tavily", "google_news", "brave", "exa"]`  
- POWER: `["__all__"]`

---

## Files Touched

### New
- `src/truebrief/collector/brave_layer.py`
- `src/truebrief/collector/exa_layer.py`
- `tests/test_brave_exa.py`
- `docs/steps/phase_3/STEP_3.19.md`

### Modified
- `src/truebrief/models/article.py` — add `BRAVE = "brave"`, `EXA = "exa"` to `ArticleSource`
- `src/truebrief/pipeline/runner.py` — add imports + `BraveLayer()`, `ExaLayer()` to default sources; update keyword filter
- `config/settings.py` — add `BRAVE_API_KEY: str = ""` and `EXA_API_KEY: str = ""`
- `requirements.txt` — add `exa-py>=1.1.0`

### NOT Touched
- `src/truebrief/billing/tiers.py` — already has "brave" and "exa" in tier lists
- `src/truebrief/models/tier.py` — already lists these sources per tier
- Frontend — no UI changes needed

---

## Tests

1. `test_brave_layer_no_key_returns_empty` — BraveLayer returns [] when API key missing
2. `test_brave_layer_search_parses_results` — mock httpx → returns 2 RawArticles with correct fields
3. `test_brave_layer_handles_api_error` — httpx exception → returns [] gracefully
4. `test_exa_layer_no_key_returns_empty` — ExaLayer returns [] when API key missing
5. `test_exa_layer_search_parses_results` — mock exa.search_and_contents → returns RawArticles
6. `test_exa_layer_handles_sdk_error` — SDK exception → returns [] gracefully
7. `test_runner_includes_brave_and_exa_in_default_sources` — PipelineRunner default has both
8. `test_runner_filters_brave_when_not_in_allowlist` — free tier excludes brave/exa
9. `test_keyword_filter_skips_brave_and_exa` — brave/exa articles pass without keyword match

---

## Acceptance Criteria

- [ ] `BraveLayer.name == "brave"` and `ExaLayer.name == "exa"`
- [ ] Both return `[]` gracefully when API key is unset
- [ ] `ArticleSource.BRAVE` and `ArticleSource.EXA` exist
- [ ] PipelineRunner default sources include both (5 total)
- [ ] Brave/Exa bypass keyword filter in `_collect_all()`
- [ ] Free-tier allowlist `["rss", "tavily"]` excludes both (existing behavior)
- [ ] All existing tests still pass
