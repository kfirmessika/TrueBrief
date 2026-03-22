import asyncio
from truebrief.engine import NoveltyFilter
from truebrief.memory import FactLedger

async def run_test():
    print("Running Temporal Normalization Verification...")
    
    engine = NoveltyFilter()
    
    # 1. Inject History (Base Fact with a Vague Date)
    history_fact = "Tesla announced its Cybercab Robotaxi will be delayed until Late Summer 2025."
    history_url = "https://reuters.com/tesla-delay-2025"
    history_date = "Late Summer 2025"
    
    print("\n--- 1. Injecting History ---")
    print(f"Fact: {history_fact} ({history_date})")
    engine.commit(history_fact, history_url, history_date)
    
    # 2. Inject DUPLICATE (Vague Date Overlap)
    # Different wording, explicit vague overlap (Q3 overlaps with Late Summer).
    duplicate_fact = "Elon Musk confirms the Robotaxi reveal event is pushed to Q3 2025."
    dup_url = "https://bloomberg.com/tesla-q3-2025"
    dup_date = "Q3 2025"
    
    print("\n--- 2. Testing Vague Overlap (Should Block due to Math) ---")
    print(f"Fact: {duplicate_fact} ({dup_date})")
    is_saved, final_fact = engine.process_extracted_alpha(duplicate_fact, dup_url, dup_date)
    print(f"Outcome: Saved={is_saved}, Final Fact={final_fact}")
    assert is_saved == False, "Engine failed to calculate overlap for 'Q3' vs 'Late Summer'!"
    
    # 3. Inject UPDATE (Explicit Out of Bounds)
    update_fact = "Tesla officially cancels the Robotaxi project entirely due to regulatory failures."
    update_url = "https://wsj.com/tesla-dead-2026"
    update_date = "January 14, 2026"
    
    print("\n--- 3. Testing Real Update (Should Pass & Output Human Date) ---")
    print(f"Fact: {update_fact} ({update_date})")
    is_saved, final_fact = engine.process_extracted_alpha(update_fact, update_url, update_date)
    print(f"Outcome: Saved={is_saved}, Final Fact={final_fact}")
    assert is_saved == True, "Engine failed to pass Update out of bounding box!"
    
    print("\n✅ Verification Complete! Temporal Bounding Boxes are Functional.")

if __name__ == "__main__":
    asyncio.run(run_test())
