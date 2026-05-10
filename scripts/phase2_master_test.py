"""
Phase 2 Master Test Suite

Aggressively tests the edges and weak points of the Phase 2 Delta Engine components.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import sys

# Force utf-8 stdout for emojis on Windows
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Setup basic logging to suppress noisy external libs, but show our test logs
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("phase2_test")
logger.setLevel(logging.INFO)

from truebrief.ledger.database import get_supabase
from truebrief.collector.google_news_layer import GoogleNewsLayer
from truebrief.collector.query_builder import SearchQuery
from truebrief.ledger.ayr_engine import calculate_topic_ayr, update_topic_interval, ayr_to_interval, MIN_SAMPLES
from truebrief.ledger.query_rotator import QueryRotator, ROTATION_AFTER_SCANS, LOW_AYR_THRESHOLD
from truebrief.arbiter.temporal import temporal_overlap, adjusted_similarity
from truebrief.pipeline.runner import PipelineRunner
from truebrief.api.routes import create_topic, TopicCreate
from truebrief.models.article import RawArticle
from truebrief.arbiter.arbiter import Arbiter
from truebrief.ledger.vector_store import VectorStore
from truebrief.models.alpha import Alpha

db = get_supabase()

def run_tests():
    report = ["# Phase 2 Master Test Report\n"]
    passed = 0
    failed = 0

    def assert_test(name, condition, error_msg=""):
        nonlocal passed, failed
        if condition:
            logger.info(f"✅ PASS: {name}")
            report.append(f"- ✅ **PASS**: {name}")
            passed += 1
        else:
            logger.error(f"❌ FAIL: {name} - {error_msg}")
            report.append(f"- ❌ **FAIL**: {name} ({error_msg})")
            failed += 1

    # ==========================================
    # 1. Temporal Overlap & Fast Path Edge Cases
    # ==========================================
    logger.info("--- Testing Temporal Math & Arbiter Fast Path ---")
    d1 = datetime(2026, 4, 30, tzinfo=timezone.utc)
    d2 = datetime(2026, 4, 25, tzinfo=timezone.utc) # 5 days apart
    overlap = temporal_overlap(d1, d2)
    assert_test("Temporal math: 5 days apart yields overlap < 1.0", overlap < 1.0, f"overlap was {overlap}")
    
    # Apply discount
    base_score = 0.98 # Above auto-merge threshold
    discounted = adjusted_similarity(base_score, d1, d2)
    assert_test("Temporal discount: identical text drops below auto-merge threshold if dates differ", 
                discounted < 0.97, f"discounted score was {discounted}")

    # ==========================================
    # 2. AYR Engine Minimum Samples Guard
    # ==========================================
    logger.info("--- Testing AYR Engine Guards ---")
    test_topic_id = str(uuid4())
    db.table("topics").insert({"id": test_topic_id, "raw_query": "Test AYR", "poll_interval_seconds": 3600}).execute()
    
    # Fake 2 logs (below MIN_SAMPLES)
    logs = [
        {"topic_id": test_topic_id, "source_url": "x.com", "source_name": "X", "source_domain": "x.com", "decision": "NEW"},
        {"topic_id": test_topic_id, "source_url": "x.com", "source_name": "X", "source_domain": "x.com", "decision": "DUPLICATE"}
    ]
    db.table("source_quality_log").insert(logs).execute()
    
    stats = calculate_topic_ayr(test_topic_id)
    assert_test("AYR engine: marks stats as UNTRUSTED below MIN_SAMPLES", not stats["trusted"])
    
    # Fake 4 more logs (now 6 total, above MIN_SAMPLES)
    logs = [{"topic_id": test_topic_id, "source_url": "y.com", "source_name": "Y", "source_domain": "y.com", "decision": "NEW"} for _ in range(4)]
    db.table("source_quality_log").insert(logs).execute()
    
    stats = calculate_topic_ayr(test_topic_id)
    assert_test("AYR engine: marks stats as TRUSTED above MIN_SAMPLES", stats["trusted"])
    assert_test("AYR engine: properly calculates AYR (5 NEW / 6 Total = 83%)", stats["ayr"] > 0.8)
    
    # Clean up AYR topic
    db.table("topics").delete().eq("id", test_topic_id).execute()

    # ==========================================
    # 3. Query Rotator Lifecycle & Fallback
    # ==========================================
    logger.info("--- Testing Query Rotator Lifecycle ---")
    try:
        topic_id_rot = str(uuid4())
        db.table("topics").insert({"id": topic_id_rot, "raw_query": "Rotator Test", "poll_interval_seconds": 3600}).execute()
        
        rotator = QueryRotator()
        # 1. Initialize and select the first one (usually the anchor)
        v_id1, v_text1 = rotator.select_variant(topic_id_rot, "Rotator Test", ["Alt 1", "Alt 2"])
        rotator.record_result(v_id1, 0, topic_id_rot, "Rotator Test") # 0 alphas, but now 'used'
        
        # 2. Select the next one (should be "Alt 1")
        v_id2, v_text2 = rotator.select_variant(topic_id_rot, "Rotator Test", ["Alt 1", "Alt 2"])
        assert_test("Rotator: Selects an alternative variant", v_id2 != v_id1)
        
        # 3. Record 5 failures (0 alphas) to trigger rotation for the alternative
        if v_id2:
            for _ in range(ROTATION_AFTER_SCANS):
                rotator.record_result(v_id2, 0, topic_id_rot, "Rotator Test")
        
        # 4. Check if it retired and generated a new one
        if v_id2:
            res = db.table("topic_query_variants").select("*").eq("id", v_id2).single().execute()
            assert_test("Rotator: Retires variant after ROTATION_AFTER_SCANS with low AYR", not res.data.get("is_active", True))
        
        # 5. Total active should still be 3 (anchor, Alt 2, and the new generated replacement)
        res_all = db.table("topic_query_variants").select("*").eq("topic_id", topic_id_rot).execute()
        active_count = sum(1 for v in res_all.data if v.get("is_active", False))
        assert_test("Rotator: Keeps fallback active variants", active_count >= 2)

        db.table("topics").delete().eq("id", topic_id_rot).execute()
    except Exception as e:
        if 'schema cache' in str(e).lower() or 'not find the table' in str(e).lower():
            assert_test("Query Rotator Tests", False, "Missing Migration 003. Run 003_topic_query_variants.sql in Supabase.")
        else:
            assert_test("Query Rotator Tests", False, f"Unexpected error: {e}")

    # ==========================================
    # 4. Subscription Constraints
    # ==========================================
    logger.info("--- Testing Subscription Fan-out Logic ---")
    try:
        u1, u2 = str(uuid4()), str(uuid4())
        db.table("users").insert([{"id": u1, "email": f"{u1}@x.com"}, {"id": u2, "email": f"{u2}@x.com"}]).execute()
        
        t1 = create_topic(TopicCreate(raw_query="Subscription Test", user_id=u1))
        t2 = create_topic(TopicCreate(raw_query="subscription test", user_id=u2)) # Case insensitive duplicate
        
        assert_test("Subscriptions: Case-insensitive raw_query reuses same topic ID", t1["id"] == t2["id"])
        
        # Double subscribe u1 to the same topic
        try:
            t3 = create_topic(TopicCreate(raw_query="Subscription Test", user_id=u1))
            assert_test("Subscriptions: Gracefully handles duplicate subscribe attempt", True)
        except Exception as e:
            assert_test("Subscriptions: Gracefully handles duplicate subscribe attempt", False, str(e))
            
        db.table("topics").delete().eq("id", t1["id"]).execute()
        db.table("users").delete().in_("id", [u1, u2]).execute()
    except Exception as e:
        if 'schema cache' in str(e).lower() or 'not find the table' in str(e).lower():
            assert_test("Subscription Tests", False, "Missing Migration 004. Run 004_topic_subscriptions.sql in Supabase.")
        else:
            assert_test("Subscription Tests", False, f"Unexpected error: {e}")

    # ==========================================
    # 5. Empty Brief Suppression
    # ==========================================
    logger.info("--- Testing Empty Brief Suppression ---")
    from truebrief.pipeline.runner import PipelineRunner
    
    class DummyQueryBuilder:
        def build(self, topic):
            return SearchQuery(topic_name=topic, primary_query=topic, status="APPROVED")
            
    class DummyHarvester:
        def extract(self, article, topic_id=None):
            return [] # Returns ZERO alphas
            
    class DummyCollector:
        name = "Dummy"
        def search(self, query):
            return [RawArticle(title="Fake", url="http://fake.com", text="fake", source_name="fake", source_type="fake")]
            
    runner = PipelineRunner()
    runner.query_builder = DummyQueryBuilder()
    runner.sources = [DummyCollector()]
    runner.harvester = DummyHarvester()
    
    brief_content = runner.run("Empty Brief Test Topic")
    assert_test("Empty Brief Suppression: Pipeline returns empty string when 0 facts found", brief_content.strip() == "")
    
    # ==========================================
    # 6. Google News Decoder Edge Case
    # ==========================================
    logger.info("--- Testing Google News Layer Fallbacks ---")
    from unittest.mock import patch
    layer = GoogleNewsLayer()
    
    # Mock decode_google_news_url to throw exception
    with patch("truebrief.collector.google_news_layer.decode_google_news_url", side_effect=Exception("Fake Network Error")):
        # We manually craft a feedparser response mock
        with patch("truebrief.collector.google_news_layer.feedparser.parse") as mock_parse:
            class MockEntry:
                title = "Test Article"
                link = "https://news.google.com/rss/articles/CBMi..."
            
            class MockFeed:
                entries = [MockEntry()]
            
            mock_parse.return_value = MockFeed()
            
            articles = layer.search(SearchQuery(topic_name="x", primary_query="x"))
            
            assert_test("Google News Decoder: Safely falls back to obfuscated URL on decoder crash", 
                        len(articles) == 1 and articles[0].url == "https://news.google.com/rss/articles/CBMi...")


    # Final Report Output
    report.append(f"\n**Total Tests:** {passed + failed}")
    report.append(f"**Passed:** {passed}")
    report.append(f"**Failed:** {failed}\n")
    
    if failed == 0:
        report.append("🏆 **Conclusion:** Phase 2 components are robust and handle edge cases gracefully. Ready for Phase 3.")
    else:
        report.append("⚠️ **Conclusion:** Weak points detected. Fixes required before Phase 3.")
        
    with open("tests/phase2_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report))
        
    print("\n".join(report))

if __name__ == "__main__":
    run_tests()
