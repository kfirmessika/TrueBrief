import requests
import time

def run_api_verification():
    print(f"{'='*10} API VERIFICATION {'='*10}")
    base_url = "http://localhost:8000"
    
    # 1. Check Alphas (should be 0 or small)
    print("\n[Step 1] Checking current Alphas...")
    res = requests.get(f"{base_url}/alphas")
    data = res.json()
    print(f"   -> Found {data['count']} Alphas.")
    
    # 2. Trigger Scan
    print("\n[Step 2] Triggering Manual Scan (this takes ~10-20s)...")
    start = time.time()
    res = requests.post(f"{base_url}/scan")
    if res.status_code == 200:
        scan_data = res.json()
        print(f"   -> Scan Success in {time.time()-start:.1f}s.")
        print(f"   -> New Alphas Discovered: {scan_data['new_alphas_discovered']}")
    else:
        print(f"   ❌ Scan Failed: {res.text}")
        return

    # 3. Verify Alphas increased
    print("\n[Step 3] Verifying Alpha count increase...")
    res = requests.get(f"{base_url}/alphas")
    new_data = res.json()
    print(f"   -> Total Alphas now: {new_data['count']}")
    
    if new_data['count'] >= data['count']:
        print("\n✅ API VERIFICATION PASSED!")
    else:
        print("\n❌ API VERIFICATION FAILED: Count did not increase correctly.")

if __name__ == "__main__":
    run_api_verification()
