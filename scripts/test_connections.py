
import sys
import os
from pathlib import Path

# Add project root and src to sys.path
root = Path(__file__).resolve().parent.parent
sys.path.append(str(root))
sys.path.append(str(root / "src"))

from config.settings import settings
from truebrief.llm.client import LLMClient
from supabase import create_client

def test_llm():
    print("Testing LLM (Gemini)...")
    client = LLMClient()
    try:
        response = client.call("query_builder", "Hello, are you working?")
        print(f"PASS - LLM Response: {response[:50]}...")
    except Exception as e:
        print(f"FAIL - LLM Error: {e}")

def test_supabase():
    print("\nTesting Supabase...")
    url = settings.SUPABASE_URL
    key = settings.SUPABASE_KEY
    
    if "dashboard" in url:
        print(f"FAIL - Supabase URL Error: You provided the Dashboard URL ({url}).")
        print("Please provide the API URL (e.g., https://xyz.supabase.co).")
        return

    try:
        supabase = create_client(url, key)
        print("PASS - Supabase Client initialized.")
    except Exception as e:
        print(f"FAIL - Supabase Error: {e}")

def test_tavily():
    print("\nTesting Tavily...")
    from tavily import TavilyClient
    try:
        tavily = TavilyClient(api_key=settings.TAVILY_API_KEY)
        response = tavily.search("latest news", search_depth="basic")
        print(f"PASS - Tavily Response: Found {len(response.get('results', []))} results.")
    except Exception as e:
        print(f"FAIL - Tavily Error: {e}")

if __name__ == "__main__":
    test_llm()
    test_tavily()
    test_supabase()
