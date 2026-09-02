"""
Tier definitions for Free / Pro / Power subscription plans.

Source-of-truth for plan limits. Blueprint-reconciled in Step 3.5.
"""

from enum import Enum
from dataclasses import dataclass, field


class Tier(str, Enum):
    FREE = "free"
    PRO = "pro"
    POWER = "power"


@dataclass
class TierLimits:
    max_topics: int          # -1 = unlimited
    min_interval_hours: float  # minimum hours between scans; 0 = unlimited
    sources: list[str] = field(default_factory=list)
    private_topics: bool = False
    api_calls_per_day: int = 0  # developer API quota; 0 = no API access, -1 = unlimited
    max_scans_per_day: int = -1  # user-initiated pipeline scans / 24h (UTC day); -1 = unlimited


# ---------------------------------------------------------------------------
# Canonical limits (reconciled with phase_3.md blueprint § Step 3.5)
# ---------------------------------------------------------------------------
TIER_LIMITS: dict[Tier, TierLimits] = {
    Tier.FREE: TierLimits(
        max_topics=2,
        min_interval_hours=24.0,
        sources=["rss", "tavily"],
        private_topics=False,
        api_calls_per_day=0,     # no developer API on free
        max_scans_per_day=25,    # kills the create→scan→delete→recreate spend loop
    ),
    Tier.PRO: TierLimits(
        max_topics=15,
        min_interval_hours=1.0,
        sources=["rss", "tavily", "google_news", "brave", "exa"],
        private_topics=True,
        api_calls_per_day=500,
        max_scans_per_day=200,
    ),
    Tier.POWER: TierLimits(
        max_topics=-1,          # unlimited
        min_interval_hours=0.25,
        sources=["__all__"],    # pipeline interprets as: enable everything
        private_topics=True,
        api_calls_per_day=5000,
        max_scans_per_day=-1,   # unlimited (still subject to the global spend breaker)
    ),
}
