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

## Current State: v3.0 (The Time Detective) COMPLETE
The pipeline successfully extracted hard metrics, detected Source Conflicts, and deployed "The Time Detective" to manage Semantic Collisions based on Time Context. The engine successfully discriminates between a Duplicate Recitation and a New Update.

## Current Mission: v4.0 (Temporal Normalization)
We found two edge-case flaws in v3.0:
1. **Flaw 1: Vague Dates**: The LLM struggles to mathematically compare vague implicit dates (e.g., "Late Summer" vs "Q3").
2. **Flaw 2: Tier-1 Bot Blocks**: The `Librarian` directs the `Sniper` to Tier-1 domains (`reuters.com`, `bloomberg.com`), but `Crawl4AI` is increasingly blocked by Cloudflare/DataDome on these premium domains.

**The Execution Plan:**
1. **Temporal Normalization (Mission 4.1)**: Upgrade the `TimeDetective` LLM Prompt. Instead of extracting a simple string for the date, force it to output a JSON Bounding Box: `{"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "human_readable": "Q3 2025"}`. This forces vague human text into mathematical constants.
2. **The Stealth Waterfall (Mission 4.2 - Future)**: Upgrade the `Sniper` to use a Residential Proxy Network API (e.g., ScrapingBee, BrightData). It will attempt the free `Crawl4AI` scrape first, and if it detects a block, it will failover to the premium proxy.

## Developer Instructions
- Code resides in `src/truebrief/`.
- Run tests from the root directory.
- For detailed architecture plans, read the markdown files in `docs/architecture/`.
- All code modifications should prioritize Metric Preservation (no smoothing numbers) and strict Python best practices.
