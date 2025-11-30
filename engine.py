"""
TrueBrief v2 "Golden Pipeline" Engine
This module contains the full 4-stage pipeline logic,
using fastembed for efficiency.
"""

import feedparser
import numpy as np
import spacy
import time
import json
import logging
import re
from fastembed import TextEmbedding
from sklearn.metrics.pairwise import cosine_similarity
from google import genai
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import requests
import config
import utils

# --- SETUP: LOAD MODELS (Done once) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    # Use fastembed
    embedder = TextEmbedding(config.EMBEDDING_MODEL, cache_dir="models")
    logging.info(f"Embedding model loaded: {config.EMBEDDING_MODEL}")
    nlp = spacy.load("en_core_web_sm")
    logging.info("NER model (spacy) loaded.")
except Exception as e:
    logging.error(f"FATAL: Could not load AI models. {e}")
    raise

# Configure the Gemini client
if not config.GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found. Please set it in your .env file.")
client = genai.Client(api_key=config.GEMINI_API_KEY)

def _embed_batch(texts: list[str]) -> np.ndarray:
    """Helper function to embed texts using fastembed."""
    # Filter out empty strings that can cause errors
    clean_texts = [t for t in texts if t and t.strip()]
    if not clean_texts:
        return np.array([], dtype=np.float32)
    return np.array(list(embedder.embed(clean_texts)), dtype=np.float32)

# --- STAGE 1: TWO-TIER FETCH ---

def _get_cheap_score(entry):
    """Calculates the 'CheapScore' (weight) for an article."""
    try:
        published_time = time.mktime(entry.published_parsed)
        now = time.time()
        hours_old = (now - published_time) / 3600
        recency_score = np.exp(-0.01 * hours_old)
    except Exception:
        recency_score = 0.1

    try:
        domain = urlparse(entry.link).netloc.replace("www.", "")
        source_score = config.SOURCE_SCORES.get(domain, config.SOURCE_SCORES["default"])
    except Exception:
        source_score = config.SOURCE_SCORES["default"]

    title_lower = entry.title.lower()
    content_penalty = 1.0
    for key, penalty in config.CONTENT_TYPE_PENALTIES.items():
        if key in title_lower:
            content_penalty = penalty
            break

    return (recency_score * 1.5 + source_score * 1.0) * content_penalty

def _run_safety_net_lottery(old_pool_articles):
    """Picks K articles from the old pool using weighted random sampling."""
    if not old_pool_articles:
        return []

    weights = [entry.cheap_score for entry in old_pool_articles]
    total_weight = sum(weights)

    if total_weight == 0:
        sample_size = min(config.SAFETY_NET_LOTTERY_COUNT, len(old_pool_articles))
        indices = np.random.choice(len(old_pool_articles), sample_size, replace=False)
        return [old_pool_articles[i] for i in indices]

    probabilities = [w / total_weight for w in weights]
    sample_size = min(config.SAFETY_NET_LOTTERY_COUNT, len(old_pool_articles))

    return np.random.choice(old_pool_articles, sample_size, p=probabilities, replace=False).tolist()


def _fetch_candidate_articles(feed_urls, last_update_timestamp):
    """Implements the "Two-Tier Fetch" with the "Safety Net Lottery." """
    logging.info(f"Stage 1: Starting Two-Tier Fetch from {len(feed_urls)} feeds...")
    tier_1_new_pool = []
    tier_2_old_pool = []

    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                try:
                    entry.publish_date = time.mktime(entry.published_parsed)
                    if entry.publish_date > last_update_timestamp:
                        tier_1_new_pool.append(entry)
                    else:
                        entry.cheap_score = _get_cheap_score(entry)
                        tier_2_old_pool.append(entry)
                except Exception:
                    continue # Skip entries with bad timestamps
        except Exception as e:
            logging.warning(f"Failed to fetch or parse feed {url}: {e}")

    logging.info(f"Stage 1: Found {len(tier_1_new_pool)} new articles.")
    lottery_winners = _run_safety_net_lottery(tier_2_old_pool)
    logging.info(f"Stage 1: Selected {len(lottery_winners)} old articles via 'Safety Net Lottery' (from a pool of {len(tier_2_old_pool)}).")

    if len(lottery_winners) > 0:
        logging.info("Stage 1: Example lottery winners:")
        for i, entry in enumerate(lottery_winners[:3]):
            logging.info(f"  {i+1}. {entry.title[:70]}... (score: {entry.cheap_score:.3f})")

    return tier_1_new_pool + lottery_winners

# --- STAGE 2: SMART RELEVANCE FILTER ---

def _filter_relevant_articles(candidate_articles, user_topic_string):
    """
    Takes candidates, batch-embeds their snippets, and returns relevant ones
    AND the user_topic_vector for use in Stage 3.
    """
    if not candidate_articles:
        return [], None

    logging.info(f"Stage 2: Running 'Smart Relevance Filter' on {len(candidate_articles)} candidates.")
    snippets = [f"{entry.title} {entry.description}" for entry in candidate_articles]

    user_vector = _embed_batch([user_topic_string])[0]
    article_vectors = _embed_batch(snippets)

    if article_vectors.shape[0] == 0:
         logging.warning("Stage 2: No valid article snippets to embed.")
         return [], None

    similarities = cosine_similarity([user_vector], article_vectors)[0]

    relevant_articles = []
    for article, score in zip(candidate_articles, similarities):
        if score > config.RELEVANCE_THRESHOLD:
            article.relevance_score = score
            relevant_articles.append(article)

    relevant_articles.sort(key=lambda x: x.relevance_score, reverse=True)
    final_relevant_list = relevant_articles[:config.TOP_K_RELEVANT]

    logging.info(f"Stage 2: Filtered down to {len(final_relevant_list)} relevant articles.")
    if len(final_relevant_list) > 0:
        logging.info("Stage 2: Example relevant articles:")
        for i, article in enumerate(final_relevant_list[:3]):
            logging.info(f"  {i+1}. Score: {article.relevance_score:.3f} | {article.title[:70]}...")

    return final_relevant_list, user_vector

# --- STAGE 3: HYBRID NOVELTY FILTER ---

def _scrape_full_text(url):
    """Simple scraper (can be improved)."""
    try:
        response = requests.get(url, timeout=5, headers={'User-Agent': 'TrueBrief/1.0'})
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = soup.find_all('p')
        full_text = ' '.join([p.get_text() for p in paragraphs if p.get_text()])
        return full_text if full_text else None
    except Exception:
        return None

def _is_junk_sentence(text):
    """A simple filter to remove common non-informational sentences."""
    text_lower = text.lower()
    if text_lower.startswith("by ") or text_lower.startswith("subscribe "):
        return True
    if "click here to" in text_lower or "all rights reserved" in text_lower:
        return True
    if len(text.split()) < 5: # Filter out very short, non-sentences
        return True
    return False

def _calculate_time_decay_factor(days_diff):
    """Calculates the penalty factor based on time."""
    lambda_val = np.log(2) / config.TIME_DECAY_HALFLIFE_DAYS
    return np.exp(-lambda_val * days_diff)

def _extract_entities(text):
    """Extracts entities using Spacy (NER)."""
    doc = nlp(text)
    return set((ent.text, ent.label_) for ent in doc.ents if ent.label_ in {'PERSON', 'ORG', 'GPE', 'EVENT', 'DATE', 'CARDINAL', 'MONEY'})

def _find_novel_facts(relevant_articles, fact_ledger_data, user_topic_vector):
    """Implements the 3-Stage Hybrid Novelty Filter."""
    logging.info(f"Stage 3: Running 'Hybrid Novelty Filter' on {len(relevant_articles)} articles.")
    novel_facts = []

    ledger_vectors = [fact['vector'] for fact in fact_ledger_data]
    has_history = len(ledger_vectors) > 0
    history_matrix = np.array(ledger_vectors, dtype=np.float32) if has_history else None

    for article in relevant_articles:
        logging.info(f"Stage 3: Processing article: {article.title[:70]}...")
        full_text = _scrape_full_text(article.link) or article.summary

        if not full_text:
            logging.warning(f"Stage 3:   Could not scrape or find summary for {article.link}, skipping.")
            continue

        article_time = article.publish_date
        article_domain = urlparse(article.link).netloc.replace("www.", "")
        article_source_name = article.get('source', {}).get('title', article_domain)

        # 1. Split into sentences
        all_sentences = [s.strip() for s in re.split(r'[.!?]\s+', full_text) if len(s.strip()) > config.SENTENCE_MIN_LENGTH]
        logging.info(f"Stage 3:   Extracted {len(all_sentences)} sentences.")

        # 2. Junk Filter
        clean_sentences = [s for s in all_sentences if not _is_junk_sentence(s)]
        junk_count = len(all_sentences) - len(clean_sentences)
        if junk_count > 0:
            logging.info(f"Stage 3:   Junk filter removed {junk_count} sentences.")
        if not clean_sentences:
            logging.info("Stage 3:   No clean sentences left, skipping article.")
            continue

        sentence_vectors = _embed_batch(clean_sentences)
        if sentence_vectors.shape[0] == 0:
            logging.info("Stage 3:   No valid sentence vectors, skipping article.")
            continue

        # 3. Sentence Relevance Filter
        relevance_scores = cosine_similarity(sentence_vectors, [user_topic_vector]).flatten()
        relevant_indices = [i for i, score in enumerate(relevance_scores) if score > config.SENTENCE_RELEVANCE_THRESHOLD]

        logging.info(f"Stage 3:   Sentence relevance check: {len(relevant_indices)}/{len(clean_sentences)} sentences passed threshold ({config.SENTENCE_RELEVANCE_THRESHOLD}).")

        if not relevant_indices:
            logging.info("Stage 3:   No relevant sentences in this article, skipping.")
            continue

        logging.info("Stage 3:   Example relevant sentences from this article:")
        for i, idx in enumerate(relevant_indices[:2]): # Log top 2
             logging.info(f"    - Score: {relevance_scores[idx]:.3f} | {clean_sentences[idx][:70]}...")

        # 4. Novelty Check (on relevant sentences ONLY)
        for i in relevant_indices:
            sentence = clean_sentences[i]
            new_vector = sentence_vectors[i]

            is_novel = False 
            if not has_history:
                is_novel = True
            else:
                similarities = cosine_similarity([new_vector], history_matrix)[0]
                best_match_index = np.argmax(similarities)
                raw_similarity = similarities[best_match_index]

                if raw_similarity < config.NOVELTY_DANGER_ZONE_MIN:
                    is_novel = True 
                elif raw_similarity <= config.NOVELTY_DANGER_ZONE_MAX:
                    # --- HYBRID CHECK ---
                    old_fact_data = fact_ledger_data[best_match_index]
                    days_diff = (article_time - old_fact_data['timestamp']) / 86400
                    if days_diff < 0: days_diff = 0
                    time_decay_factor = _calculate_time_decay_factor(days_diff)
                    final_similarity = raw_similarity * time_decay_factor

                    if final_similarity < config.NOVELTY_THRESHOLD:
                        is_novel = True
                    else:
                        new_entities = _extract_entities(sentence)
                        old_entities = _extract_entities(old_fact_data['text'])

                        if new_entities != old_entities:
                            is_novel = True
                        else:
                            is_novel = False
                # else: (raw_similarity > MAX) -> is_novel stays False

            if is_novel:
                logging.info(f"Stage 3:   ✓ NOVEL fact found: {sentence[:70]}...")
                new_fact_data = {
                    "text": sentence,
                    "vector": new_vector.tolist(),
                    "source_name": article_source_name,
                    "url": article.link,
                    "domain": article_domain,
                    "timestamp": article_time
                }
                novel_facts.append(new_fact_data)

                # Add to history matrix *in-place* to prevent duplicate finds
                history_matrix = np.vstack([history_matrix, [new_vector]])
                fact_ledger_data.append(new_fact_data) # Add to in-memory data as well

    logging.info(f"Stage 3: Found {len(novel_facts)} novel sentences.")
    return novel_facts

# --- STAGE 4: TRUST & SYNTHESIS ---

def _summarize_facts_to_json(novel_facts, user_topic_string):
    """Sends novel facts to the LLM and forces a JSON output."""
    if not novel_facts:
        return {
            "summary_text": "No significant new updates found for your topic.",
            "sources_used": []
        }, (0, 0)

    logging.info(f"Stage 4: Summarizing {len(novel_facts)} facts for topic: '{user_topic_string}'")

    facts_for_prompt = [{
        "text": fact["text"],
        "source_name": fact["source_name"],
        "url": fact["url"],
        "domain": fact["domain"]
    } for fact in novel_facts]

    logging.info("Stage 4: Facts being sent to LLM for summarization:")
    for i, fact in enumerate(novel_facts[:3]): # Log first 3 facts
        logging.info(f"  {i+1}. [{fact['domain']}] {fact['text'][:70]}...")


    prompt = f"""
    You are a 100% neutral, objective news editor for TrueBrief. Your job is to synthesize
    *only* the new facts provided below into a concise, unbiased report about "{user_topic_string}".
    You MUST return your response as a single, valid JSON object.

    **Core Rules:**
    1.  **Always Attribute:** Never state a claim as universal truth. *Always* attribute it to its source (e.g., "According to [Source Name]...").
    2.  **Present All Sides:** If you have conflicting facts, you *must* present both, attributing each.
    3.  **No Hallucinations:** Do NOT add any information or opinions not present in the facts. If the facts are trivial or unrelated, just say "No significant new updates."

    **Misinformation & Claims Handling:**
    1.  **Health & Science:** If a health claim comes from an unverified source, *must* append the note: `[This claim is not supported by scientific evidence.]`

    **Your JSON output MUST have this exact structure:**
    {{
      "summary_text": "The full text of your summary goes here. Do NOT put links or citations in this text.",
      "sources_used": [
        {{
          "url": "The full URL of the source you used",
          "domain": "The domain of the source (e.g., ynet.co.il)",
          "source_name": "The original source name"
        }}
      ]
    }}

    **Instructions:**
    - The `summary_text` should be a clean, readable paragraph.
    - The `sources_used` array should *only* contain the facts you actually included in your summary.
    - **Do NOT** output any text before or after the JSON object.

    **Facts to Summarize:**
    {json.dumps(facts_for_prompt, indent=2)}
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        
        # Get response text
        response_text = response.text if hasattr(response, 'text') else str(response)
        
        if not response_text or not response_text.strip():
            logging.error("Stage 4: Empty response from LLM")
            return None, (0, 0)
        
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

        # Get token counts (this is an approximation)
        input_tokens = len(prompt.split())
        output_tokens = len(response_text.split())

        logging.info("Stage 4: Successfully generated structured summary.")
        logging.info(f"Stage 4: Generated summary: {json_output['summary_text'][:70]}...")

        return json_output, (input_tokens, output_tokens)

    except Exception as e:
        logging.error(f"Stage 4: Error during LLM summarization: {e}")
        return None, (0, 0)

# --- MAIN ORCHESTRATOR ---

def run_engine_cycle(feed_urls, fact_ledger_path, user_topic_string, last_update_timestamp):
    """
    Runs the full v2 "Golden Pipeline".
    Returns a dictionary with the summary and metrics.
    """

    fact_ledger_data = utils.load_json_file(fact_ledger_path, [])

    # Stage 1: Two-Tier Fetch
    candidate_articles = _fetch_candidate_articles(feed_urls, last_update_timestamp)

    # Stage 2: Smart Relevance Filter
    relevant_articles, user_topic_vector = _filter_relevant_articles(candidate_articles, user_topic_string)

    if not relevant_articles:
        return {
            "summary_json": {"summary_text": "No new relevant articles found.", "sources_used": []},
            "new_fact_count": 0, "llm_input_tokens": 0, "llm_output_tokens": 0
        }

    if user_topic_vector is None:
        logging.error("Could not generate user topic vector, exiting cycle.")
        return None

    # Stage 3: Hybrid Novelty Filter
    novel_facts = _find_novel_facts(relevant_articles, fact_ledger_data, user_topic_vector)

    # Stage 4: Trust & Synthesis
    summary_json, (in_tokens, out_tokens) = _summarize_facts_to_json(novel_facts, user_topic_string)

    if not summary_json:
        return None # Indicate a failure

    if novel_facts:
        # We save the in-memory 'fact_ledger_data' which was modified
        # by _find_novel_facts
        utils.save_json_file(fact_ledger_path, fact_ledger_data)
        logging.info(f"Successfully updated fact ledger at {fact_ledger_path}")

    return {
        "summary_json": summary_json,
        "new_fact_count": len(novel_facts),
        "llm_input_tokens": in_tokens,
        "llm_output_tokens": out_tokens
    }
