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
    "query_builder":  {"provider": "gemini", "model": "gemini-3.1-flash-lite-preview"},

    # Harvester: High token usage (reads full articles), strict JSON output.
    "harvester":      {"provider": "gemini", "model": "gemini-3.1-flash-lite-preview"},

    # Arbiter (Delta/Decision): Low tokens, high reasoning.
    "arbiter":        {"provider": "gemini", "model": "gemini-3.1-flash-lite-preview"},

    # Briefer: Writes the final markdown report. High reasoning needed.
    "briefer":        {"provider": "gemini", "model": "gemini-3.1-flash-lite-preview"},

    # Garbage Filter: Trivial classification, low tokens.
    "garbage_filter": {"provider": "gemini", "model": "gemini-3.1-flash-lite-preview"},

    # Query Rotator: Generates fresh search queries when variants underperform.
    "query_rotator":  {"provider": "gemini", "model": "gemini-3.1-flash-lite-preview"},

    # Story Summarizer: Merges previous summary + new fact → updated summary (Phase 3, Task 3.3).
    "story_summarizer": {"provider": "gemini", "model": "gemini-3.1-flash-lite-preview"},
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
