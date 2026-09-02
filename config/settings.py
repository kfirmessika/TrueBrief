"""
Central configuration for TrueBrief v2.

All runtime settings are loaded from the .env file via pydantic-settings.
Change values here or in .env - never hardcode secrets in source.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


# Resolve project root so settings.py can find .env regardless of cwd
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    Environment-based configuration.

    Add new secrets here as fields - they auto-populate from .env.
    """

    # --- LLM ---
    # Primary key — all Gemini calls in production.
    GOOGLE_API_KEY: str = ""
    # Fallback key — different Google account → independent quota.
    # LLMClient auto-retries with this on primary 429.
    GOOGLE_API_KEY_BACKUP: str = ""
    # Dev/testing key — local benchmarks and experiments; keeps prod quota clean.
    # LLMClient uses this instead of GOOGLE_API_KEY when ENV=development and it is set.
    GOOGLE_API_KEY_DEV: str = ""
    # Groq API key — unlocks near-unlimited cheap inference for dashboard_summary/story_stitch.
    # When set, those steps automatically route to Groq (llama-3.1-8b-instant) instead of Gemini.
    GROQ_API_KEY: str = ""
    # OpenAI API key — optional. Any LLM_CONFIG step whose provider is "openai" uses this.
    # Empty by default (no OpenAI usage in production); the provider path is wired and
    # capability-checked but only exercised when a step is explicitly switched to it.
    OPENAI_API_KEY: str = ""
    # Which grounded-search provider the collector uses. Feeds LLM_CONFIG["gemini_search"]
    # (the one dict that shows every stage's provider). One of:
    #   'gemini' / 'gemini_grounding' — Gemini Google-Search grounding (free tier, quota-limited)
    #   'linkup'                      — Linkup sourcedAnswer (paid, no quota; LINKUP_API_KEY)
    #   'brave'                       — Brave web search + summarizer (BRAVE_API_KEY)
    SEARCH_PROVIDER: str = "gemini"
    # Model used when BOTH Gemini keys are quota-exhausted and a call falls back to Groq.
    # 70b class: strong enough for harvester/arbiter-grade work in emergencies.
    GROQ_FALLBACK_MODEL: str = "llama-3.3-70b-versatile"
    # Cheaper fallback for steps that don't need 70b-grade judgment (briefer is markdown
    # synthesis from already-extracted facts, not open-ended reasoning). llm/client.py
    # picks this over GROQ_FALLBACK_MODEL for steps in GROQ_FALLBACK_CHEAP_STEPS.
    # $0.05/$0.08 per 1M vs 70b's $0.59/$0.79 — was previously landing on 70b for every
    # step on quota-exhaustion, including briefer, at ~10x the necessary cost.
    GROQ_FALLBACK_CHEAP_MODEL: str = "llama-3.1-8b-instant"

    # --- Search layer candidates (V5 benchmark) ---
    BRAVE_API_KEY: str = ""    # Search Plan — $5/1k, auth: X-Subscription-Token header
    LINKUP_API_KEY: str = ""   # Standard depth — $0.006/call with sourcedAnswer

    # --- Database (Supabase) ---
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""          # anon/service role key

    # --- Paddle ---
    PADDLE_API_KEY: str = ""
    PADDLE_WEBHOOK_SECRET: str = ""
    PADDLE_PRICE_PRO: str = ""      # Price ID from Paddle dashboard (e.g. pri_xxx)
    PADDLE_PRICE_POWER: str = ""    # Price ID from Paddle dashboard

    # Display prices (USD / month) shown on /pricing and the upgrade buttons. These
    # are DISPLAY ONLY — the amount actually charged is whatever the Paddle price ID
    # above is set to. Keep them in sync with Paddle. 0 = not set → the UI shows no
    # number (avoid shipping a wrong price).
    PRICE_PRO_USD: float = 0.0
    PRICE_POWER_USD: float = 0.0

    # --- Supabase Auth ---
    # Derived from SUPABASE_URL by default (see below); overridable via env var for
    # non-standard setups (e.g. a custom auth domain).
    SUPABASE_JWKS_URL: str = ""
    SUPABASE_ISSUER: str = ""

    # --- App ---
    LOG_LEVEL: str = "INFO"
    ENV: str = "development"        # "development" | "production"
    FOUNDER_EMAIL: str = ""         # If set, restricts /admin/* endpoints to this email

    # --- Spend guardrails (billing/spend_guard.py) ---
    # Global daily ceiling on LLM spend. Once today's llm_call_log total (UTC) crosses
    # this, every non-admin scan trigger returns 503 until 00:00 UTC. 0 disables the
    # breaker entirely. Tune to your real budget — the default is deliberately generous
    # headroom over normal usage, tight enough to stop a runaway loop.
    GLOBAL_DAILY_SPEND_CEILING_USD: float = 25.0

    # Days a past-due subscription keeps its paid tier before it falls back to free.
    # Enforced on read (resolve_effective_tier) — no scheduled job needed. A recovered
    # payment restores the tier via Paddle's subscription.updated webhook.
    PADDLE_PAST_DUE_GRACE_DAYS: int = 3

    # --- Telemetry retention (tasks/retention_task.py, daily) ---
    # llm_call_log keeps its cost/latency columns forever; the heavy prompt/response
    # TEXT is dropped after this many days. pipeline_trace rows are deleted outright.
    TELEMETRY_PAYLOAD_RETENTION_DAYS: int = 14
    PIPELINE_TRACE_RETENTION_DAYS: int = 14

    # --- V3 Feature Flags (all False = V1 behaviour; flip in .env to enable V3 changes) ---
    # 1a.1 — harvester year guard: clamp event_date to [publish_date−1y, today]
    V3_DATE_GUARD: bool = False
    # 1a.2 — relevance gate: drop off-topic facts after harvesting
    V3_RELEVANCE_GATE: bool = False
    # 1a.3 — entity-aware dedup: arbiter uses semantic + temporal + entity/location
    V3_ENTITY_DEDUP: bool = False
    # 1a.4 — pause story graph: skip story_manager.assign + story_summarizer.refresh
    V3_PAUSE_STORY_GRAPH: bool = False
    # 1b.1 — batch judge: send grey-zone facts to LLM in one call instead of one-by-one
    V3_BATCH_JUDGE: bool = False
    # 1b.2b — near-dup / syndication collapse: drop near-identical articles (same story,
    # different URL) via SimHash before extraction, so we don't harvest the same wire story
    # N times. Exact-URL dedup is always on; this catches syndication.
    V3_NEARDUP_COLLAPSE: bool = False
    # IC2 — development-type weighting: harvester emits event_class; runner sorts decisions
    # by event_class_weight before briefer so state_change/escalation lead the brief.
    V3_DEV_CLASS_RANK: bool = True
    # IC1 — running-total / tally collapse: incoming tally fact with entity-overlap to an
    # existing tally → force UPDATE (never NEW), preventing N duplicate casualty-count rows.
    V3_TALLY_COLLAPSE: bool = False
    # Stage 2 arbiter integrity fix (2026-08-16, docs/benchmarks/2026-08-13_stage2-fix-and-remeasure.md):
    # spelled-out-number normalization guard on the raw-cosine auto-merge (Step 2c) and
    # same-day near-identical (Step 3c) fast-paths, plus the same-day entity/subject-overlap
    # guard. Default True (not the section's usual False-until-opt-in) because the plan's own
    # Stage 3 re-measurement validated it live before merge (76.0% strict accuracy, 0.939
    # precision, vs a 56.6%/0.590 baseline) — this exists as a rollback lever for the canary
    # window, not an opt-in trial. Flipping False reverts each guarded gate to its exact
    # pre-Stage-2 check (raw _digit_runs() equality, no entity guard on same-day).
    V3_DIGIT_GUARD: bool = True
    # IC7 — state-of-play: topic-header status block (situation line + agreed/contested/
    # postponed/escalating checklist) generated from stored facts only, regenerated when a
    # state_change fact lands. Needs migration 014 (topics.state_of_play). Degrades to no-op.
    # V4-1: disabled — frontend StateOfPlayBlock removed; generator kept but flag off.
    V3_STATE_OF_PLAY: bool = False
    # IC4 — contradiction flag: when a NEW fact contradicts an existing fact (same actors +
    # overlapping time, incompatible value: Hormuz open/closed, toll 3,912 vs 3,468), flag the
    # pair instead of storing deadpan. Needs migration 015 (known_facts.contradicts_id). No-op fallback.
    V3_CONTRADICTION_FLAG: bool = False
    # IC9 — Jina Reader fallback: when trafilatura / httpx fails to extract text (403, bot wall,
    # paywall), retry via https://r.jina.ai/<url> which renders the page server-side.
    # Free, no API key, recovers most paywalled / bot-walled sources (NYT, WSJ, AP).
    V3_JINA_READER: bool = False
    # IC10 — SOP lede: when True and a stored state-of-play exists for the topic, the runner
    # passes its situation line to the briefer as an anchor for the "📌 Bottom line" synthesis.
    # Prevents the briefer from leading with a subordinate fact. Zero extra LLM calls.
    V3_SOP_LEDE: bool = False
    # IC11 — Domain-based parallel queries: QueryBuilder generates 3-4 topic-specific domains
    # (e.g. military_operations, diplomacy, humanitarian) each with 2 search queries.
    # At scan time, one query per domain fires in parallel → diverse retrieval at query stage.
    # Requires QueryBuilder to have run at least once with the new domain-aware prompt.
    V3_DOMAIN_QUERIES: bool = False
    # IC12 — Dynamic domain blocklist: ArticleExtractor tracks per-domain extraction
    # success/fail rates in `domain_extraction_stats`. Domains with >75% fail rate and
    # ≥5 attempts are skipped during collection. Requires migration 016.
    V3_DYNAMIC_BLOCKLIST: bool = False
    # IC13 — Per-(topic × tool) UCB1 AYR matrix: after 3 cold-start scans, runner uses
    # UCB1 bandit to decide which paid tools (Tavily, Brave) to call per scan.
    # Free tools (RSS, Google News) always fire. Requires migration 017.
    V3_TOOL_UCB1: bool = False
    # IC14 — Targeted follow-up fetch: after the main judging pass, re-query Tavily once
    # per state_change NEW alpha to catch sub-details MMR diversity may have suppressed.
    V3_FOLLOWUP_FETCH: bool = False
    # History doc (architecture §7.2) — after facts land, rebuild the topic's no-LLM
    # "story so far" timeline and store it in history_docs. Requires migration 018.
    V3_HISTORY_DOC: bool = False
    # §8B development-lag gate — drop stale one-time events (development long predates the
    # reporting article) from the harvest so old news never leads "today". Tallies exempt.
    V3_LAG_GATE: bool = False
    # §5/§15 step 4 — assemble the live brief from fact+context with NO LLM briefer
    # (kills editorial synthesis + saves a Gemini call/scan). The briefer becomes optional.
    V3_NO_LLM_BRIEF: bool = False

    # --- V4 Feature Flags ---
    # V4-4: when True, add_fact() spawns a background thread that generates and caches
    # stitch sentences for each adjacent fact pair in fact_stitches. The story endpoint
    # then serves cached stitches (cache hit) and falls back to on-demand LLM (cache miss).
    # Requires migration 023 (fact_stitches table). Safe to leave False until that migration runs.
    V4_STORY_STITCHING: bool = False

    # V4-5 Signal Scorer: runs the SignalScorer batch quality gate between the
    # Harvester and the Arbiter. Filters off-topic/REACTION/NOISE facts before
    # dedup/storage. Migrations 024+025 applied to prod 2026-07-06.
    # Default True since 2026-07-07 (user directive) — validated live on 3 topics:
    # isreal 16→5, us 44→12, iran war 36→6, zero junk stored.
    # Replaces the broken 0.50 cosine relevance gate (V3_RELEVANCE_GATE).
    V4_SIGNAL_SCORER: bool = True

    # --- Admin / founder accounts ---
    # Comma-separated emails that bypass tier limits (scan speed, topic cap) entirely.
    # These users are treated as unlimited regardless of their subscription tier.
    ADMIN_EMAILS: str = "kfirmessika@gmail.com"

    # --- Embedding provider ---
    # "gemini"  → gemini-embedding-2 (768 dim, 100 req/min free tier)
    # "local"   → sentence-transformers BAAI/bge-base-en-v1.5 (768 dim, unlimited, CPU)
    # "openai"  → text-embedding-3-small (768 dim via Matryoshka, $0.02/1M tokens)
    # All output 768 dims → pgvector column compatible with no migration.
    EMBED_PROVIDER: str = "gemini"
    # Which sentence-transformers model to use when EMBED_PROVIDER=local.
    LOCAL_EMBED_MODEL: str = "BAAI/bge-base-en-v1.5"
    # Which OpenAI embedding model to use when EMBED_PROVIDER=openai.
    OPENAI_EMBED_MODEL: str = "text-embedding-3-small"

    # --- Pipeline Observability (A.7 admin trace panel) ---
    # When True, every scan records a full per-run trace (pipeline_trace table) AND the
    # actual prompt/response of each LLM call (llm_call_log.prompt/response). Founder-only
    # debugging. Safe to leave on at low volume; flip off to stop storing payloads.
    TRACE_PIPELINE: bool = True
    # Hard cap on any single captured prompt/response/article-text field, in characters.
    # Keeps trace rows bounded even when an article body is huge.
    TRACE_MAX_CHARS: int = 20000

    class Config:
        env_file = str(_PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"            # Don't crash on unknown env vars


# Singleton - import this everywhere
settings = Settings()

# Derive Supabase Auth JWKS/issuer URLs from SUPABASE_URL when not explicitly overridden
# via env var. Keeps deployment config to a single SUPABASE_URL for the common case.
if not settings.SUPABASE_JWKS_URL and settings.SUPABASE_URL:
    settings.SUPABASE_JWKS_URL = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
if not settings.SUPABASE_ISSUER and settings.SUPABASE_URL:
    settings.SUPABASE_ISSUER = f"{settings.SUPABASE_URL}/auth/v1"


# ---------------------------------------------------------------------------
# Provider registry — the ONE place that says, for each provider TrueBrief can
# call: which settings field holds its API key, its endpoint/base_url, and what
# it is capable of. llm/client.py reads this to auto-select the right key when a
# step is switched to a different provider, and to refuse a step that is pointed
# at a provider that cannot serve it (e.g. arbiter → linkup, gemini_search → groq).
#
# capabilities: "llm"       plain/JSON text generation (call(), extract/judge/brief)
#               "embed"     vector embeddings
#               "grounding" grounded web search (collector_search)
#
# To add a provider: one entry here + its key field on Settings above + a branch
# in the matching llm/client.py method. Nothing else in the codebase changes.
# ---------------------------------------------------------------------------
PROVIDER_REGISTRY: dict[str, dict] = {
    "gemini": {
        "key_settings": ["GOOGLE_API_KEY", "GOOGLE_API_KEY_BACKUP"],
        "dev_key_setting": "GOOGLE_API_KEY_DEV",
        "capabilities": {"llm", "embed", "grounding"},
    },
    "groq": {
        "key_settings": ["GROQ_API_KEY"],
        "base_url": "https://api.groq.com/openai/v1",
        "capabilities": {"llm"},
    },
    "openai": {
        "key_settings": ["OPENAI_API_KEY"],
        "capabilities": {"llm", "embed"},
    },
    "linkup": {
        "key_settings": ["LINKUP_API_KEY"],
        "endpoint": "https://api.linkup.so/v1/search",
        "capabilities": {"grounding"},
    },
    "brave": {
        "key_settings": ["BRAVE_API_KEY"],
        "endpoint": "https://api.search.brave.com/res/v1/web/search",
        "capabilities": {"grounding"},
    },
    "local": {
        "key_settings": [],
        "capabilities": {"embed"},
    },
}

_PROVIDER_ALIASES = {"gemini_grounding": "gemini", "google": "gemini", "lookup": "linkup"}


def _norm_provider(name: str) -> str:
    """Map provider aliases (e.g. legacy SEARCH_PROVIDER='gemini_grounding') to a
    canonical PROVIDER_REGISTRY key."""
    n = (name or "").strip().lower()
    return _PROVIDER_ALIASES.get(n, n)


# ---------------------------------------------------------------------------
# LLM Configuration
# ---------------------------------------------------------------------------
# LLM_CONFIG below is the single dict that shows every pipeline stage's
# provider + model. Each V5 stage has ONE control (a constant here, or the
# matching env var that feeds it) — change that one line to switch the stage.
# llm/client.py exposes a named method per stage (collector_search, extract_facts,
# judge_case/judge_batch, write_brief, embed_fact/embed_facts) that reads its
# entry here and resolves the key via PROVIDER_REGISTRY.
# ---------------------------------------------------------------------------
_cheap_provider = "groq" if settings.GROQ_API_KEY else "gemini"
_cheap_model = "llama-3.1-8b-instant" if settings.GROQ_API_KEY else "gemini-3.5-flash-lite"

# V5 active steps — one constant per step, change here (or the env var) to swap.
# gemini_search + embedding take their provider from env (SEARCH_PROVIDER /
# EMBED_PROVIDER) so a benchmark/script can flip them without a code edit; the
# other stages are set directly here.
_COLLECTOR_PROVIDER = _norm_provider(settings.SEARCH_PROVIDER) or "gemini"
_COLLECTOR_MODEL    = "gemini-3.5-flash-lite"   # step: gemini_search — only used by the gemini provider
_EXTRACT_PROVIDER   = "gemini"
_EXTRACT_MODEL      = "gemini-3.5-flash-lite"   # step: gemini_extract (structure facts from prose)
_ARBITER_PROVIDER   = "gemini"
_ARBITER_MODEL      = "gemini-3.5-flash-lite"   # step: arbiter (dedup judge)
_BRIEFER_PROVIDER   = "gemini"
_BRIEFER_MODEL      = "gemini-3.5-flash-lite"   # step: briefer (write final brief)
_EMBED_PROVIDER     = _norm_provider(getattr(settings, "EMBED_PROVIDER", "gemini")) or "gemini"
if _EMBED_PROVIDER == "local":
    _EMBED_MODEL = f"local/{getattr(settings, 'LOCAL_EMBED_MODEL', 'BAAI/bge-base-en-v1.5')}"
elif _EMBED_PROVIDER == "openai":
    _EMBED_MODEL = getattr(settings, "OPENAI_EMBED_MODEL", "text-embedding-3-small")
else:
    _EMBED_MODEL = "models/gemini-embedding-2"

LLM_CONFIG: dict[str, dict[str, str]] = {
    # --- V4 steps (not active in V5 — kept so existing telemetry keys don't break) ---
    "query_builder":    {"provider": "gemini", "model": "gemini-3.5-flash-lite"},
    "harvester":        {"provider": "gemini", "model": "gemini-3.5-flash-lite"},
    "garbage_filter":   {"provider": "gemini", "model": "gemini-3.5-flash-lite"},
    "query_rotator":    {"provider": "gemini", "model": "gemini-3.5-flash-lite"},
    "story_summarizer": {"provider": "gemini", "model": "gemini-3.5-flash-lite"},
    "state_of_play":    {"provider": "gemini", "model": "gemini-3.5-flash-lite"},

    # --- V5 active steps — controlled by the constants above ---
    "arbiter":        {"provider": _ARBITER_PROVIDER,   "model": _ARBITER_MODEL},
    "briefer":        {"provider": _BRIEFER_PROVIDER,   "model": _BRIEFER_MODEL},

    # Embedding stage (arbiter dedup + vector store writes + query-side search).
    # provider from EMBED_PROVIDER env: "gemini" (models/gemini-embedding-2, 768d) or
    # "local" (sentence-transformers, 768d, $0). Output MUST be 768d — the
    # known_facts.alpha_embedding pgvector column width; llm/client.py enforces it.
    "embedding":      {"provider": _EMBED_PROVIDER,     "model": _EMBED_MODEL},

    # Dashboard summary (V4-3): 2-3 sentence executive summary of the most recent facts.
    # Routes to Groq (llama-3.1-8b-instant) when GROQ_API_KEY is set; falls back to Gemini.
    "dashboard_summary": {"provider": _cheap_provider, "model": _cheap_model},

    # Story stitch (V4): one short connective sentence between each adjacent pair of
    # alphas on the topic story view. Same provider/model as dashboard_summary.
    "story_stitch": {"provider": _cheap_provider, "model": _cheap_model},

    # Signal scorer (V4-5): batch quality gate — classify + score each harvested fact.
    # NEEDS the 70b tier: validated 2026-07-07 that llama-3.1-8b applies the topic-fit
    # rule incoherently (kept Kyiv war facts at 8 on an Iran topic while dropping
    # near-identical ones). One call per scan — the 70b cost is negligible.
    "signal_scorer": {
        "provider": "groq" if settings.GROQ_API_KEY else "gemini",
        "model": "llama-3.3-70b-versatile" if settings.GROQ_API_KEY else "gemini-2.0-flash",
    },

    # V5 grounded-search collector (docs/core/architecture_v5.md). provider from
    # SEARCH_PROVIDER env: "gemini" (Google-Search grounding — free tier 5,000
    # queries/month, plain-prose only or grounding_chunks are suppressed), "linkup"
    # (sourcedAnswer, paid, no quota), or "brave" (web search + summarizer). model is
    # only consulted for the gemini provider; linkup/brave are flat-fee HTTP APIs.
    "gemini_search": {"provider": _COLLECTOR_PROVIDER, "model": _COLLECTOR_MODEL},

    # Restructures the grounded prose into the alpha+context JSON contract. Plain (non-grounded)
    # extraction call.
    "gemini_extract": {"provider": _EXTRACT_PROVIDER, "model": _EXTRACT_MODEL},

    # --- Topic Finisher experiment (scripts/topic_finisher_experiment.py) ---
    # Candidate topics.raw_query cleanup step, NOT wired into production yet. Same
    # provider/model as query_builder (low token usage, simple reasoning); split into
    # distinct step names purely so cost telemetry can distinguish the 3 strategies.
    "topic_finisher_combined": {"provider": "gemini", "model": "gemini-3.5-flash-lite"},
    "topic_finisher_name":     {"provider": "gemini", "model": "gemini-3.5-flash-lite"},
    "topic_finisher_search":   {"provider": "gemini", "model": "gemini-3.5-flash-lite"},
    "topic_finisher_corrected": {"provider": "gemini", "model": "gemini-3.5-flash-lite"},
}


# ---------------------------------------------------------------------------
# RSS Feed Configuration
# ---------------------------------------------------------------------------
# Path to curated RSS feed database (config/rss_feeds.yaml)
RSS_FEEDS_PATH = _PROJECT_ROOT / "config" / "rss_feeds.yaml"


# ---------------------------------------------------------------------------
# V5 cutover
# ---------------------------------------------------------------------------
# The Gemini Search collector went live in production on 2026-07-22 (commit 8e5b9ae).
# Everything stored before that came from the V4 collect/harvest/scrape pipeline, which
# is frozen and no longer runs (docs/core/V4_ARCHIVE.md). Verified against real data:
# on the "iran war" topic, all 774 facts up to 2026-07-20 have zero Gemini grounding
# URLs, and every fact from 2026-07-25 on has them — a clean break with no overlap.
#
# User-facing history views filter to this boundary so the UI shows the current
# system's output only. The V4 rows stay in the database untouched; this hides them,
# it does not delete them.
V5_CUTOVER_DATE = "2026-07-22"


# ---------------------------------------------------------------------------
# Arbiter Thresholds
# ---------------------------------------------------------------------------
SIMILARITY_THRESHOLD_DUPLICATE = 0.90   # Phase 1 baseline (still used by tests)
SIMILARITY_THRESHOLD_UPDATE = 0.75      # Bottom of grey zone (send to Judge LLM)
AUTO_MERGE_THRESHOLD = 0.97             # Phase 2: above this = AUTO-DUPLICATE, no LLM
CONFIDENCE_MIN = 0.60                   # Alphas below this confidence are dropped


# ---------------------------------------------------------------------------
# Story Node Configuration (Phase 3)
# ---------------------------------------------------------------------------
STORY_ASSIGNMENT_THRESHOLD = 0.70       # Min similarity to attach a NEW Alpha to existing story
STORY_MATCH_LIMIT = 5                   # Max stories to consider when matching
