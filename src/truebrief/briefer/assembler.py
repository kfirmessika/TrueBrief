"""
Brief Assembler — briefer/assembler.py  (architecture §3/§5/§15 step 4)

The V3 live "brief" is a COMPUTED DIFF assembled from facts + their inline context —
NO LLM. This replaces the LLM Briefer in the live path: it removes the editorial
synthesis layer (the "represents a major shift" / "creating instability" voice that
leaked opinion into briefs) and saves a Gemini call per scan.

Output is the SAME markdown the topic UI already parses (📌 Bottom line, 🆕 NEW STORIES,
📈 UPDATES, "• fact → Sources: [domain](url)") so nothing downstream changes.

The bottom line is GROUNDED, never synthesised:
  - the IC7 state-of-play situation line when available (itself re-derived from facts), else
  - the single most significant new fact, verbatim.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse

from truebrief.models.alpha import AlphaDecision, DecisionType

logger = logging.getLogger(__name__)

# Significance weights — same ordering the runner/history/feed use (IC2).
# "casualty" (an individual death/injury) sits below development so a single death never
# leads over a topic-level state_change (ceasefire, court ruling, leadership change).
_CLASS_WEIGHT = {
    "state_change": 1.0,
    "escalation":   0.8,
    "development":  0.6,
    "casualty":     0.45,
    "incremental":  0.4,
    "routine":      0.2,
    "tally":        0.1,
}
_DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━━━━━"


def _domain(url: Optional[str], fallback: Optional[str] = None) -> str:
    if url:
        try:
            host = urlparse(url).netloc.replace("www.", "")
            if host:
                return host
        except Exception:
            pass
    return (fallback or "source").strip()


def _salience(d: AlphaDecision, now: datetime) -> float:
    """Significance × light recency — orders facts within the brief."""
    a = d.alpha
    base = _CLASS_WEIGHT.get(a.event_class or "", 0.5)
    ev = a.event_date
    if ev is not None:
        if ev.tzinfo is not None:
            ev = ev.replace(tzinfo=None)
        age_days = max((now - ev).days, 0)
    else:
        age_days = 0
    recency = 0.5 ** (age_days / 4.0)              # half-weight per 4 days
    verified = min(int(a.verified_count or 0), 5) / 50.0
    score = base * (0.6 + 0.4 * recency) + verified
    # Single-source facts sort just below otherwise-equal corroborated ones.
    if int(a.verified_count or 0) <= 1:
        score -= 0.03
    return score


def _render_bullet(d: AlphaDecision) -> str:
    """One fact → one bullet: clean fact text + source chip + corroboration marker.

    The count is labelled "reports" (not "sources"): verified_count is the number of
    distinct domains running related coverage, not outlets that confirmed THIS exact
    claim — so we never imply auditable confirmation we can't show.
    """
    a = d.alpha
    # For UPDATEs, lead with the delta (what changed) when the arbiter provided one.
    text = (d.delta or a.alpha_text or "").strip()
    if text and not text.endswith((".", "!", "?")):
        text += "."
    n = max(int(a.verified_count or 0), 1)
    count = f" ({n} reports)" if n > 1 else ""
    dom = _domain(a.source_url, a.source_name)
    src = f"→ Sources: [{dom}]({a.source_url})" if a.source_url else f"→ Sources: {dom}"
    return f"• {text}{count} {src}"


def assemble_brief(
    decisions: List[AlphaDecision],
    topic_name: str,
    situation: Optional[str] = None,
) -> str:
    """
    Build the brief markdown from facts — no LLM. Returns "" when there is nothing new.

    Args:
        decisions: arbiter decisions; only NEW / UPDATE are rendered.
        topic_name: display name for the header.
        situation:  IC7 state-of-play situation line (grounded), used as the bottom line.
    """
    # Defense-in-depth: background/standing-state facts are not "new" developments and must
    # never headline (the harvester already drops them when V3_LAG_GATE is on).
    active = [d for d in decisions
              if d.decision in (DecisionType.NEW, DecisionType.UPDATE)
              and not getattr(d.alpha, "is_background", False)]
    if not active:
        return ""

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    new = sorted([d for d in active if d.decision == DecisionType.NEW],
                 key=lambda d: _salience(d, now), reverse=True)
    updates = sorted([d for d in active if d.decision == DecisionType.UPDATE],
                     key=lambda d: _salience(d, now), reverse=True)

    today = datetime.now().strftime("%B %d, %Y")
    out: List[str] = [f"📋 TrueBrief | {topic_name} | {today}", ""]

    # Grounded bottom line — state-of-play situation, else the single highest-salience
    # development across BOTH pools (a structural UPDATE can outrank every NEW fact), using
    # its delta when an UPDATE wins so the lede shows what changed.
    bottom = (situation or "").strip()
    if not bottom:
        lead = sorted(active, key=lambda d: _salience(d, now), reverse=True)
        if lead:
            top = lead[0]
            bottom = (top.delta or top.alpha.alpha_text or "").strip()
    if bottom:
        if not bottom.endswith((".", "!", "?")):
            bottom += "."
        out += [f"**📌 Bottom line:** {bottom}", ""]

    if new:
        out += [f"🆕 NEW STORIES ({len(new)})", _DIVIDER]
        out += [_render_bullet(d) for d in new]
        out.append("")

    if updates:
        out += [f"📈 UPDATES ({len(updates)})", _DIVIDER]
        out += [_render_bullet(d) for d in updates]

    text = "\n".join(out).strip()
    logger.info(
        "[ASSEMBLER] No-LLM brief: %d new, %d updates, %d chars (bottom from %s).",
        len(new), len(updates), len(text), "state-of-play" if situation else "top-fact",
    )
    return text
