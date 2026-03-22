# Implementation Plan - Mission 3.0: The Time Detective

## Goal Description
Convert TrueBrief from an "Event-Blind News Summarizer" into a "Time-Aware Intelligence Engine." 

Currently, the engine cannot distinguish between a *New Event* and an *Old Event* being recited, because the Vector Memory only checks semantic similarity without temporal context. Furthermore, the `Librarian` relies on generic search engines, leading to low-quality sources.

Mission 3.0 introduces:
1.  **Source Whitelisting (Tier 1)**: Moving from a "Shotgun Search" to "Targeted Monitoring" of high-trust domains (Reuters, SEC, Bloomberg).
2.  **Temporal Metadata Extraction**: Capturing `published_date` at the extraction layer.
3.  **The LLM Time Detective**: Combining Vector Similarity (Fast filtering) with LLM Reasoning (IQ) to determine if a semantically similar fact is an "Echo" or a "New Development/Update."

## Proposed Changes

---

### Step 1: The Foundation (Temporal Metadata)

#### [MODIFY] `src/truebrief/sniper.py`
- **Method**: `_shoot_async`
- **Change**: Configure `Crawl4AI` or use a secondary parser (like `BeautifulSoup` or `newspaper3k`) to explicitly extract the `published_date` meta tags (`<meta property="article:published_time">` or similar) alongside the markdown payload.
- **Output**: Return a dictionary `{"markdown": text, "published_date": date_string}` instead of just the markdown string.

#### [MODIFY] `src/truebrief/memory.py`
- **Method**: `add_fact` / `is_novel`
- **Change**: Update the Qdrant payload schema to accept and store the `published_date`. 
- **Change**: Modify `is_novel` to return the `published_date` and `payload` of the closest matches, not just the text.

---

### Step 2: The Core Logic (Context Verifier)

#### [NEW] `src/truebrief/context_verifier.py`
- **Class**: `TimeDetective`
- **Purpose**: Instead of dropping facts instantly if Vector similarity > 85%, we use this LLM agent to analyze the "Collision."
- **Logic**:
    1.  Receives `New Fact` (with publish date) and `Top 3 Historic Matches` (with publish dates).
    2.  Prompts the LLM: *"Here is historical context. Here is a new report. Is this new report a RECITATION of the old news, or a NEW UPDATE/DEVELOPMENT? Extract the actual 'Event Date' implied in the text."*
    3.  Returns a classification: `DUPLICATE`, `NEW_EVENT`, or `UPDATE`. If `UPDATE` or `NEW`, it outputs a final Alpha.

#### [MODIFY] `src/truebrief/engine.py` (The Brain V3)
- **Method**: `analyze`
- **Change**: Incorporate the `TimeDetective`. When `memory.is_novel` returns `False` (indicating a semantic match), DO NOT immediately drop the fact. Instead, collect the conflicting / similar historical points and pass them to `TimeDetective.evaluate(new_fact, history)`.

---

### Step 3: Source Trust (The White List)

#### [MODIFY] `src/truebrief/librarian.py`
- **Method**: `search_sources`
- **Change**: Hard-code a Target List (e.g., `["reuters.com", "sec.gov", "bloomberg.com", "apnews.com"]`). Modify the DDG search query to append `site:reuters.com OR site:sec.gov` etc., or build dedicated scrapers for these specific high-value endpoints.

## Verification Plan

### Automated Tests
-   **Test 1 (Recitation Detection)**: Ingest Fact A ("Trump proposes 10% tariffs", Jan 2024). Ingest Fact B ("Remember last year when Trump proposed 10% tariffs?", Feb 2024). Ensure Engine classifies B as `DUPLICATE`.
-   **Test 2 (Update Detection)**: Ingest Fact A ("TSMC yields hit 80%", Q1). Ingest Fact B ("TSMC yields improved to 92%", Q2). Ensure Engine classifies B as `UPDATE` and generates a Delta Alpha ("Yields increased from 80% to 92%").

### Manual Verification
-   Run the standard TSMC/Aramco benchmark and review database state to ensure `published_date` and `event_date` are populating correctly.
