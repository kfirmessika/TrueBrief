---
description: Run a read-only TrueBrief database health snapshot via the supabase MCP — topic health, orphan facts, fact_count drift, brief quality, and advisories.
argument-hint: (none)
---

Use the `truebrief-database` skill. Load the supabase MCP tools via ToolSearch
(`select:mcp__supabase__execute_sql,mcp__supabase__list_tables,mcp__supabase__get_advisors`). If a tool reports
unauthenticated, run `mcp__supabase__authenticate` and have the user authorize.

Run these **read-only** checks with `execute_sql` and present each as a small table:

1. **Topic health** — subs / stories / facts / briefs + hours since last run:
```sql
SELECT t.raw_query, t.is_active, t.poll_interval_seconds,
  EXTRACT(EPOCH FROM (now()-t.last_run_at))::int/3600 AS hrs_since_run,
  (SELECT count(*) FROM topic_subscriptions ts WHERE ts.topic_id=t.id) AS subs,
  (SELECT count(*) FROM story_nodes sn WHERE sn.topic_id=t.id)         AS stories,
  (SELECT count(*) FROM known_facts kf WHERE kf.topic_id=t.id)         AS facts,
  (SELECT count(*) FROM briefs b WHERE b.topic_id=t.id)                AS briefs
FROM topics t ORDER BY subs DESC, facts DESC;
```
2. **Orphan facts** (`story_node_id IS NULL`):
```sql
SELECT t.raw_query, count(*) FILTER (WHERE kf.story_node_id IS NULL) AS orphans, count(*) AS total
FROM topics t LEFT JOIN known_facts kf ON kf.topic_id=t.id
GROUP BY t.raw_query HAVING count(*) FILTER (WHERE kf.story_node_id IS NULL) > 0;
```
3. **fact_count drift** (declared vs actual):
```sql
SELECT sn.id, sn.title, sn.fact_count AS declared, count(kf.id) AS actual
FROM story_nodes sn LEFT JOIN known_facts kf ON kf.story_node_id=sn.id
GROUP BY sn.id, sn.title, sn.fact_count HAVING sn.fact_count != count(kf.id);
```
4. **Brief quality** (error strings / too short):
```sql
SELECT t.raw_query,
  count(*) FILTER (WHERE b.content LIKE '%Error generating brief%') AS error_briefs,
  count(*) FILTER (WHERE length(b.content) < 30) AS too_short, count(*) AS total
FROM briefs b JOIN topics t ON t.id=b.topic_id GROUP BY t.raw_query ORDER BY error_briefs DESC;
```

Then run `get_advisors` and surface any security/performance advisories. **Do not modify any data** — flag issues and recommend the `truebrief-db` agent for any fix.
