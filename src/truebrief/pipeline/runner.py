"""
Pipeline Runner - pipeline/runner.py

Orchestrates the entire intelligence pipeline end-to-end.

Design Principles:
  - Sources are PLUG-IN/OUT: pass any list of SourceLayer instances to __init__.
  - Article selection uses MMR (Maximal Marginal Relevance), NOT greedy diversity.
  - All embeddings go through VectorStore.llm.embed(), the one canonical system.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import List, Optional

from config.settings import settings
from truebrief.llm.client import pipeline_run_id_var
from truebrief.collector.base import SourceLayer
from truebrief.collector.query_builder import QueryBuilder, SearchQuery, TopicDomain
from truebrief.collector.rss_layer import RSSLayer
from truebrief.collector.tavily_layer import TavilyLayer
from truebrief.collector.google_news_layer import GoogleNewsLayer
from truebrief.collector.brave_layer import BraveLayer
from truebrief.collector.exa_layer import ExaLayer
from truebrief.collector.extractor import ArticleExtractor
from truebrief.harvester.harvester import Harvester
from truebrief.ledger.vector_store import VectorStore
from truebrief.ledger.source_logger import SourceQualityLogger
from truebrief.ledger.query_rotator import QueryRotator
from truebrief.ledger.story_manager import StoryManager
from truebrief.ledger.story_summarizer import StorySummarizer
from truebrief.arbiter.arbiter import Arbiter
from truebrief.briefer.briefer import Briefer
from truebrief.briefer.state_of_play import StateOfPlayGenerator
from truebrief.verifier.verifier import Verifier
from truebrief.models.article import RawArticle
from truebrief.models.alpha import DecisionType

logger = logging.getLogger(__name__)

# Minimum and maximum articles processed per scan (adaptive-K, P2).
# Actual K = min(max(MIN_K, candidates // 3), MAX_K) — ~⅓ of candidates.
MIN_K = 5
MAX_K = 25

# MMR weights: relevance + recency together, minus diversity penalty.
# Must sum such that a single best article scores ~1.0.
MMR_LAMBDA = 0.62    # relevance weight (raised from 0.55; lowers implicit diversity to 0.23)
MMR_RECENCY = 0.15   # recency weight: today=+0.15, 5-day-old=+~0.02
# Implicit diversity weight: 1 - MMR_LAMBDA - MMR_RECENCY = 0.23

# Per-domain cap: after this many articles from one domain are selected,
# add a score penalty so other sources get a chance.
# Raised cap 2→3 and lowered penalty 0.35→0.20 so a second article from
# the same domain can still get in if it carries a materially different sub-detail.
MMR_DOMAIN_CAP = 3
MMR_DOMAIN_PENALTY = 0.20

# V3_RELEVANCE_GATE: minimum cosine similarity between an alpha and the topic query.
# Alphas below this are considered off-topic and dropped before the arbiter.
_RELEVANCE_THRESHOLD = 0.50

# IC2 significance × recency (lede salience). Class weight sets the ceiling; recency
# decays it so a current escalation outranks a stale state_change, while a current
# state_change still outranks a current tally. Floor keeps significance always relevant.
_CLASS_WEIGHT = {
    "state_change": 1.0,
    "escalation":   0.8,
    "development":  0.6,
    "casualty":     0.45,   # an individual death/injury — never leads over a state_change
    "incremental":  0.4,
    "routine":      0.2,
    "tally":        0.1,
}
_SALIENCE_RECENCY_FLOOR = 0.4   # a fact never decays below 40% of its class weight
_SALIENCE_HALF_LIFE_DAYS = 4.0  # recency multiplier ≈0.5 at 4 days old


def _salience_score(event_class: Optional[str], event_date, now: Optional[datetime] = None) -> float:
    """Significance × recency. Higher = leads the brief.

    salience = class_weight × (FLOOR + (1-FLOOR) × exp(-age_days / HALF_LIFE))
    Unknown class → neutral 0.5; unknown/future date → no recency penalty.
    """
    import math
    base = _CLASS_WEIGHT.get(event_class or "", 0.5)
    now = now or datetime.now()
    age_days = 0.0
    if event_date is not None:
        try:
            d = event_date
            if isinstance(d, str):
                d = datetime.fromisoformat(d.replace("Z", "+00:00"))
            if getattr(d, "tzinfo", None) is not None:
                d = d.replace(tzinfo=None)
            age_days = max(0.0, (now.replace(tzinfo=None) - d).total_seconds() / 86400.0)
        except Exception:
            age_days = 0.0
    recency = _SALIENCE_RECENCY_FLOOR + (1.0 - _SALIENCE_RECENCY_FLOOR) * math.exp(
        -age_days / _SALIENCE_HALF_LIFE_DAYS
    )
    return base * recency


class PipelineRunner:
    """
    Wires all pillars together:
    Topic → Collect (pluggable sources) → MMR Select → Harvest → Judge → Brief
    """

    def __init__(
        self,
        sources: Optional[List[SourceLayer]] = None,
        allowed_sources: Optional[List[str]] = None,
    ):
        """
        Args:
            sources: List of SourceLayer plugins to use for collection.
                     Defaults to [TavilyLayer, RSSLayer, GoogleNewsLayer].
                     Pass a custom list to plug in/out sources freely.
            allowed_sources: Optional allowlist of source names (e.g. ["rss", "tavily"]).
                             Filters the active source list down to the user's tier.
                             Pass ["__all__"] or None to skip filtering (POWER tier).
        """
        logger.info("Initializing Pipeline Components...")
        self.query_builder = QueryBuilder()
        self.extractor = ArticleExtractor()
        self.harvester = Harvester()
        self.verifier = Verifier()
        self.vector_store = VectorStore()
        self.arbiter = Arbiter(vector_store=self.vector_store)
        self.briefer = Briefer()
        self.state_of_play = StateOfPlayGenerator(llm_client=self.vector_store.llm)
        self.last_state_of_play = None  # latest generated block (IC7), exposed for callers
        self.source_logger = SourceQualityLogger()
        self.query_rotator = QueryRotator()
        self.story_manager = StoryManager(
            supabase_client=self.vector_store.db,
            llm_client=self.vector_store.llm,
        )
        self.story_summarizer = StorySummarizer(
            story_manager=self.story_manager,
            llm_client=self.vector_store.llm,
        )

        # Build default source list.
        all_sources: List[SourceLayer] = sources or [
            TavilyLayer(), RSSLayer(), GoogleNewsLayer(), BraveLayer(), ExaLayer()
        ]

        # Apply tier-based source filtering when an allowlist is provided.
        if allowed_sources and "__all__" not in allowed_sources:
            self.sources = [s for s in all_sources if s.name in allowed_sources]
            skipped = [s.name for s in all_sources if s.name not in allowed_sources]
            if skipped:
                logger.info("Tier source filter: skipping %s", skipped)
        else:
            self.sources = all_sources

    def run(self, topic_input: str, topic_id: Optional[str] = None) -> str:
        """
        Run the full intelligence pipeline for a given topic.
        Returns the formatted brief string.
        """
        import traceback
        self._trace_seq = 0
        try:
            start_time = time.time()
            logger.info(f"--- PIPELINE START: {topic_input} ---")
            self._trace(
                "start",
                f"Scan started: '{topic_input}'",
                topic_input=topic_input,
                topic_id=topic_id,
                sources_enabled=[s.name for s in self.sources],
            )

            # 1. Build / load search strategy
            # Design: QueryBuilder makes ONE LLM call at topic creation and caches the
            # result in topics.search_strategy. Subsequent scans skip the LLM entirely
            # and use UCB1 to rotate among stored variants.
            logger.info("[1] Building Search Strategy")
            _variant_id = None

            if topic_id and self.query_rotator.has_variants(topic_id):
                # Common path (all scans after the first): zero LLM calls here.
                query = self._load_strategy(topic_id, topic_input)
                logger.info(f"    [CACHED] topic_name='{query.topic_name}' — no LLM call")

                try:
                    _variant_id, best_query = self.query_rotator.select_variant(
                        topic_id=topic_id,
                        raw_query=topic_input,
                    )
                    if best_query != topic_input:
                        logger.info(f"    [UCB1] Variant: '{best_query[:60]}'")
                    query.primary_query = best_query
                except Exception as rot_err:
                    logger.warning(f"    [ROTATOR] UCB1 failed (non-fatal): {rot_err}")
                self._trace(
                    "query",
                    f"Cached strategy + UCB1 variant (no LLM call): '{query.primary_query}'",
                    mode="cached",
                    why="Topic already has variants — zero-LLM common path; UCB1 picked the variant below.",
                    topic_name=query.topic_name,
                    chosen_query=query.primary_query,
                    variant_id=_variant_id,
                    rss_categories=getattr(query, "rss_categories", None),
                )
            else:
                # First scan for this topic: one lifetime LLM call.
                query = self.query_builder.build(topic_input)
                if query.status == "REJECTED":
                    self._trace("query", f"Topic REJECTED: {query.reason}", mode="rejected", reason=query.reason)
                    return f"Topic rejected: {query.reason}"
                logger.info(f"    [LLM] Strategy built: {query.topic_name}")

                if topic_id:
                    self._store_strategy(topic_id, query)
                    try:
                        _variant_id, best_query = self.query_rotator.select_variant(
                            topic_id=topic_id,
                            raw_query=query.primary_query,
                            alt_queries=query.alt_queries,
                        )
                        query.primary_query = best_query
                    except Exception as rot_err:
                        logger.warning(f"    [ROTATOR] Init failed (non-fatal): {rot_err}")
                self._trace(
                    "query",
                    f"Fresh LLM strategy (1 lifetime call): '{query.primary_query}'",
                    mode="llm_build",
                    why="First scan for this topic — QueryBuilder made its one lifetime LLM call; "
                        "variants seeded for future UCB1 rotation. (Prompt/response in llm_call_log, stage=query_builder.)",
                    topic_name=query.topic_name,
                    chosen_query=query.primary_query,
                    alt_queries=getattr(query, "alt_queries", None),
                    variant_id=_variant_id,
                    rss_categories=getattr(query, "rss_categories", None),
                )

            # 2. Collect Raw Articles
            logger.info("[2] Collecting Sources")

            # 2a. Dynamic blocklist: skip domains with >75% extraction fail rate.
            _blocked_domains: set[str] = set()
            if settings.V3_DYNAMIC_BLOCKLIST:
                try:
                    from truebrief.ledger.domain_stats import get_blocked_domains
                    _blocked_domains = get_blocked_domains()
                except Exception:
                    pass

            # 2b. UCB1 tool selection: after cold-start (3 scans), skip low-AYR paid tools.
            # Free tools (RSS, Google News) always fire. Degrades to all-fire if migration
            # 017 not applied or if this is the first few scans (cold-start exploration).
            _active_sources = self.sources
            if settings.V3_TOOL_UCB1 and topic_id:
                try:
                    from truebrief.ledger.source_stats import get_tool_fire_set
                    _fire_set = get_tool_fire_set(
                        topic_id, [s.name for s in self.sources]
                    )
                    _active_sources = [s for s in self.sources if s.name in _fire_set]
                    skipped = [s.name for s in self.sources if s.name not in _fire_set]
                    if skipped:
                        logger.info("    [UCB1-TOOL] Skipping low-AYR tools: %s", skipped)
                except Exception:
                    pass

            if settings.V3_DOMAIN_QUERIES and query.domains:
                raw_articles = self._collect_all_domains(
                    query, _blocked_domains, sources=_active_sources
                )
            else:
                raw_articles = self._collect_all(
                    query, _blocked_domains, sources=_active_sources
                )
            logger.info(f"    Collected {len(raw_articles)} candidate articles total.")

            # Build url→tool map for per-tool AYR attribution later in the run.
            _url_to_tool: dict[str, str] = {
                a.url: getattr(a.source_type, "value", "unknown")
                for a in raw_articles
            }

            if not raw_articles:
                logger.info("    No articles found. Ending early.")
                self._trace("collect", "No articles returned by any source — ending early.", total=0)
                return ""

            # 2b. URL dedup: skip articles already processed for this topic in the last 14 days
            if topic_id:
                try:
                    seen_urls = self.vector_store.get_seen_urls(topic_id, days=14)
                    before = len(raw_articles)
                    dropped_urls = [a.url for a in raw_articles if a.url in seen_urls]
                    raw_articles = [a for a in raw_articles if a.url not in seen_urls]
                    skipped = before - len(raw_articles)
                    if skipped:
                        logger.info(f"    URL dedup: skipped {skipped} already-processed articles.")
                    self._trace(
                        "dedup",
                        f"URL dedup: {skipped} already-seen skipped, {len(raw_articles)} remain.",
                        skipped=skipped,
                        remaining=len(raw_articles),
                        skipped_urls=dropped_urls[:25],
                    )
                except Exception as dedup_err:
                    logger.warning(f"    URL dedup failed (non-fatal): {dedup_err}")

            if not raw_articles:
                logger.info("    All articles already processed. Ending early.")
                self._trace("dedup", "All candidate articles were already processed — ending early.", remaining=0)
                return ""

            # 2c. Near-dup / syndication collapse (V3): same story, different URL → keep one.
            if settings.V3_NEARDUP_COLLAPSE and len(raw_articles) > 1:
                try:
                    from truebrief.collector.dedup import collapse_near_duplicates
                    raw_articles, collapsed = collapse_near_duplicates(raw_articles)
                    if collapsed:
                        logger.info(f"    Near-dup collapse: dropped {len(collapsed)} syndicated articles.")
                    self._trace(
                        "dedup",
                        f"Near-dup collapse: {len(collapsed)} syndicated dropped, {len(raw_articles)} remain.",
                        collapsed=len(collapsed),
                        remaining=len(raw_articles),
                        collapsed_articles=collapsed[:25],
                    )
                except Exception as nd_err:
                    logger.warning(f"    Near-dup collapse failed (non-fatal): {nd_err}")

            # 3. MMR Selection (adaptive-K: ~⅓ of candidates, MIN_K–MAX_K).
            # Widened from //5→//3 (2026-06-21): vs a full-index competitor the
            # long-tail completeness facts (e.g. nuclear-inspection detail) sit in
            # articles 7–12; reading only 18% of a hot day's pool left them on the floor.
            _k = min(max(MIN_K, len(raw_articles) // 3), MAX_K)
            logger.info(f"[3] Selecting top {_k} diverse articles via MMR (adaptive-K from {len(raw_articles)} candidates)...")
            selected = self._mmr_select(query=query, articles=raw_articles, limit=_k)
            logger.info(f"    MMR selected {len(selected)} articles.")
            self._trace(
                "mmr",
                f"MMR selected {len(selected)} of {len(raw_articles)} candidates (λ={MMR_LAMBDA}, recency={MMR_RECENCY}, K={_k}).",
                why=f"Adaptive-K (~20% of candidates, {MIN_K}–{MAX_K}). "
                    f"MMR: {int(MMR_LAMBDA*100)}% relevance + {int(MMR_RECENCY*100)}% recency − "
                    f"{int((1-MMR_LAMBDA-MMR_RECENCY)*100)}% diversity. Per-pick scores in 'selected'.",
                candidates=len(raw_articles),
                limit=_k,
                selected=getattr(self, "_last_mmr_scores", None) or [
                    {"title": a.title, "url": a.url, "source": getattr(a.source_type, "value", str(a.source_type))}
                    for a in selected
                ],
            )

            # 4. Harvesting
            logger.info("[4] Harvesting Facts (Alphas)")
            all_alphas = []
            article_texts: dict = {}  # url → text; passed to Verifier for entity grounding
            for i, article in enumerate(selected):
                logger.info(f"    Processing article {i+1}/{len(selected)}: {article.url}")
                article = self.extractor.extract(article)
                if not article.text:
                    self._trace(
                        "harvest",
                        f"[{i+1}/{len(selected)}] Extraction returned no text — skipped: {article.url}",
                        article_url=article.url, article_title=article.title, alphas=0, skipped="no_text",
                    )
                    continue
                article_texts[article.url] = article.text
                alphas = self.harvester.extract(
                    article,
                    topic_id=topic_id,
                    topic_context=query.topic_name or topic_input,
                )
                all_alphas.extend(alphas)
                self._trace(
                    "harvest",
                    f"[{i+1}/{len(selected)}] {len(alphas)} fact(s) from {article.source_name or article.url}",
                    why="Harvester LLM call — exact prompt & raw response in llm_call_log (stage=harvester).",
                    article_url=article.url,
                    article_title=article.title,
                    article_chars=len(article.text or ""),
                    alphas=len(alphas),
                    facts=[a.alpha_text[:300] for a in alphas],
                )
                if i < len(selected) - 1:
                    time.sleep(2)
            logger.info(f"    Harvested {len(all_alphas)} total facts.")

            # 4b. Verification (entity grounding + cross-source + date sanity)
            logger.info("[4b] Verifying Facts")
            try:
                all_alphas = self.verifier.verify_batch(all_alphas, article_texts)
            except Exception as ver_err:
                logger.warning(f"    Verifier failed (non-fatal, continuing): {ver_err}")

            # 4c. V3 Relevance gate — drop off-topic facts before judging.
            # Pre-embedding here means the arbiter reuses these embeddings; no extra calls.
            if settings.V3_RELEVANCE_GATE and all_alphas:
                try:
                    topic_text = query.topic_name or topic_input
                    topic_emb = self.vector_store.llm.embed(topic_text)
                    alpha_embs = self.vector_store.llm.embed_batch(
                        [a.alpha_text for a in all_alphas]
                    )
                    before_gate = len(all_alphas)
                    gated = []
                    dropped_detail = []
                    for alpha, emb in zip(all_alphas, alpha_embs):
                        alpha.embedding = emb
                        sim = self._cosine_similarity(emb, topic_emb)
                        if sim >= _RELEVANCE_THRESHOLD:
                            gated.append(alpha)
                        else:
                            dropped_detail.append({"sim": round(sim, 3), "text": alpha.alpha_text[:200]})
                            logger.info(
                                f"    [RELEVANCE GATE] dropped (sim={sim:.3f}): "
                                f"{alpha.alpha_text[:70]}"
                            )
                    dropped_gate = before_gate - len(gated)
                    if dropped_gate:
                        logger.info(
                            f"    Relevance gate: {len(gated)} kept, {dropped_gate} dropped"
                        )
                    self._trace(
                        "relevance",
                        f"Relevance gate: kept {len(gated)}, dropped {dropped_gate} "
                        f"(threshold cosine ≥ {_RELEVANCE_THRESHOLD} vs topic '{topic_text}').",
                        threshold=_RELEVANCE_THRESHOLD,
                        topic_text=topic_text,
                        kept=len(gated),
                        dropped=dropped_gate,
                        dropped_facts=dropped_detail,
                    )
                    all_alphas = gated
                except Exception as rel_err:
                    logger.warning(f"    Relevance gate failed (non-fatal): {rel_err}")

            # 5. Judging
            logger.info("[5] Judging Novelty")
            decisions = []
            # judge_alphas batches the grey-zone Judge LLM calls into one request
            # when V3_BATCH_JUDGE is on; otherwise it judges each fact individually
            # (identical to the old per-alpha loop). Order matches all_alphas.
            judged = self.arbiter.judge_alphas(all_alphas, topic_id=topic_id)
            for alpha, decision in zip(all_alphas, judged):
                decisions.append(decision)
                self._trace(
                    "judge",
                    f"{getattr(decision.decision, 'value', decision.decision)}: {alpha.alpha_text[:120]}",
                    why="Arbiter: semantic+temporal(+entity) similarity vs the existing ledger. "
                        "Grey-zone calls hit the Judge LLM (prompt/response in llm_call_log, stage=arbiter).",
                    decision=getattr(decision.decision, "value", str(decision.decision)),
                    alpha_text=alpha.alpha_text[:300],
                    event_date=str(getattr(alpha, "event_date", "") or ""),
                    similarity_score=round(getattr(decision, "similarity_score", 0) or 0, 4),
                    matched_alpha_id=getattr(decision, "matched_alpha_id", None),
                    reasoning=getattr(decision, "reasoning", None),
                )
                if decision.decision in (DecisionType.NEW, DecisionType.UPDATE):
                    story_node_id = None
                    if not settings.V3_PAUSE_STORY_GRAPH:
                        try:
                            story_node_id = self.story_manager.assign_to_story(
                                decision, topic_id=topic_id
                            )
                            if story_node_id:
                                logger.info(f"    → Story: {story_node_id}")
                        except Exception as story_err:
                            logger.warning(f"    Story assignment failed: {story_err}")

                    try:
                        self.vector_store.add_fact(
                            decision.alpha, story_node_id=story_node_id
                        )
                    except Exception as e:
                        logger.error(f"    Failed to save fact: {e}")

                    if story_node_id and not settings.V3_PAUSE_STORY_GRAPH:
                        try:
                            self.story_summarizer.refresh_summary(
                                story_node_id=story_node_id,
                                new_alpha=decision.alpha,
                            )
                        except Exception as sum_err:
                            logger.warning(f"    Summary refresh failed: {sum_err}")
            logger.info(f"    Novelty check complete. {len(decisions)} decisions made.")

            # 5.5 Targeted follow-up fetch on state_change NEW facts.
            # The main MMR diversity penalty can suppress a second article from the same event
            # thread even when that article contains a materially different sub-detail (e.g.,
            # delegation walkout buried inside a broader Switzerland talks piece). Here we
            # re-query Tavily once per state_change alpha to catch those sub-details.
            # Runs AFTER add_fact() above, so the arbiter deduplicates correctly.
            if settings.V3_FOLLOWUP_FETCH:
                try:
                    _state_changes = [
                        d for d in decisions
                        if d.decision == DecisionType.NEW
                        and getattr(d.alpha, "event_class", "") == "state_change"
                    ][:3]
                    if _state_changes:
                        _followup = self._collect_and_judge_followup(
                            _state_changes, query, topic_input, topic_id,
                            seen_urls={a.url for a in raw_articles},
                        )
                        if _followup:
                            decisions.extend(_followup)
                            logger.info(
                                "[5.5] Follow-up added %d new decision(s).", len(_followup)
                            )
                except Exception as _fu_err:
                    logger.debug("[5.5] Follow-up fetch failed (non-fatal): %s", _fu_err)

            # 5b. Log source quality (fire-and-forget - never blocks the pipeline)
            _alphas = sum(1 for d in decisions if d.decision.value in ("NEW", "UPDATE"))
            _dupes  = len(decisions) - _alphas
            logger.info(f"    Alpha/Dupe breakdown: {_alphas} alpha, {_dupes} duplicate")
            self.source_logger.log_batch(decisions, topic_id)

            # 5c. Record variant performance for keyword rotation
            if topic_id and _variant_id:
                try:
                    self.query_rotator.record_result(
                        variant_id=_variant_id,
                        alphas_produced=_alphas,
                        topic_id=topic_id,
                        raw_query=topic_input,
                    )
                except Exception as rot_err:
                    logger.warning(f"    [ROTATOR] record_result failed: {rot_err}")


            # 5d. IC2 significance × recency sort: order NEW/UPDATE decisions so the briefer
            # leads with the most significant CURRENT development. A stale state_change no
            # longer outranks a fresh escalation; a fresh tally still sits last.
            if settings.V3_DEV_CLASS_RANK:
                _now = datetime.now()
                decisions = sorted(
                    decisions,
                    key=lambda d: _salience_score(d.alpha.event_class, d.alpha.event_date, _now),
                    reverse=True,
                )
                logger.info("[5d] Decisions sorted by significance × recency (lede salience).")

            # 6. Briefing
            logger.info("[6] Generating Brief")
            # SOP lede: load the topic's stored state-of-play situation line (grounded,
            # re-derived from facts) as the bottom-line anchor.
            _sop_situation = None
            if settings.V3_SOP_LEDE and topic_id:
                try:
                    from truebrief.ledger.state_of_play_store import load_state_of_play
                    _stored = load_state_of_play(topic_id)
                    if _stored:
                        _sop_situation = _stored.get("situation")
                except Exception:
                    pass
            # V3 (§5/§15 step 4): assemble the brief from fact+context with NO LLM — removes
            # the briefer's editorial synthesis. Falls back to the LLM briefer when flag is off.
            if settings.V3_NO_LLM_BRIEF:
                from truebrief.briefer.assembler import assemble_brief
                brief_text = assemble_brief(decisions, query.topic_name, situation=_sop_situation)
                logger.info("[6] Brief assembled from facts (no LLM).")
            else:
                brief_text = self.briefer.generate(decisions, query.topic_name, situation=_sop_situation)

            # 6b. IC7 State-of-play: regenerate the topic status block ONLY when a
            # state_change fact landed this run (cheap — at most one extra LLM call,
            # and only on material change). Facts-only, fire-and-forget, never blocks.
            if settings.V3_STATE_OF_PLAY and topic_id:
                self._maybe_refresh_state_of_play(decisions, topic_id, query.topic_name)

            # 6b-2. History doc (§7.2) — rebuild the topic's no-LLM "story so far" timeline
            # whenever new/updated facts landed this run. Pure data, fire-and-forget.
            if settings.V3_HISTORY_DOC and topic_id and _alphas > 0:
                try:
                    from truebrief.ledger.history_doc import store_history_doc
                    store_history_doc(topic_id)
                except Exception as _hist_err:
                    logger.debug("History doc rebuild failed (non-fatal): %s", _hist_err)

            end_time = time.time()
            logger.info(f"--- PIPELINE COMPLETE ({end_time - start_time:.1f}s) ---")
            self._trace(
                "brief",
                f"Brief generated: {len(brief_text or '')} chars from "
                f"{_alphas} new/updated fact(s) in {end_time - start_time:.1f}s.",
                why="Briefer LLM call — full prompt/response in llm_call_log (stage=briefer).",
                brief_length=len(brief_text or ""),
                new_or_updated=_alphas,
                duplicates=_dupes,
                brief_preview=(brief_text or "")[:2000],
            )
            # 6c. Update per-tool AYR matrix (fire-and-forget; never blocks delivery).
            # Attribute each new/update alpha back to the tool that sourced its article.
            if topic_id:
                try:
                    from collections import Counter as _Counter
                    from truebrief.ledger.source_stats import update_tool_stats

                    # Count articles offered and selected per tool
                    _tool_offered = _Counter(
                        getattr(a.source_type, "value", "unknown") for a in raw_articles
                    )
                    _tool_selected = _Counter(
                        _url_to_tool.get(a.url, "unknown") for a in selected
                    )
                    # Count new/update alphas per tool via url→tool map
                    _tool_new: _Counter = _Counter()
                    for d in decisions:
                        if d.decision in (DecisionType.NEW, DecisionType.UPDATE):
                            tool = _url_to_tool.get(d.alpha.source_url, "unknown")
                            _tool_new[tool] += 1

                    _tool_results = {}
                    all_tool_names = (
                        set(_tool_offered) | set(_tool_selected) | set(_tool_new)
                    )
                    for t in all_tool_names:
                        _tool_results[t] = {
                            "offered":    _tool_offered.get(t, 0),
                            "selected":   _tool_selected.get(t, 0),
                            "new_alphas": _tool_new.get(t, 0),
                        }
                    update_tool_stats(topic_id, _tool_results)
                    logger.info("[6c] Tool AYR matrix updated: %s", {
                        t: v["new_alphas"] for t, v in _tool_results.items()
                    })
                except Exception as _ts_err:
                    logger.debug("Tool stats update failed (non-fatal): %s", _ts_err)

            # Expose counts so pipeline_task.py can pass them to finish_run.
            self.last_run_stats = {
                "articles_collected":  len(raw_articles),
                "articles_selected":   len(selected),
                "alphas_extracted":    len(all_alphas),
                "decisions_new":       sum(1 for d in decisions if d.decision == DecisionType.NEW),
                "decisions_update":    sum(1 for d in decisions if d.decision == DecisionType.UPDATE),
                "decisions_duplicate": sum(1 for d in decisions if d.decision == DecisionType.DUPLICATE),
            }
            return brief_text
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"PIPELINE CRASHED: {e}\nTraceback:\n{tb}")
            self._trace("error", f"Pipeline crashed: {e}", error=str(e), traceback=tb[:4000])
            raise e

    # -------------------------------------------------------------------------
    # IC14: targeted follow-up fetch on high-significance state_change facts
    # -------------------------------------------------------------------------

    def _collect_and_judge_followup(
        self,
        state_changes: list,
        query,
        topic_input: str,
        topic_id,
        seen_urls: set,
    ) -> list:
        """
        Re-query Tavily once per state_change NEW alpha using the alpha text as the
        search query. Catches sub-details (delegation walkouts, command changes, etc.)
        that MMR diversity suppressed because the parent article was already selected.

        Returns a list of additional AlphaDecision objects with decision=NEW/UPDATE.
        Runs after add_fact() for the main pass, so the arbiter can correctly
        deduplicate against facts already committed to the ledger.
        """
        from truebrief.models.alpha import DecisionType as _DT

        tavily = next((s for s in self.sources if s.name == "tavily"), None)
        if not tavily:
            return []

        extra: list = []
        for sc_decision in state_changes:
            try:
                # Use alpha_text[:100] as the targeted sub-query.
                claim = sc_decision.alpha.alpha_text[:100]
                from truebrief.collector.query_builder import SearchQuery as _SQ
                fq = _SQ(topic_name=query.topic_name, primary_query=claim, alt_queries=[])
                articles = tavily.search(fq)
                new_arts = [a for a in articles if a.url not in seen_urls]
                if not new_arts:
                    continue
                seen_urls.update(a.url for a in new_arts)
                logger.info("[5.5] '%s...' → %d follow-up articles", claim[:50], len(new_arts))

                # Extract text
                extracted = [self.extractor.extract(a) for a in new_arts]
                extracted = [a for a in extracted if a.text]
                if not extracted:
                    continue

                # Harvest facts
                fu_alphas = []
                for article in extracted:
                    try:
                        fu_alphas.extend(self.harvester.extract(article, topic_id=topic_id))
                    except Exception:
                        pass
                if not fu_alphas:
                    continue

                # Relevance gate
                if settings.V3_RELEVANCE_GATE and fu_alphas:
                    topic_text = query.topic_name or topic_input
                    topic_emb = self.vector_store.llm.embed(topic_text)
                    embs = self.vector_store.llm.embed_batch([a.alpha_text for a in fu_alphas])
                    gated = []
                    for alpha, emb in zip(fu_alphas, embs):
                        alpha.embedding = emb
                        if self._cosine_similarity(emb, topic_emb) >= _RELEVANCE_THRESHOLD:
                            gated.append(alpha)
                    fu_alphas = gated
                if not fu_alphas:
                    continue

                # Judge and store new facts
                judged = self.arbiter.judge_alphas(fu_alphas, topic_id=topic_id)
                for alpha, decision in zip(fu_alphas, judged):
                    if decision.decision in (_DT.NEW, _DT.UPDATE):
                        try:
                            self.vector_store.add_fact(decision.alpha)
                        except Exception:
                            pass
                        extra.append(decision)
                        logger.info("[5.5] NEW follow-up: %s", alpha.alpha_text[:80])

            except Exception as e:
                logger.debug("[5.5] Follow-up for '%s' failed: %s", sc_decision.alpha.alpha_text[:40], e)

        return extra

    # -------------------------------------------------------------------------
    # IC7: state-of-play regeneration (only on material change)
    # -------------------------------------------------------------------------

    def _maybe_refresh_state_of_play(
        self, decisions: List, topic_id: str, topic_name: str
    ) -> None:
        """Regenerate the topic status block iff a state_change fact landed. Never raises."""
        try:
            landed_state_change = any(
                d.decision in (DecisionType.NEW, DecisionType.UPDATE)
                and (d.alpha.event_class == "state_change")
                for d in decisions
            )
            if not landed_state_change:
                logger.info("[6b] No state_change this run — state-of-play unchanged.")
                return

            # Pull the topic's recent stored facts (most significant/recent first).
            res = (
                self.vector_store.db.table("known_facts")
                .select("alpha_text, event_class, event_date, source_domain")
                .eq("topic_id", topic_id)
                .order("event_date", desc=True)
                .limit(40)
                .execute()
            )
            facts = res.data or []
            if not facts:
                return

            block = self.state_of_play.generate(facts, topic_name)
            if block:
                self.last_state_of_play = block  # exposed for benchmark / callers
                from truebrief.ledger.state_of_play_store import save_state_of_play
                save_state_of_play(topic_id, block)
                logger.info(
                    f"[6b] State-of-play refreshed: {len(block.get('threads', []))} threads."
                )
        except Exception as exc:
            logger.warning(f"[6b] State-of-play refresh skipped (non-fatal): {exc}")

    # -------------------------------------------------------------------------
    # Observability: per-run trace (writes to pipeline_trace via TelemetryLogger)
    # -------------------------------------------------------------------------

    def _trace(self, stage: str, label: Optional[str] = None, **data) -> None:
        """Record one structured trace event for the current run. Never raises.

        No-ops when TRACE_PIPELINE is off or there is no active pipeline_run
        (e.g. unit tests call run() directly without telemetry).
        """
        if not getattr(settings, "TRACE_PIPELINE", False):
            return
        try:
            run_id = pipeline_run_id_var.get()
            if not run_id:
                return
            from truebrief.ledger.telemetry import get_telemetry
            tel = get_telemetry()
            if tel is None:
                return
            self._trace_seq = getattr(self, "_trace_seq", 0) + 1
            tel.log_trace(run_id, seq=self._trace_seq, stage=stage, label=label, data=data)
        except Exception:
            pass  # observability must never break the pipeline

    # -------------------------------------------------------------------------
    # Collection
    # -------------------------------------------------------------------------

    def _collect_all(
        self,
        query: SearchQuery,
        blocked_domains: Optional[set] = None,
        sources: Optional[List[SourceLayer]] = None,
    ) -> List[RawArticle]:
        """
        Run all plugged-in sources and aggregate their results.
        For keyword-based sources like RSS, filters by query keywords to avoid
        off-topic articles from general feeds.
        blocked_domains: set of domains to skip (from dynamic blocklist).
        """
        blocked_domains = blocked_domains or set()
        active_sources = sources if sources is not None else self.sources
        all_articles: List[RawArticle] = []
        seen_urls: set = set()

        for source in active_sources:
            try:
                articles = source.search(query)
                logger.info(f"  [{source.name}] returned {len(articles)} articles.")

                kept_here = []
                for a in articles:
                    if a.url in seen_urls:
                        continue
                    seen_urls.add(a.url)

                    # Drop articles from domains with high extraction fail rates.
                    if blocked_domains:
                        from truebrief.ledger.domain_stats import _to_domain
                        if _to_domain(a.url) in blocked_domains:
                            continue

                    all_articles.append(a)
                    kept_here.append(a)

                self._trace(
                    "collect",
                    f"[{source.name}] returned {len(articles)}, kept {len(kept_here)} after dedup filter.",
                    source=source.name,
                    query=query.primary_query,
                    returned=len(articles),
                    kept=len(kept_here),
                    articles=[{"title": a.title, "url": a.url} for a in kept_here[:20]],
                )

            except Exception as e:
                logger.error(f"Source [{source.name}] failed: {e}")
                self._trace(
                    "collect",
                    f"[{source.name}] FAILED: {e}",
                    source=source.name, error=str(e), returned=0, kept=0,
                )

        return all_articles

    def _collect_all_domains(
        self,
        query: SearchQuery,
        blocked_domains: Optional[set] = None,
        sources: Optional[List[SourceLayer]] = None,
    ) -> List[RawArticle]:
        """
        Parallel multi-domain collection (V3_DOMAIN_QUERIES).

        Strategy:
          - RSS / broad sources: fire ONCE with the topic query (category-based, query-agnostic).
          - Targeted engines (Tavily, Google News): fire ONE call per domain in parallel,
            each using that domain's primary query → surfaces articles the other domains wouldn't.
          - Results from all domains are URL-deduped before returning.

        This mirrors the approach Gemini Search uses: diverse retrieval at query stage
        rather than post-hoc diversity enforcement only at MMR.
        """
        import concurrent.futures as _cf
        blocked_domains = blocked_domains or set()
        active_sources = sources if sources is not None else self.sources

        # Targeted engines benefit from per-domain queries; broad sources are category-based.
        _TARGETED = {"tavily", "brave", "exa", "google_news"}
        rss_sources = [s for s in active_sources if s.name not in _TARGETED]
        targeted_sources = [s for s in active_sources if s.name in _TARGETED]

        all_articles: List[RawArticle] = []
        seen_urls: set = set()

        def _add(articles: List[RawArticle]) -> int:
            added = 0
            for a in articles:
                if a.url in seen_urls:
                    continue
                seen_urls.add(a.url)
                if blocked_domains:
                    from truebrief.ledger.domain_stats import _to_domain
                    if _to_domain(a.url) in blocked_domains:
                        continue
                all_articles.append(a)
                added += 1
            return added

        # Step 1: RSS fires once (categories are topic-level, same result per domain)
        for source in rss_sources:
            try:
                arts = source.search(query)
                kept = []
                for a in arts:
                    if a.url in seen_urls:
                        continue
                    seen_urls.add(a.url)
                    if blocked_domains:
                        from truebrief.ledger.domain_stats import _to_domain
                        if _to_domain(a.url) in blocked_domains:
                            continue
                    all_articles.append(a)
                    kept.append(a)
                logger.info(f"  [{source.name}] RSS: returned {len(arts)}, kept {len(kept)}")
                self._trace(
                    "collect",
                    f"[{source.name}] RSS (shared): returned {len(arts)}, kept {len(kept)}",
                    source=source.name, returned=len(arts), kept=len(kept),
                    articles=[{"title": a.title, "url": a.url} for a in kept[:20]],
                )
            except Exception as e:
                logger.error(f"[{source.name}] RSS failed: {e}")

        # Step 2: targeted engines, one call per domain, all in parallel
        if not targeted_sources or not query.domains:
            return all_articles

        def _search_domain(source, domain: TopicDomain):
            domain_q = SearchQuery(
                topic_name=query.topic_name,
                primary_query=domain.queries[0],
                rss_categories=query.rss_categories,
            )
            return source.search(domain_q), source.name, domain.name

        tasks = [
            (source, domain)
            for domain in query.domains
            for source in targeted_sources
        ]

        with _cf.ThreadPoolExecutor(max_workers=min(8, len(tasks))) as pool:
            futures = {pool.submit(_search_domain, s, d): (s.name, d.name) for s, d in tasks}
            for future in _cf.as_completed(futures):
                src_name, dom_name = futures[future]
                try:
                    arts, src_name, dom_name = future.result()
                    added = _add(arts)
                    logger.info(
                        f"  [{src_name}] domain={dom_name}: "
                        f"returned {len(arts)}, {added} new after dedup"
                    )
                    self._trace(
                        "collect",
                        f"[{src_name}] domain={dom_name}: returned {len(arts)}, {added} new",
                        source=src_name,
                        domain=dom_name,
                        returned=len(arts),
                        added=added,
                        articles=[{"title": a.title, "url": a.url} for a in arts[:10]],
                    )
                except Exception as e:
                    logger.error(f"[{src_name}] domain={dom_name} failed: {e}")

        logger.info(
            f"  [DOMAIN] Total after parallel collection: {len(all_articles)} unique articles "
            f"({len(query.domains)} domains × {len(targeted_sources)} targeted sources + RSS)"
        )
        return all_articles

    # -------------------------------------------------------------------------
    # MMR Article Selection
    # -------------------------------------------------------------------------

    def _mmr_select(
        self,
        query: SearchQuery,
        articles: List[RawArticle],
        limit: int,
    ) -> List[RawArticle]:
        """
        Maximal Marginal Relevance selection.

        Balances two forces:
          1. Relevance: How similar is this article to the search query?
          2. Diversity: How different is this article from articles already selected?

        MMR Score = λ × sim(article, query) − (1−λ) × max_sim(article, selected)

        λ=1.0 → pure relevance (like taking top-5 by ranking)
        λ=0.0 → pure diversity (what greedy was wrongly doing)
        λ=MMR_LAMBDA → balanced: relevant first, but no redundant repetition.

        Uses the same LLMClient.embed() in VectorStore to avoid duplication.
        """
        # Reset per-run capture; the runner's mmr trace reads this (falls back to a
        # plain title/url list when scoring was skipped).
        self._last_mmr_scores = None

        if len(articles) <= limit:
            return articles

        # 1. Embed the query itself (the "target" we want to stay close to)
        try:
            query_embedding = self.vector_store.llm.embed(query.primary_query)
        except Exception as e:
            logger.warning(f"MMR: Failed to embed query ({e}). Falling back to first {limit} articles.")
            return articles[:limit]

        # 2. Batch-embed all article titles
        titles = [a.title for a in articles]
        try:
            article_embeddings = self._batch_embed_titles(titles)
            
            # CRITICAL SAFETY: If the LLM didn't return an embedding for every title,
            # MMR will crash with IndexError. Fallback to simple top-N.
            if len(article_embeddings) != len(articles):
                logger.warning(f"MMR: Embedding count ({len(article_embeddings)}) != article count ({len(articles)}). Falling back.")
                return articles[:limit]
                
        except Exception as e:
            logger.warning(f"MMR: Failed to batch-embed article titles ({e}). Falling back to first {limit} articles.")
            return articles[:limit]

        # 3. Pre-compute recency scores (P2): exponential decay, 36h half-life.
        import math
        from datetime import datetime as _dt
        _now = _dt.now()
        recency_scores: List[float] = []
        for a in articles:
            if a.published_at:
                pub = a.published_at.replace(tzinfo=None) if a.published_at.tzinfo else a.published_at
                hours_ago = max(0.0, (_now - pub).total_seconds() / 3600)
                recency_scores.append(math.exp(-hours_ago / 36))
            else:
                recency_scores.append(0.5)  # neutral for dateless articles

        # 4. Run MMR with recency term + per-domain cap
        _diversity_w = 1.0 - MMR_LAMBDA - MMR_RECENCY  # implicit: 0.30
        selected_indices: List[int] = []
        remaining_indices = list(range(len(articles)))

        pick_scores: List[dict] = []
        while len(selected_indices) < limit and remaining_indices:
            best_idx = -1
            best_score = float("-inf")
            best_relevance = 0.0

            # Count how many articles per domain are already selected
            from collections import Counter
            sel_domain_counts: Counter = Counter(
                articles[j].source_name for j in selected_indices
            )

            for i in remaining_indices:
                relevance = self._cosine_similarity(article_embeddings[i], query_embedding)
                recency = recency_scores[i]

                # Domain diversity penalty: discourage >MMR_DOMAIN_CAP from same source
                domain_pen = (
                    MMR_DOMAIN_PENALTY
                    if sel_domain_counts.get(articles[i].source_name, 0) >= MMR_DOMAIN_CAP
                    else 0.0
                )

                if not selected_indices:
                    mmr_score = MMR_LAMBDA * relevance + MMR_RECENCY * recency
                else:
                    max_sim_to_selected = max(
                        self._cosine_similarity(article_embeddings[i], article_embeddings[j])
                        for j in selected_indices
                    )
                    mmr_score = (
                        MMR_LAMBDA * relevance
                        + MMR_RECENCY * recency
                        - _diversity_w * max_sim_to_selected
                        - domain_pen
                    )

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_relevance = relevance
                    best_idx = i

            if best_idx != -1:
                selected_indices.append(best_idx)
                remaining_indices.remove(best_idx)
                _a = articles[best_idx]
                pick_scores.append({
                    "rank": len(selected_indices),
                    "title": _a.title,
                    "url": _a.url,
                    "source": getattr(_a.source_type, "value", str(_a.source_type)),
                    "relevance": round(best_relevance, 4),
                    "mmr_score": round(best_score, 4),
                })

        # Expose scores so the runner's mmr trace can show WHY each article was chosen.
        self._last_mmr_scores = pick_scores
        return [articles[i] for i in selected_indices]

    # ── Search strategy cache (topics.search_strategy jsonb) ──────────────────

    def _load_strategy(self, topic_id: str, fallback_input: str):
        """
        Load the cached SearchQuery metadata from topics.search_strategy.
        Returns a SearchQuery with topic_name, rss_categories, and domains populated.
        Falls back gracefully if the column is missing or null.
        """
        from truebrief.collector.query_builder import SearchQuery, TopicDomain
        try:
            res = (
                self.vector_store.db
                .table("topics")
                .select("search_strategy")
                .eq("id", topic_id)
                .single()
                .execute()
            )
            strat = (res.data or {}).get("search_strategy") or {}
        except Exception:
            strat = {}

        # Reconstruct TopicDomain objects from stored JSON
        domains: list[TopicDomain] = []
        for d in (strat.get("domains") or []):
            name = d.get("name", "")
            desc = d.get("description", "")
            queries = d.get("queries", [])
            if name and queries:
                domains.append(TopicDomain(name=name, description=desc, queries=queries))

        return SearchQuery(
            topic_name=strat.get("topic_name") or fallback_input,
            primary_query=fallback_input,
            rss_categories=strat.get("rss_categories") or ["general"],
            domains=domains,
        )

    def _store_strategy(self, topic_id: str, query) -> None:
        """Persist the QueryBuilder output to topics.search_strategy (fire-and-forget)."""
        try:
            # Serialize domains to plain JSON-safe dicts
            domains_data = [
                {"name": d.name, "description": d.description, "queries": d.queries}
                for d in (getattr(query, "domains", None) or [])
            ]
            self.vector_store.db.table("topics").update({
                "search_strategy": {
                    "topic_name":     query.topic_name,
                    "rss_categories": query.rss_categories,
                    "domains":        domains_data,
                }
            }).eq("id", topic_id).execute()
            logger.info(
                f"    [STRATEGY] Cached search_strategy for topic {topic_id} "
                f"({len(domains_data)} domain(s))"
            )
        except Exception as exc:
            logger.warning(f"    [STRATEGY] Failed to cache (non-fatal): {exc}")

    def _batch_embed_titles(self, titles: List[str]) -> List[List[float]]:
        """
        Batch-embed a list of titles using the LLM client's shared method.
        """
        return self.vector_store.llm.embed_batch(titles)

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """Cosine similarity between two vectors. Returns 0.0 if either is zero."""
        dot = sum(a * b for a, b in zip(v1, v2))
        n1 = sum(a * a for a in v1) ** 0.5
        n2 = sum(b * b for b in v2) ** 0.5
        return dot / (n1 * n2) if (n1 and n2) else 0.0
