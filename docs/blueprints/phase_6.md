# Phase 6: Domain Intelligence Pipelines
> 📍 Read FIRST: [.ai/BOOT.md](file:///d:/projects/Apps/TrueBrief/.ai/BOOT.md)
> 📐 Status: `[ ]` Not Started

## Goal
Specialized domain pipelines for finance, legal, medical, and geopolitics. The long-term moat: 12+ months of domain-specific training data, custom extraction prompts, and specialized sources that no generalist competitor can replicate quickly.

**Build sequence:** Pick the domain your first B2B customer needs. Build ONE completely before starting the next. Each domain = a new market segment funded by B2B revenue.

---

## Step Summary
| # | Task | Status | PLAN | BUILD | UNIT | INTG |
|---|------|--------|---|---|---|---|
| 6.1 | Domain Router Brain | [ ] | [ ] | [ ] | [ ] | [ ] |
| 6.2 | Finance Intelligence Pipeline | [ ] | [ ] | [ ] | [ ] | [ ] |
| 6.3 | Legal Intelligence Pipeline | [ ] | [ ] | [ ] | [ ] | [ ] |
| 6.4 | Medical Intelligence Pipeline | [ ] | [ ] | [ ] | [ ] | [ ] |
| 6.5 | Fine-Tuned Local Router | [ ] | [ ] | [ ] | [ ] | [ ] |
| 6.6 | System-Wide Feedback Loop | [ ] | [ ] | [ ] | [ ] | [ ] |

---

### Step 6.1: Domain Router Brain

| Detail | Value |
|--------|-------|
| **What** | Classify incoming user queries into domains, then route to matching specialized pipelines |
| **Files** | `src/truebrief/router/domain_router.py`, `config/domain_config.yaml` |
| **Status** | `[ ]` |

#### Design

```python
# router/domain_router.py
class DomainRouter:
    """V1: LLM classifies user query into one or more domains."""

    DOMAINS = ["finance", "legal", "medical", "geopolitics", "technology", "general"]

    def classify(self, query: str) -> List[DomainMatch]:
        """
        Returns ordered list of matched domains with confidence scores.
        A query can match multiple domains: "FDA drug approval for Pfizer" → medical + finance.
        """
        prompt = ROUTER_PROMPT.format(query=query, domains=self.DOMAINS)
        result = llm.call("router", prompt)
        # Returns: [{"domain": "medical", "confidence": 0.92}, {"domain": "finance", "confidence": 0.71}]
        return [DomainMatch(**d) for d in result if d["confidence"] >= 0.60]

    def get_pipeline_config(self, domain: str) -> DomainPipelineConfig:
        """Returns domain-specific sources, harvester prompt, arbiter rules."""
        return load_domain_config(domain)
```

```
# LLM Prompt for domain classification
You are a news intelligence routing system. Classify this user query into one or more domains.

Query: {query}

Available domains: {domains}

Rules:
- A query can match multiple domains (e.g., "pharma earnings" = finance + medical)
- Assign confidence 0.0-1.0 for each match
- "general" is the fallback for queries that don't match specialized domains
- Output ONLY valid JSON: [{"domain": "...", "confidence": 0.0-1.0}, ...]
```

#### Multi-Domain Fan-Out

```python
# pipeline/runner.py (extended for Phase 6)
async def run_domain_pipeline(topic: Topic, user: User) -> Brief:
    domains = domain_router.classify(topic.raw_query)
    
    if len(domains) == 1 or domains[0].domain == "general":
        return await run_single_pipeline(topic, domains[0].domain, user)
    
    # Multi-domain: run pipelines in parallel, merge alphas before Arbiter
    results = await asyncio.gather(*[
        run_single_pipeline(topic, d.domain, user) for d in domains
    ])
    merged_alphas = merge_and_deduplicate(results)  # Cross-domain dedup
    return await briefer.generate(merged_alphas, topic)
```

#### Domain Config Schema
```yaml
# config/domain_config.yaml
finance:
  sources: [rss_layer, tavily_layer, brave_layer, sec_edgar_layer, exa_layer]
  harvester_prompt: finance_harvester_v1
  arbiter_rules:
    numeric_delta_threshold: 0.01   # 1% change in any number = UPDATE
    custom_fields: [ticker, financial_metric, period]
  confidence_floor: 0.70            # Finance facts require higher confidence
  
medical:
  sources: [rss_layer, tavily_layer, pubmed_layer, fda_layer]
  harvester_prompt: medical_harvester_v1
  arbiter_rules:
    numeric_delta_threshold: 0.05   # 5% change in trial data = UPDATE
    custom_fields: [drug_name, trial_phase, patient_count, p_value]
  confidence_floor: 0.80            # Medical facts require highest confidence

legal:
  sources: [rss_layer, tavily_layer, eu_reg_layer]
  harvester_prompt: legal_harvester_v1
  arbiter_rules:
    citation_aware: true
    custom_fields: [ruling_citation, jurisdiction, effective_date]
  confidence_floor: 0.75

geopolitics:
  sources: [rss_layer, tavily_layer, google_news_layer, brave_layer]
  harvester_prompt: geopolitics_harvester_v1
  arbiter_rules:
    entity_sensitivity: high   # Country/leader changes are always NEW, never MERGE
    custom_fields: [country, actor, conflict_region]
  confidence_floor: 0.65
```

#### Acceptance Criteria
- `domain_router.classify("TSMC earnings beat")` → `[finance(0.88), technology(0.72)]`
- `domain_router.classify("FDA approves Pfizer obesity drug")` → `[medical(0.95), finance(0.68)]`
- "general" fallback fires for any query scoring < 0.60 on all domains
- Router LLM call costs < $0.001 per query (Gemini Flash)
- Multi-domain fan-out merges alphas and deduplicates across domain runs before Arbiter

---

### Step 6.2: Finance Intelligence Pipeline

| Detail | Value |
|--------|-------|
| **What** | Specialized pipeline for financial intelligence — earnings, SEC filings, market events, ticker tracking |
| **Files** | `src/truebrief/domains/finance/harvester.py`, `src/truebrief/domains/finance/arbiter_rules.py`, `prompts/finance_harvester_v1.txt` |
| **Status** | `[ ]` |

#### What Makes Finance Different from General

| Dimension | General Pipeline | Finance Pipeline |
|-----------|-----------------|-----------------|
| Sources | RSS, Tavily, Brave | + SEC EDGAR, Exa (earnings PDFs) |
| Extraction | Any atomic fact | Must preserve: numbers, tickers, periods, % changes |
| Dedup rule | Cosine similarity | 1% change in any number = UPDATE (not MERGE) |
| Confidence floor | 0.60 | 0.70 (financial facts must be high confidence) |
| Alpha fields | Standard | + `ticker`, `financial_metric`, `reporting_period` |

#### Finance Harvester Prompt

```
You are a financial intelligence analyst. Extract every verifiable financial fact from this article.

For each fact:
1. alpha_text: The fact as one precise sentence. Always include:
   - Exact numbers with units ($, %, basis points, shares)
   - The specific ticker symbol if mentioned (e.g., TSMC, NVDA)
   - The reporting period (Q1 2026, FY2025, etc.)
   - Comparison vs prior period or analyst consensus if stated

2. financial_metric: What category is this? 
   ONE OF: revenue | eps | guidance | analyst_rating | price_target | 
           insider_trade | sec_filing | merger | dividend | buyback | other

3. ticker: Primary stock ticker if applicable (e.g., "TSM", "NVDA"). Null if none.

4. entities, event_date, context, confidence (same as standard prompt)

Rules:
- A 1% change in any financial number is a significant fact. Never round or approximate.
- "Revenue grew" without a number = SKIP (not verifiable).
- Analyst opinions without price targets = SKIP.
- Forward guidance must include specific number OR specific date range.

Output ONLY valid JSON.
```

#### Finance Arbiter Rules

```python
# domains/finance/arbiter_rules.py
class FinanceArbiterRules:
    """Override general arbiter thresholds for financial facts."""

    NUMERIC_DELTA_THRESHOLD = 0.01  # 1% change = UPDATE

    def is_numeric_update(self, new_alpha: Alpha, existing_alpha: Alpha) -> bool:
        """
        Extract numbers from both alphas. If same metric, same entity, same period,
        but different number (>1% delta) → UPDATE, not MERGE.
        """
        new_nums = extract_numbers(new_alpha.alpha_text)
        existing_nums = extract_numbers(existing_alpha.alpha_text)
        if not new_nums or not existing_nums:
            return False
        largest_delta = max(
            abs(n - e) / e for n, e in zip(new_nums, existing_nums) if e != 0
        )
        return largest_delta >= self.NUMERIC_DELTA_THRESHOLD
```

#### B2B Target: Hedge Funds & Analysts
**Value prop:** "Every earnings call, SEC filing, and analyst revision — deduplicated, delta-only, delivered via webhook within 5 minutes of publication."

**Pricing:** $500-2,000/mo for Finance Intelligence API access.

#### Acceptance Criteria
- Finance-specific alpha schema stored in `known_facts` with `ticker`, `financial_metric`, `reporting_period` JSONB fields
- `?financial_metric=revenue&ticker=NVDA` filter works on `/delta` endpoint
- Two articles reporting same earnings with different rounding → correctly detected as same alpha (MERGE)
- Two articles where EPS changed by $0.05 → correctly detected as UPDATE
- SEC 8-K filing ingested within 15 minutes of EDGAR publication (near real-time for Power/Enterprise)

---

### Step 6.3: Legal Intelligence Pipeline

| Detail | Value |
|--------|-------|
| **What** | Specialized pipeline for legal intelligence — court decisions, regulatory changes, compliance updates, citations |
| **Files** | `src/truebrief/domains/legal/harvester.py`, `src/truebrief/domains/legal/arbiter_rules.py`, `prompts/legal_harvester_v1.txt` |
| **Status** | `[ ]` |

#### What Makes Legal Different

| Dimension | General Pipeline | Legal Pipeline |
|-----------|-----------------|---------------|
| Sources | RSS, Tavily | + EUR-Lex, CourtListener, Federal Register |
| Extraction | Any atomic fact | Must preserve: citations, jurisdiction, effective dates, ruling parties |
| Dedup rule | Cosine similarity | Citation-aware: same case citation = same fact regardless of phrasing |
| Alpha fields | Standard | + `ruling_citation`, `jurisdiction`, `effective_date`, `ruling_type` |
| Confidence floor | 0.60 | 0.75 |

#### Legal Harvester Prompt

```
You are a legal intelligence analyst. Extract every verifiable legal fact from this article.

For each fact:
1. alpha_text: The fact as one precise sentence. Always include:
   - Full case citation or regulation number (e.g., "Case C-123/24", "GDPR Art. 17")
   - Jurisdiction (EU, US Federal, UK, California, etc.)
   - Ruling parties (plaintiff vs defendant, or regulatory body vs subject)
   - Effective date or ruling date

2. ruling_type: ONE OF: court_ruling | regulation | legislation | enforcement_action | 
                        settlement | opinion | compliance_deadline | other

3. jurisdiction: Country or region code (e.g., "EU", "US-Federal", "US-CA", "UK")

4. ruling_citation: Formal citation string (case number, regulation number, etc.)

5. effective_date: When does this take effect? YYYY-MM-DD or "unknown"

6. entities, event_date, context, confidence (same as standard prompt)

Rules:
- Legal facts MUST have a citation or formal reference. Vague legal claims = SKIP.
- Settlement amounts are financial facts — include exact numbers.
- "Proposed regulation" is a different fact from "enacted regulation" — note the status.

Output ONLY valid JSON.
```

#### Citation-Aware Deduplication

```python
# domains/legal/arbiter_rules.py
class LegalArbiterRules:
    def is_same_ruling(self, new_alpha: Alpha, existing_alpha: Alpha) -> bool:
        """
        If both alphas reference the same citation (case number, regulation ID),
        they are the same legal event. Merge even if phrased very differently.
        """
        new_citation = new_alpha.metadata.get("ruling_citation")
        existing_citation = existing_alpha.metadata.get("ruling_citation")
        if new_citation and existing_citation:
            return normalize_citation(new_citation) == normalize_citation(existing_citation)
        return False
```

#### B2B Target: Law Firms, Compliance Teams
**Value prop:** "Every EU regulation change, US court ruling, and compliance deadline — tracked automatically with full citation, effective date, and jurisdiction context."

#### Additional Sources for Legal
- **CourtListener** (courtlistener.com/api/) — US federal court opinions, free API
- **Federal Register** (federalregister.gov/api/) — US regulatory changes, free
- **EUR-Lex** (Step 5.6 plugin) — EU legislation and court decisions

#### Acceptance Criteria
- Legal alphas include `ruling_citation`, `jurisdiction`, `effective_date` fields
- Same court ruling covered by Reuters AND Bloomberg → MERGE (citation-aware)
- `GET /delta?ruling_type=court_ruling&jurisdiction=EU` filter works
- EU AI Act updates detected and delivered within 2 hours of EUR-Lex publication
- Contradictions flagged when two sources disagree on ruling outcome (won/lost)

---

### Step 6.4: Medical Intelligence Pipeline

| Detail | Value |
|--------|-------|
| **What** | Specialized pipeline for medical intelligence — clinical trials, drug approvals, research publications, safety alerts |
| **Files** | `src/truebrief/domains/medical/harvester.py`, `src/truebrief/domains/medical/arbiter_rules.py`, `prompts/medical_harvester_v1.txt` |
| **Status** | `[ ]` |

#### What Makes Medical Different

| Dimension | General Pipeline | Medical Pipeline |
|-----------|-----------------|-----------------|
| Sources | RSS, Tavily | + PubMed, FDA openFDA, ClinicalTrials.gov |
| Extraction | Any atomic fact | Must preserve: drug names, trial phases, patient counts, p-values, endpoints |
| Confidence floor | 0.60 | 0.80 (highest — medical misinformation is dangerous) |
| Alpha fields | Standard | + `drug_name`, `trial_phase`, `trial_id`, `primary_endpoint`, `p_value` |

#### Medical Harvester Prompt

```
You are a medical intelligence analyst. Extract every verifiable medical/clinical fact.

For each fact:
1. alpha_text: One precise sentence including:
   - Generic drug name (not brand names, or include both)
   - Trial phase (Phase 1/2/3/4) if applicable
   - Patient count (N=X) if stated
   - Primary endpoint and result (e.g., "met primary endpoint of 40% HbA1c reduction")
   - Statistical significance if stated (p<0.05, etc.)
   - Regulatory body if applicable (FDA, EMA, PMDA)

2. drug_name: Generic name of drug or intervention. Null if not applicable.
3. trial_phase: "Phase 1" | "Phase 2" | "Phase 3" | "Phase 4" | "Preclinical" | null
4. trial_id: ClinicalTrials.gov ID if mentioned (NCT number)
5. primary_endpoint: Brief description of what the trial measured

6. entities, event_date, context, confidence (same as standard prompt)

Rules:
- NEVER extract unverified claims, case reports without peer review, or social media medical claims.
- Conference presentations without peer review: confidence max 0.70.
- Peer-reviewed publications: confidence may reach 0.95.
- Preprints (medRxiv, bioRxiv): confidence max 0.65, note as "preprint".
- Patient count (N) is required for any trial result — no N = lower confidence.
- Minimum confidence for medical facts: 0.80.

Output ONLY valid JSON.
```

#### Clinical Trial Lifecycle Tracking

Medical alpha unique challenge: the same trial evolves over years. The Story Node system handles this naturally:

```
Story Node: "Pfizer oral GLP-1 (PF-07081532) Phase 3 OASIS trial"
├── Alpha: Phase 2 interim: 12.5% weight loss (N=700) [2025-03]
├── Alpha: Phase 3 enrollment complete (N=3,000) [2025-09]
├── Alpha: Phase 3 interim: 18.2% weight loss (p<0.001) [2026-02]
└── Alpha: FDA submission filed [2026-04]
```

Recursive summary captures the full trial arc, not just the latest update.

#### B2B Target: Pharma, Biotech, Healthcare Investors
**Value prop:** "Every trial result, FDA action, and competitive drug update — with full trial context, automatically tracked from Phase 1 through approval."

#### Additional Sources
- **ClinicalTrials.gov API** — NCT trial registry, free, comprehensive
- **FDA openFDA** (Step 5.6) — approvals, recalls, adverse events
- **PubMed/NCBI E-utilities** (Step 5.6) — peer-reviewed research

#### Acceptance Criteria
- Drug approval alpha includes: drug name, indication, FDA action type, approval date
- Trial result alpha includes: NCT number (if available), phase, N, primary endpoint result, p-value
- Same trial covered by multiple journals → MERGE on NCT number (citation-aware like legal)
- Preprint vs peer-reviewed same paper → UPDATE with confidence change noted
- `GET /delta?trial_phase=Phase%203&drug_name=semaglutide` filter works

---

### Step 6.5: Fine-Tuned Local Router

| Detail | Value |
|--------|-------|
| **What** | Replace the LLM-based domain classifier (V1) with a small fine-tuned model trained on TrueBrief's own routing history |
| **Files** | `src/truebrief/router/classifier.py`, `scripts/train_router.py`, `models/router/` |
| **Status** | `[ ]` |

#### Why This Matters
V1 router = 1 LLM call per topic creation (~$0.001). At 100K topics → $100/month just for routing. Worse: latency. A fine-tuned local classifier = <10ms, zero API cost.

#### Training Data Source
Every routing decision made since Phase 6.1 launch is logged:
```sql
-- routing_log table
CREATE TABLE routing_log (
    id UUID PRIMARY KEY,
    query TEXT,
    predicted_domain TEXT,
    confidence FLOAT,
    user_corrected_domain TEXT,   -- Filled if user gave feedback
    was_correct BOOL,
    created_at TIMESTAMPTZ
);
```

After 6 months: ~50K-500K labeled routing decisions. Gold for fine-tuning.

#### V2 Architecture

```python
# router/classifier.py
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression

class LocalDomainClassifier:
    """
    Lightweight classifier: sentence embedding → logistic regression → domain label.
    Trained on TrueBrief routing history. Runs locally, no API call.
    """
    
    def __init__(self):
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")   # 80MB, fast
        self.clf = joblib.load("models/router/classifier_v2.pkl")

    def classify(self, query: str) -> List[DomainMatch]:
        embedding = self.embedder.encode([query])
        probs = self.clf.predict_proba(embedding)[0]
        return [
            DomainMatch(domain=label, confidence=prob)
            for label, prob in zip(self.clf.classes_, probs)
            if prob >= 0.60
        ]
```

#### Training Script

```python
# scripts/train_router.py
def train():
    # Load labeled routing decisions from DB
    records = fetch_routing_log(min_samples=1000, only_confirmed=True)
    
    # Embed queries
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    X = embedder.encode([r.query for r in records])
    y = [r.confirmed_domain for r in records]
    
    # Train multi-label classifier
    clf = LogisticRegression(multi_class="ovr", max_iter=500)
    clf.fit(X, y)
    
    # Evaluate
    accuracy = cross_val_score(clf, X, y, cv=5).mean()
    print(f"5-fold CV accuracy: {accuracy:.3f}")
    
    # Save
    joblib.dump(clf, "models/router/classifier_v2.pkl")
```

#### Rollout Strategy
1. Run V2 alongside V1 for 2 weeks (shadow mode — log both results, use V1)
2. Compare agreement rate. If > 95% → switch to V2 as primary
3. V1 (LLM) as fallback when V2 confidence < 0.55

#### Acceptance Criteria
- Classifier loads and classifies a query in < 10ms (local inference)
- 5-fold CV accuracy ≥ 90% on held-out test set
- Shadow mode: V2 agreement with V1 ≥ 93% before going live
- `scripts/train_router.py` runs end-to-end in < 5 minutes on 50K samples
- Model versioned and stored in `models/router/` with training metadata (date, accuracy, sample count)
- V1 LLM fallback triggers when V2 confidence < 0.55 (with logging)

---

### Step 6.6: System-Wide Feedback Loop

| Detail | Value |
|--------|-------|
| **What** | Close the loop: user corrections on domain routing, alpha quality, and story classification feed back into system improvement automatically |
| **Files** | `src/truebrief/tasks/feedback_loop.py`, `scripts/retrain_router.py` |
| **Status** | `[ ]` |

#### Three Feedback Channels

**Channel 1: Domain Routing Corrections**
```python
# User sees a brief about FDA regulations filed under "general" instead of "medical"
# UI: "Wrong category?" → user selects correct domain → logged in routing_log
# Weekly Celery task: retrain router classifier if 1,000+ new confirmed samples
```

**Channel 2: Alpha Quality Corrections** (builds on Step 5.3)
```python
# User thumbs-down + reason "wrong_topic" on a finance alpha → 
# Feeds into: query_builder refinement for that topic, source deprioritization
# Feeds into: domain classifier — if topic consistently misrouted, adjust thresholds
```

**Channel 3: Story Node Corrections**
```python
# User sees two separate Story Nodes that should be one story →
# User action: "Merge these stories" → logged as StoryMergeCorrection
# Used to tune: story_manager's similarity threshold for clustering
```

#### Automated Retraining Pipeline

```python
# tasks/feedback_loop.py
@celery_app.task
def weekly_system_improvement():
    """Runs every Sunday 03:00 UTC."""

    # 1. Check if router retraining needed
    new_confirmations = count_routing_corrections_since_last_train()
    if new_confirmations >= 1000:
        retrain_domain_classifier()    # scripts/train_router.py
        log_retrain_event(new_confirmations)

    # 2. Update global AYR from past week's runs
    flush_ayr_to_global_network()

    # 3. Generate system health report
    report = {
        "arbiter_accuracy": calculate_arbiter_accuracy(),    # % of arbitrations confirmed by user feedback
        "router_accuracy": calculate_router_accuracy(),      # % of routings confirmed correct
        "ayr_top_sources": get_top_global_ayr_sources(n=10),
        "ayr_bottom_sources": get_bottom_global_ayr_sources(n=10),
    }
    send_weekly_report_to_admin(report)
```

#### System Health Dashboard (Admin)

Extend admin dashboard (Step 4.8) with a "System Intelligence" tab:

| Metric | What It Shows |
|--------|---------------|
| Router accuracy (7d) | % of routing decisions confirmed correct by feedback |
| Arbiter accuracy (7d) | % of NEW/MERGE/UPDATE decisions confirmed correct |
| Top AYR sources | Sources producing most new information globally |
| Bottom AYR sources | Sources to potentially prune or deprioritize |
| Feedback volume | Thumbs up/down counts, by topic domain |
| Story merge rate | How often users merge separate Story Nodes |

#### The Compounding Moat

```
More users → More routing corrections → Better classifier → Better domain routing
          → More alpha feedback → Better source ranking → Higher quality alphas
          → More story merges → Better narrative clustering → Better briefs
          → Users trust system more → More topics → More data → repeat
```

This flywheel cannot be bootstrapped by a new competitor. It requires 12+ months of real user feedback at scale.

#### Acceptance Criteria
- Weekly task runs automatically via Celery Beat without human intervention
- Router retraining only triggers if ≥ 1,000 new confirmed samples (prevents overfit on small batches)
- Retrained model auto-deployed only if new accuracy ≥ current accuracy - 0.02 (safety gate)
- Weekly system report emailed to admin automatically every Monday 08:00 UTC
- Feedback loop metrics visible in admin dashboard "System Intelligence" tab
- All feedback events immutable (append-only log) — never modify, only accumulate

---

## Phase 6 Architecture Summary

```
User Query
    │
    ▼
Domain Router (V1: LLM → V2: Fine-tuned local classifier)
    │
    ├─ finance ──────→ Finance Pipeline (SEC, Exa, custom prompt)
    ├─ legal ────────→ Legal Pipeline (EUR-Lex, CourtListener, citation-aware)
    ├─ medical ──────→ Medical Pipeline (PubMed, FDA, high confidence floor)
    ├─ geopolitics ──→ Geopolitics Pipeline (conflict trackers, diplo sources)
    └─ general ──────→ General Pipeline (RSS, Tavily, Brave, standard prompt)
                              │
                    (multi-domain: run in parallel, merge alphas)
                              │
                              ▼
                        Arbiter (domain-aware rules)
                              │
                              ▼
                      Story Node Manager
                              │
                              ▼
                          Briefer
                              │
                              ▼
                      User Feedback → System-Wide Feedback Loop
```

**The end state:** TrueBrief is not a news reader — it's a domain intelligence platform with specialized pipelines, a self-improving router, and a compounding data flywheel that grows more accurate with every user and every topic.

---
