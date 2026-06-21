-- 016_domain_extraction_stats.sql
-- Dynamic domain blocklist: tracks per-domain extraction success/fail rate.
-- Extractor fire-and-forget upserts after each extract() call.
-- Runner reads get_blocked_domains() before MMR to skip chronically failing domains.
-- Threshold: >75% fail rate + ≥5 attempts → domain blocked for that scan.
-- Stats decay naturally: rows with updated_at > 30 days old can be pruned manually:
--   DELETE FROM domain_extraction_stats WHERE updated_at < NOW() - INTERVAL '30 days';

CREATE TABLE IF NOT EXISTS domain_extraction_stats (
  domain            TEXT PRIMARY KEY,
  success_count     INT  NOT NULL DEFAULT 0,
  fail_count        INT  NOT NULL DEFAULT 0,
  last_success_at   TIMESTAMPTZ,
  last_fail_at      TIMESTAMPTZ,
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Atomic increment via stored function — avoids read-modify-write race in Python client.
CREATE OR REPLACE FUNCTION record_domain_extraction(p_domain TEXT, p_success BOOLEAN)
RETURNS VOID AS $$
BEGIN
  INSERT INTO domain_extraction_stats
    (domain, success_count, fail_count, last_success_at, last_fail_at, updated_at)
  VALUES (
    p_domain,
    CASE WHEN p_success THEN 1 ELSE 0 END,
    CASE WHEN NOT p_success THEN 1 ELSE 0 END,
    CASE WHEN p_success THEN NOW() ELSE NULL END,
    CASE WHEN NOT p_success THEN NOW() ELSE NULL END,
    NOW()
  )
  ON CONFLICT (domain) DO UPDATE SET
    success_count   = domain_extraction_stats.success_count + EXCLUDED.success_count,
    fail_count      = domain_extraction_stats.fail_count    + EXCLUDED.fail_count,
    last_success_at = COALESCE(EXCLUDED.last_success_at, domain_extraction_stats.last_success_at),
    last_fail_at    = COALESCE(EXCLUDED.last_fail_at,    domain_extraction_stats.last_fail_at),
    updated_at      = NOW();
END;
$$ LANGUAGE plpgsql;
