# Phase 5: Scale + Moat
> 📍 Read FIRST: [.ai/BOOT.md](file:///d:/projects/Apps/TrueBrief/.ai/BOOT.md)
> 📐 Status: `[ ]` Not Started

## Goal
Build defensibility through scale, network effects, and specialized data quality. The longer the system runs, the harder it is to replicate — AYR data, source reputation scores, and multi-user intelligence compound into a moat.

---

## Step Summary
| # | Task | Status | PLAN | BUILD | UNIT | INTG |
|---|------|--------|---|---|---|---|
| 5.1 | Plugin Architecture (Formalized) | [ ] | [ ] | [ ] | [ ] | [ ] |
| 5.2 | Global AYR Network | [ ] | [ ] | [ ] | [ ] | [ ] |
| 5.3 | User Feedback Loop | [ ] | [ ] | [ ] | [ ] | [ ] |
| 5.4 | Contradiction Detection | [ ] | [ ] | [ ] | [ ] | [ ] |
| 5.5 | Multi-Language Support | [ ] | [ ] | [ ] | [ ] | [ ] |
| 5.6 | Specialized Source Plugins | [ ] | [ ] | [ ] | [ ] | [ ] |
| 5.7 | Team / Org Accounts | [ ] | [ ] | [ ] | [ ] | [ ] |
| 5.8 | White-Label B2B UI | [ ] | [ ] | [ ] | [ ] | [ ] |
| 5.9 | Mobile App (React Native) | [ ] | [ ] | [ ] | [ ] | [ ] |

---

### Step 5.1: Plugin Architecture (Formalized)

| Detail | Value |
|--------|-------|
| **What** | Config-driven component swapping for collectors, harvesters, and arbiters — A/B test without code changes |
| **Files** | `src/truebrief/collector/registry.py`, `config/plugins.yaml`, `src/truebrief/core/plugin_loader.py` |
| **Status** | `[ ]` |

#### Design

```python
# core/plugin_loader.py
class PluginRegistry:
    """Load and instantiate pipeline components from config, not hardcode."""
    
    def get_collector_layers(self, topic: Topic, user: User) -> List[SourceLayer]:
        """Returns ordered list of source plugins for this topic+tier combination."""
        config = load_routing_rules(topic.domain, user.plan)
        return [self._load_plugin(name) for name in config["layers"]]

    def get_harvester(self, variant: str = "default") -> Harvester:
        """Support A/B test: 'default' vs 'experimental' harvester prompt."""

    def _load_plugin(self, plugin_name: str) -> Any:
        """Dynamic import from plugin registry. No hardcoded class names in runner."""
```

```yaml
# config/plugins.yaml — all pipeline components registered here
collectors:
  rss_layer:        {class: "truebrief.collector.rss_layer.RSSLayer",        enabled: true}
  tavily_layer:     {class: "truebrief.collector.tavily_layer.TavilyLayer",  enabled: true}
  brave_layer:      {class: "truebrief.collector.brave_layer.BraveLayer",    enabled: true, tiers: [pro, power]}
  exa_layer:        {class: "truebrief.collector.exa_layer.ExaLayer",        enabled: true, tiers: [power]}
  sec_edgar_layer:  {class: "truebrief.collector.sec_edgar_layer.SECLayer",  enabled: false}

harvesters:
  default:          {class: "truebrief.harvester.harvester.Harvester",       model: gemini-2.5-flash}
  precision:        {class: "truebrief.harvester.harvester.Harvester",       model: gemini-2.5-pro}

arbiters:
  default:          {class: "truebrief.arbiter.arbiter.Arbiter"}
  strict:           {class: "truebrief.arbiter.arbiter.Arbiter",             merge_threshold: 0.85}
```

#### A/B Testing Support
```python
# Enable an experiment per-topic:
topic.harvester_variant = "precision"   # Uses gemini-2.5-pro for this topic
topic.arbiter_variant = "strict"        # Tighter merge threshold

# PluginLoader respects topic.harvester_variant and topic.arbiter_variant
```

#### Acceptance Criteria
- Adding a new source plugin = 1 class file + 1 line in `plugins.yaml` (zero changes to runner)
- Disabling a plugin in config stops it being used within 60s (hot-reload or next topic run)
- A/B variant assignment persists per-topic in `topics.harvester_variant` column
- Plugin load failures logged as errors but don't crash the pipeline (fallback to defaults)
- Unit test: `PluginRegistry().get_collector_layers(topic, free_user)` returns only free-tier plugins

---

### Step 5.2: Global AYR Network

| Detail | Value |
|--------|-------|
| **What** | Share Alpha Yield Rate (AYR) signals across all users — system-level source reputation |
| **Files** | `src/truebrief/ledger/ayr_network.py`, `src/truebrief/ledger/ayr_engine.py` (extend) |
| **Status** | `[ ]` |

#### Why This Matters
Phase 2 built per-topic AYR. If Reuters scores 0.72 on "TSMC" for one user, that signal stays isolated. The global network aggregates AYR across all users tracking similar topics — making the whole system smarter, not just one user's pipeline.

#### Design

```python
# ledger/ayr_network.py
class GlobalAYRNetwork:
    """Aggregate per-topic AYR into global source reputation scores."""

    def update_global_score(self, source_domain: str, topic_domain: str, session_utility: float) -> None:
        """Weighted update to global source scores, segmented by topic domain."""
        # Stored in: source_reputation table (source_domain, topic_domain, global_ayr, sample_count)
        alpha = 0.1   # Slower decay for global — more samples needed to move the needle
        current = get_global_score(source_domain, topic_domain)
        new_score = (session_utility * alpha) + (current * (1 - alpha))
        upsert_global_score(source_domain, topic_domain, new_score)

    def get_routing_weights(self, topic_domain: str) -> Dict[str, float]:
        """Returns {source_domain: ayr_score} for routing decisions."""
        # Used by PluginLoader to order sources by expected yield
```

#### Global Score Table Schema
```sql
CREATE TABLE source_reputation (
    source_domain     TEXT,
    topic_domain      TEXT,    -- 'finance', 'tech', 'geopolitics', 'general'
    global_ayr        FLOAT DEFAULT 0.5,
    sample_count      INT DEFAULT 0,
    last_updated_at   TIMESTAMPTZ,
    PRIMARY KEY (source_domain, topic_domain)
);
```

#### Network Effect
- 100 users tracking "AI regulation" → 100 per-topic AYR samples flow into `source_reputation`
- Reuters/AI gets 100 signal inputs/week vs a solo user's 1
- System learns faster: good sources surface quickly, garbage sources get deprioritized globally
- This data cannot be replicated by a new competitor starting from zero

#### Acceptance Criteria
- After each pipeline run, session utility feeds both per-topic AYR (existing) and global AYR
- `get_routing_weights("finance")` returns sorted source scores for routing
- Global AYR score visible in admin dashboard per source (Step 4.8)
- Privacy: global AYR aggregates do NOT expose which users track which topics
- Seeded with reasonable defaults (0.5) so cold-start works before data accumulates

---

### Step 5.3: User Feedback Loop

| Detail | Value |
|--------|-------|
| **What** | Thumbs up/down on briefs + individual alphas → improve relevance scoring over time |
| **Files** | `src/truebrief/api/feedback.py`, `src/truebrief/tasks/feedback_processor.py` |
| **Status** | `[ ]` |

#### Design

```python
# api/feedback.py
# POST /api/v1/briefs/{brief_id}/feedback
class BriefFeedback(BaseModel):
    rating: int           # 1 = thumbs up, -1 = thumbs down
    note: Optional[str]   # Optional free-text (max 200 chars)

# POST /api/v1/alphas/{alpha_id}/feedback
class AlphaFeedback(BaseModel):
    rating: int           # 1 = relevant, -1 = irrelevant / already knew this
    reason: Optional[str] = None   # "irrelevant" | "duplicate" | "wrong_topic" | "outdated"
```

```python
# tasks/feedback_processor.py
class FeedbackProcessor:
    """Async Celery task: process feedback signals to improve future runs."""

    def process_alpha_feedback(self, alpha_id: str, rating: int, reason: str) -> None:
        alpha = get_alpha(alpha_id)
        if rating == -1:
            if reason == "duplicate":
                # Lower arbiter merge_threshold for this topic (tighter future dedup)
                adjust_topic_arbiter_threshold(alpha.topic_id, delta=-0.02)
            elif reason == "irrelevant":
                # Add source domain to topic's deprioritized sources list
                deprioritize_source(alpha.topic_id, alpha.source_domain)
            elif reason == "wrong_topic":
                # Flag query_builder to tighten search strategy for this topic
                flag_for_query_refinement(alpha.topic_id)
        elif rating == 1:
            # Boost source AYR for this topic
            boost_source_ayr(alpha.topic_id, alpha.source_domain, delta=+0.05)
```

#### UI Integration
- Brief page: thumbs up/down on entire brief (below the brief content)
- Individual alpha: small 👍/👎 on each fact bullet
- After 3 consecutive thumbs-down on a topic → "Refine this topic?" prompt with query editing

#### Acceptance Criteria
- Feedback stored in `alpha_feedback` and `brief_feedback` tables
- Feedback processing runs async (Celery task), does not block UI response
- 10+ negative feedbacks on a source for a topic → source visibly deprioritized in next run
- Feedback signals visible in admin dashboard (most downvoted sources, most downvoted topics)
- Feedback does NOT retroactively alter the `known_facts` table (only influences future runs)

---

### Step 5.4: Contradiction Detection

| Detail | Value |
|--------|-------|
| **What** | Detect when two sources disagree on the same fact — flag for the user instead of silently picking one |
| **Files** | `src/truebrief/arbiter/contradiction.py` |
| **Status** | `[ ]` |

#### Design

```python
# arbiter/contradiction.py
class ContradictionDetector:
    """Called when Arbiter finds STRONG_MATCH (0.85-0.94) but entities mismatch in key fields."""

    def detect(self, new_alpha: Alpha, existing_alpha: Alpha) -> Optional[Contradiction]:
        """
        Returns a Contradiction if the two alphas:
        1. Are about the same event/entity (high semantic similarity)
        2. Disagree on a specific verifiable field (number, date, name)
        """
        prompt = CONTRADICTION_PROMPT.format(
            alpha_a=existing_alpha.alpha_text,
            alpha_b=new_alpha.alpha_text,
        )
        result = llm.call("contradiction", prompt)
        # LLM output: {"is_contradiction": bool, "field": "...", "value_a": "...", "value_b": "..."}
```

```
# LLM Prompt for contradiction detection
You are a fact-checking analyst. Two sources report on the same topic.
Determine if they CONTRADICT each other on a specific, verifiable field.

Source A: {alpha_a}
Source B: {alpha_b}

A contradiction = they disagree on the same measurable fact (number, date, name, quantity).
NOT a contradiction = different but compatible facts about the same event.

Output JSON:
{
  "is_contradiction": true/false,
  "field": "the field where they disagree, or null",
  "value_a": "what source A says, or null",
  "value_b": "what source B says, or null"
}
```

#### Brief Rendering — Contradiction Format
```
⚠️ CONFLICTING REPORTS
━━━━━━━━━━━━━━━━━━━━━━
TSMC Q1 2026 yield rate:
  Reuters: "94% yield on N3E process"
  Bloomberg: "89% yield on N3E process"
→ We cannot determine which is accurate. Both sources cited.
```

#### Acceptance Criteria
- Contradiction detector called only for STRONG_MATCH alphas (0.85-0.94 cosine) — not for IDENTICAL or NO_MATCH
- Contradiction detection adds ≤ 1 LLM call per STRONG_MATCH (fast-pathed if entities differ entirely)
- Contradictions stored in `alpha_contradictions` table with both alpha IDs
- Brief sections: contradictions shown in dedicated "⚠️ CONFLICTING REPORTS" block
- Users can vote on which source they trust (feeds source reputation)

---

### Step 5.5: Multi-Language Support

| Detail | Value |
|--------|-------|
| **What** | Support non-English topics and sources via multilingual embeddings and LLM prompts |
| **Files** | `src/truebrief/ledger/vector_store.py` (embedding model swap), `config/settings.py` |
| **Status** | `[ ]` |

#### Design

**Current bottleneck:** `text-embedding-004` (Gemini) is primarily English-optimized. Cross-language similarity scores degrade for non-English facts.

**Solution:** Switch embedding model to `multilingual-e5-large` or `cohere-embed-multilingual-v3.0` for topics flagged as multilingual.

```python
# settings.py — embedding config
EMBEDDING_CONFIG = {
    "default": {
        "provider": "gemini",
        "model": "text-embedding-004",
        "dimensions": 768,
    },
    "multilingual": {
        "provider": "cohere",
        "model": "embed-multilingual-v3.0",
        "dimensions": 1024,
    }
}

# topics table: add `embedding_model` column
# "default" for English-primary, "multilingual" for mixed/non-English
```

```python
# Harvester: language detection + prompt language matching
class Harvester:
    def extract(self, article_text: str, published_date: datetime, lang: str = "en") -> List[Alpha]:
        if lang != "en":
            prompt = HARVESTER_PROMPT_MULTILINGUAL.format(language=lang, text=article_text)
        else:
            prompt = HARVESTER_PROMPT.format(text=article_text)
        # LLM always outputs alpha_text in English (normalized) regardless of source language
```

#### Language Detection
```python
from langdetect import detect  # pip install langdetect
lang = detect(article_text)    # Returns ISO 639-1 code: "en", "de", "zh", "ar"
```

#### Acceptance Criteria
- German/French/Spanish article → facts extracted correctly in English
- Multilingual embedding model used for topics with `embedding_model = "multilingual"`
- Cross-language duplicate detection works: same fact in EN and DE → MERGE (not NEW)
- Language detection adds < 10ms per article (langdetect is local, no API call)
- Admin can set `embedding_model` per topic; old embeddings regenerated on next run

---

### Step 5.6: Specialized Source Plugins

| Detail | Value |
|--------|-------|
| **What** | Domain-specific source plugins for SEC filings, PubMed, FDA, EU regulatory databases |
| **Files** | `src/truebrief/collector/sec_edgar_layer.py`, `src/truebrief/collector/pubmed_layer.py`, `src/truebrief/collector/fda_layer.py`, `src/truebrief/collector/eu_reg_layer.py` |
| **Status** | `[ ]` |

#### Plugin Specifications

**SEC EDGAR Layer** (`sec_edgar_layer.py`)
```python
class SECEdgarLayer(SourceLayer):
    """Pull 8-K, 10-K, 10-Q filings for tracked companies via EDGAR full-text search."""
    BASE_URL = "https://efts.sec.gov/LATEST/search-index"
    # Free, no API key. Rate limit: 10 req/sec.
    # Returns: filing document URLs → Article Extractor for full text
    # Best for: earnings, material events, insider trading disclosures
```

**PubMed Layer** (`pubmed_layer.py`)
```python
class PubMedLayer(SourceLayer):
    """NCBI E-utilities API for medical research papers."""
    # Free, no API key for < 3 req/sec. Register email for 10 req/sec.
    # Returns: abstract + title + DOI link
    # Best for: clinical trials, drug approvals, medical research topics
```

**FDA Layer** (`fda_layer.py`)
```python
class FDALayer(SourceLayer):
    """FDA openFDA API for drug approvals, recalls, adverse events."""
    BASE_URL = "https://api.fda.gov"
    # Free, 1,000 req/day without key, 120,000/day with key (free registration)
```

**EU Regulatory Layer** (`eu_reg_layer.py`)
```python
class EURegulatoryLayer(SourceLayer):
    """EUR-Lex API for EU legislation, directives, and court decisions."""
    # Free, no API key
    # Best for: GDPR updates, AI Act, financial regulations
```

#### Routing Configuration
```yaml
# config/routing_rules.yaml
overrides:
  - domain: finance
    add_layers: [sec_edgar_layer]
  - domain: medical
    add_layers: [pubmed_layer, fda_layer]
  - domain: legal
    add_layers: [eu_reg_layer]
  - tier: power
    topics_with_entities: ["public_company"]
    add_layers: [sec_edgar_layer]
```

#### Acceptance Criteria
- Each plugin implements `SourceLayer` ABC identically to existing plugins
- SEC layer returns actual filing text (not just headline) via Article Extractor
- PubMed layer returns structured abstract + metadata as `RawArticle`
- Each plugin gracefully skips on API errors (no crash, logged warning)
- Plugins registered in `plugins.yaml` with `enabled: false` initially (opt-in per topic)

---

### Step 5.7: Team / Org Accounts

| Detail | Value |
|--------|-------|
| **What** | Multiple users under one billing account — shared topics, usage pooling, role-based access |
| **Files** | `src/truebrief/models/org.py`, `src/truebrief/api/org_routes.py`, new DB tables |
| **Status** | `[ ]` |

#### Data Model

```python
# models/org.py
@dataclass
class Organization:
    org_id: str
    name: str
    plan: str               # "team" | "enterprise"
    stripe_id: str
    max_members: int        # Team = 5, Enterprise = unlimited
    created_at: datetime

@dataclass
class OrgMembership:
    org_id: str
    user_id: str
    role: str              # "owner" | "admin" | "member" | "viewer"
    joined_at: datetime
```

#### Role Permissions
| Action | Owner | Admin | Member | Viewer |
|--------|-------|-------|--------|--------|
| Add/remove topics | ✅ | ✅ | ✅ | ❌ |
| Trigger manual scan | ✅ | ✅ | ✅ | ❌ |
| View briefs | ✅ | ✅ | ✅ | ✅ |
| Manage members | ✅ | ✅ | ❌ | ❌ |
| Billing management | ✅ | ❌ | ❌ | ❌ |
| Delete org | ✅ | ❌ | ❌ | ❌ |

#### Shared Topics in Org
- Topics created within an org are visible to all org members
- `topics.org_id` FK links topic to org (NULL = personal topic)
- Pipeline runs once per shared org topic, briefs visible to all members

#### Acceptance Criteria
- Org owner can invite members via email (generates invite link)
- Invited user joins via link → added to `org_memberships`
- Org topics visible to all members in their dashboard
- Viewer can read briefs but "Add Topic" button is hidden
- Billing consolidated: org pays once, all members get Pro features
- Member count enforced: Team plan blocks invite beyond 5 members (HTTP 402)

---

### Step 5.8: White-Label B2B UI

| Detail | Value |
|--------|-------|
| **What** | Allow enterprise clients to deploy TrueBrief with their own branding, domain, and colors |
| **Files** | `src/truebrief/api/tenant.py`, `frontend/lib/tenant.ts`, `config/tenants/` |
| **Status** | `[ ]` |

#### Design

```python
# api/tenant.py
class TenantConfig(BaseModel):
    tenant_id: str
    name: str                    # "Acme Intelligence Platform"
    logo_url: str
    primary_color: str           # "#1A73E8"
    custom_domain: str           # "intel.acmecorp.com"
    allowed_sources: List[str]   # Subset of global source plugins
    custom_css_url: Optional[str]
    support_email: str
```

```typescript
// frontend/lib/tenant.ts
// Detects current hostname → fetches tenant config → applies to layout
async function loadTenantConfig(): Promise<TenantConfig | null> {
    const hostname = window.location.hostname;
    if (hostname === "truebrief.io") return null;   // Default branding
    return await fetch(`/api/v1/tenants/config?domain=${hostname}`).then(r => r.json());
}
```

```yaml
# config/tenants/acme.yaml
tenant_id: acme
name: "Acme Intelligence Platform"
logo_url: "https://cdn.acmecorp.com/logo.svg"
primary_color: "#1A73E8"
custom_domain: "intel.acmecorp.com"
allowed_sources: [rss_layer, tavily_layer, sec_edgar_layer]
support_email: "intel-support@acmecorp.com"
```

#### Pricing
White-label = Enterprise plan only ($500-2,000/mo). Custom domain setup is manual (DNS delegation + Vercel custom domain).

#### Acceptance Criteria
- `intel.acmecorp.com` shows Acme logo, Acme colors, no TrueBrief branding
- `/api/v1/tenants/config?domain=...` returns correct config for known domains, 404 for unknown
- TrueBrief branding not visible in white-label deployments (no footer links, no "Powered by")
- Custom CSS URL supported for fine-grained styling beyond color + logo
- Tenant configs hot-reloaded from `config/tenants/` (no code deploy for new tenant)

---

### Step 5.9: Mobile App (React Native)

| Detail | Value |
|--------|-------|
| **What** | Native iOS and Android app — only build this when PWA users are requesting native |
| **Files** | `mobile/` directory (new Expo/React Native project) |
| **Status** | `[ ]` |

#### Trigger Condition
**Do NOT build until:** 10K+ active users AND user feedback consistently requests native app features (offline access, system notifications, widgets). PWA covers 90% of use cases. Native = ops cost + app store maintenance.

#### Architecture (if built)

```
mobile/
├── app/
│   ├── (tabs)/
│   │   ├── dashboard.tsx    # Topic list
│   │   └── profile.tsx      # Account settings
│   ├── topics/[id].tsx      # Topic detail + scan
│   └── briefs/[id].tsx      # Full brief
├── components/
│   ├── BriefCard.tsx
│   └── TopicCard.tsx
└── lib/
    └── api.ts               # Same typed API client as frontend
```

- **Framework:** Expo (React Native) — single codebase for iOS + Android
- **Auth:** Clerk React Native SDK (same auth as web)
- **State:** React Query (same as web — shared `lib/api.ts`)
- **Notifications:** Expo Push Notifications (replaces web push for native users)

#### Features Native App Adds Over PWA
- Home screen widget (brief preview on lock screen)
- System-level push notifications (more reliable than web push)
- Offline brief reading (cached briefs available without connectivity)

#### Acceptance Criteria (if/when built)
- App builds and runs on iOS 16+ and Android 12+
- Authentication works with same Clerk account as web
- Push notifications delivered within 60s of brief generation
- Brief history available offline (last 20 briefs cached locally)
- Submitted to App Store and Google Play with privacy policy

---
