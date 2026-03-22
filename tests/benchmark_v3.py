import requests
import time
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "http://localhost:8000"

# Complex, evolving topics to test the "Time Detective" and "Metric Extraction"
TOPICS = [
    "Tesla robotaxi cybercab reveal delay exact hardware changes",
    "Federal Reserve Jerome Powell core inflation rate cut probabilities next meeting",
    "OpenAI Sora video generator exact public release timeline and token limits"
]

def run_benchmark():
    print("🥊 Starting v3.0 Benchmark (Time Detective & Metric Extraction)...\n")
    
    for topic in TOPICS:
        print(f"🥊 Testing Topic: {topic}...")
        
        try:
            start_time = time.time()
            response = requests.post(f"{BASE_URL}/scan", json={"feed_url": topic}, timeout=300)
            data = response.json()
            duration = time.time() - start_time
            
            print(f"   ✅ Scan Complete in {duration:.2f}s.")
            print(f"   found {data.get('new_alphas_discovered')} new alphas.")
            time.sleep(3) # Cooldown
            
        except Exception as e:
            print(f"   ❌ Error scanning {topic}: {e}")

    # Collect Results
    print("\n📊 Collecting Final Results...")
    try:
        alphas_res = requests.get(f"{BASE_URL}/alphas")
        all_alphas = alphas_res.json()['alphas']
        
        output_file = "tests/benchmark_v3_output.json"
        with open(output_file, "w", encoding='utf-8') as f:
            json.dump(all_alphas, f, indent=2, ensure_ascii=False)
            
        print(f"   Saved {len(all_alphas)} Alphas to '{output_file}'")
        
    except Exception as e:
        print(f"❌ Error collecting results: {e}")

if __name__ == "__main__":
    time.sleep(2)
    run_benchmark()
