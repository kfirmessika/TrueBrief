from truebrief.memory import FactLedger

import time
import shutil
import os

def run_stress_test_memory():
    print(f"{'='*10} QA STRESS TEST: MEMORY {'='*10}")
    
    # 1. Setup - Use a fresh ledger
    if os.path.exists("./storage_db"):
        print("   -> Existing DB found. Keeping it for persistence test later?")
        # Actually for a stress test we usually want clean, but let's test appending
    
    ledger = FactLedger()
    
    # Test 1: Novelty Detection
    print("\n[Test 1] Novelty Logic")
    fact_a = "The quick brown fox jumps over the lazy dog."
    ledger.add_fact(fact_a, "http://test.com/1")
    
    # Immediate check (Should be NOT NOVEL - 1.0 similarity)
    novel, score, match = ledger.is_novel(fact_a)
    print(f"   Same Fact: Novel={novel} (Score={score:.4f})")
    if not novel and score > 0.99:
        print("✅ PASS: Identical fact recognized.")
    else:
        print("❌ FAIL: Identical fact treated as novel.")

    # Similar check
    fact_b = "A quick brown fox jumped over a lazy dog."
    novel, score, match = ledger.is_novel(fact_b)
    print(f"   Similar Fact: Novel={novel} (Score={score:.4f})")
    if not novel and score > 0.85:
        print("✅ PASS: Similar fact recognized.")
    else:
         print(f"❌ FAIL: Similar fact treated as novel (Score {score}).")
         
    # Distinct check
    fact_c = "Quantum physics explores the subatomic world."
    novel, score, match = ledger.is_novel(fact_c)
    print(f"   Distinct Fact: Novel={novel} (Score={score:.4f})")
    if novel:
        print("✅ PASS: Distinct fact is novel.")
    else:
        print("❌ FAIL: distinct fact marked as old news.")

    # Test 2: Persistence (Re-instantiation)
    print("\n[Test 2] Persistence")
    del ledger # Force explicit deletion (client close)
    time.sleep(1)
    
    ledger2 = FactLedger() # Should load same DB
    novel, score, match = ledger2.is_novel(fact_a)
    if not novel:
        print("✅ PASS: Memory persisted after reload.")
    else:
        print("❌ FAIL: Amnesia! Forgot the fact after reload.")

if __name__ == "__main__":
    run_stress_test_memory()
