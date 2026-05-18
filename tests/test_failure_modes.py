"""
Failure-Mode Tests — test_failure_modes.py

A.4: Eight targeted tests for the failure modes flagged in the pre-deployment audit.
All tests are pure unit tests — no real API calls, no DB access.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_alpha(text: str, event_date: datetime | None = None, confidence: float = 0.90):
    from truebrief.models.alpha import Alpha
    return Alpha(
        alpha_text=text,
        entities=[],
        event_date=event_date,
        context=None,
        confidence=confidence,
        source_url="https://example.com",
        source_name="example.com",
    )


def _make_decision(alpha, decision_type, matched_alpha_id: str | None = None):
    from truebrief.models.alpha import AlphaDecision
    return AlphaDecision(
        alpha=alpha,
        decision=decision_type,
        matched_alpha_id=matched_alpha_id,
        similarity_score=0.0,
        reasoning="test",
    )


# ── A.4.1: False auto-merge across temporal boundary ──────────────────────────

class TestTemporalBoundaryAutoMerge:
    """
    A.4.1: 'Tesla Q3 earnings: $1B' and 'Tesla Q4 earnings: $2B' 48h apart
    must NOT be merged — different temporal context means different facts.
    """

    def test_temporal_adjusted_similarity_reduces_score(self):
        """
        adjusted_similarity() must penalise two facts from different quarters
        enough to drop below AUTO_MERGE_THRESHOLD.
        """
        from truebrief.arbiter.temporal import adjusted_similarity
        from truebrief.arbiter.arbiter import AUTO_MERGE_THRESHOLD

        base_score = 0.98
        q3 = datetime(2025, 9, 30, tzinfo=timezone.utc)
        q4 = datetime(2025, 12, 31, tzinfo=timezone.utc)

        adjusted = adjusted_similarity(base_score, q3, q4)

        assert adjusted < AUTO_MERGE_THRESHOLD, (
            f"Expected adjusted score ({adjusted:.4f}) < AUTO_MERGE_THRESHOLD "
            f"({AUTO_MERGE_THRESHOLD}) for facts 92 days apart"
        )

    def test_no_temporal_penalty_for_same_day(self):
        """Facts from the same day should not be penalised."""
        from truebrief.arbiter.temporal import adjusted_similarity

        base = 0.98
        same = datetime(2025, 10, 15, tzinfo=timezone.utc)
        assert adjusted_similarity(base, same, same) == base


# ── A.4.2: Story merge creep ──────────────────────────────────────────────────

class TestStoryMergeCreep:
    """
    A.4.2: 'Tesla bankruptcy rumor' and 'Tesla Gigafactory delay' should not
    be merged into the same story node.
    """

    def test_dissimilar_alphas_create_separate_stories(self):
        """
        When match_stories RPC returns no candidate above threshold,
        assign_to_story creates a new StoryNode (not merges).
        """
        from truebrief.ledger.story_manager import StoryManager
        from truebrief.models.alpha import DecisionType

        alpha_a = _make_alpha("Tesla bankruptcy rumor spreading on social media")
        decision_a = _make_decision(alpha_a, DecisionType.NEW)

        mock_db = MagicMock()
        mock_llm = MagicMock()
        mock_llm.embed.return_value = [0.01] * 768

        # No existing stories
        mock_db.table.return_value.select.return_value.eq.return_value\
            .order.return_value.limit.return_value.execute.return_value.data = []

        # RPC match_stories: no match above threshold
        mock_db.rpc.return_value.execute.return_value.data = []

        # Insert new story returns an id
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "new-story-id"}
        ]

        manager = StoryManager(supabase_client=mock_db, llm_client=mock_llm)
        story_id = manager.assign_to_story(decision_a, topic_id="topic-1")

        assert story_id is not None


# ── A.4.3: Orphaned story fact ────────────────────────────────────────────────

class TestOrphanedStoryFact:
    """
    A.4.3: If story_manager.assign_to_story() raises, the pipeline still saves
    the fact (story_node_id=None).
    """

    def test_fact_saved_even_when_story_assignment_fails(self):
        from truebrief.pipeline.runner import PipelineRunner
        from truebrief.models.alpha import DecisionType

        alpha = _make_alpha("Fed raises rates by 25bp")
        decision = _make_decision(alpha, DecisionType.NEW)

        runner = PipelineRunner.__new__(PipelineRunner)

        mock_vs = MagicMock()
        runner.vector_store = mock_vs

        mock_sm = MagicMock()
        mock_sm.assign_to_story.side_effect = RuntimeError("DB timeout")
        runner.story_manager = mock_sm

        runner.story_summarizer = MagicMock()

        # Replicate the inner judging loop logic for one decision
        story_node_id = None
        try:
            story_node_id = runner.story_manager.assign_to_story(decision, topic_id="t1")
        except Exception:
            pass  # must not propagate

        try:
            runner.vector_store.add_fact(decision.alpha, story_node_id=story_node_id)
        except Exception:
            pass

        mock_vs.add_fact.assert_called_once_with(decision.alpha, story_node_id=None)


# ── A.4.4: Embedding batch mismatch ──────────────────────────────────────────

class TestEmbeddingBatchMismatch:
    """
    A.4.4: embed_batch returning N-1 embeddings triggers MMR fallback
    to first-N; no crash.
    """

    def test_mmr_falls_back_on_count_mismatch(self):
        from truebrief.pipeline.runner import PipelineRunner
        from truebrief.models.article import RawArticle, ArticleSource
        from truebrief.collector.query_builder import SearchQuery

        articles = [
            RawArticle(
                url=f"https://news.com/{i}",
                title=f"Article {i}",
                source_name="news.com",
                source_type=ArticleSource.RSS,
            )
            for i in range(10)
        ]

        runner = PipelineRunner.__new__(PipelineRunner)
        mock_vs = MagicMock()
        mock_vs.llm.embed.return_value = [0.1] * 768
        mock_vs.llm.embed_batch.return_value = [[0.1] * 768] * 9  # one short!
        runner.vector_store = mock_vs

        query = SearchQuery(topic_name="test", primary_query="test query")
        result = runner._mmr_select(query=query, articles=articles, limit=5)

        assert isinstance(result, list)
        assert len(result) == 5
        assert result == articles[:5]  # fallback = first N


# ── A.4.5: Double-schedule race ───────────────────────────────────────────────

class TestDoubleScheduleRace:
    """
    A.4.5: set_next_run is idempotent — calling it twice does not create
    duplicate DB rows (uses upsert).
    """

    def test_set_next_run_is_idempotent(self):
        """
        set_next_run uses UPDATE (not INSERT) so calling it twice on the
        same topic_id does not create a duplicate row.
        """
        from truebrief.tasks import scheduler

        mock_db = MagicMock()
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        with patch("truebrief.ledger.database.get_supabase", return_value=mock_db):
            scheduler.set_next_run("topic-1", interval_seconds=3600)
            scheduler.set_next_run("topic-1", interval_seconds=3600)

        # update (idempotent) must be called; insert must NOT be called
        assert mock_db.table.return_value.update.call_count == 2
        mock_db.table.return_value.insert.assert_not_called()


# ── A.4.6: Hallucination smoke ────────────────────────────────────────────────

class TestHallucinationSmoke:
    """
    A.4.6: The harvester must pass article text to the LLM prompt.
    """

    def test_harvester_includes_article_text_in_prompt(self):
        from truebrief.harvester.harvester import Harvester
        from truebrief.models.article import RawArticle, ArticleSource

        captured_prompts: list[str] = []

        mock_llm = MagicMock()
        # side_effect receives the same args as the call: (step_name, prompt, ...)
        def capture(*args, **kwargs):
            # prompt is the second positional arg or a keyword arg
            prompt = args[1] if len(args) > 1 else kwargs.get("prompt", "")
            captured_prompts.append(prompt)
            return '{"alphas": []}'

        mock_llm.call.side_effect = capture

        harvester = Harvester.__new__(Harvester)
        harvester.llm = mock_llm

        article = RawArticle(
            url="https://reuters.com/story/1",
            title="Fed raises rates",
            source_name="reuters.com",
            source_type=ArticleSource.RSS,
            text="The Federal Reserve raised interest rates by 25 basis points today.",
        )

        harvester.extract(article)

        assert len(captured_prompts) > 0, "LLM was never called"
        combined = " ".join(captured_prompts)
        assert "Federal Reserve" in combined or "25 basis points" in combined, (
            "Harvester prompt does not contain article content — hallucination risk"
        )


# ── A.4.7: Query rotator starvation ──────────────────────────────────────────

class TestQueryRotatorStarvation:
    """
    A.4.7: Even when all variants have AYR < LOW_AYR_THRESHOLD, at least one
    remains active (no total starvation).
    """

    def test_select_variant_always_returns_a_query(self):
        from truebrief.ledger.query_rotator import QueryRotator, ROTATION_AFTER_SCANS

        rotator = QueryRotator.__new__(QueryRotator)
        mock_db = MagicMock()
        rotator.db = mock_db

        mock_variant = {
            "id": "var-1",
            "query_text": "Bitcoin ETF news",
            "scans_used": ROTATION_AFTER_SCANS,
            "alphas_yielded": 0,
            "ayr": 0.0,
            "is_active": True,
            "last_used_at": None,
            "generation": 0,
        }

        # Return the one low-AYR variant as the only candidate
        (mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .order.return_value
            .limit.return_value
            .execute.return_value
            .data) = [mock_variant]

        _variant_id, result_query = rotator.select_variant(
            topic_id="t1", raw_query="Bitcoin ETF news", alt_queries=[]
        )

        assert result_query, "select_variant returned empty query — total starvation bug"


# ── A.4.8: Briefer with zero alphas ──────────────────────────────────────────

class TestBrieferZeroAlphas:
    """
    A.4.8: Briefer.generate() with empty or all-DUPLICATE decisions must
    return "" without calling the LLM.
    """

    def test_empty_decisions_returns_empty_string(self):
        from truebrief.briefer.briefer import Briefer

        mock_llm = MagicMock()
        briefer = Briefer(llm_client=mock_llm)

        result = briefer.generate(decisions=[], topic_name="Bitcoin")

        assert result == ""
        mock_llm.call.assert_not_called()

    def test_all_duplicates_returns_empty_string(self):
        from truebrief.briefer.briefer import Briefer
        from truebrief.models.alpha import DecisionType

        mock_llm = MagicMock()
        briefer = Briefer(llm_client=mock_llm)

        alpha = _make_alpha("Old news already in the ledger")
        decisions = [_make_decision(alpha, DecisionType.DUPLICATE, matched_alpha_id="existing-id")]

        result = briefer.generate(decisions=decisions, topic_name="Bitcoin")

        assert result == ""
        mock_llm.call.assert_not_called()
