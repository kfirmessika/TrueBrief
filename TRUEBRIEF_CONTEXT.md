# TrueBrief: AI Developer Context

**If you are an AI assistant reading this, this is your project context. Read this before suggesting changes.**

## The Project
**TrueBrief** is an autonomous "Intelligence Engine" designed for Hedge Funds and Analysts. It is NOT a generic news summarizer. It extracts hard metrics, compares conflicting sources, and filters out noise.

## Current Architecture Pipeline (v2.0)
1. **Librarian (`librarian.py`)**: Finds URLs via DuckDuckGo.
2. **Sniper (`sniper.py`)**: Uses Crawl4AI to bypass bot-protections and extract Markdown.
3. **Engine (`engine.py`)**: Uses SpaCy to clean text and split into atomic sentences.
4. **Memory (`memory.py`)**: Uses Qdrant & BAAI/bge-small-en-v1.5 embeddings for semantic deduplication.
5. **Verifier (`verifier.py`)**: Uses Gemini LLM to extract "Alphas" (hard metrics) and execute a "Cross-Examination" layer to detect reporting conflicts between sources.
6. **Router/Server (`router.py`)**: FastAPI backend.
7. **Scheduler (`manager.py`, `scheduler.py`)**: Infinite loop for real-time monitoring.

## Current State: v4.0 (Temporal Normalization) & v5.0 (Master Benchmark) COMPLETE
The system successfully enforces mathematical date bounding (`start_date`, `end_date`) to prevent timeline hallucinations. We created the Master Assessment Suite (`tests/master_benchmark.py`), consisting of 21 highly-diverse test prompts. The Engine profoundly outperformed standard LLMs by actively rejecting noise and accurately scraping SEC and FT Tier-1 sources for hard metrics.

## Current State: v6.0 (Scale & Polish) COMPLETE
To address edge-cases found in the Benchmark, the pipeline received three major architectural upgrades:
1. **The Pre-Flight Garbage Filter**: `librarian.py` now uses a blazing-fast `Gemini-Flash` call to instantaneously *reject* useless prompts (e.g. "test test 123", "how to tie a tie") BEFORE wasting DuckDuckGo search queries or scraper bandwidth.
2. **The Stealth Proxy Waterfall**: `sniper.py` was structurally upgraded. If `Crawl4AI` hits a Cloudflare bot-block (e.g., Bloomberg), the system automatically hot-swaps to a premium residential proxy via `os.getenv("RESIDENTIAL_PROXY_URL")`.
3. **The "Visual Proof" Dashboard**: `index.html` was heavily overhauled. It now explicitly renders Glowing Trust Badges ("Verified Tier-1") and Temporal Bounding Boxes ("Active: Start -> End") directly onto the Intelligence Cards.

## Current Mission: v7.0 (The Scale Up - FUTURE ROADMAP)
With the backend completely stable, the next iteration phase involves User scaling.
1. **User Portfolios**: Converting the static index into user-specific profiles (Database transition).
2. **Alerting Hooks**: Attaching Twilio/SMTP APIs so users get live emails/SMS when their specific surveillance topics trigger a TrueBrief Alpha extraction.

## Developer Instructions
- Code resides in `src/truebrief/`.
- Run tests from the root directory.
- For detailed architecture plans, read the markdown files in `docs/architecture/`.
- All code modifications should prioritize Metric Preservation (no smoothing numbers) and strict Python best practices.
