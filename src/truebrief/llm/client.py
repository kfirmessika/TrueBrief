"""
LLM Abstraction Layer - llm/client.py

Thin, config-driven wrapper around any LLM provider.
Switch providers by changing LLM_CONFIG in config/settings.py - zero code changes here.
Uses the modern google-genai SDK for Gemini.
"""

from __future__ import annotations

import logging
import time
from typing import Optional, List, Any

logger = logging.getLogger(__name__)

class LLMError(Exception):
    """Raised when an LLM call fails after all retries."""

class LLMClient:
    """
    Call any LLM via config. Switch providers by changing settings.py.

    Supported providers:
      - "gemini"  → google-genai (modern SDK)
      - "openai"  → openai
    """

    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 5.0

    def __init__(self) -> None:
        from config.settings import LLM_CONFIG, settings
        self._config = LLM_CONFIG
        self._settings = settings
        self._gemini_client: Optional[Any] = None
        self._openai_client: Optional[Any] = None

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
            try:
                if provider == "gemini":
                    return self._call_gemini(model, prompt, json_mode, system_prompt)
                elif provider == "openai":
                    return self._call_openai(model, prompt, json_mode, system_prompt)
                else:
                    raise LLMError(f"Unknown provider '{provider}'.")
            except Exception as exc:
                if attempt < self.MAX_RETRIES:
                    wait = self.RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                    logger.warning(f"Attempt {attempt} failed: {exc}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise LLMError(f"Failed after {self.MAX_RETRIES} attempts: {exc}") from exc
        return ""

    def embed(self, text: str) -> List[float]:
        """Generate a vector embedding for a single text string."""
        if not text or not text.strip():
            logger.warning("Attempted to embed empty text. Returning zero vector.")
            return [0.0] * 768

        client = self._get_gemini_client()
        from google.genai import types
        try:
            res = client.models.embed_content(
                model="models/gemini-embedding-2",
                contents=[text],
                config=types.EmbedContentConfig(
                    output_dimensionality=768,
                    task_type="RETRIEVAL_DOCUMENT"
                )
            )
            if not res or not res.embeddings:
                raise LLMError("Gemini returned no embeddings for the provided text.")
            return res.embeddings[0].values
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            raise LLMError(f"Embedding failed: {e}") from e

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate vector embeddings for a list of strings."""
        if not texts:
            return []
        
        # Filter out empty strings which cause Gemini to error
        valid_texts = [t if (t and t.strip()) else "[empty]" for t in texts]

        client = self._get_gemini_client()
        from google.genai import types
        try:
            res = client.models.embed_content(
                model="models/gemini-embedding-2",
                contents=valid_texts,
                config=types.EmbedContentConfig(
                    output_dimensionality=768,
                    task_type="RETRIEVAL_DOCUMENT"
                )
            )
            if not res or not res.embeddings:
                raise LLMError("Gemini returned no embeddings for the batch.")
            
            embeddings = [emb.values for emb in res.embeddings]
            if len(embeddings) != len(texts):
                logger.warning(f"Batch embedding returned {len(embeddings)} items for {len(texts)} inputs.")
            
            return embeddings
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            raise LLMError(f"Batch embedding failed: {e}") from e

    def _get_gemini_client(self) -> Any:
        if self._gemini_client is None:
            from google import genai
            api_key = self._settings.GOOGLE_API_KEY
            if not api_key:
                raise LLMError("GOOGLE_API_KEY not set.")
            self._gemini_client = genai.Client(api_key=api_key)
        return self._gemini_client

    def _call_gemini(
        self,
        model: str,
        prompt: str,
        json_mode: bool,
        system_prompt: Optional[str],
    ) -> str:
        client = self._get_gemini_client()
        from google.genai import types
        
        config = types.GenerateContentConfig(
            system_instruction=system_prompt if system_prompt else None,
            response_mime_type="application/json" if json_mode else "text/plain",
        )
        
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )
            if not response or not response.text:
                logger.warning(f"Gemini returned empty text for model {model}. Possible safety block.")
                return "{}" if json_mode else ""
            return response.text.strip()
        except Exception as e:
            # If it's a safety block, sometimes text access raises an error
            if "safety" in str(e).lower():
                logger.warning(f"Gemini call blocked by safety filters: {e}")
                return "{}" if json_mode else "Content blocked by safety filters."
            raise e

    def _get_openai_client(self) -> Any:
        if self._openai_client is None:
            from openai import OpenAI
            api_key = getattr(self._settings, "OPENAI_API_KEY", None)
            if not api_key:
                raise LLMError("OPENAI_API_KEY not set.")
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
