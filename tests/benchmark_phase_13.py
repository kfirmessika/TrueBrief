import requests
import time
import json

BASE_URL = "http://localhost:8000"

# User-Defined Prompts
TOPICS = [
    "TSMC Arizona fab 4nm production yield rate delay union negotiations",
    # "Eli Lilly Zepbound Germany factory investment 2026 capacity",
    # "Saudi Aramco blue hydrogen export plan cancellation cost reasons"
]

def run_benchmark():
    print("🥊 Starting Phase 13 Benchmark (User Scenarios)...\n")
    
    results = {}
    
    for topic in TOPICS:
        print(f"🥊 Testing Topic: {topic[:30]}...")
        
        try:
            # Trigger Scan
            start_time = time.time()
            response = requests.post(f"{BASE_URL}/scan", json={"feed_url": topic}, timeout=300)
            data = response.json()
            duration = time.time() - start_time
            
            print(f"   ✅ Scan Complete in {duration:.2f}s.")
            print(f"   found {data.get('new_alphas_discovered')} new alphas.")
            time.sleep(2) # Cooldown
            
        except Exception as e:
            print(f"   ❌ Error scanning {topic}: {e}")

    # Collect Results
    print("\n📊 Collecting Final Results...")
    try:
        alphas_res = requests.get(f"{BASE_URL}/alphas")
        all_alphas = alphas_res.json()['alphas']
        
        # Save to file for analysis
        with open("tests/benchmark_phase_13_output.json", "w") as f:
            json.dump(all_alphas, f, indent=2)
            
        print(f"   Saved {len(all_alphas)} Alphas to 'tests/benchmark_phase_13_output.json'")
        
        # Print for immediate review
        print("\n🔍 PREVIEW OF FINDINGS:")
        for item in all_alphas[-10:]: # Show last 10
            print(f"   - {item['text'][:100]}...")
            
    except Exception as e:
        print(f"❌ Error collecting results: {e}")

if __name__ == "__main__":
    # Wait for server just in case
    time.sleep(2)
    run_benchmark()
