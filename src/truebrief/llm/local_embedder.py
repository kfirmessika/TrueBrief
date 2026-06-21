"""
Local Embedder - llm/local_embedder.py

Sentence-transformers based embedder that runs fully on-device (CPU/GPU).
No API calls, no quota limits, no cost beyond CPU time.

Why: Gemini free-tier caps at 100 embed calls/min. A single MMR pass on a
100-article pool fires 100 calls simultaneously → instant quota exhaust.
Local inference runs as ONE true batched forward pass in <500ms on CPU.

Model: BAAI/bge-base-en-v1.5
  - 768 dims  → same as gemini-embedding-2 (zero pgvector migration)
  - MTEB ~64  → vs Gemini ~73. Gap is small for short news titles / fact dedup.
  - 420 MB    → downloads once on first use, cached in ~/.cache/huggingface
  - ~120ms    → for a batch of 100 titles on a modern CPU

Keep EMBED_PROVIDER=gemini in .env to use Gemini (default).
Set EMBED_PROVIDER=local to use this module instead.
"""

from __future__ import annotations

import logging
from typing import List, Optional, TYPE_CHECKING

logger = logging.getLogger(__name__)

# Default model: 768-dim, same as gemini-embedding-2 → no pgvector migration needed.
# Switch to bge-small-en-v1.5 (384-dim) for faster inference at slightly lower quality.
DEFAULT_MODEL = "BAAI/bge-base-en-v1.5"


class LocalEmbedder:
    """
    Wraps sentence-transformers with the same API as LLMClient.embed / embed_batch.
    Lazy-loads the model on first call so import is instant.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self._model_name = model_name
        self._model = None   # loaded on first embed call

    def _load(self):
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is required for local embeddings. "
                "Run: pip install sentence-transformers"
            ) from e
        logger.info(f"[LocalEmbedder] Loading model '{self._model_name}' (first call only)...")
        self._model = SentenceTransformer(self._model_name)
        dim = getattr(self._model, "get_embedding_dimension", None) or \
              getattr(self._model, "get_sentence_embedding_dimension", None)
        logger.info(f"[LocalEmbedder] Model ready. Dimension: {dim() if dim else '?'}")

    def embed(self, text: str) -> List[float]:
        """Embed a single string. Returns a list of floats."""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of strings in ONE batched forward pass. No quota limits."""
        if not texts:
            return []
        self._load()
        # normalize_embeddings=True → cosine similarity = dot product (consistent with Gemini)
        clean = [t if (t and t.strip()) else "[empty]" for t in texts]
        vecs = self._model.encode(
            clean,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=64,
        )
        return [v.tolist() for v in vecs]

    @property
    def dimension(self) -> Optional[int]:
        """Return embedding dimension, or None if model not loaded yet."""
        if self._model is None:
            return None
        fn = getattr(self._model, "get_embedding_dimension", None) or \
             getattr(self._model, "get_sentence_embedding_dimension", None)
        return fn() if fn else None
