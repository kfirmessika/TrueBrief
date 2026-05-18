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


def render_digest(user_name: str, briefs: list[dict]) -> str:
    """
    Render the digest HTML email.

    Args:
        user_name: Display name for the greeting line.
        briefs:    List of brief dicts, each with keys:
                     topic_name, brief_id, summary_preview, delivered_at

    Returns:
        Rendered HTML string.
    """
    template = _env.get_template("digest.html")
    return template.render(user_name=user_name, briefs=briefs)
