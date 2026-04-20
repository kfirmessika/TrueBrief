# TrueBrief

A noise-free news intelligence platform.

TrueBrief acts as an intelligent layer between you and the internet, continuously monitoring requested topics, extracting verifiable facts, detecting and discarding duplicates, and delivering concise briefs containing only genuinely novel information.

## Architecture
TrueBrief consists of 5 core pillars:
1. **Collector**: Collects raw articles across multiple sources.
2. **Harvester**: Extracts atomic facts (alphas) using an LLM.
3. **Ledger**: Stores these facts as vectors (Supabase pgvector).
4. **Arbiter**: Decides if a new fact is identical to an existing one or is fundamentally novel.
5. **Briefer**: Generates the final readable report.

For full architectural details, refer to `docs/architecture.md`.
For the development roadmap, refer to `docs/roadmap.md`.
