import requests
import time
import json

BASE_URL = "http://localhost:8000"

# Only test the failing topic
TOPIC = "Nvidia China export license H200 Trump administration conflict"

def run_test():
    print(f"🥊 Re-Testing Noise Filter for: {TOPIC[:30]}...")
    
    try:
        response = requests.post(f"{BASE_URL}/scan", json={"feed_url": TOPIC}, timeout=300)
        data = response.json()
        print(f"   ✅ Scan Complete. New Alphas: {data.get('new_alphas_discovered')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
            
    print("\n📉 Checking Alphas for Noise...")
    try:
        alphas_res = requests.get(f"{BASE_URL}/alphas")
        alphas = alphas_res.json()['alphas']
        
        # Check specifically for the noise keywords found last time
        noise_keywords = ["Lindsey Vonn", "Brad Arnold", "Chicken Wings", "Jeffrey Epstein", "Narges Mohammadi"]
        found_noise = [item['text'] for item in alphas if any(k in item['text'] for k in noise_keywords)]
        
        if found_noise:
            print("❌ FAILURE: Noise Detected!")
            for n in found_noise:
                print(f"   - {n[:50]}...")
            
            print("\n🔍 FULL ALPHA LIST (DEBUG):")
            for item in alphas:
                print(f"   [{item['source_index']}] {item['text'][:100]}...")
        else:
            print("✅ SUCCESS: No Noise Detected.")
            print("   (Alphas found below:)")
            for item in alphas:
                # Simple filter to only show new ones (mock check)
                print(f"   - {item['text'][:100]}...")

    except Exception as e:
        print(f"❌ Error getting alphas: {e}")

if __name__ == "__main__":
    # Wait for server
    time.sleep(2)
    run_test()
