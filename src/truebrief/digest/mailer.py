"""
Resend Email Client — digest/mailer.py

Wraps the Resend transactional email API to send HTML digest emails.
Reads RESEND_API_KEY and DIGEST_FROM_EMAIL from environment variables.

Returns True on success, False on any error (never raises — callers handle retries).
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
FROM_ADDRESS: str = os.getenv("DIGEST_FROM_EMAIL", "briefs@truebrief.ai")


def send_digest_email(to_email: str, subject: str, html_body: str) -> bool:
    """
    Send a single digest email via Resend.

    Args:
        to_email:  Recipient address.
        subject:   Email subject line.
        html_body: Rendered HTML content.

    Returns:
        True if the email was accepted by Resend, False otherwise.
    """
    if not RESEND_API_KEY:
        logger.warning(
            "RESEND_API_KEY not set — digest email to %s skipped.", to_email
        )
        return False

    try:
        import resend  # imported lazily so missing dep is only an error at call-time

        resend.api_key = RESEND_API_KEY
        resend.Emails.send(
            {
                "from": FROM_ADDRESS,
                "to": [to_email],
                "subject": subject,
                "html": html_body,
            }
        )
        logger.info("Digest email sent to %s", to_email)
        return True

    except Exception as exc:
        logger.error("Failed to send digest email to %s: %s", to_email, exc)
        return False
