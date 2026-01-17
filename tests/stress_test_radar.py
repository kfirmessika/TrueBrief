from truebrief.radar import Radar


def run_stress_test_radar():
    print(f"{'='*10} QA STRESS TEST: RADAR {'='*10}")
    radar = Radar()
    
    # Test 1: Deduplication Attack
    print("\n[Test 1] Deduplication Logic")
    url = "http://feeds.feedburner.com/TechCrunch/"
    
    print("   Run 1 (Expected: >0 items)...")
    res1 = radar.scan_feed(url)
    print(f"   -> Got {len(res1)} items.")
    
    print("   Run 2 (Expected: 0 items - Duplicates)...")
    res2 = radar.scan_feed(url)
    print(f"   -> Got {len(res2)} items.")
    
    if len(res1) > 0 and len(res2) == 0:
        print("✅ PASS: Deduplication works.")
    elif len(res1) == 0:
        print("⚠️ SKIP: Network error on Run 1, cannot test dedupe.")
    else:
        print("❌ FAIL: Deduplication failed (Run 2 found items).")

    # Test 2: Trash Input (Not RSS)
    print("\n[Test 2] Trash Input (HTML Page)")
    # Using a reliable site that is definitely NOT RSS
    res3 = radar.scan_feed("https://www.google.com") 
    # Feedparser is resilient, it might return empty or throw bozo exception. 
    # Key is: IT MUST NOT CRASH.
    print(f"   -> Result: {len(res3)} items (Should be 0 or handled).")
    print("✅ PASS: Did not crash.")

    # Test 3: The Black Hole (Bad URL)
    print("\n[Test 3] Non-Existent URL")
    res4 = radar.scan_feed("http://this-domain-does-not-exist-12345.com/rss")
    print(f"   -> Result: {len(res4)} items.")
    if len(res4) == 0:
        print("✅ PASS: Gracefully handled 404/DNS error.")
    else:
        print("❌ FAIL: Somehow found data in a black hole?")

if __name__ == "__main__":
    run_stress_test_radar()
