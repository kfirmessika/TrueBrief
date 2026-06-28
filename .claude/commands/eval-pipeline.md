---
description: Run one topic through the real TrueBrief pipeline + audit the stored data, and summarize signal quality. A fast end-to-end smoke + quality read.
argument-hint: <topic> — e.g. "Iran War ceasefire deal"
---

Use the `run-truebrief-locally` and `truebrief-pipeline` skills.

**Topic:** $ARGUMENTS

1. Run `python scripts/run_pipeline.py "$ARGUMENTS" --debug` and capture the generated brief.
2. Run `python scripts/audit_topic.py "<key keyword from the topic>"` → writes a report to `reports/`.
3. **Summarize signal quality:**
   - fact counts by decision (NEW / UPDATE / DUPLICATE)
   - number of story nodes
   - % of facts with a populated `event_date` (known to run low — flag if so)
   - source diversity (distinct domains)
   - does the brief **lead with the single most important current development**, or is the lede buried?
4. Cross-check against the known issues in the `truebrief-pipeline` skill (paraphrase-as-NEW, re-scraped URLs, wrong/old `event_date`, tally noise). If quality looks off, recommend dispatching the **pipeline-debugger** agent and following up with **`/accuracy-check "$ARGUMENTS"`**.

Read-only investigation — don't change code or data here.
