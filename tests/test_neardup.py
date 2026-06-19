"""Tests for near-duplicate / syndication collapse (collector/dedup.py)."""

from __future__ import annotations

from truebrief.collector.dedup import collapse_near_duplicates, hamming, simhash64
from truebrief.models.article import ArticleSource, RawArticle

# A realistic article-length body — SimHash@Hamming≤3 is stable on long text
# (which is what real articles are; thin headlines are excluded by _MIN_TOKENS).
_LONG = (
    "The Federal Reserve held interest rates steady on Wednesday and signaled two "
    "potential cuts later this year as inflation continued to cool toward the central "
    "bank's target. Policymakers voted unanimously to keep the benchmark federal funds "
    "rate in its current range, citing a labor market that remains resilient even as "
    "hiring has slowed from last year's torrid pace. In a statement, the committee said "
    "economic activity had continued to expand at a solid pace and that the risks to its "
    "employment and inflation goals had moved into better balance. The chair told "
    "reporters that officials wanted to see further evidence that price pressures were "
    "durably easing before lowering borrowing costs, and stressed that future decisions "
    "would depend on the incoming data rather than a preset path. Investors had widely "
    "expected the decision, and stocks were little changed in afternoon trading as bond "
    "yields edged lower across the curve."
)


def _art(url: str, title: str, text: str | None = None) -> RawArticle:
    return RawArticle(
        url=url, title=title, source_name="src",
        source_type=ArticleSource.RSS, text=text,
    )


def test_simhash_is_deterministic_and_equal_for_same_text():
    assert simhash64(_LONG) == simhash64(_LONG)
    assert hamming(simhash64(_LONG), simhash64(_LONG)) == 0


def test_identical_articles_collapse_to_one():
    arts = [
        _art("https://a.com/x", "Fed holds rates", _LONG),
        _art("https://b.com/y", "Fed holds rates", _LONG),  # syndicated copy
        _art("https://c.com/z", "Fed holds rates", _LONG),
    ]
    kept, collapsed = collapse_near_duplicates(arts)
    assert len(kept) == 1
    assert kept[0].url == "https://a.com/x"        # first seen is kept
    assert len(collapsed) == 2
    assert collapsed[0]["near_to"] == "https://a.com/x"


def test_formatting_only_differences_collapse():
    # Syndicated copy that differs only in case / punctuation / whitespace — the
    # tokenizer normalizes these, so it's the same fingerprint → collapse. (A copy that
    # ADDS real content is intentionally NOT collapsed: that may be corroboration.)
    near = "   " + _LONG.upper().replace(".", " ... ").replace(",", " ; ")
    kept, collapsed = collapse_near_duplicates([
        _art("https://a.com/x", "Fed", _LONG),
        _art("https://b.com/y", "Fed", near),
    ])
    assert len(kept) == 1
    assert len(collapsed) == 1


def test_distinct_articles_are_both_kept():
    other = (
        "A magnitude six earthquake struck off the coast of northern Japan early "
        "Thursday, prompting a brief tsunami advisory that was later lifted by "
        "authorities with no reports of significant damage."
    )
    kept, collapsed = collapse_near_duplicates([
        _art("https://a.com/x", "Fed holds rates", _LONG),
        _art("https://b.com/y", "Quake hits Japan", other),
    ])
    assert len(kept) == 2
    assert collapsed == []


def test_thin_articles_are_never_collapsed():
    # Bare headlines (< _MIN_TOKENS) must not be merged even if similar.
    kept, collapsed = collapse_near_duplicates([
        _art("https://a.com/x", "Fed", None),
        _art("https://b.com/y", "Fed", None),
    ])
    assert len(kept) == 2
    assert collapsed == []


def test_order_is_preserved():
    other = (
        "Researchers published a new study describing a method to capture carbon "
        "dioxide directly from seawater at lower energy cost than air capture."
    )
    arts = [
        _art("https://a.com/1", "A", _LONG),
        _art("https://b.com/2", "B", other),
        _art("https://c.com/3", "C", _LONG),  # dup of #1
    ]
    kept, collapsed = collapse_near_duplicates(arts)
    assert [k.url for k in kept] == ["https://a.com/1", "https://b.com/2"]
    assert len(collapsed) == 1 and collapsed[0]["url"] == "https://c.com/3"
