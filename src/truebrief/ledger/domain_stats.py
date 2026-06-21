"""
Domain Extraction Stats - ledger/domain_stats.py

Tracks per-domain extraction success/fail rates for the dynamic blocklist.

Lifecycle:
  - ArticleExtractor.extract() calls record_extraction() after every attempt.
  - PipelineRunner calls get_blocked_domains() before MMR to skip failing domains.

Block rule: fail_rate > MAX_FAIL_RATE AND total_attempts >= MIN_ATTEMPTS.

Requires migration 016 (domain_extraction_stats table + record_domain_extraction function).
Degrades silently if the table is missing — never blocks the pipeline.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Domain is blocked when > this fraction of extractions fail
MAX_FAIL_RATE: float = 0.75
# Require at least this many attempts before blocking (avoids false positives on new domains)
MIN_ATTEMPTS: int = 5

# Infrastructure/delivery subdomains to strip (same list as source_logger.py)
_STRIP_PREFIXES = ("www.", "feeds.", "feed.", "rss.", "news.", "m.", "amp.")


def _to_domain(url: str) -> str:
    """Canonical domain from a URL, subdomains stripped."""
    try:
        host = urlparse(url).netloc.lower()
        for prefix in _STRIP_PREFIXES:
            if host.startswith(prefix):
                host = host[len(prefix):]
                break
        return host or "unknown"
    except Exception:
        return "unknown"


def record_extraction(url: str, success: bool) -> None:
    """
    Fire-and-forget: atomically increment domain success/fail counter.
    Called by ArticleExtractor after every extract() attempt.
    Never raises — degrades silently if migration 016 not applied.
    """
    domain = _to_domain(url)
    if domain in ("unknown", ""):
        return
    try:
        from truebrief.ledger.database import get_supabase
        db = get_supabase()
        db.rpc("record_domain_extraction", {
            "p_domain": domain,
            "p_success": success,
        }).execute()
    except Exception as exc:
        logger.debug("[DOMAIN_STATS] record failed (non-fatal): %s", exc)


def get_blocked_domains(
    min_attempts: int = MIN_ATTEMPTS,
    max_fail_rate: float = MAX_FAIL_RATE,
) -> set[str]:
    """
    Return domains to skip: high extraction fail rate with enough evidence.
    Empty set on any error so the pipeline degrades gracefully.
    """
    try:
        from truebrief.ledger.database import get_supabase
        db = get_supabase()
        res = (
            db.table("domain_extraction_stats")
            .select("domain, success_count, fail_count")
            .execute()
        )
        blocked: set[str] = set()
        for row in (res.data or []):
            total = row["success_count"] + row["fail_count"]
            if total < min_attempts:
                continue
            if row["fail_count"] / total > max_fail_rate:
                blocked.add(row["domain"])
        if blocked:
            logger.info(
                "[DOMAIN_STATS] %d domain(s) blocked: %s",
                len(blocked),
                sorted(blocked)[:10],
            )
        return blocked
    except Exception as exc:
        logger.debug("[DOMAIN_STATS] get_blocked_domains failed (non-fatal): %s", exc)
        return set()
