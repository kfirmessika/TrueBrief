import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    TAVILY_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""

    class Config:
        env_file = ".env"

settings = Settings()

# LLM Configuration
LLM_CONFIG = {
    "query_builder": {"provider": "gemini", "model": "gemini-2.5-flash"},
    "harvester":     {"provider": "gemini", "model": "gemini-2.5-flash"},
    "arbiter":       {"provider": "gemini", "model": "gemini-2.5-flash"},
    "briefer":       {"provider": "gemini", "model": "gemini-2.5-flash"},
    "garbage_filter": {"provider": "gemini", "model": "gemini-2.5-flash"},
}
