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
    
    def _pre_flight_check(self, topic: str) -> bool:
        """Uses a blazing fast LLM call to reject garbage inputs before scraping."""
        try:
            import google.generativeai as genai
            import os
            from dotenv import load_dotenv
            load_dotenv()
            genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
            
            prompt = f"""You are the TrueBrief Librarian Pre-Flight System.
Your job is to REJECT inputs that are complete nonsense, literal garbage bytes, or completely unrelated to news, finance, science, geopolitics, or actionable intelligence.
If the input is valid intelligence or news gathering (even vague ones like 'inflation' or 'apple'), reply 'YES'.
If the input is completely useless (like 'test test 123', 'best chocolate chip cookie recipe', or random keyboard smashing), reply 'NO'.

Input: {topic}
Decision (YES/NO):"""
            
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            decision = response.text.strip().upper()
            
            if "YES" in decision:
                return True
            else:
                return False
        except Exception as e:
            print(f"   ⚠️ Pre-Flight Check Error, defaulting to Pass: {e}")
            return True

    def search_sources(self, topic: str) -> Dict[str, List[str]]:
        """
        Dual-Mode Discovery:
        1. Commodity Hunt: Find RSS feeds for context.
        2. Alpha Hunt: Find Static Targets (Investor Relations) for the Sniper.
        """
        print(f"📚 Librarian researching topic: '{topic}'...")
        results = {
            "rss": [],
            "static": []
        }
        
        # 0. Pre-Flight Check
        if not self._pre_flight_check(topic):
            print(f"   🛑 PRE-FLIGHT REJECTION: '{topic}' is not a valid intelligence target. Aborting Search.")
            return results
        
        try:
            with DDGS() as ddgs:
                # 1. Commodity Hunt (RSS)
                # We look for explicit RSS feeds first
                rss_query = f"{topic} rss feed"
                print(f"   🔎 Searching Commodity Sources: {rss_query}")
                keywords = ["rss", "xml", "feed"]
                
                search_results = list(ddgs.text(rss_query, max_results=5))
                for r in search_results:
                    url = r['href']
                    # Heuristic: URL likely points to a feed
                    if any(k in url.lower() for k in keywords):
                        results["rss"].append(url)
                
                # 2. Alpha Hunt (Static Targets)
                # We look for high-value pages exclusively on Tier 1 Domains
                site_filter = " OR ".join([f"site:{site}" for site in TIER_1_SOURCES])
                alpha_query = f"{topic} ({site_filter})"
                print(f"   🔎 Searching Tier-1 Targets: {alpha_query}")
                
                search_results = list(ddgs.text(alpha_query, max_results=5))
                for r in search_results:
                    url = r.get('href', '')
                    if url and isinstance(url, str) and url.startswith('http'):
                        results["static"].append(url)
                    else:
                        print(f"   ⚠️ Skipping invalid DDG result: {r}")
                    
        except Exception as e:
            print(f"❌ Librarian Error: {e}")
            
        print(f"   ✅ Found {len(results['rss'])} feeds and {len(results['static'])} static targets.")
        return results

if __name__ == "__main__":
    # Smoke Test
    lib = Librarian()
    res = lib.search_sources("Nvidia")
    print(res)
