"""
Unified per-stage provider/model switch (config/settings.py PROVIDER_REGISTRY +
LLM_CONFIG, llm/client.py named stage methods).

Covers:
  1. PROVIDER_REGISTRY resolves each provider's API key from the right settings field
  2. ENV=development → GOOGLE_API_KEY_DEV override (gemini, primary slot only)
  3. _require_capability blocks a stage pointed at an incapable provider
  4. collector_search dispatches to the right grounding adapter per LLM_CONFIG
  5. json_object guard injects the "json" token only when the prompt lacks it
  6. embedding dimension guard fails loudly on a wrong-width vector
  7. every V5 stage has an LLM_CONFIG entry whose provider is a real registry entry
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from truebrief.llm.client import EMBED_DIM, GroundedResult, LLMClient, LLMError, _search_window


def _client(config: dict, **settings_kw) -> LLMClient:
    s = SimpleNamespace(
        GOOGLE_API_KEY="g_primary", GOOGLE_API_KEY_BACKUP="g_backup",
        GOOGLE_API_KEY_DEV="", GROQ_API_KEY="gsk", OPENAI_API_KEY="",
        LINKUP_API_KEY="lk", BRAVE_API_KEY="brv", ENV="production",
        EMBED_PROVIDER="gemini", TRACE_PIPELINE=False,
    )
    for k, v in settings_kw.items():
        setattr(s, k, v)
    c = LLMClient.__new__(LLMClient)
    c._config = config
    c._settings = s
    c._gemini_client = c._gemini_client_backup = c._openai_client = c._groq_client = None
    return c


# ── 1 + 2. key resolution ──────────────────────────────────────────────────────

def test_resolve_api_key_per_provider():
    c = _client({})
    assert c._resolve_api_key("gemini") == "g_primary"
    assert c._resolve_api_key("gemini", want_backup=True) == "g_backup"
    assert c._resolve_api_key("groq") == "gsk"
    assert c._resolve_api_key("linkup") == "lk"
    assert c._resolve_api_key("brave") == "brv"
    assert c._resolve_api_key("local") == ""          # no key needed
    assert c._resolve_api_key("openai") == ""          # not configured


def test_dev_key_override_only_in_development_and_only_primary():
    c = _client({}, ENV="development", GOOGLE_API_KEY_DEV="g_dev")
    assert c._resolve_api_key("gemini") == "g_dev"                    # primary → dev
    assert c._resolve_api_key("gemini", want_backup=True) == "g_backup"  # backup unchanged
    c_prod = _client({}, ENV="production", GOOGLE_API_KEY_DEV="g_dev")
    assert c_prod._resolve_api_key("gemini") == "g_primary"          # ignored in prod


# ── 3. capability guard ────────────────────────────────────────────────────────

@pytest.mark.parametrize("step,provider,cap", [
    ("gemini_search", "groq", "grounding"),    # groq can't ground
    ("gemini_search", "openai", "grounding"),
    ("arbiter", "linkup", "llm"),               # linkup can't do text
    ("briefer", "brave", "llm"),
    ("embedding", "groq", "embed"),             # groq has no embeddings
])
def test_require_capability_blocks_incapable_provider(step, provider, cap):
    c = _client({step: {"provider": provider, "model": "x"}})
    with pytest.raises(LLMError, match="capability"):
        c._require_capability(step, cap)


@pytest.mark.parametrize("step,provider,cap", [
    ("gemini_search", "gemini", "grounding"),
    ("gemini_search", "linkup", "grounding"),
    ("gemini_search", "brave", "grounding"),
    ("arbiter", "gemini", "llm"),
    ("arbiter", "groq", "llm"),
    ("embedding", "gemini", "embed"),
    ("embedding", "local", "embed"),
    ("embedding", "openai", "embed"),
])
def test_require_capability_allows_capable_provider(step, provider, cap):
    c = _client({step: {"provider": provider, "model": "x"}})
    assert c._require_capability(step, cap) == provider


# ── 4. collector_search dispatch ───────────────────────────────────────────────

@pytest.mark.parametrize("provider,adapter", [
    ("gemini", "call_gemini_with_grounding"),
    ("linkup", "_grounded_linkup"),
    ("brave", "_grounded_brave"),
])
def test_collector_search_dispatches_per_config(provider, adapter):
    c = _client({"gemini_search": {"provider": provider, "model": "gemini-3.5-flash-lite"}})
    sentinel = GroundedResult(text="ok", chunks=[], supports=[])
    with patch.object(LLMClient, adapter, return_value=sentinel) as m:
        out = c.collector_search("Iran War", last_run_str="2026-08-25", today_str="2026-08-31")
    assert out is sentinel
    assert m.called


def test_collector_search_rejects_non_grounding_provider():
    c = _client({"gemini_search": {"provider": "groq", "model": "llama-3.3-70b-versatile"}})
    with pytest.raises(LLMError, match="capability"):
        c.collector_search("Iran War")


# ── 5. json_object token guard ────────────────────────────────────────────────

def test_json_object_guard_injects_only_when_missing():
    msgs = [{"role": "user", "content": "summarize this"}]
    LLMClient._json_object_messages(msgs, None, "summarize this")
    assert "JSON object only" in msgs[-1]["content"]

    msgs2 = [{"role": "user", "content": "return json here"}]
    LLMClient._json_object_messages(msgs2, None, "return json here")
    assert msgs2[-1]["content"] == "return json here"          # untouched

    msgs3 = [{"role": "user", "content": "do it"}]
    LLMClient._json_object_messages(msgs3, "Output ONLY valid JSON.", "do it")
    assert msgs3[-1]["content"] == "do it"                      # system carries the token


# ── 6. embedding dimension guard ─────────────────────────────────────────────

def test_check_embed_dim():
    LLMClient._check_embed_dim([0.0] * EMBED_DIM, "gemini")     # ok, no raise
    with pytest.raises(LLMError, match=str(EMBED_DIM)):
        LLMClient._check_embed_dim([0.0] * 1536, "openai")


def test_openai_embed_dispatch():
    c = _client({"embedding": {"provider": "openai", "model": "text-embedding-3-small"}}, EMBED_PROVIDER="openai")
    dummy_vec = [0.1] * EMBED_DIM
    with patch.object(LLMClient, "_embed_openai", return_value=dummy_vec) as m:
        vec = c.embed("test text")
        assert len(vec) == EMBED_DIM
        assert m.called


def test_openai_embed_batch_dispatch():
    c = _client({"embedding": {"provider": "openai", "model": "text-embedding-3-small"}}, EMBED_PROVIDER="openai")
    dummy_vecs = [[0.1] * EMBED_DIM, [0.2] * EMBED_DIM]
    with patch.object(LLMClient, "_embed_batch_openai", return_value=dummy_vecs) as m:
        vecs = c.embed_batch(["text1", "text2"])
        assert len(vecs) == 2
        assert len(vecs[0]) == EMBED_DIM
        assert m.called


# ── 8. search window (Linkup/Brave same-day 400 guard) ──────────────────────

def test_search_window_never_zero_width():
    # same-day rescan (last_run == today) is the case that 400'd Linkup in prod
    frm, to = _search_window("2026-08-31", "2026-08-31")
    assert frm < to, f"{frm} not before {to}"
    assert to == "2026-08-31"
    assert frm == "2026-08-30"


def test_search_window_normal_and_firstrun():
    assert _search_window("2026-08-24", "2026-08-31") == ("2026-08-24", "2026-08-31")
    frm, to = _search_window("", "2026-08-31")            # first-ever run
    assert to == "2026-08-31" and frm == "2026-08-24"
    frm, to = _search_window("garbage", "also-bad")       # unparseable → safe default
    assert frm < to


def test_collector_search_falls_back_when_configured_provider_errors(monkeypatch):
    c = _client({"gemini_search": {"provider": "linkup", "model": "x"}}, LINKUP_API_KEY="lk", BRAVE_API_KEY="brv")
    good = GroundedResult(text="from brave " * 30, chunks=[], supports=[])
    with patch.object(LLMClient, "_grounded_linkup", side_effect=LLMError("Linkup 400")), \
         patch.object(LLMClient, "_grounded_brave", return_value=good) as brave:
        out = c.collector_search("Iran War", last_run_str="2026-08-31", today_str="2026-08-31")
    assert out is good
    assert brave.called


def test_collector_search_no_news_falls_through_then_returns_cleanly():
    """A provider answering 'nothing happened' should let the next provider try;
    if EVERY provider says nothing, return that (pipeline → no_update), don't raise."""
    from truebrief.llm.client import _looks_like_no_news
    assert _looks_like_no_news("No newsworthy developments were reported in this window.")
    assert not _looks_like_no_news("The US struck Iran. " * 40)  # long real answer

    c = _client({"gemini_search": {"provider": "linkup", "model": "x"}}, LINKUP_API_KEY="lk", BRAVE_API_KEY="brv")
    quiet = GroundedResult(text="No newsworthy developments about this topic were reported.", chunks=[], supports=[])
    real = GroundedResult(text="Something real happened on 2026-08-31. " * 20, chunks=[], supports=[])

    # linkup quiet -> brave real -> return brave
    with patch.object(LLMClient, "_grounded_linkup", return_value=quiet), \
         patch.object(LLMClient, "_grounded_brave", return_value=real):
        out = c.collector_search("T", last_run_str="2026-08-30", today_str="2026-08-31")
    assert out is real

    # linkup quiet -> brave quiet -> gemini errors -> return the quiet result, no raise
    with patch.object(LLMClient, "_grounded_linkup", return_value=quiet), \
         patch.object(LLMClient, "_grounded_brave", return_value=quiet), \
         patch.object(LLMClient, "call_gemini_with_grounding", side_effect=LLMError("quota")):
        out = c.collector_search("T", last_run_str="2026-08-30", today_str="2026-08-31")
    assert _looks_like_no_news(out.text)


def test_brave_query_is_short_keywords_not_the_long_question():
    from truebrief.llm.prompts import build_search_query
    long_topic = "Confirmed player transfers, injury reports, and official squad changes in top football leagues"
    kw = build_search_query(long_topic, "2026-09-01 09:14 UTC", "2026-09-01 21:00 UTC", style="keywords")
    q = build_search_query(long_topic, "2026-09-01 09:14 UTC", "2026-09-01 21:00 UTC", style="question")
    assert len(kw) < 300 and kw.endswith("news")           # Brave q param is length-limited
    assert "since 2026-09-01 09:14 UTC" in q                # Linkup gets the precise lower bound
    assert "present moment" in q                            # upper bound left open on purpose


# ── 9. config completeness ───────────────────────────────────────────────────

def test_every_v5_stage_has_a_registry_backed_config_entry():
    from config.settings import LLM_CONFIG, PROVIDER_REGISTRY
    for step in ("gemini_search", "gemini_extract", "arbiter", "briefer", "embedding"):
        assert step in LLM_CONFIG, f"{step} missing from LLM_CONFIG"
        provider = LLM_CONFIG[step]["provider"]
        assert provider in PROVIDER_REGISTRY, f"{step} → unknown provider {provider!r}"
