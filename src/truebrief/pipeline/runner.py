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
from typing import List, Optional

from config.settings import settings
from truebrief.llm.client import pipeline_run_id_var
from truebrief.collector.base import SourceLayer
from truebrief.collector.query_builder import QueryBuilder, SearchQuery
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
from truebrief.verifier.verifier import Verifier
from truebrief.models.article import RawArticle
from truebrief.models.alpha import DecisionType

logger = logging.getLogger(__name__)

# How many articles to process per scan. Tune vs. API limits.
MAX_ARTICLES = 5

# MMR lambda: 1.0 = pure relevance, 0.0 = pure diversity. 0.65 is balanced.
MMR_LAMBDA = 0.65

# V3_RELEVANCE_GATE: minimum cosine similarity between an alpha and the topic query.
# Alphas below this are considered off-topic and dropped before the arbiter.
_RELEVANCE_THRESHOLD = 0.35


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
            raw_articles = self._collect_all(query)
            logger.info(f"    Collected {len(raw_articles)} candidate articles total.")

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

            # 3. MMR Selection
            logger.info(f"[3] Selecting top {MAX_ARTICLES} diverse articles via MMR...")
            selected = self._mmr_select(query=query, articles=raw_articles, limit=MAX_ARTICLES)
            logger.info(f"    MMR selected {len(selected)} articles.")
            self._trace(
                "mmr",
                f"MMR selected {len(selected)} of {len(raw_articles)} candidates (λ={MMR_LAMBDA}).",
                why=f"Maximal Marginal Relevance balances relevance to the query vs. diversity "
                    f"(λ={MMR_LAMBDA}: {int(MMR_LAMBDA*100)}% relevance / {int((1-MMR_LAMBDA)*100)}% diversity). "
                    f"Per-pick scores in 'selected'.",
                candidates=len(raw_articles),
                limit=MAX_ARTICLES,
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
            for alpha in all_alphas:
                decision = self.arbiter.judge(alpha, topic_id=topic_id)
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


            # 6. Briefing
            logger.info("[6] Generating Brief")
            brief_text = self.briefer.generate(decisions, query.topic_name)

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
            return brief_text
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"PIPELINE CRASHED: {e}\nTraceback:\n{tb}")
            self._trace("error", f"Pipeline crashed: {e}", error=str(e), traceback=tb[:4000])
            raise e

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

    def _collect_all(self, query: SearchQuery) -> List[RawArticle]:
        """
        Run all plugged-in sources and aggregate their results.
        For keyword-based sources like RSS, filters by query keywords to avoid
        off-topic articles from general feeds.
        """
        all_articles: List[RawArticle] = []
        seen_urls: set = set()

        # Build keyword set for basic relevance pre-filter (used for RSS/broad sources)
        query_words = (query.topic_name + " " + query.primary_query).lower().split()
        keywords = [w for w in query_words if len(w) > 3]

        for source in self.sources:
            try:
                articles = source.search(query)
                logger.info(f"  [{source.name}] returned {len(articles)} articles.")

                kept_here = []
                for a in articles:
                    if a.url in seen_urls:
                        continue
                    seen_urls.add(a.url)

                    # For broad sources (RSS, Google News), apply keyword filter.
                    # Targeted engines (Tavily, Brave, Exa) already return on-topic results.
                    _TARGETED = {"tavily", "brave", "exa"}
                    if source.name not in _TARGETED and keywords:
                        text = (a.title + " " + (a.text or "")).lower()
                        if not any(k in text for k in keywords):
                            continue

                    all_articles.append(a)
                    kept_here.append(a)

                self._trace(
                    "collect",
                    f"[{source.name}] returned {len(articles)}, kept {len(kept_here)} after keyword/dedup filter.",
                    source=source.name,
                    query=query.primary_query,
                    returned=len(articles),
                    kept=len(kept_here),
                    keywords=keywords if source.name not in {"tavily", "brave", "exa"} else None,
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

        # 3. Run MMR
        selected_indices: List[int] = []
        remaining_indices = list(range(len(articles)))

        pick_scores: List[dict] = []
        while len(selected_indices) < limit and remaining_indices:
            best_idx = -1
            best_score = float("-inf")
            best_relevance = 0.0

            for i in remaining_indices:
                relevance = self._cosine_similarity(article_embeddings[i], query_embedding)

                if not selected_indices:
                    # First pick: pure relevance (no selected set yet)
                    mmr_score = relevance
                else:
                    max_sim_to_selected = max(
                        self._cosine_similarity(article_embeddings[i], article_embeddings[j])
                        for j in selected_indices
                    )
                    mmr_score = MMR_LAMBDA * relevance - (1 - MMR_LAMBDA) * max_sim_to_selected

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
        Returns a SearchQuery with topic_name and rss_categories populated.
        Falls back gracefully if the column is missing or null.
        """
        from truebrief.collector.query_builder import SearchQuery
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
        return SearchQuery(
            topic_name=strat.get("topic_name") or fallback_input,
            primary_query=fallback_input,
            rss_categories=strat.get("rss_categories") or ["general"],
        )

    def _store_strategy(self, topic_id: str, query) -> None:
        """Persist the QueryBuilder output to topics.search_strategy (fire-and-forget)."""
        try:
            self.vector_store.db.table("topics").update({
                "search_strategy": {
                    "topic_name":     query.topic_name,
                    "rss_categories": query.rss_categories,
                }
            }).eq("id", topic_id).execute()
            logger.info(f"    [STRATEGY] Cached search_strategy for topic {topic_id}")
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
