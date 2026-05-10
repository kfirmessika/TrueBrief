
---

## V1 -> V2 Complete Reuse Reference

| v2 Component | v1 File | What's Valuable | What Changes |
|-------------|---------|-----------------|-------------|
| LLM Client | New | -- | New abstraction layer |
| Query Builder | `librarian.py` | Intent prompt, garbage rejection | Gemini via LLM client, match RSS categories |
| RSS Layer | `radar.py` | feedparser scan loop | Returns `RawArticle`, curated feed database |
| Tavily Layer | New | -- | New (replaces DuckDuckGo/Google scraping) |
| Article Extractor | `sniper.py` | Date extraction, bot detection | trafilatura replaces Crawl4AI |
| Harvester | `verifier.py` | Batch extraction prompt, metric preservation | JSON output, temporal normalization built-in |
| Vector Store | `memory.py` | add_fact, is_novel, similarity threshold | Supabase replaces Qdrant |
| Arbiter | `engine.py` + `context_verifier.py` | NoveltyFilter, temporal math, Time Detective | Cleaner, proper enum decisions |
| Pipeline | `manager.py` + `router.py` | scan_topic flow | Async, Celery later |
| Topics CRUD | `topics.py` | CRUD pattern | PostgreSQL replaces JSON file |
| API | `router.py` | FastAPI setup, endpoints | Versioned `/api/v1/` |
| Benchmarks | `tests/master_benchmark.py` | 21 test prompts, runner pattern | pytest, automated comparison |

---

## Professional Practices

### Git Workflow
```bash
# Feature branches for big changes
git checkout -b feat/collector-rss-layer
# ... work ...
git commit -m "feat(collector): add RSS layer with curated feed database"
git checkout main && git merge feat/collector-rss-layer

# Direct commits for small fixes
git commit -m "fix(arbiter): correct similarity threshold to 0.90"
```

### Commit Message Format
```
type(scope): short description
Types: feat, fix, refactor, test, docs, chore
Scope: collector, harvester, ledger, arbiter, briefer, api, pipeline, llm
```

---

## API Keys Needed

| Key | Where to get it | When needed | Cost |
|-----|----------------|-------------|------|
| `GOOGLE_API_KEY` | [Google AI Studio](https://aistudio.google.com/) | Phase 0 | Free (1,500 req/day) |
| `TAVILY_API_KEY` | [tavily.com](https://tavily.com) | Phase 0 | Free (1,000 credits/month) |
| `SUPABASE_URL` + `SUPABASE_KEY` | Your Supabase dashboard | Phase 0 | Free (500MB) |
| News API keys (Brave, Exa) | Later | Phase 3+ | Pay-per-use |


