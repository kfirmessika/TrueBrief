"""
Email Renderer — digest/renderer.py

Renders the Jinja2 HTML digest template.

Usage:
    from truebrief.digest.renderer import render_digest
    html = render_digest(user_name="Alice", briefs=[...])
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_digest(
    user_name: str,
    date_label: str,
    total: int,
    topics: list[dict],
) -> str:
    """
    Render the §13 fact-delta digest email ("two envelopes, one feed").

    Args:
        user_name:  Display name for the greeting line.
        date_label: Dated header ceremony, e.g. "Tue Jun 16".
        total:      Total new facts across all topics since the last digest.
        topics:     List of topic dicts, each:
                      { "topic_name": str,
                        "facts": [ {text, source_domain, age_label, event_class}, ... ] }

    Returns:
        Rendered HTML string.
    """
    template = _env.get_template("digest.html")
    return template.render(
        user_name=user_name,
        date_label=date_label,
        total=total,
        topics=topics,
    )
