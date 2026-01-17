from truebrief.sniper import Sniper


def run_stress_test_sniper():
    print(f"{'='*10} QA STRESS TEST: SNIPER {'='*10}")
    sniper = Sniper()
    
    # Test 1: Real Target (sanity check)
    print("\n[Test 1] Real Target (Wikipedia)")
    res1 = sniper.capture("https://en.wikipedia.org/wiki/Python_(programming_language)")
    if res1 and "Python" in res1:
        print(f"✅ PASS: Captured {len(res1)} chars.")
    else:
        print("❌ FAIL: Could not fetch Wikipedia.")

    # Test 2: 404 Page (Dead Link)
    print("\n[Test 2] 404 Page")
    res2 = sniper.capture("https://google.com/this-page-does-not-exist")
    if res2 is None:
        print("✅ PASS: Correctly handled 404 (Returned None).")
    else:
        print(f"❌ FAIL: Returned content for 404 page? ({len(res2)} chars)")

    # Test 3: Bad Domain
    print("\n[Test 3] Bad Domain")
    res3 = sniper.capture("http://domain-does-not-exist-123.com")
    if res3 is None:
        print("✅ PASS: Handled DNS Error.")
    else:
        print("❌ FAIL: Fetched data from void?")

    # Test 4: Text File (Non-HTML)
    print("\n[Test 4] Raw Text File")
    # Using a common text file mirror or just typical site
    res4 = sniper.capture("https://www.w3.org/Robots.txt")
    if res4 and len(res4) > 0:
        print(f"✅ PASS: Handled raw text ({len(res4)} chars).")
    else:
        print("⚠️ SKIP: Could not fetch Robots.txt (maybe blocked).")

if __name__ == "__main__":
    run_stress_test_sniper()
