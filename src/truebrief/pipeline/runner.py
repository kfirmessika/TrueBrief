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
from truebrief.models.article import RawArticle
from truebrief.models.alpha import DecisionType

logger = logging.getLogger(__name__)

# How many articles to process per scan. Tune vs. API limits.
MAX_ARTICLES = 5

# MMR lambda: 1.0 = pure relevance, 0.0 = pure diversity. 0.65 is balanced.
MMR_LAMBDA = 0.65


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
        try:
            start_time = time.time()
            logger.info(f"--- PIPELINE START: {topic_input} ---")
            
            # 1. Build Query
            logger.info("[1] Building Search Strategy")
            query = self.query_builder.build(topic_input)
            if query.status == "REJECTED":
                return f"Topic rejected: {query.reason}"
            logger.info(f"    Strategy built: {query.topic_name}")

            # 1b. Select the best active query variant (overrides primary_query)
            _variant_id = None
            if topic_id:
                try:
                    _variant_id, best_query = self.query_rotator.select_variant(
                        topic_id=topic_id,
                        raw_query=query.primary_query,
                        alt_queries=query.alt_queries,
                    )
                    if best_query != query.primary_query:
                        logger.info(f"    [ROTATOR] Using variant: '{best_query[:60]}'")
                    query.primary_query = best_query
                except Exception as rot_err:
                    logger.warning(f"    [ROTATOR] Skipped variant selection: {rot_err}")

            # 2. Collect Raw Articles
            logger.info("[2] Collecting Sources")
            raw_articles = self._collect_all(query)
            logger.info(f"    Collected {len(raw_articles)} candidate articles total.")

            if not raw_articles:
                logger.info("    No articles found. Ending early.")
                return ""

            # 2b. URL dedup: skip articles already processed for this topic in the last 14 days
            if topic_id:
                try:
                    seen_urls = self.vector_store.get_seen_urls(topic_id, days=14)
                    before = len(raw_articles)
                    raw_articles = [a for a in raw_articles if a.url not in seen_urls]
                    skipped = before - len(raw_articles)
                    if skipped:
                        logger.info(f"    URL dedup: skipped {skipped} already-processed articles.")
                except Exception as dedup_err:
                    logger.warning(f"    URL dedup failed (non-fatal): {dedup_err}")

            if not raw_articles:
                logger.info("    All articles already processed. Ending early.")
                return ""

            # 3. MMR Selection
            logger.info(f"[3] Selecting top {MAX_ARTICLES} diverse articles via MMR...")
            selected = self._mmr_select(query=query, articles=raw_articles, limit=MAX_ARTICLES)
            logger.info(f"    MMR selected {len(selected)} articles.")

            # 4. Harvesting
            logger.info("[4] Harvesting Facts (Alphas)")
            all_alphas = []
            for i, article in enumerate(selected):
                logger.info(f"    Processing article {i+1}/{len(selected)}: {article.url}")
                article = self.extractor.extract(article)
                if not article.text:
                    continue
                alphas = self.harvester.extract(article, topic_id=topic_id)
                all_alphas.extend(alphas)
                if i < len(selected) - 1:
                    time.sleep(2)
            logger.info(f"    Harvested {len(all_alphas)} total facts.")

            # 5. Judging
            logger.info("[5] Judging Novelty")
            decisions = []
            for alpha in all_alphas:
                decision = self.arbiter.judge(alpha, topic_id=topic_id)
                decisions.append(decision)
                if decision.decision in (DecisionType.NEW, DecisionType.UPDATE):
                    # Phase 3: Assign to a StoryNode before persisting
                    story_node_id = None
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

                    # Phase 3 (Task 3.3): Recursive summary update.
                    # Trigger only when a fact joins an EXISTING story (not when
                    # a brand-new story is created - its summary = the fact).
                    if story_node_id:
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
            return brief_text
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"PIPELINE CRASHED: {e}\nTraceback:\n{tb}")
            raise e

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

            except Exception as e:
                logger.error(f"Source [{source.name}] failed: {e}")

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

        while len(selected_indices) < limit and remaining_indices:
            best_idx = -1
            best_score = float("-inf")

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
                    best_idx = i

            if best_idx != -1:
                selected_indices.append(best_idx)
                remaining_indices.remove(best_idx)

        return [articles[i] for i in selected_indices]

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
