# General Info

> **Living document.** Tactical details, ADRs, code specs, and step-by-step tasks for every phase.  
> **Last updated:** 2026-04-18 -- ADR-1 (LLM), ADR-2 (Database), ADR-3 (Sources) applied.
>
> 📌 **Read first:** [AI Rules & Workflow](file:///d:/projects/Apps/TrueBrief/docs/ai_rules.md) -> [Roadmap](file:///d:/projects/Apps/TrueBrief/docs/roadmap.md) -> [Phase Plans](file:///d:/projects/Apps/TrueBrief/docs/plans/) -> [Architecture](file:///d:/projects/Apps/TrueBrief/docs/architecture.md)

---

## How We Work Together (The Antigravity Workflow)

You're a solo developer. I'm your AI pair-programmer. Together we work like a professional team. Here's the system:

### The Loop (for every feature)

```
1. PLAN   -> We discuss what to build. I create/update this roadmap.
2. SPEC   -> I write the exact file changes before touching code.
3. BUILD  -> I write the code. You review.
4. TEST   -> We run it. Fix what breaks.
5. COMMIT -> You commit to git with a clean message.
6. NEXT   -> Move to the next item on the roadmap.
```

### Rules We Follow

| Rule | Why |
|------|-----|
| **Never code from zero when v1 has working logic** | v1 has battle-tested code. We read it first, extract the good parts, then build clean on top. |
| **One feature per conversation** | Keep conversations focused. Each session = one roadmap item. |
| **Test before moving on** | No skipping. Run the code. Verify it works. Then continue. |
| **Git commit after every working feature** | Small, clean commits. Not a giant "add everything" bomb. |
| **Ask me questions -- don't guess** | If you don't understand something (architecture, business logic, a Python pattern), ask. That's how you learn. |

### How to Start a Session

When you open Antigravity to work on TrueBrief, say something like:

> *"Let's work on Phase 1, Step 1.2 -- the RSS Layer collector plugin."*

I'll read this roadmap, find where we are, check the v1 reuse map, and we go.

### How to Use Planning Mode

- For **big features** (new pillar, new system): Use `/planning` mode -> I research -> create a plan -> you approve -> we build.
- For **small tasks** (fix a bug, tweak a prompt, add a field): Just ask directly -> I code it -> you test.

---

## Architecture Decision Records (ADR)

> These are the final decisions after research. Each decision includes what you said, what I found, and what's correct.

---

### ADR-1: LLM Strategy -- Multi-LLM with Gemini as Primary

#### What you said
> "We can use different LLMs for each step. Use Gemini for prototype because free daily limit. Maybe private LLM on server later."

#### What I found (verified)
- **Gemini Flash free tier:** ~1,000-1,500 requests/day, 15 RPM. No credit card needed. ✅ Real.
- **OpenAI:** No free tier for API. Pay-per-use only. ❌ Not usable for zero-cost prototype.
- **Claude/Anthropic:** No free API tier. ❌ Same problem.
- **Grok/xAI:** No free tier suitable for automation. ❌

#### My Decision: ✅ You're correct -- Gemini is the right choice for prototype

The pipeline has **5 LLM call points**. Here's exactly which LLM handles which call, and why:

| Pipeline Step | LLM Call | Model (Phase 1) | Model (Production) | Why |
|--------------|----------|-----------------|-------------------|-----|
| **Query Builder** | Topic -> search queries | `gemini-2.5-flash` | `gemini-2.5-flash` | Simple task. Flash is fast and free. Never needs upgrade. |
| **Harvester** | Article -> extract facts | `gemini-2.5-flash` | `gemini-2.5-pro` or `gpt-4o` | This is the most important call. Flash is fine for prototype; production needs higher accuracy for numbers/dates. |
| **Arbiter (Judge)** | Is this fact NEW/DUPLICATE/UPDATE? | `gemini-2.5-flash` | `gemini-2.5-flash` | Structured decision with clear rules. Flash handles this well. |
| **Briefer** | Facts -> clean report | `gemini-2.5-flash` | `gemini-2.5-flash` | Text formatting. Doesn't need expensive model. |
| **Garbage Filter** | Reject bad input | `gemini-2.5-flash` | `gemini-2.5-flash` | Trivial classification. Flash forever. |

**Implementation: LLM abstraction layer**

```python
# config/settings.py
LLM_CONFIG = {
    "query_builder": {"provider": "gemini", "model": "gemini-2.5-flash"},
    "harvester":     {"provider": "gemini", "model": "gemini-2.5-flash"},
    "arbiter":       {"provider": "gemini", "model": "gemini-2.5-flash"},
    "briefer":       {"provider": "gemini", "model": "gemini-2.5-flash"},
    "garbage_filter": {"provider": "gemini", "model": "gemini-2.5-flash"},
}
```

We build a thin `LLMClient` wrapper that reads this config. To switch any step to OpenAI/Claude/local, you change ONE line in config. Zero code changes.

**About private/local LLMs:** Your instinct is right for the future, but wrong for now. Local LLMs (Llama, Mistral, etc.) need: GPU hardware (~$1K+), setup time, worse accuracy on structured JSON extraction. The free Gemini tier gives you 1,500 calls/day = enough to run 50+ full pipeline executions daily. That's more than enough through Phase 1-2. Revisit local LLMs when Gemini costs become real (Phase 3+, production traffic).

---

### ADR-2: Database -- Supabase Cloud ✅ (Keep What You Set Up)

#### What you said
> "I opened Supabase, created project, enabled pgvector. Is local better?"

#### What I found (verified)
| Factor | Supabase Cloud (Free) | Local PostgreSQL |
|--------|----------------------|-----------------|
| Setup time | ✅ Done (you already did it) | ❌ Need to install PostgreSQL + pgvector extension on Windows (painful) |
| pgvector | ✅ Already enabled | ❌ Manual compilation on Windows |
| Cost | ✅ Free (500MB, enough for 100K+ facts) | ✅ Free |
| Maintenance | ✅ Zero (Supabase handles it) | ❌ You're the DBA |
| Access from anywhere | ✅ Yes (cloud) | ❌ Only from your machine |
| Production migration | ✅ Already cloud-ready | ❌ Need to migrate later |
| Downside | ⚠️ Pauses after 7 days inactive | None |

#### My Decision: ✅ Keep Supabase. You're already set up.

The "pauses after 7 days" problem is irrelevant during active development -- you'll be using it daily. When we hit production, we either upgrade to Supabase Pro ($25/mo) or migrate to Railway/Render PostgreSQL (both simple SQL exports).

**Action:** When we start Phase 0, I'll tell you exactly when to grab the connection string and where to put it.

---

### ADR-3: News Source APIs -- The Collector Strategy

This is the most complex decision. Let me address everything you said point by point.

#### What you said (fact-checked)

| Your claim | Verdict | Details |
|-----------|---------|---------|
| "Google News RSS gives redirected links, hard to get originals" | ✅ **CORRECT** | Google News RSS returns encoded redirect URLs (e.g., `news.google.com/rss/articles/CBMi...`). Decoding them requires calling a Google internal endpoint. Libraries exist (`googlenewsdecoder`) but they break frequently as Google changes the format. |
| "If we keep using same keywords, Google knows" | ⚠️ **Partially correct** | Google doesn't "learn" your queries, but they do rate-limit/block repeated automated access. No official rate limits = they can block you anytime. The dynamic keyword rotation idea is good but is a Phase 2+ optimization. |
| "NewsAPI free tier is limited to 100/day" | ✅ **CORRECT** | And worse than you think -- the free tier has a **24-hour delay** AND **cannot be used in production** (their terms explicitly forbid it). Using it in a deployed product = license revocation. |
| "Direct RSS + Tavily for MVP to keep cost at $0" | ✅ **EXCELLENT RECOMMENDATION** | Direct RSS = truly free, no rate limits, publishers WANT you to read their feeds. Tavily = 1,000 free credits/month (500-1,000 searches). Combined = zero cost for MVP. |

#### The Full Source Comparison (researched)

| Source | Free Tier | Rate Limit | Quality | Real-Time? | Reliability | URL Issues |
|--------|-----------|------------|---------|------------|-------------|------------|
| **Direct RSS Feeds** | ✅ Unlimited | None | 🟢 High (publisher-direct) | 🟢 Yes (5-15 min delay) | 🟢 Very stable (RSS is a standard) | ✅ Direct original URLs |
| **Google News RSS** | ✅ Unlimited (unofficial) | ⚠️ Undefined (can block) | 🟢 High coverage | 🟢 Yes | 🔴 Fragile (unofficial, links break) | ❌ Redirect URLs need decoding |
| **Tavily API** | ✅ 1,000 credits/month | Defined & clear | 🟢 High (returns clean text!) | 🟢 Yes | 🟢 Stable (official API) | ✅ Direct URLs + full text |
| **NewsAPI.org** | 100 req/day | 100/day | 🟢 Good (150K sources) | 🔴 No (24h delay on free) | 🟢 Stable | ✅ Direct URLs |
| **Brave Search API** | ~1,000 req/month ($5 credit) | Defined | 🟡 Medium | 🟢 Yes | 🟢 Stable | ✅ Direct URLs |
| **Exa API** | $10 initial credit | Defined | 🟢 High (semantic search) | 🟢 Yes | 🟢 Stable | ✅ Direct URLs |

#### My Decision: Phase 1 Sources

```
Phase 1 (MVP -- $0 cost):
  ├── Direct RSS Feeds ← PRIMARY (unlimited, free, real-time, original URLs)
  L── Tavily API       ← SECONDARY (1,000 free searches/month, returns CLEAN TEXT)

Phase 2 (scaling -- still ~$0):
  ├── Direct RSS Feeds
  ├── Tavily API
  L── Google News RSS  ← ADD with googlenewsdecoder library (more coverage, accept fragility)

Phase 3+ (growth -- pay for quality):
  ├── Direct RSS Feeds (always free)
  ├── Tavily API (pay-per-use beyond 1,000)
  ├── Brave Search API ($5/month for 1,000 req)
  L── Exa API (semantic deep search, $7/1,000 req)

NOT using:
  ├── NewsAPI.org -- 24h delay on free tier + cannot use in production = useless for us
  L── Apify -- too expensive for news scraping, better for social media (Phase 5+)
```

#### Why Direct RSS is the foundation (not Google News RSS)

| Reason | Detail |
|--------|--------|
| **Zero cost forever** | Publishers provide RSS for free. It's how they want you to consume their content. |
| **Original URLs** | No redirect decoding headaches. The URL in the RSS feed IS the article URL. |
| **Real-time** | Most major publishers update RSS within 5-15 minutes of publishing. |
| **Reliable** | RSS is a 20-year-old standard. It won't change or break. |
| **Legal** | Publishers choose to have RSS feeds. You're reading published content, not scraping. |

#### BUT -- Direct RSS alone isn't enough

Direct RSS requires you to **know which feeds to subscribe to** for a given topic. This is where the **Query Builder + Tavily** combo fills the gap:

```
User enters: "TSMC semiconductor manufacturing"

1. Query Builder (LLM) -> generates search queries
2. Tavily API -> searches the web for those queries -> returns article URLs + clean text
3. ALSO: match topic to known RSS feeds from our curated feed database

Result: Tavily catches breaking news Tavily finds. RSS catches everything from known publishers.
```

#### The Curated Feed Database (built into config)

```yaml
# config/rss_feeds.yaml
general:
  - url: https://feeds.reuters.com/reuters/topNews
    name: Reuters Top News
  - url: https://feeds.bbci.co.uk/news/rss.xml
    name: BBC News
  - url: https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml
    name: NYT Homepage

technology:
  - url: https://feeds.arstechnica.com/arstechnica/index
    name: Ars Technica
  - url: https://www.theverge.com/rss/index.xml
    name: The Verge
  - url: https://techcrunch.com/feed/
    name: TechCrunch

finance:
  - url: https://feeds.reuters.com/reuters/businessNews
    name: Reuters Business
  - url: https://www.cnbc.com/id/100003114/device/rss/rss.html
    name: CNBC Top News

geopolitics:
  - url: https://feeds.reuters.com/Reuters/worldNews
    name: Reuters World
  - url: https://feeds.bbci.co.uk/news/world/rss.xml
    name: BBC World
  - url: https://rss.nytimes.com/services/xml/rss/nyt/World.xml
    name: NYT World
```

The Query Builder decides which RSS categories to scan based on the topic. This is config-driven, not hardcoded.

#### Your AYR Keyword Rotation Idea -- ✅ Good but Phase 2+

You said: *"create different keywords from the prompt and rate them based on alphas they produce"*

This is exactly what the AYR (Alpha Yield Rate) system does in the definitive plan. But it's Phase 2+ because:
1. You need data first (run the pipeline 100+ times to have meaningful AYR scores)
2. The core pipeline must work before you optimize it
3. We track source quality from Day 1 (logging) but don't act on it until Phase 2

---

## Pre-Work: Archive v1 & Start Clean

> [!IMPORTANT]
> The current `d:\projects\Apps\TrueBrief` contains v1 code. We archive it into a branch, then reset `main` to a clean state. **No code is lost.**

### Status: `[ ]` Not Started

### Steps

| # | Task | Status | Command/Action |
|---|------|--------|----------------|
| 0.1 | Commit all current v1 changes | `[ ]` | `git add -A && git commit -m "v1-final: archive before v2 rewrite"` |
| 0.2 | Create archive branch | `[ ]` | `git branch v1-archive` |
| 0.3 | Verify archive branch exists | `[ ]` | `git branch -a` (should show `v1-archive`) |
| 0.4 | Clean the working tree for v2 | `[ ]` | Delete all source files **except** `.git/`, `.gitignore`, `.env`, `.env.example` |
| 0.5 | Create v2 project skeleton (see Phase 0) | `[ ]` | I generate the folder structure |
| 0.6 | Initial v2 commit | `[ ]` | `git add -A && git commit -m "v2: project skeleton"` |

### How to Get v1 Code Later

```bash
git show v1-archive:src/truebrief/memory.py      # View any v1 file
git diff v1-archive -- src/truebrief/verifier.py  # Compare v1 vs v2
```

**V1 lives in the `v1-archive` branch forever.**


