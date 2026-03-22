import requests
import time
import json
import urllib3
from typing import Dict, List

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "http://127.0.0.1:8000"

# ==========================================
# MISSION 5.0: THE MASTER ASSESSMENT SUITE
# ==========================================
# This dictionary contains a diverse set of search prompts spanning multiple domains.
# The goal is to stress-test the Librarian (Source finding), the Sniper (Extraction),
# and the Time Detective (Conflict/Update detection) across different types of language.

CATEGORIES: Dict[str, List[str]] = {
    
    "Tier-1 Finance (Strict Metrics)": [
        "JPMorgan Chase upcoming dividend increase CEO Jamie Dimon quotes",
        "Nvidia Blackwell GB200 chip delay revenue impact Q4 2025",
        "European Central Bank interest rate cut lagarde inflation target"
    ],
    
    "Geopolitics & Defense (Vague Timelines)": [
        "Taiwan semiconductor manufacturing US subsidies CHIPS act timeline",
        "Red sea shipping attacks Maersk route diversion financial cost",
        "US Space Force budget allocation space debris clearing initiative"
    ],
    
    "Science & Medicine (Research Data)": [
        "CRISPR sickle cell gene therapy FDA approval patient outcome statistics",
        "Eli Lilly tirzepatide weight loss phase 3 trial side effects",
        "Solid state battery commercialization timeline Toyota patent release"
    ],

    "Mental Health & Social (Qualitative Nuance)": [
        "Surgeon general warning social media teenage anxiety statistics",
        "Corporate return to office mandates employee retention survey data",
        "Telehealth therapy platform startup funding Series B valuation"
    ],

    "Extreme Edge Cases (Noise & Ambiguity)": [
        "\"Breaking news\" unidentified anomalous phenomena pentagon report release date", # High noise, low facts
        "Latest major earthquake fault line shift structural damage reports", # Breaking, rapidly changing data
        "Sam Altman cryptic tweet agi timeline speculation" # Pure speculation, testing the verifier's hallucination block
    ],
    
    "The 'Lazy User' Test (Extreme Breadth)": [
        "Apple",
        "AI",
        "Economy"
    ],
    
    "The 'Garbage Input' Test (Non-News & Nonsense)": [
        "test test 123",
        "best chocolate chip cookie recipe",
        "how to tie a tie"
    ]
}

def run_benchmark():
    print("================================================")
    print("🌍 MISSION 5.0: MASTER ASSESSMENT SUITE")
    print("================================================\n")
    
    total_prompts = sum(len(prompts) for prompts in CATEGORIES.values())
    current_prompt = 1
    
    for category, prompts in CATEGORIES.items():
        print(f"\n📂 CATEGORY: {category.upper()}")
        print("-" * 50)
        
        for topic in prompts:
            print(f"[{current_prompt}/{total_prompts}] 🎯 Scanning: {topic}")
            
            try:
                start_time = time.time()
                response = requests.post(f"{BASE_URL}/scan", json={"feed_url": topic}, timeout=300)
                data = response.json()
                duration = time.time() - start_time
                
                new_alphas = data.get('new_alphas_discovered', 0)
                
                if new_alphas > 0:
                    print(f"      ✅ SUCCESS: Extracted {new_alphas} Alphas in {duration:.1f}s")
                else:
                    metrics = data.get('metrics', {})
                    sources = metrics.get('sources_found', 0)
                    scraped = metrics.get('scraped_successfully', 0)
                    extracted = metrics.get('extracted_by_llm', 0)
                    
                    reason = "Unknown Error"
                    if sources == 0:
                        reason = "Librarian found no valid URLs"
                    elif scraped == 0:
                        reason = "Sniper Blocked/Failed on all URLs"
                    elif extracted == 0:
                        reason = "Verifier rejected as Noise/Off-Topic"
                    else:
                        reason = "Engine NoveltyFilter blocked as DUPLICATE (Old News)"
                        
                    print(f"      ⚠️ EMPTY: 0 Alphas. Reason: {reason} (in {duration:.1f}s)")
                    
            except Exception as e:
                print(f"      ❌ ERROR: Pipeline Failure - {e}")
                
            current_prompt += 1
            time.sleep(3) # Anti-ban cooldown

    # Collect and Save Results
    print("\n================================================")
    print("📊 COLLECTING GLOBAL RESULTS")
    print("================================================")
    try:
        alphas_res = requests.get(f"{BASE_URL}/alphas")
        all_alphas = alphas_res.json()['alphas']
        
        output_file = "tests/master_benchmark_results.json"
        with open(output_file, "w", encoding='utf-8') as f:
            json.dump(all_alphas, f, indent=2, ensure_ascii=False)
            
        print(f"\n🏆 ASSESSMENT COMPLETE.")
        print(f"Saved a total of {len(all_alphas)} Alphas across all domains to '{output_file}'")
        print("Please review the JSON file to manually grade the LLM's performance.")
        
    except Exception as e:
        print(f"❌ Error collecting results: {e}")

if __name__ == "__main__":
    time.sleep(2)
    run_benchmark()
