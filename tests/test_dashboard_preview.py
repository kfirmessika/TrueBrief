"""Unit tests for the dashboard brief-preview extraction (_brief_preview).

Guards the dashboard card against showing raw markdown — dividers (━━━),
section badges (🆕 NEW STORIES (3)), and section titles — instead of a real
story sentence.
"""

from truebrief.api.routes import _brief_preview


NEW_BRIEF = """📋 TrueBrief | iran war | June 18, 2026
🆕 NEW STORIES (1)
━━━━━━━━━━━━
**Public Disengagement from International Conflict Coverage**
• The Reuters Institute reports that prolonged international conflict coverage is fueling public cynicism as of June 2026. → Sources: [reuters.com](https://reuters.com/x)"""


def test_prefers_first_bullet_over_section_title():
    out = _brief_preview(NEW_BRIEF)
    assert out.startswith("The Reuters Institute reports")
    assert "→" not in out and "Sources" not in out  # attribution stripped
    assert "━" not in out and "*" not in out         # divider + emphasis stripped


def test_strips_sources_attribution():
    brief = "• A 25% tariff was announced today. → Sources: [a.com](url1), [b.com](url2)"
    assert _brief_preview(brief) == "A 25% tariff was announced today."


def test_skips_divider_and_badge_lines():
    brief = "🆕 NEW STORIES (4)\n━━━━━━━━━━━━\n• Real content here that matters."
    assert _brief_preview(brief) == "Real content here that matters."


def test_falls_back_to_prose_when_no_bullets():
    brief = "📋 TrueBrief | t | d\n━━━\n**Just a section title**"
    assert _brief_preview(brief) == "Just a section title"


def test_empty_and_error_inputs():
    assert _brief_preview("") == ""
    assert _brief_preview("Error: scan failed") == "Error: scan failed"


def test_long_line_is_truncated_with_ellipsis():
    long = "• " + ("word " * 100)
    out = _brief_preview(long)
    assert out.endswith("…")
    assert len(out) <= 201
