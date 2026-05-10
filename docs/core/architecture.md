# TrueBrief - Architecture (Definitive System Design)

> Full theoretical picture. Business logic, data models, algorithms, and design decisions.  
> **Updated 2026-04-18:** ADR-1 (LLM), ADR-2 (Database), ADR-3 (News Sources) applied.  
> 📌 Read: [AI Rules](file:///d:/projects/Apps/TrueBrief/docs/ai_rules.md) → [Roadmap](file:///d:/projects/Apps/TrueBrief/docs/roadmap.md) → [Implementation Plan](file:///d:/projects/Apps/TrueBrief/docs/implementation_plan.md) → **this file** (theory)

---

## What Is TrueBrief?

Today when something happens in the world and you want to stay informed, your options are broken:

- **TV / News Sites** - They decide what you see. Repetitive. Clickbait. Algorithmic noise.
- **Google News** - 50 articles saying the same thing. You click, read, hunt for the one new sentence.
- **Social Media** - Opinions dressed as news. Entertainment, not information.

The pattern: **someone else controls what you see**, and they're incentivized to waste your time.

**TrueBrief flips this:**

1. You write what you care about in free text - *"EU AI regulation updates"*
2. The system monitors the internet, reads every relevant article, extracts facts
3. It remembers what it already told you
4. You get ONLY what's genuinely new - no repetition, no clickbait, no noise

**The analogy:** Google Search → GPT happened for information lookup. TrueBrief does the same for staying informed. Traditional news is the old Google (10 blue links, do the work yourself). TrueBrief is the GPT (just give me what I need).

---

## The 5-Pillar Architecture

```
┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐
│ COLLECTOR  │ →  │ HARVESTER  │ →  │   LEDGER   │ →  │  ARBITER   │ →  │  BRIEFER   │
│ (Ingestion)│    │ (Extract)  │    │  (Memory)  │    │  (Judge)   │    │  (Output)  │
└────────────┘    └────────────┘    └────────────┘    └────────────┘    └────────────┘
       ↑                                  ↑
       └────────── SCHEDULER & COST CONTROL ──────────┘
```

| Pillar | Responsibility |
|--------|---------------|
| **Collector** | Gather raw articles from the internet for a given topic |
| **Harvester** | LLM extracts atomic facts ("Alphas") from raw article text |
| **Ledger** | Store knowledge, search for matches, track what was already reported |
| **Arbiter** | Decide: is this fact new, a duplicate, or an update to a known story? |
| **Briefer** | Generate the final clean report from only the genuinely new facts |
| **Scheduler** | Decide what to run, when, at what cost |

---

## Pillar 1: The Collector (Ingestion)

### What It Does
Takes a topic and returns raw article text from across the internet.

### Query Builder (1 small LLM call per topic)

User writes: *"TSMC semiconductor manufacturing"*

LLM produces:
```json
{
  "primary_query": "TSMC semiconductor manufacturing news 2026",
  "alt_queries": ["TSMC 3nm yield rate", "TSMC earnings 2026"],
  "date_filter": "last 24 hours",
  "exclude_terms": ["opinion", "rumor", "sponsored"]
}
```

### Source Layers (Plugin Architecture)

Every source is a self-contained plugin implementing one interface:

```python
class SourceLayer(ABC):
    def search(self, query: SearchQuery) -> List[RawArticle]:
        ...
```

**Phase 1 sources (MVP - $0 cost):**

| Layer | API | Cost | Good For |
|-------|-----|------|----------|
| `RSSLayer` | Direct RSS feeds (curated) | **Free, unlimited** | Publisher-direct, real-time, original URLs |
| `TavilyLayer` | Tavily API | **Free (1,000 credits/month)** | Any topic, returns clean full text, no scraping needed |

> **Why NOT Google News RSS in Phase 1?** The links are encoded redirect URLs (e.g., `news.google.com/rss/articles/CBMi...`). Decoding them requires calling a Google internal endpoint that changes frequently and breaks decoders. Unreliable for production.

> **Why NOT NewsAPI.org in Phase 1?** Free tier has a **24-hour delay** and their Terms of Service **explicitly forbid production use**. Using it in a deployed product = license revocation. Not suitable.

**Phase 2 sources (adding coverage):**

| Layer | API | Cost | Good For |
|-------|-----|------|----------|
| `RSSLayer` | Direct RSS feeds | Free | Always the primary backbone |
| `TavilyLayer` | Tavily API | Free tier / pay-per-use beyond 1K | Still core, now paid beyond free limit |
| `GoogleNewsRSSLayer` | Google News RSS (with decoder) | Free (unofficial) | Broader coverage, add with fragility accepted |

**Phase 3+ sources (scale):**

| Layer | API | Cost | Good For |
|-------|-----|------|----------|
| `BraveLayer` | Brave Search | ~$5/mo (~1,000 requests) | Broad web search |
| `ExaLayer` | Exa API | $7/1,000 requests | Semantic deep search, PDFs |
| `SocialLayer` | Apify | Pay-per-use | Twitter/Reddit real-time |

> **Why plugins?** You MUST be able to add, remove, and swap sources without touching core code. Sources die, APIs change pricing, new ones launch. This is config, not code.

### Source Router

Which plugins fire for which topic? Controlled by config, not hardcoded:

```yaml
# routing_rules.yaml
defaults:
  layers: [rss_layer, tavily_layer]   # Phase 1 defaults

overrides:
  - domain: finance
    add_layers: [sec_edgar_layer]
  - domain: tech
    add_layers: [github_layer]

# config/rss_feeds.yaml - Curated feed database
general:
  - url: https://feeds.reuters.com/reuters/topNews
    name: Reuters Top News
  - url: https://feeds.bbci.co.uk/news/rss.xml
    name: BBC News
technology:
  - url: https://feeds.arstechnica.com/arstechnica/index
    name: Ars Technica
  - url: https://techcrunch.com/feed/
    name: TechCrunch
finance:
  - url: https://feeds.reuters.com/reuters/businessNews
    name: Reuters Business
  - url: https://www.cnbc.com/id/100003114/device/rss/rss.html
    name: CNBC
geopolitics:
  - url: https://feeds.reuters.com/Reuters/worldNews
    name: Reuters World
  - url: https://feeds.bbci.co.uk/news/world/rss.xml
    name: BBC World
```

### Article Content Extraction

Many APIs return just headlines/snippets. TrueBrief needs the FULL article.

- Use `trafilatura` (Python library) - extracts clean text, strips ads/nav/boilerplate
- **Tavily results skip this step** - Tavily already returns clean full text
- Cache every article by URL hash - **never fetch or process the same article twice**
- Respect rate limits and robots.txt

### Output Structure

```python
@dataclass
class RawArticle:
    url: str
    title: str
    text: str                  # Full clean article text
    published_date: datetime
    source_domain: str
    collection_method: str     # Which plugin found this
```

---

## Pillar 2: The Harvester (Intelligence)

### What It Does
Takes raw article text, extracts structured atomic facts ("Alphas").

### Why Not Just Summarize?
Summaries lose information. If 5 articles cover the same event, 5 summaries repeat each other. You can't deduplicate summaries cleanly.

Instead: extract **atomic facts**. Multiple articles produce overlapping facts. Deduplication happens at the fact level, precisely.

### The Harvester LLM Prompt

```
You are a precision intelligence analyst. Extract every atomic, verifiable fact
from this article into a structured JSON list.

For each fact extract:
1. alpha_text: The fact as one clean standalone sentence.
2. entities: Named entities (companies, people, countries, products).
3. event_date: When this HAPPENED (not when it was published).
   Convert relative dates ("yesterday", "last quarter") to YYYY-MM-DD
   using the article's published_date as anchor. If unknown: "unknown".
4. context: 20-40 words - why does this fact matter? What story does it belong to?
5. confidence: How verifiable is this? (0.0-1.0)

Rules:
- NEVER extract opinions, predictions, or editorial commentary.
- NEVER extract meta-information about the article itself.
- Drop anything with confidence < 0.6.
- Each fact must stand alone - a reader with no other context should understand it.

Output ONLY valid JSON.
```

### Example

**Article:** *"Tesla reported Q3 revenue of $25.2B, beating analyst expectations of $24.1B. CEO Elon Musk announced plans to begin Robotaxi production in 2025."*

**Harvester Output:**
```json
[
  {
    "alpha_text": "Tesla reported Q3 2026 revenue of 25.2 billion dollars.",
    "entities": ["Tesla"],
    "event_date": "2026-09-30",
    "context": "Quarterly earnings for Tesla, relevant to stock price and growth trajectory.",
    "confidence": 0.95
  },
  {
    "alpha_text": "Tesla Q3 2026 revenue beat analyst consensus of 24.1 billion dollars by 1.1 billion.",
    "entities": ["Tesla"],
    "event_date": "2026-09-30",
    "context": "Earnings beat signals stronger-than-expected demand and execution.",
    "confidence": 0.92
  },
  {
    "alpha_text": "Elon Musk announced Robotaxi production will begin in 2025.",
    "entities": ["Elon Musk", "Tesla", "Robotaxi"],
    "event_date": "2026-09-30",
    "context": "First official production timeline for Tesla's autonomous taxi service.",
    "confidence": 0.88
  }
]
```

### Temporal Normalization

The LLM handles relative dates using the article's publish date:

| Article Says | Published Date | Normalized event_date |
|-------------|---------------|----------------------|
| "yesterday" | 2026-04-16 | 2026-04-15 |
| "last quarter" | 2026-04-16 | 2026-03-31 |
| "this morning" | 2026-04-16 | 2026-04-16 |
| "in 2024" | 2026-04-16 | 2024-01-01 |

---

## Pillar 3: The Ledger (Memory)

### What It Does
Stores everything the system has ever learned, per topic. Enables searching for "have I seen this fact before?"

### Phase 1 Data Model (Simple - Start Here)

**4 core tables:**

```
USERS
├── id, email, plan (free/pro/power), stripe_id, created_at

TOPICS
├── id, user_id (FK), raw_query, search_strategy (JSON)
├── frequency (fast/medium/slow), is_active, last_checked_at

KNOWN_FACTS (the heart of the system)
├── id, topic_id (FK), alpha_text, alpha_embedding (vector)
├── entities (JSON), event_date, context, confidence
├── source_url, source_domain, first_seen_at

BRIEFS
├── id, topic_id (FK), content, facts_json
├── delivered_at, is_read
```

### Pillar 3: The Ledger (Memory)

### Story Nodes (Phase 3 Implementation)

Flat facts were used for the MVP, but Story Nodes now capture **story evolution**. When a story develops over weeks, facts are grouped into a living narrative thread.

**Story Nodes** group related facts into a cohesive unit:

```json
{
  "node_id": "uuid",
  "topic_id": "uuid",
  "type": "root | sub_event",
  "parent_node_id": "null | uuid",
  "recursive_summary": "TSMC's 3nm N3E yield improved from 80% Q4 2025 to 94% Q1 2026, ahead of schedule, enabling earlier Apple M5 and Nvidia Blackwell delivery.",
  "entities": ["TSMC", "Apple", "Nvidia"],
  "earliest_event_date": "2025-10-01",
  "latest_event_date": "2026-03-31",
  "alpha_count": 7,
  "alphas": [
    {
      "alpha_id": "uuid",
      "alpha_text": "...",
      "context": "...",
      "source_url": "...",
      "published_date": "2026-04-12",
      "vector_id": "uuid"
    }
  ]
}
```

> **Why not start with Story Nodes?** Because you need to validate that fact extraction and delta detection work FIRST. Story Nodes are an optimization of a working system, not a prerequisite.

### Vector Storage

**Dual-Vector Search:** We use `pgvector` in Supabase with two separate vector columns per fact/story pair:
- **alpha_embedding (in `known_facts`):** "Is this the exact same fact?" (fact-level matching, identity detection).
- **summary_embedding (in `story_nodes`):** "Is this part of the same story?" (story-level matching, narrative clustering).

The **Arbiter** uses the alpha vector to detect duplicates, while the **StoryManager** uses the summary vector to decide which Story Node a new Alpha belongs to.

**Recursive Summarization (Task 3.3):**
To keep story summaries fresh without re-reading all facts, we use a recursive LLM pattern:
`new_summary = LLM(previous_summary + new_fact)`
This maintains narrative continuity at O(1) LLM cost per update.

---

## Pillar 4: The Arbiter (Judge)

### What It Does
For each new Alpha, decides: **Is this genuinely new, a duplicate, or an update?**

### Step 1: Vector Search

```python
# Search existing facts for this topic
matches = pgvector_search(
    table="known_facts",
    vector=new_alpha_embedding,
    filter={"topic_id": topic_id},
    limit=5
)
```

### Step 2: Score-Based Labeling

| Cosine Similarity | Label | Meaning |
|-------------------|-------|---------|
| 0.95 - 1.00 | `IDENTICAL` | Almost certainly the same fact |
| 0.85 - 0.94 | `STRONG_MATCH` | Same topic, possibly different details |
| 0.75 - 0.84 | `RELATED` | Same story area, needs judgment |
| < 0.75 | `NO_MATCH` | Not related to anything known |

### Step 3: Fast Path (Skip LLM When Obvious)

Before burning an LLM call on the Judge, handle the easy cases for free:

| Condition | Auto-Decision | LLM Saved? |
|-----------|--------------|------------|
| `IDENTICAL` + score > 0.97 + same entities | → **AUTO-MERGE** (duplicate) | ✅ Yes |
| Zero matches returned | → **AUTO-NEW** (brand new fact) | ✅ Yes |
| Everything else | → Send to Judge LLM | ❌ No |

**Expected savings: ~50% of all Judge LLM calls eliminated.**

### Step 4: The Judge LLM Prompt (for ambiguous cases)

```
You are a news intelligence arbiter. You see a NEW FACT and its closest EXISTING
KNOWLEDGE, ranked by similarity:

LABELS:
- IDENTICAL: Very likely the same fact
- STRONG_MATCH: Same topic, possibly different details
- RELATED: Part of the same story area

Choose exactly ONE decision:

MERGE - Duplicate or trivial restatement. No new information.
  Output: { "decision": "MERGE" }

UPDATE - Genuinely new information that updates or extends a known fact/story.
  Output: { "decision": "UPDATE", "delta": "one sentence - what specifically is new" }

NEW - No existing knowledge matches. Brand new information.
  Output: { "decision": "NEW" }

Rules:
- A change in numbers (stock price, percentage, count) = UPDATE, not MERGE.
- Non-overlapping entities → lean toward NEW.
- "Apple" ≠ "Samsung" → never merge across different entities.
- When in doubt, choose UPDATE over MERGE (false positives are worse than false negatives).
- Output ONLY valid JSON.
```

### Post-Decision Actions

**MERGE:**
- Skip this fact. Don't store it again.
- Log it for source quality tracking (this source produced a duplicate).

**UPDATE:**
- Store the new Alpha in known_facts.
- Add the `delta` sentence to the brief queue.
- Log as "Alpha" for source quality tracking.
- *Phase 2+:* Update the parent Story Node's recursive_summary.

**NEW:**
- Store the Alpha.
- Add to brief queue as a new story.
- Log as "Alpha" for source quality tracking.
- *Phase 2+:* Create a new Story Node.

### Recursive Summary Update (Phase 2+)

When an UPDATE hits a Story Node, rewrite the summary:

```
Existing summary: {current_summary}
New development: {delta}

Rewrite the summary in under 70 words to incorporate the new development.
Preserve all specific numbers, dates, and named entities. Be concise.
```

**Batching:** If 3+ updates hit the same node in one pipeline run, combine ALL deltas into ONE rewrite call. Saves N LLM calls → 1.

---

## Pillar 5: The Briefer (Output)

### What It Does
Takes only the genuinely new facts (Alphas that passed the Arbiter as UPDATE or NEW) and generates a clean, readable brief.

### Brief Format

```
📋 TrueBrief | Tesla & EVs | April 16, 2026

🆕 NEW STORIES (1)
━━━━━━━━━━━━━━━━━━━━━━━━━━
Tesla announced a new Gigafactory in Indonesia, targeting 500K
vehicles/year production capacity by 2028.
→ Sources: Reuters, Bloomberg

📈 UPDATES (1)
━━━━━━━━━━━━━━━━━━━━━━━━━━
Q3 Revenue [Updated]
WHAT'S NEW: Revenue beat expectations by $1.1B ($25.2B actual vs $24.1B expected).
FULL CONTEXT: Tesla has beaten consensus in 3 of the last 4 quarters,
cumulative revenue up 18% YoY.
→ Sources: Reuters, CNBC, TechCrunch

⏸️ No changes: Robotaxi production timeline, Cybertruck pricing
```

Key design choices:
- **NEW vs UPDATE** separation - user instantly knows the structure
- **"WHAT'S NEW" + "FULL CONTEXT"** - the delta AND the story so far
- **"No changes" footer** - confirms the system is watching, nothing happened
- **Source attribution** - always linked, builds trust, mitigates hallucination risk

### Delivery Channels

| Channel | Available | Notes |
|---------|-----------|-------|
| In-app web feed | Phase 1 | Default, always available |
| Email digest | Phase 3 | Daily or weekly, user configurable |
| Push notifications | Phase 3 | Web push (PWA) |
| Webhook (B2B) | Phase 4 | REST push to business systems |
| Slack / Teams | Phase 4+ | Enterprise integration |

---

## The Scheduler & Cost Control Layer

### Topic Registry

Every topic has scheduling metadata:

```python
@dataclass
class Topic:
    topic_id: str
    type: str              # "shared" or "private"
    owner_user_id: str     # null if shared
    raw_query: str
    search_strategy: dict  # LLM-generated search plan
    speed: str             # "fast" | "medium" | "slow"
    last_run_at: datetime
    next_run_at: datetime
```

### The Shared Topic Insight (Critical for Profitability)

Every topic is either:
- **Shared:** One pipeline run. Results served to ALL subscribed users. Cost = fixed.
- **Private:** One pipeline per user. Cost = per user.

If 500 users track "AI regulation" → you run the pipeline ONCE → serve personalized deltas to each user based on their individual knowledge state.

> **Business rule:** Free users → shared topics only. Pro users → can create private topics.

### Speed Settings & Polling Intervals

| Speed | Typical Interval | Example Topics |
|-------|-----------------|----------------|
| `fast` | 1-4 hours | Breaking news, stock events, live conflict |
| `medium` | 6-12 hours | Market updates, political developments |
| `slow` | 24-48 hours | Scientific research, regulations, long-form trends |

### AYR: Alpha Yield Rate (Source Quality Tracking - Phase 2)

Not all sources are equal. Some produce 90% new information; others repeat what you already know. AYR tracks this dynamically and adjusts how often you check each source.

After each scrape, you know:
- `A` = new Alphas found (genuinely new facts)
- `D` = Duplicates (facts already known)
- `T` = total facts analyzed

**Calculate session performance:**
```
Density   = (A + D) / T          # How relevant is this source to this topic?
Freshness = A / (A + D)          # Of relevant facts, how many are new?
Utility   = (0.4 × Density) + (0.6 × Freshness)    # Weighted - freshness matters more
```

**Smooth with exponential moving average:**
```
α = 0.3
AYR_new = (Utility × α) + (AYR_old × (1 - α))
```

**Convert to polling interval:**
```
T_base = Topic speed in seconds (fast=3600, medium=21600, slow=86400)
Interval = T_base / max(AYR, 0.1)
```

**The effect:**
- Reuters (AYR=0.72), fast topic: `3600 / 0.72 = 5000s ≈ 83 min` → checked often
- Low-quality blog (AYR=0.15), fast topic: `3600 / 0.15 = 24000s ≈ 6.7 hrs` → checked rarely

> **Why this matters:** Without AYR, you either waste money checking garbage sources, or miss good ones. AYR auto-tunes your scraping budget to where it produces the most value.

### LLM Cost Optimization Summary

| Technique | What It Saves |
|-----------|--------------|
| Gemini Flash for Query Builder, Garbage Filter, Arbiter, Briefer | Free in prototype; very cheap in production |
| Gemini Flash for Harvester (prototype) / Pro model (production) | Quality where it matters most |
| Fast Path (auto-MERGE / auto-NEW) | ~50% of Judge LLM calls |
| Article content caching (by URL hash) | Never process same article twice |
| Tavily returns full text | No separate scraping cost for Tavily results |
| Summary rewrite batching | N updates → 1 LLM call per node |
| Shared topic execution | Cost scales with unique topics, not users |

**Target cost:** 10 articles ingested on a shared topic ≤ $0.05 total LLM cost.

**Per-user monthly cost estimate:**
- Free user (2 shared topics, daily): ~$0.10/mo
- Pro user (15 topics, hourly): ~$0.80/mo
- Pro user pays $8/mo → 90% gross margin ✅

---

## Tech Stack

> **Principle:** Start boring. Add complexity only when proven necessary. Every extra service is ops burden for a solo dev.

### Backend

| Component | Tech | Why |
|-----------|------|-----|
| Language | **Python** | LLM ecosystem, AI libraries, one language for everything |
| API Framework | **FastAPI** | Async, auto-docs, type-safe, production-ready |
| Task Queue | **Celery + Redis** | Background pipeline jobs, scheduled runs (Celery Beat) |
| Database | **Supabase** (PostgreSQL cloud) | Zero-maintenance, pgvector built-in, free 500MB tier for prototype |
| Vector Search | **pgvector** via Supabase | No extra service. Lives in Supabase Postgres |
| Cache | **Redis** | Already running for Celery. Article cache, rate limiting |
| LLM - Prototype | **Gemini API** (Google AI Studio) | Free tier: ~1,500 req/day. No credit card. Fast to start. |
| LLM - Production | **Multi-provider** (Gemini / OpenAI / Claude) | Config-driven abstraction layer. Swap per step via `settings.py`. |
| LLM per step | Query Builder, Garbage Filter, Arbiter, Briefer → `gemini-2.5-flash` | Simple structured tasks. Fast, cheap, free in prototype. |
| LLM per step | Harvester → `gemini-2.5-flash` (prototype) / `gemini-2.5-pro` or `gpt-4o` (prod) | Most accuracy-critical call. Upgrade when moving to production. |
| Content Extraction | **trafilatura** | Best Python lib for clean article text. No browser needed for most sites. |

### Frontend

| Component | Tech | Why |
|-----------|------|-----|
| Framework | **Next.js** (React) | SSR for SEO, API routes, solid DX |
| Styling | **Tailwind CSS** | Fast iteration, consistent, solo-dev friendly |
| State | **React Query** | Server state management, caching, auto-refetch |
| Auth | **Clerk** or **NextAuth.js** | Never build auth yourself |

### Infrastructure

| Component | Tech | Monthly Cost |
|-----------|------|-------------|
| Backend hosting | Railway or Render | $5-20 |
| Frontend hosting | Vercel | $0-20 |
| PostgreSQL + pgvector | **Supabase** (free → Pro $25/mo) | $0 prototype / $25 production |
| Redis | Managed (Railway/Upstash) | $0-10 |
| LLM - Prototype | Gemini API free tier | **$0** |
| LLM - Production | Gemini / OpenAI pay-per-use | $10-50 |
| News APIs - Phase 1 | Direct RSS (free) + Tavily (1K free/mo) | **$0** |
| News APIs - Phase 3+ | Tavily / Brave / Exa pay-per-use | $5-30 |
| Domain + CDN | Cloudflare | ~$1/mo |
| Payments | Stripe | 2.9% + $0.30/txn |
| Error tracking | Sentry (free tier) | $0 |
| **Total Month 1-6 (prototype)** | | **~$10-50/mo** |
| **Total Month 6+ (production)** | | **~$50-150/mo** |

### What NOT To Use (Yet)

| Don't Use | Use Instead | Upgrade When |
|-----------|------------|-------------|
| Qdrant / Pinecone / Weaviate | pgvector via Supabase | 500K+ vectors with latency issues |
| Kubernetes | Railway/Render | You need multi-region or 10+ services |
| Kafka / RabbitMQ | Celery + Redis | Processing 10K+ messages/sec |
| Microservices | Monolith | Team grows to 3+ people |
| Mobile app (native) | PWA | 10K+ active users requesting native |
| OpenAI in prototype | Gemini free tier | When production traffic makes $0 cost impossible |
| NewsAPI.org | Direct RSS + Tavily | Never (24h delay + production ToS violation) |
| Google News RSS | Direct RSS first | Phase 2 only, with URL decoder, accept fragility |

---

## Monetization Strategy

### The Core Challenge

> *"Why pay for news when it's free everywhere?"*

**You're not paying for news. You're paying for TIME.**

Free news costs hours of scrolling, clicking, reading, filtering. TrueBrief costs 30 seconds per topic. The product is **attention efficiency**, not journalism.

### B2C Tiers

| Tier | Price | Topics | Speed | Sources | Features |
|------|-------|--------|-------|---------|----------|
| **Free** | $0 | 2 shared topics | Daily (24h delay) | Basic (RSS, Tavily) | Web feed only |
| **Pro** | $8/mo | 15 topics (shared + private) | Hourly (real-time) | All sources | Email digest, push notifications, brief history |
| **Power** | $20/mo | Unlimited topics | 15-minute | All + priority | API access, data export, priority processing |

**Free tier must be genuinely useful** - not crippled. 2 topics with daily updates is enough to demonstrate real value. The 24-hour delay creates natural upgrade pressure (news is time-sensitive).

### Conversion Levers

| Trigger | Action |
|---------|--------|
| After 7 days of use | Show "You saved X hours this week" |
| User tries to add 3rd topic | Soft paywall: "Upgrade for more topics" |
| User clicks a brief that's delayed | "Get real-time updates with Pro" |
| Free email digest | Persistent value reminder → "Upgrade for hourly" |
| Public shared briefs | Viral loop: "Powered by TrueBrief" |

### B2B Revenue (The Real Money)

| Offering | Price | Target Customer |
|----------|-------|----------------|
| **API Access** | $0.01-0.05 per brief | Developers embedding news intel in their apps |
| **White-Label** | $500-2,000/mo | Agencies, media companies |
| **Enterprise** | Custom ($1K-5K/mo) | Large orgs - PR, risk, competitive intel |

**Target B2B use cases:**
- **PR/Comms** - monitor brand/client coverage
- **Investment firms** - track portfolio companies, sectors
- **Competitive intelligence** - watch competitor moves
- **Risk/Compliance** - regulatory change monitoring
- **Research** - academic, policy, industry trends

> Even 5 enterprise clients at $2K/mo = $120K/year. That's a sustainable solo-dev business.

### Revenue Projections (Conservative)

| Milestone | Timeline | B2C Monthly | B2B Monthly | Total |
|-----------|----------|------------|------------|-------|
| 1K free, 50 Pro | Month 6 | $400 | $0 | $400 |
| 5K free, 300 Pro, 2 B2B | Month 12 | $2,400 | $2,000 | $4,400 |
| 20K free, 1.5K Pro, 10 B2B | Month 24 | $12,000 | $15,000 | $27,000 |

---

## Build Phases - What to Build When

### Phase 1: Core MVP (Weeks 1-4)

**Goal:** One user can enter a topic and receive a useful brief.

**Build:**
- [ ] LLM abstraction layer: `llm/client.py` - config-driven, supports Gemini / OpenAI / others via `settings.py`
- [ ] FastAPI backend: `POST /api/v1/topics`, `GET /api/v1/topics`, `GET /api/v1/briefs/{topic_id}`
- [ ] Query Builder: topic → Gemini Flash → search queries + RSS category matching
- [ ] Collector - `RSSLayer`: scan curated RSS feeds from `config/rss_feeds.yaml` (direct, original URLs)
- [ ] Collector - `TavilyLayer`: search Tavily API for topic-specific articles (returns clean text, no scraping needed)
- [ ] Article extractor (trafilatura): for RSS articles that provide URLs but not full text
- [ ] Harvester: Gemini Flash extracts atomic facts (Alphas) - JSON output with alpha_text, entities, event_date, context, confidence
- [ ] Ledger: Supabase PostgreSQL schema - users, topics, known_facts (with pgvector column), briefs
- [ ] Simple Arbiter: pgvector cosine similarity, >0.90 = DUPLICATE, else = NEW
- [ ] Brief generation: Gemini Flash formats new/updated facts into clean brief
- [ ] Deploy backend to Railway, connect to Supabase cloud DB

**NOT building:** Frontend (Phase 3), Story Nodes, AYR, scheduling, payments, email, fast-path Arbiter

**API Keys required:** `GOOGLE_API_KEY` (Gemini, free at AI Studio) · `TAVILY_API_KEY` (free 1K/mo at tavily.com) · `SUPABASE_URL` + `SUPABASE_KEY` (already set up)

**Validate:** Show to 10 people. Does the output make sense? Would they use this daily?

---

### Phase 2: Delta Engine + Scheduling (Weeks 5-8)

**Goal:** The system runs autonomously and never repeats information.

**Build:**
- [ ] Celery Beat scheduler: run pipeline per topic at configured intervals
- [ ] Fast Path for Arbiter: auto-MERGE (>0.97) and auto-NEW (zero matches)
- [ ] Full Judge LLM prompt for ambiguous cases (MERGE/UPDATE/NEW)
- [ ] "Nothing new" handling: don't deliver empty briefs
- [ ] Brief history: see past briefs per topic
- [ ] Source quality tracking: log Alpha vs Duplicate per source (foundation for AYR)
- [ ] GoogleNewsRSS as 3rd source plugin (with URL decoder library, Phase 2 only)
- [ ] AYR calculation and dynamic polling intervals
- [ ] Dynamic keyword rotation: track which search terms produce best alphas per topic
- [ ] Shared topic infrastructure: one pipeline, fan out to subscribers

**This phase is make-or-break.** Without working delta detection, you're just another summarizer.

---

### Phase 3: Product Polish + Monetization (Weeks 9-14)

**Goal:** A product people will pay for.

**Build:**
- [ ] Story Nodes: group related facts into evolving stories
- [ ] Dual vectors: alpha_embedding + summary_embedding (still pgvector)
- [ ] Recursive summary updates when stories evolve
- [ ] Stripe integration: subscription management
- [ ] Free / Pro / Power tier enforcement (topic limits, speed, sources)
- [ ] Email digest delivery (daily/weekly, user configurable)
- [ ] Web push notifications (PWA)
- [ ] Onboarding flow: explain the product, suggest starter topics
- [ ] "Time saved" metric per user (engagement + conversion tool)
- [ ] Public brief sharing pages (viral growth + SEO)
- [ ] Landing page with clear value proposition
- [ ] Rate limiting and abuse prevention
- [ ] Mobile-responsive design (PWA)
- [ ] Add Brave Search + Exa as Phase 3+ source plugins
- [ ] Next.js frontend: topic input, topic list, brief display, brief history

---

### Phase 4: B2B API (Weeks 15-20)

**Goal:** Revenue from business customers.

**Build:**
- [ ] Public REST API with API key auth
- [ ] API documentation (auto-generated from FastAPI + polished)
- [ ] Core endpoints:
  - `GET /api/v1/topics/{id}/delta?since={timestamp}` - new facts since timestamp
  - `GET /api/v1/topics/{id}/nodes` - full story graph
  - `POST /api/v1/topics` - create private topic
  - `GET /api/v1/briefs/{id}` - retrieve formatted brief
  - `POST /api/v1/webhooks` - register delivery endpoint
- [ ] Usage tracking and per-call billing
- [ ] Webhook delivery (push briefs to client systems)
- [ ] Admin dashboard for B2B accounts
- [ ] API versioning: URL-based (`/api/v1/`), deprecation headers, 12-month support window
- [ ] Rate limits by tier (Business: 1K/day, Enterprise: unlimited)

---

### Phase 5: Scale + Moat (Months 6-12)

**Goal:** Build defensibility and compound advantages.

**Build:**
- [ ] Plugin architecture formalized: config-driven component swapping (A/B test harvesters, judges, collectors)
- [ ] Source quality reputation network (AYR shared across users = system-level source ranking)
- [ ] User feedback loop: thumbs up/down on briefs → improve relevance scoring
- [ ] Multi-language support (multilingual embeddings)
- [ ] Contradiction detection: two sources disagree on same fact → flag for user
- [ ] Specialized source plugins: SEC EDGAR, FDA, PubMed, EU regulatory feeds
- [ ] Team/organization accounts
- [ ] White-label options for B2B (custom branding, domain)
- [ ] Mobile app (React Native) if user demand justifies it

### Phase 6: Domain Intelligence Pipelines (Year 2+)

**The long-term moat.** The general pipeline works for any topic but is sub-optimal for specialized fields.

Domain pipelines are custom configurations with:
- **Specialized sources** (SEC EDGAR for finance, PubMed for medical)
- **Custom Harvester prompts** (financial fact extraction needs numerical precision, legal needs citation tracking)
- **Custom Arbiter rules** ("1% change in EPS = UPDATE, not MERGE")
- **Domain-specific Alpha fields** (`ticker`, `financial_metric`, `ruling_citation`)

```
USER PROMPT → ROUTER (which domains?) → Run matching pipelines → Merge Alphas → Arbiter → Brief
```

**The Router evolves:**
1. **V1 (now):** LLM classifies prompt into domains (~$0.001 per call)
2. **V2 (6 months):** Fine-tuned small classifier trained on YOUR routing data (near-zero cost, <10ms)
3. **V3 (12 months):** Feedback loop - user says "missed finance context" → router adjusts

**Planned domain catalog:**

| Domain | Differentiator | B2B Target |
|--------|---------------|-----------|
| `finance` | SEC filings, ticker tracking, earnings precision | Hedge funds, analysts |
| `legal` | Court dockets, citation-aware facts | Law firms, compliance |
| `medical` | PubMed, clinical trials, drug approvals | Pharma, biotech |
| `geopolitics` | Diplomatic sources, conflict trackers | Think tanks, defense |

> **Build sequence:** General pipeline first (Phase 1-4). Pick the domain your first B2B customer needs. Build ONE completely before starting the next. Each domain = new market segment funded by B2B revenue.

---

## Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **LLM costs spike** | Bankruptcy | Shared pipelines, fast-path, caching, cost caps per user |
| **News APIs shut down** | No data | Multiple redundant source plugins, never depend on one |
| **Users won't pay** | No revenue | Focus B2B early (B2C = growth engine, not primary revenue) |
| **Hallucinated facts** | Trust destroyed | Always link sources, confidence thresholds, verification layer |
| **Legal (copyright)** | Shutdown | Extract facts (transformative use), never republish full articles |
| **Competitor** | Irrelevant | Data flywheel: more users → better AYR → better routing → more users |
| **Solo dev burnout** | Everything dies | Ship in phases, get paying customers early, reinvest in help |

---

## Success Metrics

### Product
- **Brief quality** - % rated useful by users (target: >80%)
- **Delta accuracy** - % of updates that are genuinely new (target: >90%)
- **Topics per user** - engagement depth (target: 3+ for actives)

### Business
- **MRR** - Monthly Recurring Revenue
- **Free → Pro conversion** - target: 5-8%
- **Churn** - target: <5% monthly
- **LTV:CAC** - target: >3:1
- **Cost per brief** - target: <$0.02 at scale

### Growth
- **WAU** - Weekly Active Users
- **Organic sign-ups** - from shared briefs, SEO
- **B2B pipeline** - leads → demos → contracts

---

## Summary

TrueBrief is not a news app. It's an **attention efficiency engine** that uses news as its first domain.

**The architecture in one sentence:** Collect articles → Extract atomic facts → Compare against what's known → Only deliver the delta → Remember everything → Get smarter over time.

**The moat that compounds:**
1. **Knowledge graph** - longer usage → better delta detection → more trust
2. **Source quality data (AYR)** - system learns which sources are reliable
3. **Shared intelligence** - more users → more topics → more efficient for everyone
4. **Domain pipelines** - 12+ months of domain-specific training data can't be replicated quickly
5. **Habit** - once someone replaces their news routine, switching cost is high

**The timeline:**
- Week 4: Working MVP
- Week 8: Delta engine running autonomously
- Week 14: First paying customer
- Week 20: First B2B client
- Month 12: $4K+ MRR
- Month 24: $27K+ MRR

**Build. Ship. Learn. Don't overbuild. Don't underthink. Ship fast. Learn faster.**
