# The TrueBrief Master Plan: From Zero to Automated Income 🗺️

**Goal**: $10k/mo profit as a solo developer.
**Strategy**: Build a "B2B Intelligence Engine" first (high value), then wrap it as a "B2C App" later (high volume).

---

## 🏁 Phase 0: The Strategy & Pivot (Completed)
**Goal**: Stop working on a "dead end" idea (Generic News App).
- [x] **Market Analysis**: Analyzed why Artifact failed (General news is a commodity; people won't pay $5).
- [x] **The Pivot**: Decided to focus on "Professional Intelligence" (B2B/Prosumer) where accuracy = money.
- [x] **The Architecture**: Designed the "Delta Engine" (Input: Raw Data -> Output: New Facts Only).

## ⚙️ Phase 1: The Core Engine (Where We Are Now)
**Goal**: Prove we can technically find "Alpha" (new facts) cheaper than Bloomberg.
- [x] **The Radar**: Built logic to scan RSS feeds.
- [x] **The Sniper**: Built the "Stealth Browser" to bypass blocks (CyberGuard) and scrape high-value sites. **(DONE & VALID)**
- [x] **The Novelty Filter**: Implemented Vector DB (FastEmbed) to mathematically filter out "Old News."
- [x] **The Benchmark**: Proved the engine beats Google Search in finding specific facts (e.g., RunPod revenue).

> **Status**: 90% Complete. (Engine is functional code, just needs to be "wrapped" to run continuously).

---

## 🧠 Phase 2: The "Manager" Layer (Immediate Next Step)
**Goal**: Stop running scripts manually. Make the system autonomous.

### Mission 2.1: The Librarian Agent (COMPLETED)
**Goal**: Intelligent Source Discovery.
- [x] **Dual-Mode Discovery**: Build `search_tool.py` / `librarian.py`.
    - **Input**: User Topic (e.g., "Nvidia").
    - **Output**: 
        1. `rss_feeds` (Commodity context).
        2. `sniper_targets` (High-Value Static Pages like Investor Relations).
- [x] **Integration**: Connect Librarian to Radar (for RSS) and Sniper (for Static Targets).

### Mission 2.2: The "Topic Manager" (COMPLETED)
- [x] **Configuration**: Simple file to define {"Topic": "Nvidia", "Sources": [...]}.
- [x] **Persistence**: Ensure Qdrant saves correctly.

### Mission 2.3: The Scheduler (COMPLETED)
- [x] **Automation**: Script to run the cycle every 15 minutes.

### Mission 2.4: The Noise Filter (NEXT)
- [ ] **Goal**: Fix "Sidebar Hallucinations" (Lindsey Vonn in Nvidia Search).
- [ ] **Strategy**: Add "Topic-Aware" prompt constraints to the Verifier.


---

## 🖥️ Phase 3: The MVP Product (The "Dashboard")
**Goal**: Turn the "Log File" into something a human (or customer) can read.
- [ ] **The Alert System**: Connect to Telegram / Discord / Slack.
- [ ] **The Simple Dashboard**: Basic web page showing timeline of "Deltas".
- [ ] **The "Smoke Test" Sale**: Sell access to 5 beta testers for $50/mo.

## 📱 Phase 4: The B2C Expansion (The "App")
**Goal**: Use the profitable Engine to power a mass-market app.
- [ ] **The "Concierge" UI**: Mobile app interface.
- [ ] **The "Free Tier" Logic**: Delayed summaries for free users.
- [ ] **Text-to-Speech**: "Listen while driving" feature.

## 🌴 Phase 5: Maintenance & Scale (The Endgame)
**Goal**: Automated Passive Income.
- [ ] **API Access**: Open the JSON API for B2B2C.
- [ ] **Self-Healing**: Auto-fix broken scrapers.
- [ ] **Marketing Automation**: SEO pages from public facts.
