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

logger = logging.getLogger(__name__)


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

    def embed(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
        """Generate a vector embedding for a single text string.

        task_type: "RETRIEVAL_DOCUMENT" for facts/documents (default),
                   "RETRIEVAL_QUERY" for search queries and topic labels.
        Delegates to the provider set by EMBED_PROVIDER:
          "local"  → sentence-transformers (one batched CPU call, no quota; task_type ignored)
          "gemini" → gemini-embedding-2 (768 dim, 100 req/min free tier)
        """
        if not text or not text.strip():
            logger.warning("Attempted to embed empty text. Returning zero vector.")
            return [0.0] * 768

        provider = getattr(self._settings, "EMBED_PROVIDER", "gemini")
        t0 = time.monotonic()
        if provider == "local":
            result = self._get_local_embedder().embed(text)
            model = self._local_embed_model_label()
        else:
            result = self._embed_gemini(text, task_type=task_type)
            model = "models/gemini-embedding-2"
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

    def embed_batch(self, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[List[float]]:
        """Generate vector embeddings for a list of strings.

        task_type: "RETRIEVAL_DOCUMENT" for facts (default), "RETRIEVAL_QUERY" for queries.
        "local"  → ONE batched forward pass, <500ms for 100 titles, no quota; task_type ignored.
        "gemini" → N parallel API calls via ThreadPoolExecutor (8 workers).
                   Free tier: 100 req/min — bursts >100 titles will hit quota.
        """
        if not texts:
            return []

        provider = getattr(self._settings, "EMBED_PROVIDER", "gemini")
        t0 = time.monotonic()
        if provider == "local":
            result = self._get_local_embedder().embed_batch(texts)
            model = self._local_embed_model_label()
        else:
            result = self._embed_batch_gemini(texts, task_type=task_type)
            model = "models/gemini-embedding-2"
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
    # Gemini embedding internals (kept intact — switch back via settings)
    # ------------------------------------------------------------------

    def _embed_gemini(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
        client = self._get_gemini_client()
        from google.genai import types
        try:
            embed_config = types.EmbedContentConfig(
                output_dimensionality=768,
                task_type=task_type,
            )
            res = self._call_with_timeout(
                lambda: client.models.embed_content(
                    model="models/gemini-embedding-2",
                    contents=[text],
                    config=embed_config,
                ),
                _GEMINI_EMBED_TIMEOUT,
            )
            if not res or not res.embeddings:
                raise LLMError("Gemini returned no embeddings for the provided text.")
            return res.embeddings[0].values
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            raise LLMError(f"Embedding failed: {e}") from e

    def _embed_batch_gemini(self, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[List[float]]:
        """Gemini batch embed via ThreadPoolExecutor (N separate API calls)."""
        valid_texts = [t if (t and t.strip()) else "[empty]" for t in texts]
        _client = self._get_gemini_client()
        from google.genai import types

        embed_config = types.EmbedContentConfig(
            output_dimensionality=768,
            task_type=task_type,
        )

        def _one(text: str) -> List[float]:
            res = self._call_with_timeout(
                lambda: _client.models.embed_content(
                    model="models/gemini-embedding-2",
                    contents=text,
                    config=embed_config,
                ),
                _GEMINI_EMBED_TIMEOUT,
            )
            if not res or not res.embeddings:
                raise LLMError("Gemini returned no embedding for text.")
            return list(res.embeddings[0].values)

        try:
            workers = min(8, len(valid_texts))
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                embeddings = list(pool.map(_one, valid_texts))
            return embeddings
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            raise LLMError(f"Batch embedding failed: {e}") from e

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

    def _get_gemini_client_backup(self) -> Optional[Any]:
        """Return a Gemini client using GOOGLE_API_KEY_BACKUP, or None if not configured."""
        backup_key = getattr(self._settings, "GOOGLE_API_KEY_BACKUP", "")
        if not backup_key:
            return None
        if self._gemini_client_backup is None:
            from google import genai
            self._gemini_client_backup = genai.Client(api_key=backup_key)
        return self._gemini_client_backup

    def _get_gemini_client(self) -> Any:
        if self._gemini_client is None:
            from google import genai
            # In development, prefer GOOGLE_API_KEY_DEV so prod quota is never
            # consumed by local benchmark runs or experiments.
            dev_key = getattr(self._settings, "GOOGLE_API_KEY_DEV", "")
            is_dev = getattr(self._settings, "ENV", "production") == "development"
            api_key = (dev_key if (is_dev and dev_key) else None) or self._settings.GOOGLE_API_KEY
            if not api_key:
                raise LLMError("GOOGLE_API_KEY not set.")
            self._gemini_client = genai.Client(api_key=api_key)
        return self._gemini_client

    def _get_openai_client(self) -> Any:
        if self._openai_client is None:
            from openai import OpenAI
            api_key = getattr(self._settings, "OPENAI_API_KEY", None)
            if not api_key:
                raise LLMError("OPENAI_API_KEY not set.")
            self._openai_client = OpenAI(api_key=api_key)
        return self._openai_client

    def _get_groq_client(self) -> Any:
        """Return (and lazily init) an OpenAI-compatible client pointed at Groq's API."""
        if self._groq_client is None:
            from openai import OpenAI
            api_key = getattr(self._settings, "GROQ_API_KEY", "")
            if not api_key:
                raise LLMError("GROQ_API_KEY not set. Add it to .env to use Groq.")
            self._groq_client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
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

        response = self._call_with_timeout(
            lambda: client.chat.completions.create(**kwargs), 30.0
        )
        text = response.choices[0].message.content.strip()
        in_tok = response.usage.prompt_tokens if response.usage else 0
        out_tok = response.usage.completion_tokens if response.usage else 0
        return text, in_tok, out_tok
