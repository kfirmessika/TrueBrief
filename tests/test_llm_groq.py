"""
Tests for LLM client Groq provider (V4-3).

Scenario coverage:
  1. _get_groq_client() raises LLMError when GROQ_API_KEY is empty
  2. _get_groq_client() returns a cached client on second call
  3. call() with provider="groq" delegates to _call_groq_instrumented
  4. call() with provider="groq" and no key raises LLMError after retries
  5. _call_groq_instrumented passes json_mode as response_format
  6. settings._cheap_provider / _cheap_model resolve correctly based on GROQ_API_KEY
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, ".")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_groq_client(groq_key: str = "gsk_test") -> "LLMClient":
    """Build an LLMClient configured for a groq step."""
    from truebrief.llm.client import LLMClient

    settings = MagicMock()
    settings.GOOGLE_API_KEY = ""
    settings.GOOGLE_API_KEY_BACKUP = ""
    settings.GROQ_API_KEY = groq_key
    settings.TRACE_PIPELINE = False

    config = {"cheap_step": {"provider": "groq", "model": "llama-3.1-8b-instant"}}

    client = LLMClient.__new__(LLMClient)
    client._config = config
    client._settings = settings
    client._gemini_client = None
    client._gemini_client_backup = None
    client._openai_client = None
    client._groq_client = None
    client._local_embedder = None
    return client


def _fake_groq_response(text: str, in_tok: int = 10, out_tok: int = 5):
    """Build a fake OpenAI-style chat completion response."""
    choice = MagicMock()
    choice.message.content = text
    usage = MagicMock()
    usage.prompt_tokens = in_tok
    usage.completion_tokens = out_tok
    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestGetGroqClient:
    def test_raises_when_key_missing(self):
        from truebrief.llm.client import LLMError
        client = _make_groq_client(groq_key="")
        with pytest.raises(LLMError, match="GROQ_API_KEY not set"):
            client._get_groq_client()

    def test_caches_client_on_second_call(self):
        client = _make_groq_client(groq_key="gsk_test")
        mock_openai_instance = MagicMock()
        with patch("openai.OpenAI", return_value=mock_openai_instance) as MockOpenAI:
            first = client._get_groq_client()
            second = client._get_groq_client()
        assert first is second
        assert MockOpenAI.call_count == 1

    def test_uses_groq_base_url(self):
        client = _make_groq_client(groq_key="gsk_test")
        with patch("openai.OpenAI", return_value=MagicMock()) as MockOpenAI:
            client._get_groq_client()
        _, kwargs = MockOpenAI.call_args
        assert kwargs.get("base_url") == "https://api.groq.com/openai/v1"
        assert kwargs.get("api_key") == "gsk_test"


class TestCallGroqInstrumented:
    def test_returns_text_and_token_counts(self):
        client = _make_groq_client()
        fake_response = _fake_groq_response("hello world", in_tok=8, out_tok=3)
        mock_groq = MagicMock()
        mock_groq.chat.completions.create.return_value = fake_response
        client._groq_client = mock_groq

        text, in_tok, out_tok = client._call_groq_instrumented(
            "llama-3.1-8b-instant", "test prompt", False, None
        )
        assert text == "hello world"
        assert in_tok == 8
        assert out_tok == 3

    def test_json_mode_sets_response_format(self):
        client = _make_groq_client()
        fake_response = _fake_groq_response('{"key": "val"}')
        mock_groq = MagicMock()
        mock_groq.chat.completions.create.return_value = fake_response
        client._groq_client = mock_groq

        client._call_groq_instrumented(
            "llama-3.1-8b-instant", "json prompt", True, None
        )
        _, call_kwargs = mock_groq.chat.completions.create.call_args
        assert call_kwargs.get("response_format") == {"type": "json_object"}

    def test_system_prompt_added_as_system_message(self):
        client = _make_groq_client()
        fake_response = _fake_groq_response("answer")
        mock_groq = MagicMock()
        mock_groq.chat.completions.create.return_value = fake_response
        client._groq_client = mock_groq

        client._call_groq_instrumented(
            "llama-3.1-8b-instant", "user msg", False, "you are helpful"
        )
        _, call_kwargs = mock_groq.chat.completions.create.call_args
        messages = call_kwargs.get("messages", [])
        assert messages[0] == {"role": "system", "content": "you are helpful"}
        assert messages[1] == {"role": "user", "content": "user msg"}

    def test_no_system_prompt_sends_only_user_message(self):
        client = _make_groq_client()
        fake_response = _fake_groq_response("answer")
        mock_groq = MagicMock()
        mock_groq.chat.completions.create.return_value = fake_response
        client._groq_client = mock_groq

        client._call_groq_instrumented(
            "llama-3.1-8b-instant", "user only", False, None
        )
        _, call_kwargs = mock_groq.chat.completions.create.call_args
        messages = call_kwargs.get("messages", [])
        assert len(messages) == 1
        assert messages[0]["role"] == "user"


class TestCallDispatchGroq:
    def test_call_delegates_to_groq_instrumented(self):
        client = _make_groq_client(groq_key="gsk_test")

        with patch.object(
            client.__class__,
            "_call_groq_instrumented",
            return_value=("groq output", 5, 2),
        ) as mock_groq_instr, patch.object(client.__class__, "_log_call"):
            result = client.call("cheap_step", "hello")

        assert result == "groq output"
        mock_groq_instr.assert_called_once_with(
            "llama-3.1-8b-instant", "hello", False, None
        )

    def test_call_raises_llm_error_when_no_groq_key(self):
        from truebrief.llm.client import LLMError
        client = _make_groq_client(groq_key="")

        with patch("time.sleep"), patch.object(client.__class__, "_log_call"):
            with pytest.raises(LLMError, match="Failed after"):
                client.call("cheap_step", "hello")


class TestSettingsCheapProvider:
    """Verify that _cheap_provider / _cheap_model resolve correctly."""

    def test_groq_selected_when_key_present(self):
        """When GROQ_API_KEY is non-empty the config dict should use groq."""
        # We import LLM_CONFIG after patching settings to simulate a key being present.
        # The cleanest way: reload config.settings with a monkeypatched env var.
        import importlib
        import os

        old_key = os.environ.get("GROQ_API_KEY", "")
        os.environ["GROQ_API_KEY"] = "gsk_present"
        try:
            import config.settings as cs
            importlib.reload(cs)
            assert cs.LLM_CONFIG["dashboard_summary"]["provider"] == "groq"
            assert cs.LLM_CONFIG["dashboard_summary"]["model"] == "llama-3.1-8b-instant"
            assert cs.LLM_CONFIG["story_stitch"]["provider"] == "groq"
            assert cs.LLM_CONFIG["story_stitch"]["model"] == "llama-3.1-8b-instant"
        finally:
            if old_key:
                os.environ["GROQ_API_KEY"] = old_key
            else:
                os.environ.pop("GROQ_API_KEY", None)
            importlib.reload(cs)  # restore to real env state

    def test_gemini_fallback_when_no_key(self):
        """When GROQ_API_KEY is empty the config dict should use gemini."""
        import importlib
        import os

        old_key = os.environ.get("GROQ_API_KEY", "")
        os.environ["GROQ_API_KEY"] = ""
        try:
            import config.settings as cs
            importlib.reload(cs)
            assert cs.LLM_CONFIG["dashboard_summary"]["provider"] == "gemini"
            assert cs.LLM_CONFIG["story_stitch"]["provider"] == "gemini"
        finally:
            if old_key:
                os.environ["GROQ_API_KEY"] = old_key
            else:
                os.environ.pop("GROQ_API_KEY", None)
            importlib.reload(cs)

    def test_only_cheap_steps_auto_switch(self):
        """query_builder, harvester, arbiter etc. must never switch to groq."""
        import importlib
        import os

        old_key = os.environ.get("GROQ_API_KEY", "")
        os.environ["GROQ_API_KEY"] = "gsk_present"
        try:
            import config.settings as cs
            importlib.reload(cs)
            locked_steps = [
                "query_builder", "harvester", "arbiter",
                "briefer", "garbage_filter", "query_rotator", "story_summarizer",
            ]
            for step in locked_steps:
                assert cs.LLM_CONFIG[step]["provider"] == "gemini", (
                    f"{step} must stay on gemini regardless of GROQ_API_KEY"
                )
        finally:
            if old_key:
                os.environ["GROQ_API_KEY"] = old_key
            else:
                os.environ.pop("GROQ_API_KEY", None)
            importlib.reload(cs)
