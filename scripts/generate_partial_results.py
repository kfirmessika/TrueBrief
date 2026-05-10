import json
import re
from datetime import datetime

def parse_logs_to_results(log_path, output_path):
    with open(log_path, 'r', encoding='utf-8') as f:
        log_content = f.read()

    # Pattern for successful results
    # 2026-04-28 18:37:54,518 - INFO - [2/21] Testing: Nvidia Blackwell GB200 chip delay revenue impact Q4 2025
    # 2026-04-28 18:37:54,830 - INFO - HTTP Request: POST http://127.0.0.1:8000/api/v1/topics "HTTP/1.1 200 OK"
    # ...
    # 2026-04-28 18:41:20,385 - INFO -       SUCCESS: Brief generated (205.3s)
    
    # We'll do a simple sweep
    lines = log_content.split('\n')
    results = []
    
    current_topic = None
    current_category = "General"
    
    for line in lines:
        cat_match = re.search(r'CATEGORY: (.*)', line)
        if cat_match:
            current_category = cat_match.group(1).strip()
            continue
            
        topic_match = re.search(r'\[\d+/21\] Testing: (.*)', line)
        if topic_match:
            current_topic = topic_match.group(1).strip()
            continue
            
        success_match = re.search(r'SUCCESS: Brief generated \((\d+\.\d+)s\)', line)
        if success_match and current_topic:
            results.append({
                "category": current_category,
                "topic": current_topic,
                "status": "SUCCESS",
                "duration": float(success_match.group(1)),
                "content_snippet": "See logs for details"
            })
            current_topic = None
            
        error_match = re.search(r'ERROR during scan: (.*)', line)
        if error_match and current_topic:
            results.append({
                "category": current_category,
                "topic": current_topic,
                "status": "ERROR",
                "error": error_match.group(1)
            })
            current_topic = None

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    
    print(f"Generated partial results for {len(results)} topics.")

if __name__ == "__main__":
    parse_logs_to_results("tests/benchmark_v2_log.txt", "tests/benchmark_v2_results.json")
