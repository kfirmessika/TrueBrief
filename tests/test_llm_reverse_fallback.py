"""
Groq → Gemini reverse fallback (LLMClient.call).

When a groq-provider step (signal_scorer) exhausts its retries, the client
must try Gemini once before raising — a fail-open quality gate floods noise
into the DB (observed 2026-07-07 when Groq's daily token cap died mid-run).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from truebrief.llm.client import LLMClient, LLMError


def _client_with_groq_step():
    c = LLMClient()
    c._config = {"signal_scorer": {"provider": "groq", "model": "llama-3.3-70b-versatile"}}
    c.MAX_RETRIES = 1  # keep the test fast — one failure triggers the fallback path
    return c


def test_groq_failure_falls_back_to_gemini():
    c = _client_with_groq_step()
    with patch.object(c, "_call_groq_instrumented", side_effect=RuntimeError("429 rate limit")), \
         patch.object(c, "_call_gemini_instrumented", return_value=('[{"id":1}]', 10, 5)) as gem, \
         patch.object(c, "_log_call"), \
         patch.object(c, "_flag_quota") as flag:
        out = c.call(step_name="signal_scorer", prompt="p", json_mode=True)
    assert out == '[{"id":1}]'
    assert gem.called
    assert gem.call_args[0][0] == "gemini-3.1-flash-lite"
    # Groq exhausted its retries -- worth an immediate yellow even though Gemini rescued it.
    flag.assert_called_once()
    args, kwargs = flag.call_args
    assert args[0] == "yellow"
    assert kwargs.get("provider") == "groq"


def test_both_dead_still_raises():
    c = _client_with_groq_step()
    with patch.object(c, "_call_groq_instrumented", side_effect=RuntimeError("429")), \
         patch.object(c, "_call_gemini_instrumented", side_effect=RuntimeError("also dead")), \
         patch.object(c, "_log_call"), \
         patch.object(c, "_flag_quota") as flag, \
         patch("time.sleep"):
        with pytest.raises(LLMError):
            c.call(step_name="signal_scorer", prompt="p", json_mode=True)
    seen = [(call.args[0], call.kwargs.get("provider")) for call in flag.call_args_list]
    assert ("yellow", "groq") in seen   # Groq exhausted retries, tried Gemini
    assert ("red", "gemini") in seen    # Gemini reverse-fallback also failed -- nothing left


def test_no_gemini_key_no_fallback_attempt():
    c = _client_with_groq_step()
    c._settings = type("S", (), {"GOOGLE_API_KEY": "", "GROQ_API_KEY": "x"})()
    with patch.object(c, "_call_groq_instrumented", side_effect=RuntimeError("429")), \
         patch.object(c, "_call_gemini_instrumented") as gem, \
         patch.object(c, "_log_call"), \
         patch("time.sleep"):
        with pytest.raises(LLMError):
            c.call(step_name="signal_scorer", prompt="p", json_mode=True)
    assert not gem.called
