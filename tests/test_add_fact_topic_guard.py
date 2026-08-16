"""Regression test for the NULL topic_id guard added 2026-08-13.

Root cause: a live-DB audit found 675 known_facts rows with topic_id IS NULL
(2026-06-08 to 2026-08-13), traced to scripts/run_pipeline.py calling
PipelineRunner().run(topic) with no topic_id, which flows straight through to
VectorStore.add_fact(). An orphaned row can never be deduped again —
find_similar() is always topic-scoped — so add_fact() must fail loud instead
of silently inserting one.
"""
from __future__ import annotations

import pytest

from truebrief.ledger.vector_store import VectorStore
from truebrief.models.alpha import Alpha


def make_alpha(topic_id) -> Alpha:
    return Alpha(
        alpha_text="Some real fact.",
        entities=[],
        source_url="https://example.com/a",
        source_name="example.com",
        topic_id=topic_id,
    )


class TestAddFactTopicGuard:
    def test_missing_topic_id_raises_before_any_db_call(self):
        # supabase_client=None would normally blow up on first real use (get_supabase()
        # needs env/network) — passing a sentinel object with no attributes proves the
        # guard fires BEFORE any DB/embedding work, not just "eventually raises something".
        vs = VectorStore.__new__(VectorStore)
        vs.db = object()  # would AttributeError immediately if the guard didn't short-circuit
        vs.llm = object()

        with pytest.raises(ValueError, match="topic_id"):
            vs.add_fact(make_alpha(topic_id=None))

    def test_empty_string_topic_id_also_rejected(self):
        vs = VectorStore.__new__(VectorStore)
        vs.db = object()
        vs.llm = object()

        with pytest.raises(ValueError, match="topic_id"):
            vs.add_fact(make_alpha(topic_id=""))
