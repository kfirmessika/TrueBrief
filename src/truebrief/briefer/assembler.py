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
_CLASS_WEIGHT = {
    "state_change": 1.0,
    "escalation":   0.8,
    "development":  0.6,
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
    return base * (0.6 + 0.4 * recency) + verified


def _render_bullet(d: AlphaDecision) -> str:
    """One fact → one bullet, clean fact text + source chip + corroboration count."""
    a = d.alpha
    # For UPDATEs, lead with the delta (what changed) when the arbiter provided one.
    text = (d.delta or a.alpha_text or "").strip()
    if text and not text.endswith((".", "!", "?")):
        text += "."
    n = max(int(a.verified_count or 0), 1)
    count = f" ({n} sources)" if n > 1 else ""
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
    active = [d for d in decisions if d.decision in (DecisionType.NEW, DecisionType.UPDATE)]
    if not active:
        return ""

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    new = sorted([d for d in active if d.decision == DecisionType.NEW],
                 key=lambda d: _salience(d, now), reverse=True)
    updates = sorted([d for d in active if d.decision == DecisionType.UPDATE],
                     key=lambda d: _salience(d, now), reverse=True)

    today = datetime.now().strftime("%B %d, %Y")
    out: List[str] = [f"📋 TrueBrief | {topic_name} | {today}", ""]

    # Grounded bottom line — state-of-play situation, else the top new fact, verbatim.
    lead_pool = new or updates
    bottom = (situation or "").strip() or (lead_pool[0].alpha.alpha_text.strip() if lead_pool else "")
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
