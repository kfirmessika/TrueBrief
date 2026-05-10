import httpx
import time
import json
import logging
from typing import Dict, List

# Setup logging to file so we can analyze it later
# Removed emojis to avoid Windows terminal encoding issues
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("tests/benchmark_v2_log.txt", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BASE_URL = "http://127.0.0.1:8000/api/v1"

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
        "Breaking news unidentified anomalous phenomena pentagon report release date",
        "Latest major earthquake fault line shift structural damage reports",
        "Sam Altman cryptic tweet agi timeline speculation"
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
    logger.info("================================================")
    logger.info("TRUEBRIEF V2: MASTER ASSESSMENT SUITE")
    logger.info("================================================\n")
    
    results = []
    total_prompts = sum(len(prompts) for prompts in CATEGORIES.values())
    current_count = 0
    
    with httpx.Client(timeout=600.0) as client:
        for category, prompts in CATEGORIES.items():
            logger.info(f"\nCATEGORY: {category.upper()}")
            logger.info("-" * 50)
            
            for topic_text in prompts:
                current_count += 1
                logger.info(f"[{current_count}/{total_prompts}] Testing: {topic_text}")
                
                topic_id = None
                try:
                    # 1. Create Topic
                    create_res = client.post(f"{BASE_URL}/topics", json={"raw_query": topic_text})
                    if create_res.status_code != 200:
                        logger.error(f"      FAILED to create topic: {create_res.text}")
                        continue
                    
                    topic_data = create_res.json()
                    topic_id = topic_data["id"]
                    
                    # 2. Trigger Scan
                    start_time = time.time()
                    scan_res = client.post(f"{BASE_URL}/topics/{topic_id}/scan")
                    duration = time.time() - start_time
                    
                    if scan_res.status_code == 200:
                        brief = scan_res.json()
                        content = brief.get("content", "")
                        
                        if "Topic rejected" in content:
                            logger.warning(f"      REJECTED: {content[:100]}... ({duration:.1f}s)")
                            status = "REJECTED"
                        elif "No new significant intelligence" in content or "no new stories" in content.lower():
                            logger.info(f"      EMPTY: No new facts found ({duration:.1f}s)")
                            status = "EMPTY"
                        else:
                            logger.info(f"      SUCCESS: Brief generated ({duration:.1f}s)")
                            status = "SUCCESS"
                        
                        results.append({
                            "category": category,
                            "topic": topic_text,
                            "status": status,
                            "duration": duration,
                            "content_snippet": content[:200]
                        })
                    else:
                        logger.error(f"      ERROR during scan: {scan_res.text}")
                        results.append({
                            "category": category,
                            "topic": topic_text,
                            "status": "ERROR",
                            "error": scan_res.text
                        })

                except Exception as e:
                    logger.error(f"      EXCEPTION: {e}")
                
                finally:
                    # 3. Cleanup Topic
                    if topic_id:
                        client.delete(f"{BASE_URL}/topics/{topic_id}")
                
                # Small breath to avoid slamming the Gemini RPM limit (15 RPM)
                time.sleep(5)

    # Save final results
    with open("tests/benchmark_v2_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info("\n================================================")
    logger.info("BENCHMARK COMPLETE")
    logger.info(f"Summary saved to tests/benchmark_v2_results.json")
    logger.info("================================================")

if __name__ == "__main__":
    run_benchmark()
