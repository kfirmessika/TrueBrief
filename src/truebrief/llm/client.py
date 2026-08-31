"""
LLM Abstraction Layer - llm/client.py

Thin, config-driven wrapper around any LLM provider.
Switch providers by changing LLM_CONFIG in config/settings.py - zero code changes here.
Uses the modern google-genai SDK for Gemini.

Telemetry: every call() invocation logs to llm_call_log via TelemetryLogger.
Set the `pipeline_run_id` context var before calling to associate logs with a run.
"""

from __future__ import annotations

import concurrent.futures
import contextvars
import itertools
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, List, Any

_GEMINI_GENERATE_TIMEOUT = 60   # seconds; 60s covers long-form briefs
_GEMINI_EMBED_TIMEOUT = 30      # seconds; embeddings should be fast

from truebrief.llm.pricing import compute_cost_usd
from truebrief.llm.prompts import (
    GEMINI_EXTRACT_SYSTEM,
    GEMINI_SEARCH_SYSTEM,
    build_gemini_extract_prompt,
    build_gemini_search_prompt,
    build_search_query,
)

logger = logging.getLogger(__name__)

# pgvector column width for known_facts.alpha_embedding — every embedding provider
# MUST return exactly this many dimensions or similarity search silently breaks.
EMBED_DIM = 768


def _search_window(last_run_str: str, today_str: str, default_days: int = 7) -> tuple[str, str]:
    """Return (fromDate, toDate) as YYYY-MM-DD with fromDate STRICTLY before toDate.

    The Linkup API 400s ("fromDate must be before toDate") and Brave's freshness
    range misbehaves when the two dates are equal — which is exactly the
    same-day-rescan case the pipeline hits every run (topics.last_run_at is
    stamped to "now" before the scan, so last_run_str == today_str). Clamp the
    window to at least one day so "today's news" still comes back.
    """
    import datetime as _dt

    try:
        to_d = _dt.date.fromisoformat(today_str) if today_str else _dt.date.today()
    except ValueError:
        to_d = _dt.date.today()
    try:
        from_d = (
            _dt.date.fromisoformat(last_run_str)
            if last_run_str
            else to_d - _dt.timedelta(days=default_days)
        )
    except ValueError:
        from_d = to_d - _dt.timedelta(days=default_days)
    if from_d >= to_d:
        from_d = to_d - _dt.timedelta(days=1)
    return from_d.isoformat(), to_d.isoformat()


_NO_NEWS_MARKERS = (
    "no newsworthy developments",
    "no genuinely new",
    "does not contain",
    "no recent",
    "no new developments",
    "nothing significant happened",
    "no significant developments",
    "no confirmed",
    "no relevant news",
    "there were no",
    "no updates",
)


def _looks_like_no_news(text: str) -> bool:
    """A search provider (esp. Linkup/Brave) answering "nothing happened in this
    window" — short + formulaic. Distinguish from a real short brief by length:
    a genuine multi-fact answer is longer than a one-line "no news" sentence."""
    t = (text or "").strip().lower()
    if len(t) > 400:
        return False
    return any(m in t for m in _NO_NEWS_MARKERS)


@dataclass
class GroundedResult:
    """Result of a Gemini Search-grounded call. See LLMClient.call_gemini_with_grounding.

    chunks: real, verified sources (chunks[i].web.uri / .title) — the ONLY place a source_url
        should ever come from. supports: maps text spans in `text` to which chunk(s) back them
        (segment.start_index/end_index are exact Python string offsets into `text`).
    """
    text: str
    chunks: list = field(default_factory=list)
    supports: list = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0

# Context variable: set this in pipeline_task before calling the LLM so every
# call in that task automatically logs against the correct pipeline_run row.
pipeline_run_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "pipeline_run_id", default=None
)

# Steps that fall back to GROQ_FALLBACK_CHEAP_MODEL (llama-3.1-8b-instant) instead of
# GROQ_FALLBACK_MODEL (llama-3.3-70b-versatile) on quota exhaustion. briefer writes
# markdown from already-extracted facts — no open-ended judgment required.
_GROQ_FALLBACK_CHEAP_STEPS: frozenset[str] = frozenset({"briefer"})


class LLMError(Exception):
    """Raised when an LLM call fails after all retries."""


class LLMClient:
    """
    Call any LLM via config. Switch providers by changing settings.py.

    Supported providers:
      - "gemini"  → google-genai (modern SDK)
      - "openai"  → openai SDK (OpenAI endpoints)
      - "groq"    → openai SDK pointed at https://api.groq.com/openai/v1 (OpenAI-compatible)
    """

    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 5.0

    # Round-robin counter shared across all instances so calls alternate between
    # primary and backup Gemini keys from the first request, not only on failure.
    _key_counter: itertools.count = itertools.count()
    _key_lock: threading.Lock = threading.Lock()

    # Process-level LocalEmbedder singleton — loading the 420MB model takes ~1s;
    # sharing it across all LLMClient instances means it loads once per process, not
    # once per request (which was previously causing 1-2s delay on every embed call).
    _shared_local_embedder: Optional[Any] = None
    _shared_local_embedder_lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        from config.settings import LLM_CONFIG, settings
        self._config = LLM_CONFIG
        self._settings = settings
        self._gemini_client: Optional[Any] = None
        self._gemini_client_backup: Optional[Any] = None
        self._openai_client: Optional[Any] = None
        self._groq_client: Optional[Any] = None

    def _get_local_embedder(self):
        """Return the process-level LocalEmbedder singleton (loads once, reused forever)."""
        if LLMClient._shared_local_embedder is None:
            with LLMClient._shared_local_embedder_lock:
                if LLMClient._shared_local_embedder is None:
                    from truebrief.llm.local_embedder import LocalEmbedder
                    LLMClient._shared_local_embedder = LocalEmbedder(
                        model_name=getattr(self._settings, "LOCAL_EMBED_MODEL", "BAAI/bge-base-en-v1.5")
                    )
        return LLMClient._shared_local_embedder

    def call(
        self,
        step_name: str,
        prompt: str,
        json_mode: bool = False,
        system_prompt: Optional[str] = None,
    ) -> str:
        if step_name not in self._config:
            raise LLMError(f"No LLM config found for step '{step_name}'.")

        cfg = self._config[step_name]
        provider = cfg["provider"]
        model = cfg["model"]

        # Pick which Gemini key to start with (round-robin). On quota exhaustion we try
        # the other key. Both are resolved once here so the loop doesn't re-pick.
        _picked_client, _picked_other = (
            self._pick_gemini_client() if provider == "gemini" else (None, None)
        )

        for attempt in range(1, self.MAX_RETRIES + 1):
            t0 = time.monotonic()
            try:
                if provider == "gemini":
                    result, in_tok, out_tok = self._call_gemini_instrumented(
                        model, prompt, json_mode, system_prompt, client=_picked_client
                    )
                elif provider == "openai":
                    result, in_tok, out_tok = self._call_openai_instrumented(
                        model, prompt, json_mode, system_prompt
                    )
                elif provider == "groq":
                    result, in_tok, out_tok = self._call_groq_instrumented(
                        model, prompt, json_mode, system_prompt
                    )
                else:
                    raise LLMError(f"Unknown provider '{provider}'.")

                duration_ms = int((time.monotonic() - t0) * 1000)
                self._log_call(
                    stage=step_name,
                    model=model,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    duration_ms=duration_ms,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    response=result,
                )
                return result

            except Exception as exc:
                # Per-minute rate limit (RPM/TPM): wait 65s then retry same key — no switch.
                if provider == "gemini" and self._is_quota_exhausted(exc) and self._is_per_minute_limit(exc):
                    logger.warning(
                        "[LLM] Per-minute rate limit hit (step=%s). Waiting 65s before retry.", step_name
                    )
                    self._flag_quota("yellow", step_name, model, "rpm", exc)
                    time.sleep(65)
                    continue

                # Per-day quota exhausted on whichever key was picked — switch to the other immediately.
                if provider == "gemini" and self._is_quota_exhausted(exc):
                    backup = _picked_other
                    if backup:
                        logger.warning(
                            "[LLM] Gemini key quota exhausted (step=%s). "
                            "Switching to other key. Reason: %s",
                            step_name, str(exc)[:200],
                        )
                        self._flag_quota("yellow", step_name, model, "primary", exc)
                        try:
                            result, in_tok, out_tok = self._call_gemini_instrumented(
                                model, prompt, json_mode, system_prompt, client=backup
                            )
                            duration_ms = int((time.monotonic() - t0) * 1000)
                            self._log_call(step_name, model, in_tok, out_tok, duration_ms,
                                           prompt, system_prompt, result)
                            return result
                        except Exception as bexc:
                            if self._is_quota_exhausted(bexc):
                                self._flag_quota("red", step_name, model, "backup", bexc)
                                # Last resort: both Gemini keys dead → run this call on
                                # Groq if a key exists. Keeps the pipeline alive through
                                # daily quota resets instead of producing empty briefs.
                                # (Validated need 2026-07-06: local e2e died with both
                                # keys 429-exhausted mid-day.)
                                if self._settings.GROQ_API_KEY:
                                    groq_model = getattr(
                                        self._settings, "GROQ_FALLBACK_MODEL",
                                        "llama-3.3-70b-versatile",
                                    )
                                    logger.warning(
                                        "[LLM] BOTH Gemini keys quota-exhausted (step=%s). "
                                        "Falling back to Groq %s for this call.",
                                        step_name, groq_model,
                                    )
                                    try:
                                        result, in_tok, out_tok = self._call_groq_instrumented(
                                            groq_model, prompt, json_mode, system_prompt
                                        )
                                        duration_ms = int((time.monotonic() - t0) * 1000)
                                        self._log_call(step_name, groq_model, in_tok, out_tok,
                                                       duration_ms, prompt, system_prompt, result)
                                        return result
                                    except Exception as gexc:
                                        logger.error(
                                            "[LLM] Groq fallback also failed (step=%s): %s",
                                            step_name, gexc,
                                        )
                                logger.error(
                                    "[LLM] BOTH Gemini keys are quota-exhausted (step=%s). "
                                    "Primary: %s | Backup: %s.",
                                    step_name, str(exc)[:100], str(bexc)[:100],
                                )
                                raise LLMError(
                                    f"Both Gemini API keys are quota-exhausted for step "
                                    f"'{step_name}' (and no working Groq fallback)."
                                ) from bexc
                            logger.warning(
                                "[LLM] Backup key failed with non-quota error (step=%s): %s",
                                step_name, bexc,
                            )
                            self._flag_quota("red", step_name, model, "backup", bexc)
                            exc = bexc  # fall through to normal retry with backup's error
                    else:
                        # No backup key configured at all — primary is quota-exhausted and
                        # there's nothing to fall back to, so this call is already failing.
                        self._flag_quota("red", step_name, model, "primary", exc)

                if attempt < self.MAX_RETRIES:
                    wait = self._retry_wait(exc, attempt)
                    logger.warning(f"Attempt {attempt} failed: {exc}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    # Reverse fallback: Groq step exhausted its retries → try Gemini
                    # once before giving up.
                    if provider == "groq" and self._settings.GOOGLE_API_KEY:
                        gem_model = "gemini-3.1-flash-lite"
                        logger.warning(
                            "[LLM] Groq exhausted all retries (step=%s). "
                            "Falling back to Gemini %s for this call.",
                            step_name, gem_model,
                        )
                        try:
                            result, in_tok, out_tok = self._call_gemini_instrumented(
                                gem_model, prompt, json_mode, system_prompt
                            )
                            duration_ms = int((time.monotonic() - t0) * 1000)
                            self._log_call(step_name, gem_model, in_tok, out_tok,
                                           duration_ms, prompt, system_prompt, result)
                            return result
                        except Exception as gemexc:
                            logger.error(
                                "[LLM] Gemini reverse-fallback also failed (step=%s): %s",
                                step_name, gemexc,
                            )
                    raise LLMError(f"Failed after {self.MAX_RETRIES} attempts: {exc}") from exc
        return ""

    def call_gemini_with_grounding(
        self,
        step_name: str,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> "GroundedResult":
        """Call Gemini with the Google Search grounding tool. V5's collector entry point.

        Deliberately separate from call(): grounding requires tools=[GoogleSearch()] and
        MUST NOT force response_mime_type="application/json" — verified live 2026-07-22 that
        combining the two suppresses grounding_metadata entirely (grounding_chunks/supports
        come back empty) AND the model fabricates a plausible-looking-but-fake grounding-
        redirect URL when a JSON schema asks for one directly. Always request plain prose;
        real, verified source URLs come only from response.candidates[0].grounding_metadata.
        grounding_chunks — never from model-generated text.

        No cross-provider fallback (Groq doesn't do this kind of search grounding) — only the
        primary/backup Gemini key rotation that call() already does for quota exhaustion.
        """
        cfg = self._config.get(step_name)
        model = cfg["model"] if cfg else "gemini-3.5-flash-lite"
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_prompt if system_prompt else None,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )

        def _do_call(client) -> "GroundedResult":
            response = self._call_with_timeout(
                lambda: client.models.generate_content(model=model, contents=prompt, config=config),
                _GEMINI_GENERATE_TIMEOUT,
            )
            text = (response.text or "").strip() if response else ""
            in_tok = out_tok = 0
            if response is not None and getattr(response, "usage_metadata", None):
                meta = response.usage_metadata
                in_tok = getattr(meta, "prompt_token_count", 0) or 0
                out_tok = getattr(meta, "candidates_token_count", 0) or 0
            chunks: list = []
            supports: list = []
            cand = response.candidates[0] if response and response.candidates else None
            gm = cand.grounding_metadata if cand else None
            if gm:
                chunks = list(gm.grounding_chunks or [])
                supports = list(gm.grounding_supports or [])
            return GroundedResult(text=text, chunks=chunks, supports=supports,
                                   input_tokens=in_tok, output_tokens=out_tok)

        t0 = time.monotonic()
        _picked, _other = self._pick_gemini_client()
        try:
            result = _do_call(_picked)
        except Exception as exc:
            if self._is_quota_exhausted(exc) and self._is_per_minute_limit(exc):
                logger.warning(
                    "[LLM] Per-minute rate limit hit (step=%s, grounded). Waiting 65s.", step_name
                )
                self._flag_quota("yellow", step_name, model, "rpm", exc)
                time.sleep(65)
                result = _do_call(_picked)
            elif self._is_quota_exhausted(exc):
                backup = _other
                if backup:
                    logger.warning(
                        "[LLM] Gemini key quota exhausted (step=%s, grounded). "
                        "Switching to other key.", step_name,
                    )
                    self._flag_quota("yellow", step_name, model, "primary", exc)
                    try:
                        result = _do_call(backup)
                    except Exception as bexc:
                        # Real live incident (2026-08-12): backup key permanently 404'd
                        # ("model no longer available") right after primary hit its daily
                        # grounding quota — this branch previously had NO handling at all,
                        # the exception just propagated with no flag and no record.
                        logger.error(
                            "[LLM] Backup key ALSO failed (step=%s, grounded, model=%s): %s",
                            step_name, model, bexc,
                        )
                        self._flag_quota("red", step_name, model, "backup", bexc)
                        raise LLMError(
                            f"Gemini grounded call failed on both primary (quota-exhausted) "
                            f"and backup ({bexc}) for step '{step_name}'."
                        ) from bexc
                else:
                    self._flag_quota("red", step_name, model, "primary", exc)
                    raise LLMError(f"Gemini quota exhausted for grounded step '{step_name}', no backup key.") from exc
            else:
                raise

        duration_ms = int((time.monotonic() - t0) * 1000)
        self._log_call(
            stage=step_name, model=model,
            input_tokens=result.input_tokens, output_tokens=result.output_tokens,
            duration_ms=duration_ms, prompt=prompt, system_prompt=system_prompt,
            response=result.text,
        )
        return result

    # =====================================================================
    # Named pipeline-stage methods — one per V5 call. Each reads its provider +
    # model from LLM_CONFIG[step], resolves the API key via PROVIDER_REGISTRY,
    # and refuses (LLMError) a step pointed at a provider that can't serve it.
    # Switch any stage by editing its one line in config/settings.py — no code
    # change here. See config/settings.py PROVIDER_REGISTRY / LLM_CONFIG.
    # =====================================================================

    def collector_search(
        self,
        topic_name: str,
        last_run_str: str = "",
        today_str: str = "",
        known_facts: Optional[List[str]] = None,
        system_prompt: Optional[str] = None,
    ) -> "GroundedResult":
        """STAGE 1 — grounded web search. Provider from LLM_CONFIG['gemini_search']:
        'gemini' (Google-Search grounding + rich prompt + citation offsets),
        'linkup' (sourcedAnswer), or 'brave' (web search + summarizer). Returns a
        GroundedResult; .supports is empty for linkup/brave (no per-segment offsets).

        Falls back through the other grounding providers (that have a key) if the
        configured one errors or returns nothing — one provider being down
        (Linkup 4xx/5xx, Gemini quota) must never leave a scan with no brief.
        Raises LLMError only if the configured provider can't ground at all, or
        every provider failed."""
        configured = self._require_capability("gemini_search", "grounding")

        from config.settings import PROVIDER_REGISTRY

        all_grounding = [
            p for p, r in PROVIDER_REGISTRY.items() if "grounding" in r.get("capabilities", set())
        ]
        order = [configured] + [p for p in all_grounding if p != configured]

        errors: List[str] = []
        no_news: Optional["GroundedResult"] = None  # first "nothing happened" answer seen
        for idx, p in enumerate(order):
            if p != "gemini" and not self._resolve_api_key(p):
                continue  # no key for this fallback provider
            try:
                result = self._grounded_one(
                    p, topic_name, last_run_str, today_str, known_facts, system_prompt
                )
            except Exception as exc:
                errors.append(f"{p}: {type(exc).__name__}: {str(exc)[:150]}")
                logger.warning("[collector_search] grounding provider '%s' failed: %s", p, str(exc)[:200])
                continue
            text = (result.text or "").strip()
            if not text:
                errors.append(f"{p}: empty response")
                logger.warning("[collector_search] grounding provider '%s' returned empty text", p)
                continue
            if _looks_like_no_news(text):
                # Provider's index has nothing fresh for this topic (common for
                # Linkup/Brave on fast-moving niches). Try the next provider —
                # Gemini's live search often does have it. Remember this answer so
                # that if EVERY provider says "nothing", we still return cleanly
                # (pipeline → "no_update") instead of raising.
                no_news = no_news or result
                errors.append(f"{p}: no fresh results")
                logger.info("[collector_search] provider '%s' has no fresh results — trying next", p)
                continue
            if idx > 0:
                logger.warning(
                    "[collector_search] configured provider '%s' unavailable — used fallback '%s'",
                    configured, p,
                )
            return result

        if no_news is not None:
            logger.info("[collector_search] all providers report nothing new for '%s'", topic_name)
            return no_news

        raise LLMError(
            f"All grounding providers failed for '{topic_name}': " + " | ".join(errors)
        )

    def _grounded_one(
        self, provider, topic_name, last_run_str, today_str, known_facts, system_prompt
    ) -> "GroundedResult":
        """Single grounded-search call against `provider`. No fallback here — see
        collector_search."""
        if provider == "gemini":
            prompt = build_gemini_search_prompt(
                topic_name, last_run_str, today_str, known_facts=known_facts or None
            )
            return self.call_gemini_with_grounding(
                step_name="gemini_search",
                prompt=prompt,
                system_prompt=system_prompt or GEMINI_SEARCH_SYSTEM,
            )
        # linkup takes a full dated question; brave's q param 422s on that length
        # and uses its `freshness` param for the window — give it short keywords.
        if provider == "linkup":
            q = build_search_query(topic_name, last_run_str, today_str, style="question")
            return self._grounded_linkup(q, last_run_str, today_str)
        if provider == "brave":
            q = build_search_query(topic_name, last_run_str, today_str, style="keywords")
            return self._grounded_brave(q, last_run_str, today_str)
        raise LLMError(f"no grounding adapter for provider '{provider}'")

    def extract_facts(
        self,
        cited_text: str,
        source_legend: str,
        topic_name: str,
        today: str,
        news_window_start: str = "",
    ) -> str:
        """STAGE 2 — restructure grounded prose into the Alpha-JSON contract.
        Any 'llm' provider. Returns the raw JSON string (caller parses).
        news_window_start guards against stale prose being dated as today."""
        self._require_capability("gemini_extract", "llm")
        prompt = build_gemini_extract_prompt(
            cited_text, source_legend, topic_name, today, news_window_start=news_window_start
        )
        return self.call(
            step_name="gemini_extract",
            prompt=prompt,
            json_mode=True,
            system_prompt=GEMINI_EXTRACT_SYSTEM,
        )

    def judge(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """STAGE 3 — arbiter dedup judge (single case OR batch; caller builds the
        prompt). Any 'llm' provider. Returns the raw JSON string."""
        self._require_capability("arbiter", "llm")
        return self.call(
            step_name="arbiter", prompt=prompt, json_mode=True, system_prompt=system_prompt
        )

    def write_brief(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """STAGE 4 — final brief markdown (caller builds the prompt). Any 'llm' provider."""
        self._require_capability("briefer", "llm")
        return self.call(
            step_name="briefer", prompt=prompt, json_mode=False, system_prompt=system_prompt
        )

    # STAGE 5 (embedding) is embed() / embed_batch() below — already stage-named,
    # provider from LLM_CONFIG['embedding'] (EMBED_PROVIDER env: 'gemini' | 'local'),
    # output width enforced to EMBED_DIM. embed_fact / embed_facts are aliases kept
    # for naming symmetry with the other stage methods.
    def embed_fact(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
        """Alias of embed() — the embedding stage entry point."""
        return self.embed(text, task_type=task_type)

    def embed_facts(
        self, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> List[List[float]]:
        """Alias of embed_batch() — the embedding stage entry point."""
        return self.embed_batch(texts, task_type=task_type)

    # ------------------------------------------------------------------
    # Grounding adapters (linkup / brave). The gemini adapter is
    # call_gemini_with_grounding above. All return the same GroundedResult shape.
    # ------------------------------------------------------------------

    def _grounded_linkup(
        self, query: str, last_run_str: str = "", today_str: str = ""
    ) -> "GroundedResult":
        """Linkup sourcedAnswer → GroundedResult (.text = sourced prose, .chunks =
        verified source URLs, .supports = [] — Linkup gives no per-segment offsets)."""
        from types import SimpleNamespace

        import httpx

        from config.settings import PROVIDER_REGISTRY

        api_key = self._resolve_api_key("linkup")
        if not api_key:
            raise LLMError("LINKUP_API_KEY is not set — cannot use SEARCH_PROVIDER=linkup")

        from_date, to_date = _search_window(last_run_str, today_str)

        t0 = time.monotonic()
        resp = httpx.post(
            PROVIDER_REGISTRY["linkup"]["endpoint"],
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "q": query,
                "depth": "standard",
                "outputType": "sourcedAnswer",
                "maxResults": 15,
                "fromDate": from_date,
                "toDate": to_date,
            },
            timeout=_GEMINI_GENERATE_TIMEOUT,
        )
        if resp.status_code >= 400:
            raise LLMError(f"Linkup {resp.status_code} for q={query!r}: {resp.text[:300]}")
        resp.raise_for_status()
        data = resp.json()

        text = data.get("answer", "") or ""
        raw_sources = data.get("sources", []) or []
        chunks = [
            SimpleNamespace(web=SimpleNamespace(uri=s.get("url", ""), title=s.get("title", s.get("url", ""))))
            for s in raw_sources
            if s.get("url")
        ]
        logger.info("[linkup] returned %d sources for: %s", len(chunks), query[:80])
        self._log_call(
            stage="gemini_search", model="linkup/sourcedAnswer",
            input_tokens=0, output_tokens=0,
            duration_ms=int((time.monotonic() - t0) * 1000), prompt=query, response=text,
        )
        return GroundedResult(text=text, chunks=chunks, supports=[])

    def _grounded_brave(
        self, query: str, last_run_str: str = "", today_str: str = ""
    ) -> "GroundedResult":
        """Brave web search (summary=true) → GroundedResult. Uses the AI summary as
        .text when present, else concatenated result snippets; .chunks from web
        results; .supports = []."""
        from types import SimpleNamespace

        import httpx

        from config.settings import PROVIDER_REGISTRY

        api_key = self._resolve_api_key("brave")
        if not api_key:
            raise LLMError("BRAVE_API_KEY is not set — cannot use SEARCH_PROVIDER=brave")

        from_date, to_date = _search_window(last_run_str, today_str)

        t0 = time.monotonic()
        resp = httpx.get(
            PROVIDER_REGISTRY["brave"]["endpoint"],
            headers={
                "X-Subscription-Token": api_key,
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
            },
            params={
                "q": query,
                "count": 10,
                "freshness": f"{from_date}to{to_date}",
                "country": "US",
                "search_lang": "en",
                "text_decorations": "false",
                "summary": "true",
                "extra_snippets": "true",
            },
            timeout=_GEMINI_GENERATE_TIMEOUT,
        )
        if resp.status_code >= 400:
            raise LLMError(f"Brave {resp.status_code} for q={query!r}: {resp.text[:300]}")
        resp.raise_for_status()
        data = resp.json()

        ai_summary = ((data.get("summarizer") or {}).get("answer") or "").strip()
        web_results = (data.get("web", {}) or {}).get("results", []) or []
        chunks: list = []
        snippet_lines: list = []
        for r in web_results[:15]:
            url = r.get("url", "")
            if not url:
                continue
            title = r.get("title", "") or url
            chunks.append(SimpleNamespace(web=SimpleNamespace(uri=url, title=title)))
            extras = " ".join((r.get("extra_snippets") or [])[:2])
            snippet_lines.append(f"{title}: {r.get('description', '')} {extras}".strip())

        text = ai_summary or "\n".join(snippet_lines)
        logger.info("[brave] returned %d sources for: %s", len(chunks), query[:80])
        self._log_call(
            stage="gemini_search", model="brave/web-summary",
            input_tokens=0, output_tokens=0,
            duration_ms=int((time.monotonic() - t0) * 1000), prompt=query, response=text,
        )
        return GroundedResult(text=text, chunks=chunks, supports=[])

    def call_with_lookup(
        self, prompt: str, last_run_str: str = "", today_str: str = ""
    ) -> "GroundedResult":
        """Back-compat shim → _grounded_linkup. Prefer collector_search()."""
        return self._grounded_linkup(prompt, last_run_str, today_str)

    def embed(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
        """Generate a vector embedding for a single text string.

        task_type: "RETRIEVAL_DOCUMENT" for facts/documents (default),
                   "RETRIEVAL_QUERY" for search queries and topic labels.
        Delegates to the provider set by EMBED_PROVIDER:
          "local"  → sentence-transformers (one batched CPU call, no quota; task_type ignored)
          "openai" → text-embedding-3-small (768 dim via Matryoshka; task_type ignored)
          "gemini" → gemini-embedding-2 (768 dim, 100 req/min free tier)
        """
        if not text or not text.strip():
            logger.warning("Attempted to embed empty text. Returning zero vector.")
            return [0.0] * EMBED_DIM

        provider = self._embed_provider()
        t0 = time.monotonic()
        if provider == "local":
            result = self._get_local_embedder().embed(text)
            model = self._local_embed_model_label()
        elif provider == "openai":
            model = getattr(self._settings, "OPENAI_EMBED_MODEL", "text-embedding-3-small")
            result = self._embed_openai(text, model=model)
        else:
            result = self._embed_gemini(text, task_type=task_type)
            model = "models/gemini-embedding-2"
        self._check_embed_dim(result, provider)
        duration_ms = int((time.monotonic() - t0) * 1000)
        self._log_call(
            stage="embedding",
            model=model,
            input_tokens=self._estimate_tokens(text),
            output_tokens=0,
            duration_ms=duration_ms,
            prompt=text,
        )
        return result

    def embed_local(self, text: str) -> List[float]:
        """Embed text with the on-device model, independent of EMBED_PROVIDER.

        Public-topic autocomplete deliberately uses its own local vector space for
        low latency. The production pipeline continues to use ``embed()`` and its
        configured Gemini/OpenAI provider unchanged.
        """
        if not text or not text.strip():
            return [0.0] * EMBED_DIM
        t0 = time.monotonic()
        result = self._get_local_embedder().embed(text)
        self._check_embed_dim(result, "local")
        logger.debug(
            "Local public-topic search embedding completed in %dms",
            int((time.monotonic() - t0) * 1000),
        )
        return result

    def embed_batch(self, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[List[float]]:
        """Generate vector embeddings for a list of strings.

        task_type: "RETRIEVAL_DOCUMENT" for facts (default), "RETRIEVAL_QUERY" for queries.
        "local"  → ONE batched forward pass, <500ms for 100 titles, no quota; task_type ignored.
        "openai" → ONE batched API call with dimensions=768; task_type ignored.
        "gemini" → N parallel API calls via ThreadPoolExecutor (8 workers).
                   Free tier: 100 req/min — bursts >100 titles will hit quota.
        """
        if not texts:
            return []

        provider = self._embed_provider()
        t0 = time.monotonic()
        if provider == "local":
            result = self._get_local_embedder().embed_batch(texts)
            model = self._local_embed_model_label()
        elif provider == "openai":
            model = getattr(self._settings, "OPENAI_EMBED_MODEL", "text-embedding-3-small")
            result = self._embed_batch_openai(texts, model=model)
        else:
            result = self._embed_batch_gemini(texts, task_type=task_type)
            model = "models/gemini-embedding-2"
        if result:
            self._check_embed_dim(result[0], provider)
        duration_ms = int((time.monotonic() - t0) * 1000)
        self._log_call(
            stage="embedding",
            model=model,
            input_tokens=sum(self._estimate_tokens(t) for t in texts),
            output_tokens=0,
            duration_ms=duration_ms,
            prompt="\n".join(texts),
        )
        return result

    # ------------------------------------------------------------------
    # OpenAI embedding internals
    # ------------------------------------------------------------------

    def _embed_openai(self, text: str, model: str | None = None) -> List[float]:
        client = self._get_openai_client()
        model_name = model or getattr(self._settings, "OPENAI_EMBED_MODEL", "text-embedding-3-small")
        try:
            res = self._call_with_timeout(
                lambda: client.embeddings.create(
                    input=text,
                    model=model_name,
                    dimensions=EMBED_DIM,  # 768
                ),
                _GEMINI_EMBED_TIMEOUT,
            )
            if not res or not res.data:
                raise LLMError("OpenAI returned no embeddings for the provided text.")
            return res.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            raise LLMError(f"OpenAI embedding failed: {e}") from e

    def _embed_batch_openai(self, texts: List[str], model: str | None = None) -> List[List[float]]:
        valid_texts = [t if (t and t.strip()) else "[empty]" for t in texts]
        client = self._get_openai_client()
        model_name = model or getattr(self._settings, "OPENAI_EMBED_MODEL", "text-embedding-3-small")
        try:
            res = self._call_with_timeout(
                lambda: client.embeddings.create(
                    input=valid_texts,
                    model=model_name,
                    dimensions=EMBED_DIM,  # 768
                ),
                _GEMINI_EMBED_TIMEOUT * 2,
            )
            if not res or not res.data:
                raise LLMError("OpenAI returned no embeddings for batch.")
            # Preserve input ordering
            sorted_data = sorted(res.data, key=lambda x: x.index)
            return [item.embedding for item in sorted_data]
        except Exception as e:
            logger.error(f"OpenAI batch embedding failed: {e}")
            raise LLMError(f"OpenAI batch embedding failed: {e}") from e

    # ------------------------------------------------------------------
    # Gemini embedding internals (kept intact — switch back via settings)
    # ------------------------------------------------------------------

    def _gemini_embed_call(self, client: Any, contents: Any, task_type: str) -> Any:
        """One raw embed_content call. Raises the SDK exception unchanged so the
        retry driver can inspect it for 429/quota."""
        from google.genai import types

        cfg = types.EmbedContentConfig(output_dimensionality=768, task_type=task_type)
        res = self._call_with_timeout(
            lambda: client.models.embed_content(
                model="models/gemini-embedding-2", contents=contents, config=cfg
            ),
            _GEMINI_EMBED_TIMEOUT,
        )
        if not res or not res.embeddings:
            raise LLMError("Gemini returned no embeddings.")
        return res

    def _gemini_embed_retry(self, contents: Any, task_type: str, label: str):
        """Run a gemini embed_content call with the same quota resilience as
        call(): per-minute 429 → wait 65s and retry; per-day 429 → switch to the
        backup key. Embeddings are the one Gemini call that had NO retry, so a
        transient rate limit was silently dropping facts (arbiter._ensure_embedding
        / vector_store.add_fact both swallow the error)."""
        picked, other = self._pick_gemini_client()
        try:
            return self._gemini_embed_call(picked, contents, task_type)
        except Exception as exc:
            if not self._is_quota_exhausted(exc):
                logger.error("%s failed: %s", label, exc)
                raise LLMError(f"{label} failed: {exc}") from exc
            if self._is_per_minute_limit(exc):
                logger.warning("[embed] per-minute rate limit (%s) — waiting 65s", label)
                self._flag_quota("yellow", "embedding", "models/gemini-embedding-2", "rpm", exc)
                time.sleep(65)
                try:
                    return self._gemini_embed_call(picked, contents, task_type)
                except Exception as exc2:
                    exc = exc2
            if other is not None and self._is_quota_exhausted(exc):
                logger.warning("[embed] key quota exhausted (%s) — trying backup key", label)
                self._flag_quota("yellow", "embedding", "models/gemini-embedding-2", "primary", exc)
                try:
                    return self._gemini_embed_call(other, contents, task_type)
                except Exception as exc3:
                    self._flag_quota("red", "embedding", "models/gemini-embedding-2", "backup", exc3)
                    raise LLMError(f"{label} failed on both keys: {exc3}") from exc3
            self._flag_quota("red", "embedding", "models/gemini-embedding-2", "primary", exc)
            raise LLMError(f"{label} failed (quota): {exc}") from exc

    def _embed_gemini(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
        res = self._gemini_embed_retry([text], task_type, "Embedding")
        return list(res.embeddings[0].values)

    def _embed_batch_gemini(self, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[List[float]]:
        """Gemini batch embed via ThreadPoolExecutor (N separate API calls). On a
        429 anywhere in the pool, retry the whole batch once through the
        quota-resilient path (backup key / cooldown)."""
        valid_texts = [t if (t and t.strip()) else "[empty]" for t in texts]

        def _run(client_getter) -> List[List[float]]:
            from google.genai import types

            client = client_getter()
            cfg = types.EmbedContentConfig(output_dimensionality=768, task_type=task_type)

            def _one(text: str) -> List[float]:
                res = self._call_with_timeout(
                    lambda: client.models.embed_content(
                        model="models/gemini-embedding-2", contents=text, config=cfg
                    ),
                    _GEMINI_EMBED_TIMEOUT,
                )
                if not res or not res.embeddings:
                    raise LLMError("Gemini returned no embedding for text.")
                return list(res.embeddings[0].values)

            workers = min(8, len(valid_texts))
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                return list(pool.map(_one, valid_texts))

        try:
            return _run(self._get_gemini_client)
        except Exception as e:
            if not self._is_quota_exhausted(e):
                logger.error(f"Batch embedding failed: {e}")
                raise LLMError(f"Batch embedding failed: {e}") from e
            backup = self._get_gemini_client_backup()
            if self._is_per_minute_limit(e):
                logger.warning("[embed] batch per-minute limit — waiting 65s")
                time.sleep(65)
                try:
                    return _run(self._get_gemini_client)
                except Exception as e2:
                    e = e2
            if backup is not None and self._is_quota_exhausted(e):
                logger.warning("[embed] batch key quota exhausted — retrying on backup key")
                try:
                    return _run(self._get_gemini_client_backup)
                except Exception as e3:
                    raise LLMError(f"Batch embedding failed on both keys: {e3}") from e3
            raise LLMError(f"Batch embedding failed (quota): {e}") from e

    # -------------------------------------------------------------------------
    # Internal: instrumented call methods (return text + token counts)
    # -------------------------------------------------------------------------

    def _call_gemini_instrumented(
        self,
        model: str,
        prompt: str,
        json_mode: bool,
        system_prompt: Optional[str],
        client: Optional[Any] = None,
    ) -> tuple[str, int, int]:
        """Call Gemini and return (text, input_tokens, output_tokens)."""
        if client is None:
            client = self._get_gemini_client()
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_prompt if system_prompt else None,
            response_mime_type="application/json" if json_mode else "text/plain",
        )

        try:
            response = self._call_with_timeout(
                lambda: client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                ),
                _GEMINI_GENERATE_TIMEOUT,
            )
            if not response or not response.text:
                logger.warning(f"Gemini returned empty text for model {model}. Possible safety block.")
                text = "{}" if json_mode else ""
            else:
                text = response.text.strip()

            # Extract token counts from usage_metadata when available
            in_tok = 0
            out_tok = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                meta = response.usage_metadata
                in_tok = getattr(meta, "prompt_token_count", 0) or 0
                out_tok = getattr(meta, "candidates_token_count", 0) or 0

            return text, in_tok, out_tok

        except Exception as e:
            if "safety" in str(e).lower():
                logger.warning(f"Gemini call blocked by safety filters: {e}")
                return ("{}" if json_mode else "Content blocked by safety filters.", 0, 0)
            raise e

    @staticmethod
    def _json_object_messages(
        messages: list, system_prompt: Optional[str], prompt: str
    ) -> None:
        """OpenAI / Groq response_format={"type":"json_object"} 400s unless the
        literal token 'json' appears somewhere in the messages (Gemini has no such
        rule). If the caller's prompt + system text doesn't already contain it,
        append a minimal instruction to the last (user) message in place."""
        if "json" not in f"{system_prompt or ''} {prompt}".lower():
            messages[-1]["content"] += "\n\nRespond with a valid JSON object only."

    def _call_openai_instrumented(
        self,
        model: str,
        prompt: str,
        json_mode: bool,
        system_prompt: Optional[str],
    ) -> tuple[str, int, int]:
        """Call OpenAI and return (text, input_tokens, output_tokens)."""
        client = self._get_openai_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {"model": model, "messages": messages}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
            self._json_object_messages(messages, system_prompt, prompt)

        response = client.chat.completions.create(**kwargs)
        text = response.choices[0].message.content.strip()
        in_tok = response.usage.prompt_tokens if response.usage else 0
        out_tok = response.usage.completion_tokens if response.usage else 0
        return text, in_tok, out_tok

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _retry_wait(self, exc: Exception, attempt: int) -> float:
        """Return seconds to wait before the next retry.

        For Gemini 429s, parse the retryDelay from the error body so we
        actually respect the quota window instead of burning retries in 5s.
        Falls back to exponential backoff if no delay hint is available.
        """
        import re as _re
        msg = str(exc)
        # Gemini 429 body contains e.g. "Please retry in 36.731022388s."
        m = _re.search(r'retry.*?(\d+(?:\.\d+)?)s', msg, _re.IGNORECASE)
        if m:
            suggested = float(m.group(1))
            # Add a small jitter buffer and cap at 120s so the pipeline doesn't hang forever
            return min(suggested + 2.0, 120.0)
        return self.RETRY_DELAY_SECONDS * (2 ** (attempt - 1))

    def _log_call(
        self,
        stage: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: int,
        prompt: Optional[str] = None,
        system_prompt: Optional[str] = None,
        response: Optional[str] = None,
    ) -> None:
        """Fire-and-forget telemetry log. Never raises.

        When settings.TRACE_PIPELINE is on, the actual prompt / system_prompt /
        response are stored too (truncated to TRACE_MAX_CHARS) so the admin trace
        panel can show exactly what the model saw and produced.
        """
        try:
            from truebrief.ledger.telemetry import get_telemetry
            tel = get_telemetry()
            if tel is None:
                return
            run_id = pipeline_run_id_var.get()
            cost = compute_cost_usd(model, input_tokens, output_tokens, stage=stage)

            trace_on = getattr(self._settings, "TRACE_PIPELINE", False)
            cap = getattr(self._settings, "TRACE_MAX_CHARS", 20000)

            def _clip(s: Optional[str]) -> Optional[str]:
                if not trace_on or s is None:
                    return None
                return s if len(s) <= cap else (s[:cap] + f"\n…[truncated {len(s) - cap} chars]")

            tel.log_llm_call(
                run_id,
                stage=stage,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                duration_ms=duration_ms,
                prompt=_clip(prompt),
                system_prompt=_clip(system_prompt),
                response=_clip(response),
            )
        except Exception as exc:
            logger.debug("LLM telemetry log failed (non-fatal): %s", exc)

    @staticmethod
    def _call_with_timeout(func, timeout_seconds: float):
        """Run func() in a thread; raise LLMError if it exceeds timeout_seconds.

        IMPORTANT: do NOT use `with ThreadPoolExecutor(...) as executor:` here.
        The context manager calls shutdown(wait=True) on exit, which blocks until
        the background thread finishes — even when we've already timed out. On slow
        Gemini responses (large briefs, high load) this causes indefinite hangs
        instead of a clean timeout. shutdown(wait=False, cancel_futures=True) lets
        the call return immediately; the orphaned thread dies on its own.
        """
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(func)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError:
            executor.shutdown(wait=False, cancel_futures=True)
            raise LLMError(
                f"Gemini API call timed out after {timeout_seconds}s. "
                "The API may be slow or rate-limited."
            )
        else:
            executor.shutdown(wait=False)

    @staticmethod
    def _is_quota_exhausted(exc: Exception) -> bool:
        msg = str(exc)
        return "429" in msg or "RESOURCE_EXHAUSTED" in msg

    @staticmethod
    def _is_per_minute_limit(exc: Exception) -> bool:
        """True when the 429 is an RPM/TPM rate limit (retry in ~60s fixes it).
        False means it's a per-day (RPD) limit — switching key is the right move."""
        msg = str(exc)
        return (
            "PerMinute" in msg
            or "per_minute" in msg
            or "rate_limit_exceeded" in msg.lower()
            or "GenerateTokensPerMinute" in msg
        )

    @staticmethod
    def _flag_quota(severity: str, step_name: str, model: str, key_type: str, error: Exception) -> None:
        """Real-time quota-exhaustion alert: persist + push the founder. Never raises —
        wrapped so a broken alert path can never affect the LLM call it's reporting on.
        See ledger/quota_alerts.py for the full detection→persist→push design.
        """
        try:
            from truebrief.ledger.quota_alerts import flag_quota_event
            flag_quota_event(severity, step_name, model, key_type, error)
        except Exception as exc:
            logger.debug("[LLM] Quota alert failed (non-fatal): %s", exc)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token-count estimate for embedding calls (~4 chars/token, English).

        Unlike generate_content, the Gemini Developer API's embed_content response
        carries no usage_metadata — EmbedContentMetadata.billable_character_count is
        Vertex-API-only, so there's no exact count available on the API path we use.
        call()'s token counts come from real usage_metadata; this is the best available
        proxy for embed()/embed_batch() (both providers, so volume is comparable).
        """
        if not text:
            return 0
        return max(1, len(text) // 4)

    def _local_embed_model_label(self) -> str:
        """Model label logged for EMBED_PROVIDER=local calls.

        Deliberately distinct from any real Gemini model id (prefixed "local/") so
        llm_call_log / cost-by-stage can't mistake on-device inference for billed API
        usage — it prices at genuinely $0 (see llm/pricing.py) because no external call
        is made, whereas "models/gemini-embedding-2" prices at whatever pricing.py says
        Google currently charges for that endpoint.
        """
        model_name = getattr(self._settings, "LOCAL_EMBED_MODEL", "BAAI/bge-base-en-v1.5")
        return f"local/{model_name}"

    def _pick_gemini_client(self) -> tuple:
        """Return (client, other_client_or_None) alternating between primary and backup.

        Distributes calls 50/50 across both keys from the first request so neither
        key shoulders all the daily RPD quota alone. Falls back to primary-only when
        no backup is configured.
        """
        backup = self._get_gemini_client_backup()
        if not backup:
            return self._get_gemini_client(), None
        with LLMClient._key_lock:
            n = next(LLMClient._key_counter)
        if n % 2 == 0:
            return self._get_gemini_client(), backup
        else:
            return backup, self._get_gemini_client()

    # ------------------------------------------------------------------
    # Provider key / capability resolution — the "one switch" plumbing.
    # PROVIDER_REGISTRY (config/settings.py) is the single source of which
    # settings field holds each provider's key and what it can do.
    # ------------------------------------------------------------------

    def _resolve_api_key(self, provider: str, *, want_backup: bool = False) -> str:
        """Return the API key for `provider`, per PROVIDER_REGISTRY. Applies the
        ENV=development → GOOGLE_API_KEY_DEV override for gemini. Empty string when
        nothing is configured (or the provider needs no key, e.g. 'local')."""
        from config.settings import PROVIDER_REGISTRY

        reg = PROVIDER_REGISTRY.get(provider, {})
        key_fields = list(reg.get("key_settings", []))
        if not key_fields:
            return ""
        if want_backup:
            return getattr(self._settings, key_fields[1], "") if len(key_fields) > 1 else ""
        dev_field = reg.get("dev_key_setting")
        if dev_field and getattr(self._settings, "ENV", "production") == "development":
            dev_key = getattr(self._settings, dev_field, "")
            if dev_key:
                return dev_key
        return getattr(self._settings, key_fields[0], "")

    def _require_capability(self, step_name: str, capability: str) -> str:
        """Return the provider configured for `step_name`, raising LLMError if it
        lacks `capability` ("llm" | "embed" | "grounding"). This is what stops a
        stage from being pointed at a provider that can't serve it."""
        from config.settings import PROVIDER_REGISTRY

        cfg = self._config.get(step_name)
        if not cfg:
            raise LLMError(f"No LLM config found for step '{step_name}'.")
        provider = cfg["provider"]
        caps = PROVIDER_REGISTRY.get(provider, {}).get("capabilities", set())
        if capability not in caps:
            capable = sorted(
                p for p, r in PROVIDER_REGISTRY.items()
                if capability in r.get("capabilities", set())
            )
            raise LLMError(
                f"Step '{step_name}' is set to provider '{provider}', which has no "
                f"'{capability}' capability. Use one of {capable} — fix "
                f"config/settings.py LLM_CONFIG['{step_name}'] or the env var feeding it."
            )
        return provider

    def _embed_provider(self) -> str:
        """Provider for the embedding stage. EMBED_PROVIDER env is the live control
        (scripts mutate it at runtime); LLM_CONFIG['embedding'] mirrors it."""
        rt = getattr(self._settings, "EMBED_PROVIDER", "") or ""
        if rt:
            return rt.strip().lower()
        return self._config.get("embedding", {}).get("provider", "gemini")

    @staticmethod
    def _check_embed_dim(vec: List[float], provider: str) -> None:
        """Fail loudly instead of silently writing a wrong-width vector into the
        known_facts.alpha_embedding pgvector column (EMBED_DIM)."""
        if vec is not None and len(vec) != EMBED_DIM:
            raise LLMError(
                f"Embedding provider '{provider}' returned a {len(vec)}-dim vector; "
                f"known_facts.alpha_embedding requires {EMBED_DIM}. Point EMBED_PROVIDER "
                f"at a {EMBED_DIM}-dim model (gemini / local / openai) or run a pgvector migration first."
            )

    def _get_gemini_client_backup(self) -> Optional[Any]:
        """Return a Gemini client using GOOGLE_API_KEY_BACKUP, or None if not configured."""
        backup_key = self._resolve_api_key("gemini", want_backup=True)
        if not backup_key:
            return None
        if self._gemini_client_backup is None:
            from google import genai
            self._gemini_client_backup = genai.Client(api_key=backup_key)
        return self._gemini_client_backup

    def _get_gemini_client(self) -> Any:
        if self._gemini_client is None:
            from google import genai
            # _resolve_api_key applies the ENV=development → GOOGLE_API_KEY_DEV override
            # so prod quota is never consumed by local benchmark runs or experiments.
            api_key = self._resolve_api_key("gemini")
            if not api_key:
                raise LLMError("GOOGLE_API_KEY not set.")
            self._gemini_client = genai.Client(api_key=api_key)
        return self._gemini_client

    def _get_openai_client(self) -> Any:
        if self._openai_client is None:
            from openai import OpenAI
            api_key = self._resolve_api_key("openai")
            if not api_key:
                raise LLMError("OPENAI_API_KEY not set.")
            self._openai_client = OpenAI(api_key=api_key)
        return self._openai_client

    def _get_groq_client(self) -> Any:
        """Return (and lazily init) an OpenAI-compatible client pointed at Groq's API."""
        if self._groq_client is None:
            from openai import OpenAI
            from config.settings import PROVIDER_REGISTRY
            api_key = self._resolve_api_key("groq")
            if not api_key:
                raise LLMError("GROQ_API_KEY not set. Add it to .env to use Groq.")
            base_url = PROVIDER_REGISTRY["groq"].get("base_url", "https://api.groq.com/openai/v1")
            self._groq_client = OpenAI(api_key=api_key, base_url=base_url)
        return self._groq_client

    def _call_groq_instrumented(
        self,
        model: str,
        prompt: str,
        json_mode: bool,
        system_prompt: Optional[str],
    ) -> tuple[str, int, int]:
        """Call Groq via its OpenAI-compatible API and return (text, input_tokens, output_tokens)."""
        client = self._get_groq_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {"model": model, "messages": messages}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
            self._json_object_messages(messages, system_prompt, prompt)

        response = self._call_with_timeout(
            lambda: client.chat.completions.create(**kwargs), 30.0
        )
        text = response.choices[0].message.content.strip()
        in_tok = response.usage.prompt_tokens if response.usage else 0
        out_tok = response.usage.completion_tokens if response.usage else 0
        return text, in_tok, out_tok
