"""
Database Connection - ledger/database.py

Supabase client initialization.
"""

from __future__ import annotations

import logging
from supabase import create_client, Client
from config.settings import settings

logger = logging.getLogger(__name__)

_supabase_client: Client | None = None

def get_supabase() -> Client:
    """Get or create the Supabase client."""
    global _supabase_client
    if _supabase_client is None:
        url: str = settings.SUPABASE_URL
        key: str = settings.SUPABASE_KEY
        
        if not url or not key:
            logger.error("Missing Supabase credentials in settings.")
            raise ValueError(
                "Supabase credentials not configured. "
                "Ensure SUPABASE_URL and SUPABASE_KEY are in .env"
            )
            
        _supabase_client = create_client(url, key)
        logger.info("Supabase client initialized successfully.")
        
    return _supabase_client
