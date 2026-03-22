import asyncio
from truebrief.engine import NoveltyFilter
from truebrief.memory import FactLedger

async def run_test():
    print("🕰️ Running Time Detective Verification...")
    
    # Use the real ledger but we will just pass mock data
    engine = NoveltyFilter()
    
    # 1. Inject History (Base Fact)
    history_fact = "Saudi Aramco cancelled its Blue Hydrogen plant due to extreme costs."
    history_url = "https://reuters.com/aramco-2024"
    history_date = "2024-01-01"
    
    print("\n--- 1. Injecting History ---")
    print(f"Fact: {history_fact} ({history_date})")
    engine.commit(history_fact, history_url, history_date)
    
    # 2. Inject DUPLICATE (Recitation)
    # Different wording, same event, explicitly citing the old event.
    duplicate_fact = "Remember last year when Aramco halted their hydrogen facility because it was too expensive?"
    dup_url = "https://bloomberg.com/aramco-recap"
    dup_date = "2025-01-01"
    
    print("\n--- 2. Testing Recitation (Should Block) ---")
    print(f"Fact: {duplicate_fact} ({dup_date})")
    is_nov, score, match = engine.memory.is_novel(duplicate_fact)
    print(f"Vector Similarity Score: {score:.3f} (Novel? {is_nov})")
    
    is_saved, final_fact = engine.process_extracted_alpha(duplicate_fact, dup_url, dup_date)
    print(f"Outcome: Saved={is_saved}, Final Fact={final_fact}")
    assert is_saved == False, "Engine failed to block Recitation!"
    
    # 3. Inject UPDATE (New Development)
    update_fact = "Saudi Aramco announced it is restarting the Blue Hydrogen plant with a new $5B budget."
    update_url = "https://sec.gov/aramco-2025"
    update_date = "2025-06-01"
    
    print("\n--- 3. Testing Update (Should Pass & Rewrite) ---")
    print(f"Fact: {update_fact} ({update_date})")
    is_saved, final_fact = engine.process_extracted_alpha(update_fact, update_url, update_date)
    print(f"Outcome: Saved={is_saved}, Final Fact={final_fact}")
    assert is_saved == True, "Engine failed to pass Update!"
    
    print("\n✅ Verification Complete! The Time Detective is Functional.")

if __name__ == "__main__":
    asyncio.run(run_test())
