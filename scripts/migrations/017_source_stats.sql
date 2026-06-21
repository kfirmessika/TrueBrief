-- 017_source_stats.sql
-- Per-(topic × tool) AYR matrix: tracks how many alphas each search tool
-- produces per topic so the runner can UCB1-select which tools to call each scan.
--
-- Tools: 'rss', 'tavily', 'brave', 'google_news', 'exa'
-- AYR (alpha yield rate) = EMA of new_alphas_per_scan for this tool on this topic.
--
-- Cold-start: all tools fire for the first MIN_EXPLORATION_SCANS=3 runs.
-- After that: UCB1 balances exploitation (high AYR) vs exploration (rarely used).
-- Free tools (rss, google_news) always fire regardless of UCB1.

CREATE TABLE IF NOT EXISTS source_stats (
  topic_id          UUID  NOT NULL,
  tool_name         TEXT  NOT NULL,
  scans             INT   NOT NULL DEFAULT 0,
  articles_offered  INT   NOT NULL DEFAULT 0,   -- total articles collected from this tool
  articles_selected INT   NOT NULL DEFAULT 0,   -- articles that survived MMR selection
  alphas_new        INT   NOT NULL DEFAULT 0,   -- cumulative NEW/UPDATE alphas traced to this tool
  ayr               FLOAT NOT NULL DEFAULT 0.0, -- EMA(α=0.3) of per-scan new_alphas
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (topic_id, tool_name)
);
