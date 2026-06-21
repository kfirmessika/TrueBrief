"""
State-of-Play storage - ledger/state_of_play_store.py  (IC7)

Reads/writes the topic-level state-of-play block on the `topics` row
(column added in migration 014). Every call degrades to a no-op / None if the
column doesn't exist yet, so the pipeline and API never break pre-migration.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from truebrief.ledger.database import get_supabase

logger = logging.getLogger(__name__)


def save_state_of_play(topic_id: str, block: dict) -> bool:
    """Persist the state-of-play block to topics.state_of_play. Never raises."""
    if not topic_id or not block:
        return False
    try:
        get_supabase().table("topics").update(
            {
                "state_of_play": block,
                "state_of_play_updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", topic_id).execute()
        return True
    except Exception as exc:
        # Most likely the migration 014 column isn't applied yet — degrade silently.
        logger.warning(f"[STATE-OF-PLAY] save skipped (column missing?): {exc}")
        return False


def load_state_of_play(topic_id: str) -> Optional[dict]:
    """Return the stored state-of-play block for a topic, or None. Never raises."""
    if not topic_id:
        return None
    try:
        res = (
            get_supabase()
            .table("topics")
            .select("state_of_play, state_of_play_updated_at")
            .eq("id", topic_id)
            .limit(1)
            .execute()
        )
        if not res.data:
            return None
        row = res.data[0]
        block = row.get("state_of_play")
        if not block:
            return None
        # Surface the freshness stamp to the caller without mutating stored shape.
        if isinstance(block, dict) and row.get("state_of_play_updated_at"):
            block = {**block, "updated_at": row["state_of_play_updated_at"]}
        return block
    except Exception as exc:
        logger.warning(f"[STATE-OF-PLAY] load skipped (column missing?): {exc}")
        return None
