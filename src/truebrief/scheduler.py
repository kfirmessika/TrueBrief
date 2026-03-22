import asyncio
import time
from .manager import SurveillanceManager

INTERVAL_SECONDS = 15 * 60  # 15 Minutes

async def run_scheduler():
    print("🕑 Initializing TrueBrief Scheduler...")
    manager = SurveillanceManager()
    
    print(f"🔄 Loop Started. Interval: {INTERVAL_SECONDS/60} minutes.")
    
    while True:
        try:
            print(f"\n⏰ Waking up for Cycle at {time.strftime('%H:%M:%S')}")
            await manager.run_cycle()
            print(f"💤 Sleeping for {INTERVAL_SECONDS/60} minutes...")
            time.sleep(INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\n🛑 Scheduler Stopped by User.")
            break
        except Exception as e:
            print(f"❌ Critical Error in Scheduler: {e}")
            time.sleep(60) # Retry after 1 minute on error

if __name__ == "__main__":
    asyncio.run(run_scheduler())
