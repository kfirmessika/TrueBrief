"""
Tests for the Stage 2 fix to VectorStore.find_tally_match() (2026-08-16,
vector_store.py:398-478).

Root cause fixed: the old version returned the entity-overlap-gated candidate
with the MOST RECENT event_date, not the most similar one. That could hand IC1's
number-equality guard the WRONG reference fact on a verbatim duplicate when a
more-recent, less-similar tally row existed for the same entities — confirmed
live (red-team C1-01/C1-06) and independently on the Stage 3 holdout (H1).

Fix: among entity-gated candidates, rank by cosine similarity between
`alpha.embedding` and each candidate's stored `alpha_embedding`, falling back to
date order when no usable embeddings exist. These tests exercise the real
`VectorStore.find_tally_match()` against a fake Supabase client double — no
network, no LLM.
"""
from __future__ import annotations

from datetime import datetime

from truebrief.ledger.vector_store import VectorStore
from truebrief.models.alpha import Alpha


def _alpha(entities: list[str], embedding=None) -> Alpha:
    return Alpha(
        alpha_text="incoming tally fact",
        entities=entities,
        source_url="https://a.com/x",
        source_name="Test",
        topic_id="t1",
        event_class="tally",
        embedding=embedding,
    )


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    """Mimics the chained .table().select().eq().eq().order().limit().execute() calls."""

    def __init__(self, rows):
        self._rows = rows

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return _FakeResponse(self._rows)


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows

    def table(self, _name):
        return _FakeQuery(self._rows)


def _row(id_, entities, event_date, embedding=None, alpha_text="tally row"):
    return {
        "id": id_,
        "alpha_text": alpha_text,
        "alpha_embedding": embedding,
        "entities": entities,
        "event_date": event_date,
        "source_url": "https://b.com/y",
        "source_domain": "b.com",
        "context": None,
        "confidence": 1.0,
        "event_class": "tally",
    }


def _make_store(rows) -> VectorStore:
    store = VectorStore.__new__(VectorStore)
    store.db = _FakeDB(rows)
    return store


# Two orthogonal-ish unit vectors and a "near duplicate" of A, for cheap cosine tests.
EMB_A = [1.0, 0.0, 0.0]
EMB_A_NEAR = [0.99, 0.14, 0.0]   # cosine(EMB_A, EMB_A_NEAR) ~ 0.99
EMB_B = [0.0, 1.0, 0.0]         # cosine(EMB_A, EMB_B) = 0.0


def test_picks_most_similar_not_most_recent():
    """The core regression: a MORE RECENT but LESS SIMILAR row must lose to an
    OLDER but near-identical row, when both pass the entity-overlap gate."""
    rows = [
        # Query orders by event_date desc, so this (2026-08-14, dissimilar) comes first.
        _row("recent-dissimilar", ["Iran", "US"], "2026-08-14", embedding=EMB_B),
        _row("older-near-dup", ["Iran", "US"], "2026-08-10", embedding=EMB_A_NEAR),
    ]
    store = _make_store(rows)
    alpha = _alpha(["Iran", "US"], embedding=EMB_A)

    match = store.find_tally_match(alpha)

    assert match is not None
    assert match.id == "older-near-dup"


def test_falls_back_to_date_order_when_no_embeddings():
    rows = [
        _row("recent", ["Iran"], "2026-08-14", embedding=None),
        _row("older", ["Iran"], "2026-08-10", embedding=None),
    ]
    store = _make_store(rows)
    alpha = _alpha(["Iran"], embedding=EMB_A)

    match = store.find_tally_match(alpha)

    assert match is not None
    assert match.id == "recent"  # falls back to date order (query's own order)


def test_falls_back_to_date_order_when_alpha_has_no_embedding():
    rows = [
        _row("recent", ["Iran"], "2026-08-14", embedding=EMB_B),
        _row("older", ["Iran"], "2026-08-10", embedding=EMB_A_NEAR),
    ]
    store = _make_store(rows)
    alpha = _alpha(["Iran"], embedding=None)  # no embedding on the incoming alpha

    match = store.find_tally_match(alpha)

    assert match is not None
    assert match.id == "recent"


def test_gracefully_skips_rows_missing_embedding_among_others():
    """A mix of embedded and non-embedded rows: only the embedded ones are ranked;
    the un-embedded row must not crash the comparison."""
    rows = [
        _row("no-embedding", ["Iran"], "2026-08-14", embedding=None),
        _row("has-embedding", ["Iran"], "2026-08-10", embedding=EMB_A_NEAR),
    ]
    store = _make_store(rows)
    alpha = _alpha(["Iran"], embedding=EMB_A)

    match = store.find_tally_match(alpha)

    assert match is not None
    assert match.id == "has-embedding"  # only usable-embedding candidate


def test_entity_overlap_gate_still_applies():
    """A textually/vector-similar row that fails the entity-overlap gate must
    never be returned, even though it would rank highest by similarity."""
    rows = [
        _row("wrong-entities", ["Yemen"], "2026-08-14", embedding=EMB_A),  # perfect sim, wrong entities
        _row("right-entities", ["Iran"], "2026-08-10", embedding=EMB_B),   # zero sim, right entities
    ]
    store = _make_store(rows)
    alpha = _alpha(["Iran"], embedding=EMB_A)

    match = store.find_tally_match(alpha)

    assert match is not None
    assert match.id == "right-entities"


def test_no_candidates_returns_none():
    rows = [_row("x", ["Yemen"], "2026-08-14", embedding=EMB_A)]
    store = _make_store(rows)
    alpha = _alpha(["Iran"], embedding=EMB_A)

    assert store.find_tally_match(alpha) is None


def test_json_string_embedding_is_parsed():
    """Supabase sometimes returns pgvector columns as JSON strings — must not crash."""
    import json
    rows = [
        _row("recent", ["Iran"], "2026-08-14", embedding=json.dumps(EMB_B)),
        _row("older", ["Iran"], "2026-08-10", embedding=json.dumps(EMB_A_NEAR)),
    ]
    store = _make_store(rows)
    alpha = _alpha(["Iran"], embedding=EMB_A)

    match = store.find_tally_match(alpha)

    assert match is not None
    assert match.id == "older"
