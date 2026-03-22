import requests
import time
import json

BASE_URL = "http://localhost:8000"

CHALLENGES = [
    "Nvidia China export license H200 Trump administration conflict",
    "OpenAI Nvidia $100B funding deal status Jensen Huang comments",
    "Red Sea shipping Maersk return freight rates 2026 forecast"
]

def run_benchmark():
    print("🥊 Starting Phase 12 Benchmark...")
    
    # 1. Clear Memory (Optional, but good for clean test) - We don't have a clear endpoint, but that's fine.
    
    results = {}
    
    for topic in CHALLENGES:
        print(f"\n🥊 Testing Topic: {topic[:30]}...")
        try:
            # Trigger Manual Scan for immediate results
            response = requests.post(f"{BASE_URL}/scan", json={"feed_url": topic}, timeout=300)
            data = response.json()
            print(f"   ✅ Scan Complete. Status: {data.get('status')}")
            print(f"   found {data.get('new_alphas_discovered')} new alphas.")
            results[topic] = data
        except Exception as e:
            print(f"   ❌ Error: {e}")
            
    print("\n📉 Retrieving All Alphas...")
    try:
        alphas_res = requests.get(f"{BASE_URL}/alphas")
        alphas = alphas_res.json()
        print(json.dumps(alphas, indent=2))
    except Exception as e:
        print(f"❌ Error getting alphas: {e}")

if __name__ == "__main__":
    # Ensure server is up (simple retry)
    for _ in range(5):
        try:
            requests.get(BASE_URL)
            break
        except:
            print("Server not up, waiting...")
            time.sleep(2)
            
    run_benchmark()
