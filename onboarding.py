"""
TrueBrief Topic Onboarding Engine

Handles the one-time setup for a new user topic.

Pipeline:
1. (Gemini) Distill user text into search queries.
2. (Google) Run searches to find source pages.
3. (Scrape) Scrape those pages for RSS links.
4. (Validate) Check which RSS links are valid.
"""

import logging
import re
import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import feedparser
from google import genai

from google_search_tool import google_search

import config
import utils

# Configure Gemini client (matching engine.py pattern)
if not config.GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found. Please set it in your .env file.")
client = genai.Client(api_key=config.GEMINI_API_KEY)

def _get_search_queries_from_llm(user_input: str) -> dict:
    """
    Stage A: AI Topic Distillation
    Takes messy user input and turns it into clean search queries.
    """
    logging.info(f"Distilling user topic: '{user_input}'")
    
    prompt = f"""You are a Topic Analyst. Your job is to read the user's request and create a JSON object with two things:
1. `topic_string`: A clean, neutral title for this topic (max 5-7 words).
2. `search_queries`: A list of 5-7 search queries that will find RSS feeds or news sources for this topic.

IMPORTANT: At least 3-4 of the queries MUST include "RSS" or "RSS feed" in them. The other queries can be general news source searches.

User Request: "{user_input}"

Your JSON Output (must be only the JSON, no markdown):
{{
  "topic_string": "The clean topic title",
  "search_queries": ["topic RSS feed", "topic news RSS", "topic RSS", "topic news sources", "topic updates RSS"]
}}"""
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        
        # Get response text (matching engine.py pattern)
        response_text = response.text if hasattr(response, 'text') else str(response)
        
        if not response_text or not response_text.strip():
            logging.error("LLM distillation returned empty response.")
            return None
        
        # Strip markdown code fences if present (```json ... ```)
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]  # Remove ```json
        elif response_text.startswith("```"):
            response_text = response_text[3:]   # Remove ```
        
        if response_text.endswith("```"):
            response_text = response_text[:-3]  # Remove closing ```
        
        response_text = response_text.strip()
        
        json_output = json.loads(response_text)
        
        if "topic_string" in json_output and "search_queries" in json_output:
            logging.info(f"Distilled topic to: '{json_output['topic_string']}'")
            logging.info(f"Generated {len(json_output['search_queries'])} search queries")
            return json_output
        else:
            logging.error("LLM distillation failed to return correct JSON structure.")
            return None
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON from LLM: {e}")
        logging.error(f"Response text: {response_text[:200]}...")
        return None
    except Exception as e:
        logging.error(f"Error in Stage A (Distillation): {e}")
        return None

def _run_google_search(search_queries: list[str]) -> list[str]:
    """
    Stage B: Source Discovery
    Runs DuckDuckGo Search for each query and returns a list of unique links.
    """
    logging.info(f"Running DuckDuckGo Search for {len(search_queries)} queries...")
    all_links = set()
    successful_queries = 0
    
    for query in search_queries:
        try:
            # Use the google_search tool (now uses DuckDuckGo)
            search_results = google_search.search(queries=[query], num_results=5)
            if search_results and search_results.results:
                query_results_count = len(search_results.results)
                logging.info(f"Query '{query}' returned {query_results_count} results")
                for result in search_results.results:
                    all_links.add(result.url)
                successful_queries += 1
            else:
                logging.warning(f"Query '{query}' returned no results")
        except Exception as e:
            logging.warning(f"DuckDuckGo Search failed for query '{query}': {e}")
    
    logging.info(f"Found {len(all_links)} unique source pages from {successful_queries}/{len(search_queries)} successful queries.")
    return list(all_links)

def _extract_rss_feeds_from_url(base_url: str) -> set[str]:
    """
    Stage C (Helper): Scrapes a single URL to find RSS links.
    """
    found_feeds = set()
    try:
        response = requests.get(base_url, timeout=5, headers={'User-Agent': 'TrueBrief/1.0'})
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 1. Look for <link> tags (the "official" way)
        links = soup.find_all(
            'link',
            attrs={'type': re.compile(r'application/(rss|atom)\+xml')}
        )
        for link in links:
            if link.get('href'):
                feed_url = urljoin(base_url, link['href'])
                found_feeds.add(feed_url)
                
        # 2. Look for "a" tags that explicitly link to a feed (common)
        links = soup.find_all('a', attrs={'href': re.compile(r'(\.xml|/feed|/rss)')})
        for link in links:
            feed_url = urljoin(base_url, link['href'])
            found_feeds.add(feed_url)
            
    except Exception as e:
        logging.warning(f"Could not scrape {base_url} for RSS: {e}")
        
    return found_feeds

def _validate_and_save_topic(topic_id: str, topic_string: str, source_pages: list[str]):
    """
    Stage C & D: Algorithmic Extraction and Validation
    Scrapes, validates, and saves the new topic.
    """
    logging.info("Stage C/D: Extracting and validating RSS feeds...")
    final_feed_list = set()
    
    for page_url in source_pages:
        # Check if the page *is* the feed
        if any(page_url.endswith(ext) for ext in ['.xml', '/feed', '/rss']):
            final_feed_list.add(page_url)
            continue
            
        # Else, scrape the page to *find* feeds
        feeds_on_page = _extract_rss_feeds_from_url(page_url)
        final_feed_list.update(feeds_on_page)

    logging.info(f"Found {len(final_feed_list)} potential RSS feeds. Now validating...")
    
    validated_feeds = []
    for feed_url in final_feed_list:
        try:
            parsed = feedparser.parse(feed_url)
            if parsed.entries or parsed.feed:
                logging.info(f"  ✓ VALID: {feed_url}")
                validated_feeds.append(feed_url)
            else:
                logging.warning(f"  ✗ INVALID (empty): {feed_url}")
        except Exception as e:
            logging.warning(f"  ✗ FAILED (error): {feed_url}")
            
    if not validated_feeds:
        logging.error("Onboarding failed: Could not find any valid RSS feeds.")
        return None

    # Save the new topic to our "database"
    new_topic_data = {
        "user_topic_string": topic_string,
        "feeds": validated_feeds
    }
    
    # We load the *whole* topics file, add the new one, and save it
    topics_db = utils.load_json_file('topics.json', default_data={})
    topics_db[topic_id] = new_topic_data
    utils.save_json_file('topics.json', topics_db)
    
    logging.info(f"Successfully onboarded and saved new topic: '{topic_id}'")
    return new_topic_data

# --- MAIN ONBOARDING FUNCTION ---

def onboard_new_topic(user_input: str, topic_id: str) -> dict:
    """
    Runs the full one-time Topic Onboarding Pipeline.
    """
    # Stage A: Get topic string and search queries
    distilled_data = _get_search_queries_from_llm(user_input)
    if not distilled_data:
        return None
        
    # Stage B: Find source pages
    source_pages = _run_google_search(distilled_data["search_queries"])
    if not source_pages:
        logging.error("Onboarding failed: DuckDuckGo Search found no source pages.")
        return None
        
    # Stage C & D: Extract, Validate, and Save
    new_topic = _validate_and_save_topic(
        topic_id,
        distilled_data["topic_string"],
        source_pages
    )
    
    return new_topic

