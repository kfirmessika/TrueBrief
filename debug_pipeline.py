import sys
import asyncio
from src.truebrief.memory import FactLedger
from src.truebrief.manager import SurveillanceManager
from src.truebrief.topics import TopicManager

async def test_run():
    print("=== DEEP PIPELINE DIAGNOSTIC START ===", flush=True)
    
    try:
        ledger = FactLedger()
        mgr = SurveillanceManager(ledger=ledger)
        tm = TopicManager()
    except Exception as e:
        print(f"❌ FAILED TO INIT MODULES: {e}", flush=True)
        return

    topics = tm.get_all_topics()
    war_topic = next((t for t in topics if "iran regional" in t["name"].lower()), None)
    if not war_topic:
        print("❌ Topic 'war' not found in db. Cannot simulate.", flush=True)
        return
        
    print(f"📡 TARGET FOUND: '{war_topic['name']}'", flush=True)
    print(f"🔗 SOURCES IN DB: {war_topic['sources']}", flush=True)
    
    try:
        print("🚀 EXECUTING MANAGER.SCAN_TOPIC...", flush=True)
        await mgr.scan_topic(war_topic)
    except Exception as e:
        print(f"💥 CRASH IN MANAGER.SCAN_TOPIC: {e}", flush=True)
        import traceback
        traceback.print_exc()
        
    print("=== DEEP PIPELINE DIAGNOSTIC END ===", flush=True)

if __name__ == "__main__":
    asyncio.run(test_run())
