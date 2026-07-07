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
import logging
import time
from typing import Optional, List, Any

_GEMINI_GENERATE_TIMEOUT = 60   # seconds; 60s covers long-form briefs
_GEMINI_EMBED_TIMEOUT = 30      # seconds; embeddings should be fast

from truebrief.llm.pricing import compute_cost_usd

logger = logging.getLogger(__name__)

# Context variable: set this in pipeline_task before calling the LLM so every
# call in that task automatically logs against the correct pipeline_run row.
pipeline_run_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "pipeline_run_id", default=None
)


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

    def __init__(self) -> None:
        from config.settings import LLM_CONFIG, settings
        self._config = LLM_CONFIG
        self._settings = settings
        self._gemini_client: Optional[Any] = None
        self._gemini_client_backup: Optional[Any] = None
        self._openai_client: Optional[Any] = None
        self._groq_client: Optional[Any] = None
        self._local_embedder: Optional[Any] = None  # lazy-loaded LocalEmbedder

    def _get_local_embedder(self):
        """Return (and lazily init) the LocalEmbedder singleton."""
        if self._local_embedder is None:
            from truebrief.llm.local_embedder import LocalEmbedder
            self._local_embedder = LocalEmbedder(
                model_name=getattr(self._settings, "LOCAL_EMBED_MODEL", "BAAI/bge-base-en-v1.5")
            )
        return self._local_embedder

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

        for attempt in range(1, self.MAX_RETRIES + 1):
            t0 = time.monotonic()
            try:
                if provider == "gemini":
                    result, in_tok, out_tok = self._call_gemini_instrumented(
                        model, prompt, json_mode, system_prompt
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
                # Quota exhausted on primary key — switch to backup immediately (no wait).
                if provider == "gemini" and self._is_quota_exhausted(exc):
                    backup = self._get_gemini_client_backup()
                    if backup:
                        logger.warning(
                            "[LLM] Primary GOOGLE_API_KEY quota exhausted (step=%s). "
                            "Switching to GOOGLE_API_KEY_BACKUP. Reason: %s",
                            step_name, str(exc)[:200],
                        )
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
                            exc = bexc  # fall through to normal retry with backup's error

                if attempt < self.MAX_RETRIES:
                    wait = self._retry_wait(exc, attempt)
                    logger.warning(f"Attempt {attempt} failed: {exc}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise LLMError(f"Failed after {self.MAX_RETRIES} attempts: {exc}") from exc
        return ""

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
        if provider == "local":
            return self._get_local_embedder().embed(text)
        return self._embed_gemini(text, task_type=task_type)

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
        if provider == "local":
            return self._get_local_embedder().embed_batch(texts)
        return self._embed_batch_gemini(texts, task_type=task_type)

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

        Python threads cannot be forcibly killed, but the calling stack unwinds
        with a clean LLMError so the pipeline can handle it and the Celery task
        can mark itself FAILURE instead of hanging forever.
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func)
            try:
                return future.result(timeout=timeout_seconds)
            except concurrent.futures.TimeoutError:
                raise LLMError(
                    f"Gemini API call timed out after {timeout_seconds}s. "
                    "The API may be slow or rate-limited."
                )

    @staticmethod
    def _is_quota_exhausted(exc: Exception) -> bool:
        msg = str(exc)
        return "429" in msg or "RESOURCE_EXHAUSTED" in msg

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
            api_key = self._settings.GOOGLE_API_KEY
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
