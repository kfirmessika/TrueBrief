"""
Centralized configuration for the TrueBrief v2 Golden Pipeline.
"""
import os
from dotenv import load_dotenv

# Load .env once at startup
load_dotenv()

def get_env(name: str, default: str = None) -> str:
    return os.getenv(name, default)

# --- API Keys ---
GEMINI_API_KEY = get_env("GEMINI_API_KEY")

# --- Engine Configuration ---
EMBEDDING_MODEL = 'BAAI/bge-small-en-v1.5'

# Stage 1: Fetch
SAFETY_NET_LOTTERY_COUNT = 10 # How many "old" articles to pick

# Stage 2: Relevance
RELEVANCE_THRESHOLD = 0.60 # Stricter. Was 0.55
SENTENCE_RELEVANCE_THRESHOLD = 0.65 # Much stricter. Was 0.5
TOP_K_RELEVANT = 25       # Max articles to pass to the (slow) Novelty stage

# Stage 3: Novelty
NOVELTY_THRESHOLD = 0.85      # Similarity score to be considered a "duplicate"
NOVELTY_DANGER_ZONE_MIN = 0.85 # Min similarity to trigger hybrid check
NOVELTY_DANGER_ZONE_MAX = 0.98 # Max similarity (anything above is a clear duplicate)
TIME_DECAY_HALFLIFE_DAYS = 365 # How long for similarity penalty to be 50%
SENTENCE_MIN_LENGTH = 15       # Ignore sentences shorter than this

# --- LLM Token Pricing (for metrics) ---
# Using Gemini 1.5 Flash prices
INPUT_TOKEN_PRICE_USD = 0.35 / 1_000_000
OUTPUT_TOKEN_PRICE_USD = 0.70 / 1_000_000

# --- Source Scoring ---
SOURCE_SCORES = {
    # Primary Sources
    "reuters.com": 1.0, "apnews.com": 1.0, "prn.com": 1.0,
    "default": 0.5,

    # Commentary/Aggregators
    "slashdot.org": 0.3,
}

# --- Content Type Penalties ---
CONTENT_TYPE_PENALTIES = {
    "review": 0.2, "guide": 0.2, "how-to": 0.2, "best of": 0.2,
    "roundup": 0.2, "vs.": 0.2, "podcast": 0.5, "video": 0.5,
}

# --- Data File Paths ---
DATA_DIR = "data"
FACT_LEDGER_PATH_TEMPLATE = os.path.join(DATA_DIR, "{user_id}_{topic_id}_ledger.json")
METRICS_PATH = os.path.join(DATA_DIR, "metrics.json")
TOPICS_DB_PATH = "topics.json" # Our new "database" of topics
