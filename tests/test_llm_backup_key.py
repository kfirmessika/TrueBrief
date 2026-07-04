"""
Tests for LLM client backup-key fallback (GOOGLE_API_KEY_BACKUP).

Scenario coverage:
  1. Primary key returns 429  → backup key is tried → succeeds → returns result
  2. Primary key returns 429  → no backup key configured → normal retry / LLMError
  3. Both keys return 429     → LLMError with clear "both exhausted" message
  4. Primary returns 429      → backup fails with non-quota error → LLMError
  5. _is_quota_exhausted()    → detects both 429 and RESOURCE_EXHAUSTED strings
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure src is importable
sys.path.insert(0, "src")
sys.path.insert(0, ".")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(primary_key: str = "pk_test", backup_key: str = "") -> "LLMClient":
    """Build an LLMClient with mocked settings and LLM_CONFIG."""
    from truebrief.llm.client import LLMClient

    settings = MagicMock()
    settings.GOOGLE_API_KEY = primary_key
    settings.GOOGLE_API_KEY_BACKUP = backup_key
    settings.TRACE_PIPELINE = False

    config = {"test_step": {"provider": "gemini", "model": "gemini-3.1-flash-lite"}}

    client = LLMClient.__new__(LLMClient)
    client._config = config
    client._settings = settings
    client._gemini_client = None
    client._gemini_client_backup = None
    client._openai_client = None
    client._local_embedder = None
    return client


def _quota_error():
    return Exception("429 RESOURCE_EXHAUSTED: GenerateRequestsPerDayPerProjectPerModel-FreeTier")


def _other_error():
    return Exception("503 Service Unavailable")


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestIsQuotaExhausted:
    def test_detects_429(self):
        from truebrief.llm.client import LLMClient
        assert LLMClient._is_quota_exhausted(Exception("429 error")) is True

    def test_detects_resource_exhausted(self):
        from truebrief.llm.client import LLMClient
        assert LLMClient._is_quota_exhausted(Exception("RESOURCE_EXHAUSTED quota")) is True

    def test_ignores_other_errors(self):
        from truebrief.llm.client import LLMClient
        assert LLMClient._is_quota_exhausted(Exception("503 Internal")) is False

    def test_ignores_empty_exception(self):
        from truebrief.llm.client import LLMClient
        assert LLMClient._is_quota_exhausted(Exception("")) is False


class TestBackupKeyFallback:
    def test_backup_used_on_primary_quota_exhaustion(self):
        """Primary 429 → backup succeeds → result returned."""
        client = _make_client(primary_key="pk", backup_key="bk")

        primary_gemini = MagicMock()
        backup_gemini = MagicMock()
        client._gemini_client = primary_gemini
        client._gemini_client_backup = backup_gemini

        call_count = {"primary": 0, "backup": 0}

        def instrumented_side_effect(model, prompt, json_mode, system_prompt, client=None):
            if client is backup_gemini:
                call_count["backup"] += 1
                return ("backup result", 10, 5)
            call_count["primary"] += 1
            raise _quota_error()

        with patch.object(
            client.__class__, "_call_gemini_instrumented",
            side_effect=instrumented_side_effect
        ), patch.object(client.__class__, "_log_call"):
            result = client.call("test_step", "hello")

        assert result == "backup result"
        assert call_count["primary"] == 1
        assert call_count["backup"] == 1

    def test_no_backup_key_falls_through_to_retry(self):
        """Primary 429 + no backup → LLMError after MAX_RETRIES."""
        from truebrief.llm.client import LLMError
        client = _make_client(primary_key="pk", backup_key="")
        client._gemini_client = MagicMock()

        with patch.object(
            client.__class__, "_call_gemini_instrumented",
            side_effect=_quota_error()
        ), patch.object(client.__class__, "_log_call"), patch("time.sleep"):
            with pytest.raises(LLMError, match="Failed after"):
                client.call("test_step", "hello")

    def test_both_keys_exhausted_raises_clear_error(self):
        """Primary 429 + backup 429 → LLMError with 'both…quota-exhausted'."""
        from truebrief.llm.client import LLMError
        client = _make_client(primary_key="pk", backup_key="bk")

        primary_gemini = MagicMock()
        backup_gemini = MagicMock()
        client._gemini_client = primary_gemini
        client._gemini_client_backup = backup_gemini

        def always_quota(model, prompt, json_mode, system_prompt, client=None):
            raise _quota_error()

        with patch.object(
            client.__class__, "_call_gemini_instrumented",
            side_effect=always_quota
        ), patch.object(client.__class__, "_log_call"):
            with pytest.raises(LLMError, match="Both Gemini API keys are quota-exhausted"):
                client.call("test_step", "hello")

    def test_backup_non_quota_error_falls_through_to_retry(self):
        """Primary 429 + backup 503 → LLMError after retries (not 'both exhausted')."""
        from truebrief.llm.client import LLMError
        client = _make_client(primary_key="pk", backup_key="bk")

        primary_gemini = MagicMock()
        backup_gemini = MagicMock()
        client._gemini_client = primary_gemini
        client._gemini_client_backup = backup_gemini

        def side_effect(model, prompt, json_mode, system_prompt, client=None):
            if client is backup_gemini:
                raise _other_error()
            raise _quota_error()

        with patch.object(
            client.__class__, "_call_gemini_instrumented",
            side_effect=side_effect
        ), patch.object(client.__class__, "_log_call"), patch("time.sleep"):
            with pytest.raises(LLMError) as exc_info:
                client.call("test_step", "hello")
        # Should NOT say "Both … quota-exhausted" — it's a different error
        assert "both" not in str(exc_info.value).lower() or "quota" not in str(exc_info.value).lower()

    def test_get_gemini_client_backup_returns_none_when_key_missing(self):
        client = _make_client(primary_key="pk", backup_key="")
        assert client._get_gemini_client_backup() is None

    def test_get_gemini_client_backup_caches_client(self):
        client = _make_client(primary_key="pk", backup_key="bk")
        mock_genai_client = MagicMock()
        with patch("google.genai.Client", return_value=mock_genai_client) as MockClient:
            first = client._get_gemini_client_backup()
            second = client._get_gemini_client_backup()
        assert first is second
        assert MockClient.call_count == 1
