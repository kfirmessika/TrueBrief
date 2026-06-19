"""
Near-duplicate / syndication collapse — collector/dedup.py

The cheap gate before extraction (architecture §10B.1 layer 2, §6 "syndication
collapse"): the same wire story runs on a dozen sites with different URLs. Exact-URL
dedup misses them. A 64-bit SimHash with a small Hamming radius catches them for free
(no LLM, no embedding), so we harvest the story once instead of N times.

Threshold discipline (§6): *very* high text similarity = syndication → collapse to one.
*Moderate* similarity = independent corroboration → keep (that's signal, not noise). The
small Hamming radius here is deliberately tight so it only collapses true near-identicals.

Pure, dependency-free, deterministic — unit-tested without LLM/DB.
"""

from __future__ import annotations

import hashlib
import re
from typing import List, Tuple

from truebrief.models.article import RawArticle

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Below this many tokens an article has too little signal to fingerprint safely
# (e.g. a bare headline) — never collapse it, to avoid false merges.
_MIN_TOKENS = 6

# Default Hamming radius: ≤ 3 of 64 bits differ ⇒ effectively the same text. [§10B.1]
DEFAULT_MAX_HAMMING = 3


def _tokens(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


def _hash_token(token: str) -> int:
    """Stable 64-bit hash of a token (hashlib, not Python's salted hash())."""
    return int.from_bytes(hashlib.md5(token.encode("utf-8")).digest()[:8], "big")


def simhash64(text: str) -> int:
    """Charikar SimHash over the text's tokens → a 64-bit fingerprint."""
    toks = _tokens(text)
    if not toks:
        return 0
    bits = [0] * 64
    for tok in toks:
        h = _hash_token(tok)
        for i in range(64):
            bits[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i in range(64):
        if bits[i] > 0:
            out |= 1 << i
    return out


def hamming(a: int, b: int) -> int:
    """Number of differing bits between two 64-bit fingerprints."""
    return (a ^ b).bit_count()


def _fingerprint(article: RawArticle) -> int | None:
    """SimHash of an article's title+text, or None if it's too thin to fingerprint."""
    text = f"{article.title or ''} {article.text or ''}".strip()
    toks = _tokens(text)
    if len(toks) < _MIN_TOKENS:
        return None
    bits = [0] * 64
    for tok in toks:
        h = _hash_token(tok)
        for i in range(64):
            bits[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i in range(64):
        if bits[i] > 0:
            out |= 1 << i
    return out


def collapse_near_duplicates(
    articles: List[RawArticle], max_hamming: int = DEFAULT_MAX_HAMMING
) -> Tuple[List[RawArticle], List[dict]]:
    """
    Collapse near-identical articles, keeping the first seen of each cluster.

    Returns ``(kept, collapsed)`` where ``collapsed`` is a list of
    ``{"url", "title", "near_to"}`` describing each dropped near-dup (for the trace).
    Order of ``kept`` follows the input. Thin articles (too few tokens) are always kept.
    """
    kept: List[RawArticle] = []
    fingerprints: List[int | None] = []
    collapsed: List[dict] = []

    for art in articles:
        fp = _fingerprint(art)
        match = None
        if fp is not None:
            for idx, kfp in enumerate(fingerprints):
                if kfp is not None and hamming(fp, kfp) <= max_hamming:
                    match = kept[idx]
                    break
        if match is not None:
            collapsed.append({
                "url": art.url,
                "title": (art.title or "")[:120],
                "near_to": match.url,
            })
        else:
            kept.append(art)
            fingerprints.append(fp)

    return kept, collapsed
