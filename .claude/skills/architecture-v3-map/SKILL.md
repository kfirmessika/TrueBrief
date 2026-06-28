---
name: architecture-v3-map
description: Index to docs/core/architecture_v3.md, the definitive plan. ALWAYS use this before opening that file — it is 36KB and must NOT be read in full. Look up the topic you need here, then read ONLY that section slice with Read(offset/limit) or grep the heading. Covers the data model, pipeline, delta engine, scoring/eval, cost, UI, build sequence, and decision log.
---

# architecture_v3.md — Section Index

**Hard rule:** never read `docs/core/architecture_v3.md` in full. Find your topic below, then read only that
section (grep the heading line, then `Read` with `offset`/`limit`). This is the single source of truth for the plan;
`docs/roadmap.md` is the ordered task list.

| § | Section | Use it for |
|---|---|---|
| 0 | Reading guide | how the doc is organized |
| 1 | First principles | the core thesis / launch decision |
| 2 | Verified state (live DB) | what actually exists in data |
| 3 | The core model | thread-not-brief; correctness vs context split |
| 4 | Data model | tables, the delta query (= home screen, ~1ms $0) |
| 5 | The pipeline | stage-by-stage design (pairs with [[truebrief-pipeline]]) |
| 6 | Search routing, scan timing, article selection | AYR, coalescing, MMR, extraction efficiency |
| 7 | Context & history | history doc / "story so far" |
| 8 | Per-user delta engine | the "what's new" feed |
| 8B | Two-clock model | development-lag gating (no stale events) |
| 9 | Rate & depth axes | shared-scan schedule |
| 10 | Cost monitoring & budget controller | per-run cost, graceful degradation |
| 10B | Scoring, evaluation, feedback, LLM-cost | **§10B.5 = the eval harness; §10B.2 significance formula; §10B.2a lead-with-the-lede** |
| 11 | Cost & sharing (3 options) | pricing models (B recommended) |
| 12 | Shared memory & B2B/API | multi-tenant memory |
| 13 | UI | two-channels-one-feed, envelopes |
| 14 | Business | positioning |
| 15 | Build sequence | the ordered build plan |
| 16 | Decision log · red lights · open questions | locked decisions + 🔴 fixes |
| 17 | Source layers & plugin architecture | SourceLayer phases, routing_rules.yaml |
| 18 | Tech stack & "what NOT to use" | backend/frontend/infra choices |
| 19 | Monetization detail | tiers, B2B revenue, projections |
| 20 | Key risks & mitigations | risk register |
| 21 | Long-term moat & domain pipelines | Phase 6+ |
| 22 | Legal & copyright posture | compliance |

**Most-referenced for current work:** §1 (launch gate), §4 (delta query), §5 + §10B (pipeline + scoring/eval), §15 (build sequence), §16 (red lights). Cross-check the ordered tasks in `docs/roadmap.md`.
