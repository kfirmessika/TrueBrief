"""
LLM Abstraction Layer — llm/client.py

Thin, config-driven wrapper around any LLM provider.
Switch providers by changing LLM_CONFIG in config/settings.py — zero code changes here.

Usage:
    from truebrief.llm.client import LLMClient
    client = LLMClient()
    response = client.call("harvester", "Extract facts from: ...")
"""

from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy imports — only the provider you actually use gets imported.
# This keeps startup fast and avoids ImportError for unused providers.


class LLMError(Exception):
    """Raised when an LLM call fails after all retries."""


class LLMClient:
    """
    Call any LLM via config. Switch providers by changing settings.py.

    Supported providers:
      - "gemini"  → google-generativeai (primary for Phase 1/2)
      - "openai"  → openai (optional upgrade for Harvester in production)
    """

    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 5.0   # Base delay; doubles on each retry (exponential backoff)

    def __init__(self) -> None:
        # Import here to avoid circular imports and allow env loading before use
        from config.settings import LLM_CONFIG, settings
        self._config = LLM_CONFIG
        self._settings = settings
        self._gemini_client: Optional[object] = None    # initialized lazily
        self._openai_client: Optional[object] = None    # initialized lazily

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def call(
        self,
        step_name: str,
        prompt: str,
        json_mode: bool = False,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Call the LLM configured for `step_name`.

        Args:
            step_name:      Key in LLM_CONFIG (e.g. "harvester", "arbiter").
            prompt:         The user/task prompt.
            json_mode:      Hint to the provider to return valid JSON.
            system_prompt:  Optional system-level instruction (provider-dependent).

        Returns:
            The model's response as a plain string.

        Raises:
            LLMError: If all retries are exhausted or the step is misconfigured.
        """
        if step_name not in self._config:
            raise LLMError(
                f"No LLM config found for step '{step_name}'. "
                f"Available steps: {list(self._config.keys())}"
            )

        cfg = self._config[step_name]
        provider = cfg["provider"]
        model = cfg["model"]

        logger.debug(f"[LLM] {step_name} → {provider}/{model} (json_mode={json_mode})")

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                if provider == "gemini":
                    return self._call_gemini(model, prompt, json_mode, system_prompt)
                elif provider == "openai":
                    return self._call_openai(model, prompt, json_mode, system_prompt)
                else:
                    raise LLMError(f"Unknown provider '{provider}' for step '{step_name}'.")
            except LLMError:
                raise  # Config errors — don't retry
            except Exception as exc:
                wait = self.RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                if attempt < self.MAX_RETRIES:
                    logger.warning(
                        f"[LLM] {step_name} attempt {attempt}/{self.MAX_RETRIES} failed "
                        f"({exc!r}). Retrying in {wait:.0f}s…"
                    )
                    time.sleep(wait)
                else:
                    raise LLMError(
                        f"[LLM] {step_name} failed after {self.MAX_RETRIES} attempts. "
                        f"Last error: {exc!r}"
                    ) from exc

        raise LLMError("Unexpected: retry loop exited without result.")  # pragma: no cover

    # -------------------------------------------------------------------------
    # Provider implementations
    # -------------------------------------------------------------------------

    def _get_gemini_client(self) -> object:
        """Lazy-initialize the Gemini client (avoids slow import at startup)."""
        if self._gemini_client is None:
            try:
                import google.generativeai as genai  # type: ignore[import]
            except ImportError:
                raise LLMError(
                    "google-generativeai is not installed. "
                    "Run: pip install google-generativeai>=0.8.0"
                )
            api_key = self._settings.GOOGLE_API_KEY
            if not api_key:
                raise LLMError(
                    "GOOGLE_API_KEY is not set. Add it to your .env file."
                )
            genai.configure(api_key=api_key)
            self._gemini_client = genai
        return self._gemini_client

    def _call_gemini(
        self,
        model: str,
        prompt: str,
        json_mode: bool,
        system_prompt: Optional[str],
    ) -> str:
        genai = self._get_gemini_client()

        generation_config: dict = {}
        if json_mode:
            generation_config["response_mime_type"] = "application/json"

        model_kwargs: dict = {"model_name": model}
        if system_prompt:
            model_kwargs["system_instruction"] = system_prompt

        generative_model = genai.GenerativeModel(
            **model_kwargs,
            generation_config=generation_config if generation_config else None,
        )

        response = generative_model.generate_content(prompt)
        return response.text.strip()

    def _get_openai_client(self) -> object:
        """Lazy-initialize the OpenAI client."""
        if self._openai_client is None:
            try:
                from openai import OpenAI  # type: ignore[import]
            except ImportError:
                raise LLMError(
                    "openai is not installed. Run: pip install openai>=1.0.0"
                )
            api_key = getattr(self._settings, "OPENAI_API_KEY", None)
            if not api_key:
                raise LLMError(
                    "OPENAI_API_KEY is not set. Add it to your .env file."
                )
            self._openai_client = OpenAI(api_key=api_key)
        return self._openai_client

    def _call_openai(
        self,
        model: str,
        prompt: str,
        json_mode: bool,
        system_prompt: Optional[str],
    ) -> str:
        client = self._get_openai_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {"model": model, "messages": messages}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content.strip()
