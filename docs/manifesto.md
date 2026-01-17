# 📜 TRUEBRIEF MANIFESTO: THE PROJECT BIBLE
**Version:** 1.0 (Master Plan)
**Mission:** Cure information overload by manufacturing silence.
**Core Philosophy:** We do not sell "News." We sell the *absence* of noise.

---

## 1. EXECUTIVE SUMMARY

**The Problem:**
The world is split into two extremes:
1.  **The Noise:** Free apps (Google News, Twitter) are "Passive" and overwhelming. They want you to doom-scroll.
2.  **The Gatekeepers:** Professional tools (Bloomberg, FactSet) are "Expensive" and complex ($25k/yr).

**The Solution: Delta Engine**
An autonomous intelligence system that monitors the world's data streams 24/7 but remains silent until it detects a statistically **Novel Fact** ("Alpha"). It filters out 99% of repetitive information to deliver the 1% that counts.

---

## 2. THE PRODUCTS (Dual Strategy)

We build **One Engine** that powers **Two Products**.

### A. TrueBrief Pro (B2C / Prosumer)
*   **Target:** Traders, CEOs, Consultants, "Info-Obsessives."
*   **The Promise:** "The first news app designed to be empty. If nothing new happened, we tell you nothing."
*   **Key Features:**
    *   **Concierge Topics:** Highly specific tracks (e.g., "Lithium Mining Regulations," not "Business").
    *   **Quiet Mode:** Updates batched or sent instantly based on "Severity."
    *   **Fact Ledger:** A visual timeline showing the evolution of a story (provenance), not a list of articles.

### B. TrueBrief Intelligence API (B2B)
*   **Target:** Hedge Funds, PR Agencies, Competitive Intelligence Firms.
*   **The Promise:** "Clean, verified signals for your internal dashboards. No scraping required."
*   **Key Features:**
    *   **JSON Stream:** Direct feed of atomic facts.
    *   **Citation-Backed:** Source metadata and verification confidence score included.
    *   **Zero-Hallucination:** High-threshold verification layer.

---

## 3. BUSINESS MODEL (The Tiers)

| Tier | Price | User Type | Features | Economics |
| :--- | :--- | :--- | :--- | :--- |
| **Free** | $0 | Casual | Shared Topics Only (e.g., "Global Tech"). No custom tracking. | Zero Marginal Cost (1 run serves 1M users). Marketing funnel. |
| **Pro** | ~$20/mo | Prosumer | Custom Topics (Radar tracking). Instant Alerts. | High Margin. User pays for their own API calls + profit. |
| **Enterprise** | $500+/mo | Business | API Access. High-frequency monitoring. Custom Webhooks. | Volume Revenue. High-value contracts. |

---

## 4. TECHNICAL ARCHITECTURE: THE DELTA ENGINE

We do not build a "Feed." We build a **Fact Manufacturing Line**.

### **Layer 1: THE HUNTER (Acquisition)**
*Goal: Find data cheaply without paying premium API prices.*

*   **Step 1: The Radar (Discovery)**
    *   **Logic:** Polls free "Metadata" sources (RSS, Sitemaps). If a keyword spikes (e.g., "Nvidia" > 500% vol), pings Search API.
    *   **Tech:** `feedparser` (Python), `Serper.dev`.
*   **Step 2: The Sniper (Extraction)**
    *   **Logic:** Visits specific URLs found by Radar. Bypasses ads/popups. Extracts clean Markdown.
    *   **Tech:** `Crawl4AI` (Local Headless Browser).

### **Layer 2: THE BRAIN (Intelligence)**
*Goal: Turn text into "Alpha" (New Facts).*

*   **Step 3: The Atomizer (Cleaning)**
    *   **Logic:** Breaks articles into single sentences. **De-references pronouns** (changes "He said" → "Altman said") for atomic accuracy.
    *   **Tech:** `spaCy` (NLP), `GPT-4o-mini`.
*   **Step 4: The Novelty Filter (The Moat)**
    *   **Logic:** Converts facts into Vectors. Queries the **Fact Ledger** (Vector DB).
    *   **Rule:** If Cosine Similarity > 0.85 (Too similar) → **DELETE**.
    *   **Rule:** If Cosine Similarity < 0.85 → **KEEP** (Potential Alpha).
    *   **Tech:** `FastEmbed` (Local CPU Embeddings), `Qdrant` (Vector DB).
*   **Step 5: The Verifier (Quality Control)**
    *   **Logic:** LLM Check: "Does the source text explicitly support this fact?"
    *   **Tech:** `Gemini-1.5-Flash` (Low cost, High context).

### **Layer 3: THE MOUTH (Delivery)**
*Goal: Route the signal.*

*   **Step 6: The Router**
    *   **Logic:** Matches verified fact to User Interest Profiles. Pushes to App (B2C) or Webhook (B2B).
    *   **Tech:** `FastAPI` (Backend), `PostgreSQL` (User/Topic DB).

---

## 5. THE BUILD PLAN

### **Phase 1: The "Tracer Bullet" (Proof Of Concept)**
*Objective: Prove the Novelty Filter works locally.*
1.  **Mock Input:** Create a text file with 3 old articles and 1 new one.
2.  **Code Core:** Write `engine.py` (Atomizer + Novelty Filter).
3.  **Test:** Run script.
    *   *Pass Condition:* It prints **only** the new fact.

### **Phase 2: The "Hunter" Integration**
*Objective: Automate data collection.*
1.  **Build Radar:** Write script to poll 5 RSS feeds.
2.  **Build Sniper:** Integrate `Crawl4AI` to visit links automatically.
3.  **Connect:** Feed real web data into the `engine.py`.

### **Phase 3: The "Verifier" & Storage**
*Objective: Persist data and quality control.*
1.  **Add Database:** Set up `Qdrant` (Docker) to remember facts forever.
2.  **Add LLM Check:** Connect `Gemini-Flash` to verify facts before saving.

### **Phase 4: The Interface**
*Objective: Let users see the data.*
1.  **API:** Build `FastAPI` endpoints (`/add_topic`, `/get_updates`).
2.  **Simple UI:** A basic Dashboard or Telegram Bot.

---

## 6. STRATEGIC GUIDELINES (User defined)

*   **Vulnerability Warning:** The biggest risk is False Positives. Tune the Vector Threshold (0.85) carefully.
*   **Copyright Safety:** We extract **Facts** (Data), not **Stories** (Creative Expression). Always include the Source Link.
*   **Cost Control:** Use Local Compute (CPU) for Vectors/Scraping (`FastEmbed`, `Crawl4AI`). Use Paid Compute (API) only for Verification/Reasoning (`GPT-4o`, `Gemini`).
