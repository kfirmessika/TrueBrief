"""Shared pytest fixtures / cross-test isolation."""
from __future__ import annotations

import itertools

import pytest

# Captured ONCE at collection time, before any test can importlib.reload(config.settings).
# tests/test_llm_groq.py::TestSettingsCheapProvider reloads that module to exercise the
# env-var-driven provider constants; reload swaps the `settings` singleton and LLM_CONFIG
# for fresh objects, while modules that did `from config.settings import settings` keep
# the old ref — which then desyncs monkeypatch.setattr(settings, ...) in later tests
# (test_number_normalizer, test_schedule_endpoints). Restoring the originals by identity
# after every test keeps the suite order-independent.
try:
    import config.settings as _cs

    _ORIG_SETTINGS = _cs.settings
    _ORIG_LLM_CONFIG = _cs.LLM_CONFIG
    _ORIG_PROVIDER_REGISTRY = getattr(_cs, "PROVIDER_REGISTRY", None)
except Exception:  # pragma: no cover
    _cs = None


@pytest.fixture(autouse=True)
def _isolate_global_singletons():
    """Reset process-wide mutable globals before AND after each test."""
    from truebrief.llm.client import LLMClient

    # LLMClient._key_counter decides which Gemini key _pick_gemini_client starts with;
    # tests that assert "primary first, then backup" are order-dependent on it.
    LLMClient._key_counter = itertools.count()

    # Disable the Redis API response cache for every test. The read endpoints
    # (GET /topics/{id}/schedule, /topics, /briefs, ...) cache by a key that does
    # NOT include the caller, so once one test populates `schedule:<TOPIC_ID>` a
    # later test hitting the same id gets a cache hit and skips the subscription
    # 403 check entirely (tests/test_schedule_endpoints.py). Whether it bites
    # depends on whether REDIS_URL happens to be in os.environ by the time the
    # endpoint runs — i.e. on collection order. Force it off so endpoint tests are
    # deterministic. Test-only; production is unaffected.
    try:
        from truebrief.api import cache as _api_cache

        _api_cache._redis_unavailable = True
        _api_cache._redis_client = None
    except Exception:
        pass

    yield

    LLMClient._key_counter = itertools.count()
    if _cs is not None:
        _cs.settings = _ORIG_SETTINGS
        _cs.LLM_CONFIG = _ORIG_LLM_CONFIG
        if _ORIG_PROVIDER_REGISTRY is not None:
            _cs.PROVIDER_REGISTRY = _ORIG_PROVIDER_REGISTRY
