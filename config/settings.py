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
    GOOGLE_API_KEY: str = ""

    # --- Collector ---
    TAVILY_API_KEY: str = ""
    BRAVE_API_KEY: str = ""
    EXA_API_KEY: str = ""

    # --- Database (Supabase) ---
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""          # anon/service role key

    # --- Paddle ---
    PADDLE_API_KEY: str = ""
    PADDLE_WEBHOOK_SECRET: str = ""
    PADDLE_PRICE_PRO: str = ""      # Price ID from Paddle dashboard (e.g. pri_xxx)
    PADDLE_PRICE_POWER: str = ""    # Price ID from Paddle dashboard

    # --- Clerk ---
    CLERK_PUBLISHABLE_KEY: str = ""
    CLERK_SECRET_KEY: str = ""
    CLERK_JWKS_URL: str = ""
    CLERK_ISSUER: str = ""
    CLERK_AUDIENCE: str = ""

    # --- App ---
    LOG_LEVEL: str = "INFO"
    ENV: str = "development"        # "development" | "production"
    FOUNDER_EMAIL: str = ""         # If set, restricts /admin/* endpoints to this email

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


# ---------------------------------------------------------------------------
# LLM Configuration
# ---------------------------------------------------------------------------
# Maps each pipeline step → provider + model.
# To change a single step's model, edit ONE line here.
# To add a new provider, add a new `elif` in llm/client.py.

LLM_CONFIG: dict[str, dict[str, str]] = {
    # Query Builder: Low token usage, simple reasoning.
    "query_builder":  {"provider": "gemini", "model": "gemini-3.1-flash-lite"},

    # Harvester: High token usage (reads full articles), strict JSON output.
    "harvester":      {"provider": "gemini", "model": "gemini-3.1-flash-lite"},

    # Arbiter (Delta/Decision): Low tokens, high reasoning.
    "arbiter":        {"provider": "gemini", "model": "gemini-3.1-flash-lite"},

    # Briefer: Writes the final markdown report. High reasoning needed.
    "briefer":        {"provider": "gemini", "model": "gemini-3.1-flash-lite"},

    # Garbage Filter: Trivial classification, low tokens.
    "garbage_filter": {"provider": "gemini", "model": "gemini-3.1-flash-lite"},

    # Query Rotator: Generates fresh search queries when variants underperform.
    "query_rotator":  {"provider": "gemini", "model": "gemini-3.1-flash-lite"},

    # Story Summarizer: Merges previous summary + new fact → updated summary (Phase 3, Task 3.3).
    "story_summarizer": {"provider": "gemini", "model": "gemini-3.1-flash-lite"},
}


# ---------------------------------------------------------------------------
# RSS Feed Configuration
# ---------------------------------------------------------------------------
# Path to curated RSS feed database (config/rss_feeds.yaml)
RSS_FEEDS_PATH = _PROJECT_ROOT / "config" / "rss_feeds.yaml"


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
