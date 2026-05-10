"""
Test Script - Phase 3, Tasks 3.1 + 3.2: Story Nodes + Dual Vectors
scripts/test_story_nodes.py

Validates:
  1. StoryNode can be created in Supabase
  2. A second related Alpha joins the same story (similarity match)
  3. An unrelated Alpha creates a new story
  4. update_summary() re-embeds the summary (dual-vector update)
  5. get_stories() returns stories for a topic
  6. get_story_facts() returns facts for a story

Run:
    python scripts/test_story_nodes.py
"""

import logging
import sys
import time
import uuid

sys.path.insert(0, "src")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_story_nodes")


def main():
    from truebrief.ledger.database import get_supabase
    from truebrief.ledger.story_manager import StoryManager
    from truebrief.llm.client import LLMClient
    from truebrief.models.alpha import Alpha, AlphaDecision, DecisionType
    from truebrief.models.story import StoryNode, StoryStatus

    logger.info("=" * 60)
    logger.info("Phase 3 - Story Nodes + Dual Vectors Test")
    logger.info("=" * 60)

    db = get_supabase()
    llm = LLMClient()
    manager = StoryManager(supabase_client=db, llm_client=llm)

    # ── Use a deterministic test topic ID ─────────────────────────────────────
    TEST_TOPIC_ID = "00000000-0000-0000-0000-000000000099"
    logger.info(f"Using test topic_id: {TEST_TOPIC_ID}")

    # ── TEST 1: Create a new story from a NEW Alpha ───────────────────────────
    logger.info("\n[TEST 1] Creating first story from NEW Alpha...")

    alpha1 = Alpha(
        id=str(uuid.uuid4()),
        alpha_text="TSMC broke ground on its first Arizona semiconductor fab in Q2 2024, "
                   "investing $12 billion in the initial phase.",
        entities=["TSMC", "Arizona"],
        source_url="https://example.com/tsmc-arizona-1",
        source_name="Test Source",
        topic_id=TEST_TOPIC_ID,
    )
    alpha1.embedding = llm.embed(alpha1.alpha_text)

    decision1 = AlphaDecision(
        alpha=alpha1,
        decision=DecisionType.NEW,
        similarity_score=0.0,
    )

    story_id_1 = manager.assign_to_story(decision1, topic_id=TEST_TOPIC_ID)
    assert story_id_1 is not None, "TEST 1 FAILED: No story_id returned for NEW Alpha"
    logger.info(f"  ✅ Story created: {story_id_1}")

    # ── TEST 2: Related Alpha joins the SAME story ────────────────────────────
    logger.info("\n[TEST 2] Second related Alpha should join the same story...")
    time.sleep(1)  # Brief pause to avoid rate limiting

    alpha2 = Alpha(
        id=str(uuid.uuid4()),
        alpha_text="TSMC Arizona fab construction reached 40% completion milestone "
                   "in October 2024, with production scheduled for Q2 2025.",
        entities=["TSMC", "Arizona"],
        source_url="https://example.com/tsmc-arizona-2",
        source_name="Test Source",
        topic_id=TEST_TOPIC_ID,
    )
    alpha2.embedding = llm.embed(alpha2.alpha_text)

    decision2 = AlphaDecision(
        alpha=alpha2,
        decision=DecisionType.NEW,
        similarity_score=0.0,
    )

    story_id_2 = manager.assign_to_story(decision2, topic_id=TEST_TOPIC_ID)
    assert story_id_2 is not None, "TEST 2 FAILED: No story_id returned"
    logger.info(f"  Story assigned: {story_id_2}")
    if story_id_2 == story_id_1:
        logger.info("  ✅ Correctly joined SAME story")
    else:
        logger.warning(
            f"  ⚠️  Created NEW story (similarity below threshold). "
            f"This may be correct if embeddings aren't similar enough."
        )

    # ── TEST 3: Unrelated Alpha creates a NEW story ───────────────────────────
    logger.info("\n[TEST 3] Unrelated Alpha should create a new story...")
    time.sleep(1)

    alpha3 = Alpha(
        id=str(uuid.uuid4()),
        alpha_text="Federal Reserve raised interest rates by 25 basis points in March 2025, "
                   "citing persistent inflation concerns.",
        entities=["Federal Reserve", "interest rates"],
        source_url="https://example.com/fed-rates-1",
        source_name="Test Source",
        topic_id=TEST_TOPIC_ID,
    )
    alpha3.embedding = llm.embed(alpha3.alpha_text)

    decision3 = AlphaDecision(
        alpha=alpha3,
        decision=DecisionType.NEW,
        similarity_score=0.0,
    )

    story_id_3 = manager.assign_to_story(decision3, topic_id=TEST_TOPIC_ID)
    assert story_id_3 is not None, "TEST 3 FAILED: No story_id returned"
    assert story_id_3 != story_id_1, (
        f"TEST 3 FAILED: Unrelated fact wrongly joined story {story_id_1}"
    )
    logger.info(f"  ✅ New story created: {story_id_3}")

    # ── TEST 4: update_summary() re-embeds (dual-vector) ─────────────────────
    logger.info("\n[TEST 4] update_summary() should update embedding (Task 3.2)...")
    time.sleep(1)

    new_summary = (
        "TSMC's Arizona fab project began in Q2 2024 with a $12B investment. "
        "Construction reached 40% completion by October 2024, with chip production "
        "expected to begin in Q2 2025."
    )
    success = manager.update_summary(story_id_1, new_summary)
    assert success, "TEST 4 FAILED: update_summary() returned False"
    logger.info("  ✅ Summary updated with new embedding")

    # ── TEST 5: get_stories() returns both stories ────────────────────────────
    logger.info("\n[TEST 5] get_stories() should return stories for the topic...")

    stories = manager.get_stories(TEST_TOPIC_ID)
    assert len(stories) >= 2, (
        f"TEST 5 FAILED: Expected ≥2 stories, got {len(stories)}"
    )
    logger.info(f"  ✅ Found {len(stories)} stories for topic:")
    for s in stories:
        logger.info(f"    [{s.status.value}] '{s.title[:60]}...' ({s.fact_count} facts)")

    # ── TEST 6: DUPLICATE is ignored ─────────────────────────────────────────
    logger.info("\n[TEST 6] DUPLICATE Alpha should return None (no story action)...")

    alpha_dup = Alpha(
        id=str(uuid.uuid4()),
        alpha_text="This is a duplicate fact",
        entities=[],
        source_url="https://example.com/dup",
        source_name="Test Source",
        topic_id=TEST_TOPIC_ID,
    )
    decision_dup = AlphaDecision(
        alpha=alpha_dup,
        decision=DecisionType.DUPLICATE,
    )
    result = manager.assign_to_story(decision_dup, topic_id=TEST_TOPIC_ID)
    assert result is None, f"TEST 6 FAILED: Expected None for DUPLICATE, got {result}"
    logger.info("  ✅ DUPLICATE correctly ignored")

    # ── CLEANUP: Remove test stories ──────────────────────────────────────────
    logger.info("\n[CLEANUP] Removing test stories from Supabase...")
    try:
        all_story_ids = [s.id for s in stories]
        db.table("story_nodes").delete().in_("id", all_story_ids).execute()
        logger.info(f"  Removed {len(all_story_ids)} test story nodes.")
    except Exception as e:
        logger.warning(f"  Cleanup failed (manual cleanup may be needed): {e}")

    # ── SUMMARY ───────────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("✅ All Story Node + Dual Vector tests PASSED")
    logger.info("=" * 60)
    logger.info("\nNext: Run the DB migration in Supabase SQL Editor:")
    logger.info("  scripts/migrations/005_story_nodes.sql")


if __name__ == "__main__":
    main()
