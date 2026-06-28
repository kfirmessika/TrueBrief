---
name: truebrief-database
description: Reference for the TrueBrief Supabase/Postgres database — schema, migrations, RLS, FK cascades, safe delete order, data wipes, and ready-made health/inspection queries. Use when inspecting or changing the schema, debugging data issues, or running SQL via the supabase MCP (project lopsqdnfivdpsvsqzwdc).
---

# TrueBrief Database — Supabase / Postgres (pgvector)

**Scope:** schema, migrations, RLS, data inspection/repair. Do NOT edit Python (`src/truebrief/`, see [[truebrief-backend]]) or frontend code.

## MCP connection
Project ref `lopsqdnfivdpsvsqzwdc` (server `https://mcp.supabase.com/mcp?project_ref=lopsqdnfivdpsvsqzwdc`, wired in `.mcp.json`). If a tool says unauthenticated, run `mcp__supabase__authenticate` → open the OAuth URL → authorize. Tools are deferred — load schemas via ToolSearch: `select:mcp__supabase__execute_sql,mcp__supabase__apply_migration,...`.

| Tool | Use |
|---|---|
| `execute_sql` | SELECT / DML — queries, inspections, data fixes |
| `apply_migration` | DDL (ALTER/CREATE/DROP/triggers/functions) — **recorded in history** |
| `list_tables` / `list_migrations` | structure + applied history |
| `get_advisors` | security + performance advisories (RLS gaps, missing indexes) |
| `get_logs` | recent Postgres/API logs |

**Rule:** schema changes go through `apply_migration` (recorded). `execute_sql` is for reads/data only and is NOT recorded.

## Schema (core tables)
- **topics** `id, raw_query (UNIQUE lowercased, mig 007), user_id?(creator only), is_active, poll_interval_seconds, last_run_at, next_run_at`
- **topic_subscriptions** `user_id→users, topic_id→topics, UNIQUE(user_id,topic_id)` (both CASCADE)
- **users** `id (Clerk uid), email` · **user_subscriptions** `user_id, tier(free|pro|power)` · **tier_intervals** `tier PK, poll_interval_seconds` (free 86400 / pro 3600 / power 900)
- **story_nodes** `id, topic_id→topics CASCADE, title, summary, summary_embedding vector, status, fact_count (manual, no trigger)`
- **known_facts** `id, topic_id→topics CASCADE, story_node_id→story_nodes (NO ACTION), alpha_text, alpha_embedding vector, entities jsonb, event_date, confidence, source_url, source_domain, first_seen_at`
- **briefs** `id, topic_id→topics CASCADE, content (md), facts_json (DEAD — always NULL), delivered_at, is_read` (no created_at)
- **source_quality_log** `topic_id, source_domain, decision(NEW|UPDATE|DUPLICATE)` · **topic_query_variants** `topic_id, query_text, UNIQUE(topic_id,query_text)` · **push_subscriptions** · **processed_paddle_events**

All tables have RLS enabled. `tier_intervals` = public SELECT only (config).

## FK cascades & SAFE DELETE ORDER (children first)
```sql
DELETE FROM known_facts;        -- must precede story_nodes (story_node_id is NO ACTION)
DELETE FROM story_nodes;
DELETE FROM briefs;
DELETE FROM source_quality_log;
DELETE FROM topic_query_variants;
DELETE FROM topic_subscriptions;
DELETE FROM topics;
-- optional: user_subscriptions, users
-- NEVER wipe: tier_intervals (trigger needs it); push_subscriptions / processed_paddle_events unless asked
```

## Migration conventions
Files in `scripts/migrations/NNN_short_description.sql` (latest is 020). Use `IF [NOT] EXISTS` guards (re-runnable). End with a `-- Verify` SELECT. Apply via `apply_migration`, then run the verify SELECT via `execute_sql`.

## Known gotchas
1. `known_facts.story_node_id` is **NO ACTION** — deleting a story with facts fails; null the facts or delete them first.
2. `story_nodes.fact_count` is **manually maintained** (incremented in `story_manager.py`) — drifts if facts are deleted directly.
3. `briefs.facts_json` always NULL (dead column). `briefs` has no `created_at` (only `delivered_at`).
4. **AYR vs tier interval** both write `topics.poll_interval_seconds` — last writer wins (AYR on runs, tier trigger on subscription changes).
5. `topics.user_id` is nullable creator-metadata — never fan out notifications by it; use `topic_subscriptions`.

## Health snapshot (run via execute_sql)
```sql
SELECT t.raw_query, t.is_active, t.poll_interval_seconds, t.last_run_at, t.next_run_at,
  (SELECT count(*) FROM topic_subscriptions ts WHERE ts.topic_id=t.id) AS subs,
  (SELECT count(*) FROM story_nodes sn WHERE sn.topic_id=t.id)         AS stories,
  (SELECT count(*) FROM known_facts kf WHERE kf.topic_id=t.id)         AS facts,
  (SELECT count(*) FROM briefs b WHERE b.topic_id=t.id)                AS briefs
FROM topics t ORDER BY subs DESC, facts DESC;
```
Orphan facts (`story_node_id IS NULL`), `fact_count` drift, and error/short briefs queries: see the `/db-health` command, which bundles them.
