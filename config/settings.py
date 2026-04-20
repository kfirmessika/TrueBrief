"""
Central configuration for TrueBrief v2.

All runtime settings are loaded from the .env file via pydantic-settings.
Change values here or in .env — never hardcode secrets in source.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings


# Resolve project root so settings.py can find .env regardless of cwd
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    Environment-based configuration.

    Add new secrets here as fields — they auto-populate from .env.
    """

    # --- LLM ---
    GOOGLE_API_KEY: str = ""

    # --- Collector ---
    TAVILY_API_KEY: str = ""

    # --- Database (Supabase) ---
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""          # anon/service role key

    # --- App ---
    LOG_LEVEL: str = "INFO"
    ENV: str = "development"        # "development" | "production"

    class Config:
        env_file = str(_PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"            # Don't crash on unknown env vars


# Singleton — import this everywhere
settings = Settings()


# ---------------------------------------------------------------------------
# LLM Configuration
# ---------------------------------------------------------------------------
# Maps each pipeline step → provider + model.
# To change a single step's model, edit ONE line here.
# To add a new provider, add a new `elif` in llm/client.py.

LLM_CONFIG: dict[str, dict[str, str]] = {
    # Simple query generation — Flash is fast, free, sufficient forever
    "query_builder":  {"provider": "gemini", "model": "gemini-2.5-flash"},

    # Fact extraction — most important call. Flash for Phase 1; upgrade to Pro for production
    "harvester":      {"provider": "gemini", "model": "gemini-2.5-flash"},

    # Duplicate/delta detection — structured decision, Flash handles well
    "arbiter":        {"provider": "gemini", "model": "gemini-2.5-flash"},

    # Report formatting — no complex reasoning needed
    "briefer":        {"provider": "gemini", "model": "gemini-2.5-flash"},

    # Garbage input rejection — trivial classification, Flash forever
    "garbage_filter": {"provider": "gemini", "model": "gemini-2.5-flash"},
}


# ---------------------------------------------------------------------------
# RSS Feed Configuration
# ---------------------------------------------------------------------------
# Path to curated RSS feed database (config/rss_feeds.yaml)
RSS_FEEDS_PATH = _PROJECT_ROOT / "config" / "rss_feeds.yaml"


# ---------------------------------------------------------------------------
# Arbiter Thresholds
# ---------------------------------------------------------------------------
SIMILARITY_THRESHOLD_DUPLICATE = 0.90   # Score > this → DUPLICATE (auto-merge)
SIMILARITY_THRESHOLD_UPDATE = 0.75      # Score > this → UPDATE candidate (Phase 2)
CONFIDENCE_MIN = 0.60                   # Alphas below this confidence are dropped
