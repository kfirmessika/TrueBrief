# TrueBrief

[![Open Web App](https://img.shields.io/badge/Open%20Web%20App-2563EB?style=for-the-badge&logo=google-chrome&logoColor=white)](https://truebrief.up.railway.app)
[![Download Android APK](https://img.shields.io/badge/Download%20Android%20APK-16A34A?style=for-the-badge&logo=android&logoColor=white)](https://github.com/kfirmessika/TrueBrief/releases/latest/download/truebrief.apk)

> A deployed AI news-intelligence system that monitors topics, extracts verifiable facts, removes duplicates, and produces concise briefings containing genuinely new information.

## What this project demonstrates

- End-to-end ownership of an AI product, from system design to a live web deployment and Android release.
- An LLM-powered content pipeline that turns raw articles into atomic, source-grounded facts.
- Semantic deduplication using vector storage, so the product can distinguish repeated reporting from genuinely novel information.
- Scheduled, multi-stage processing rather than a one-shot chat interface.

> **Installing the Android APK:** it is self-signed and not on the Play Store, so after
> downloading, open the file and allow your browser/Files app to "install unknown apps"
> when prompted (Settings → Apps → your browser → Install unknown apps). Accept the
> Play Protect "install anyway" dialog.

## System design

TrueBrief consists of five core components:

1. **Collector**: Collects raw articles across multiple sources.
2. **Harvester**: Extracts atomic facts using an LLM.
3. **Ledger**: Stores facts as vectors in Supabase pgvector.
4. **Arbiter**: Decides whether a new fact is identical to an existing one or fundamentally novel.
5. **Briefer**: Generates the final readable report.

For full architectural details, refer to `docs/architecture.md`.
For the development roadmap, refer to `docs/roadmap.md`.
