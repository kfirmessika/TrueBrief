try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS
from typing import List, Dict

TIER_1_SOURCES = [
    "reuters.com",
    "bloomberg.com",
    "sec.gov",
    "apnews.com",
    "ft.com",
    "wsj.com"
]

class Librarian:
    """
    The Librarian Agent (Mission 2.1).
    Responsible for discovering data sources (RSS + Static Pages) from a simple topic.
    """
    
    def _analyze_intent(self, topic: str) -> dict:
        """
        Single-shot LLM call to validate, rename, and generate DDG queries.
        Returns JSON: {"status": "APPROVED", "short_name": "...", "search_queries": [...], "seed_urls": [...]}
                 OR {"status": "REJECT"}
        """
        try:
            import google.generativeai as genai
            import os
            import json
            from dotenv import load_dotenv
            load_dotenv()
            genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
            
            prompt = f"""You are the TrueBrief Librarian.
The user provided this input to track breaking news: '{topic}'

If the input is complete gibberish (e.g. 'test1234', 'asdf'), return exactly and only:
{{"status": "REJECT"}}

If it makes sense, we need to track it.
1. Clean up and formalize a 'short_name' for the topic.
2. Generate 2 highly effective news search queries.
3. Provide a list of 5-8 'seed_urls' (direct links to topic-specific sections on reuters.com, bloomberg.com, apnews.com, or ft.com) that are highly likely to contain this information.

Output MUST be valid JSON (no markdown formatting, no backticks, just the raw JSON object):
{{
  "status": "APPROVED",
  "short_name": "Official Clean Name",
  "search_queries": ["query 1", "query 2"],
  "seed_urls": [
      "https://apnews.com/hub/topic-name",
      "https://www.reuters.com/business/finance/"
  ]
}}"""
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            # Safe JSON parsing
            text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)
            
        except Exception as e:
            print(f"   ⚠️ Intent Analyzer Error, defaulting to Approval: {e}")
            return {"status": "APPROVED", "short_name": topic, "search_queries": [f"{topic} news"], "seed_urls": []}

    def _search_google_api(self, query: str) -> List[str]:
        """Official Google Custom Search JSON API Call (Tier 3 - Last Resort)."""
        import os
        import requests
        from dotenv import load_dotenv
        load_dotenv()
        
        cx = os.getenv("GOOGLE_SEARCH_CX")
        key = os.getenv("OFFICIAL_GOOGLE_API_KEY")
        proxy = os.getenv("RESIDENTIAL_PROXY_URL")
        
        if not cx or not key or "YOUR_" in cx or "YOUR_" in key:
            return []
            
        print(f"   💰 Using Official Google Search API (Tier 3 - Paid)...")
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": key,
            "cx": cx,
            "q": query,
            "num": 5
        }
        
        proxies = {"http": proxy, "https": proxy} if proxy and "YOUR_" not in proxy else None
        
        try:
            resp = requests.get(url, params=params, timeout=10, proxies=proxies)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                return [i["link"] for i in items if "link" in i]
            else:
                print(f"   ⚠️ Google API Error {resp.status_code}: {resp.text}")
                return []
        except Exception as e:
            print(f"   ⚠️ Google API Failed: {e}")
            return []

    def search_sources(self, topic: str) -> Dict[str, any]:
        """
        Eco-Tiered Discovery Strategy:
        Tier 1: AI Seeds (Free)
        Tier 2: Broad Scout (Scraping with Proxy Rotation - Free/Cheap)
        Tier 3: Golden Google API (Official Paid - Last Resort)
        """
        import os
        proxy_url = os.getenv("RESIDENTIAL_PROXY_URL")
        if proxy_url and ("YOUR_" in proxy_url or "proxy-gate" in proxy_url):
            proxy_url = None
            
        print(f"📚 Librarian researching user input: '{topic}'...")
        
        intent = self._analyze_intent(topic)
        if intent.get("status") == "REJECT":
            print(f"   🛑 PRE-FLIGHT REJECTION: '{topic}' is gibberish. Aborting.")
            return {"official_name": "", "sources": {"rss": [], "static": []}}
            
        official_name = intent.get("short_name", topic)
        queries = intent.get("search_queries", [f"{official_name} news"])
        seed_urls = intent.get("seed_urls", [])
        
        print(f"   ✨ Intent Understood. Official Name: '{official_name}'")
        
        # --- Tier 1: AI Seeds (Free) ---
        results = {"rss": [], "static": seed_urls}
        print(f"   🌱 AI Seeds Planted: {len(seed_urls)} targets.")
        
        # --- Tier 2: Broad Scout (Scraper with Proxy Scaling) ---
        print(f"   🔎 Tier 2: Launching Broad Proxy Scout...")
        try:
            from googlesearch import search
            
            # Commodity Hunt (RSS)
            rss_query = f"{queries[0]} rss feed"
            for url in search(rss_query, num_results=5, proxy=proxy_url):
                if any(k in url.lower() for k in ["rss", "xml", "feed"]):
                    if url not in results["rss"]:
                        results["rss"].append(url)
            
            # Broad Alpha Hunt
            for q in queries:
                for url in search(q, num_results=5, proxy=proxy_url):
                    if url and url.startswith('http') and url not in results["static"]:
                        results["static"].append(url)
        except Exception as e:
            print(f"   ⚠️ Tier 2 Scraper Failed (Expected if NO Proxy/Keys): {e}")

        # --- Tier 3: Official Google API (Paid - Only if yield is low) ---
        CURRENT_YIELD = len(results["static"])
        if CURRENT_YIELD < 5:
            print(f"   📉 Low yield ({CURRENT_YIELD} targets). Escalating to Tier 3 Golden API...")
            for q in queries:
                google_results = self._search_google_api(q)
                if google_results:
                    results["static"].extend([u for u in google_results if u not in results["static"]])
        else:
            print(f"   ✅ Economic Discovery Succeeded with {CURRENT_YIELD} free targets. Skipping Paid API.")
            
        print(f"   ✅ Discovery Complete. Found {len(results['rss'])} feeds and {len(results['static'])} static targets.")
        return {"official_name": official_name, "sources": results}

if __name__ == "__main__":
    # Smoke Test
    lib = Librarian()
    res = lib.search_sources("Nvidia")
    print(res)
