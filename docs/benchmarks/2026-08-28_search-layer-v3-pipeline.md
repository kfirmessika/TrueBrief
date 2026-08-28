# Search Layer Benchmark v3 — Pipeline Level
**Date:** 2026-08-28  |  **Topics:** 5  |  **Max score:** 90 per provider

All 3 providers run through the same 2-call pipeline (collect -> extract using `build_gemini_extract_prompt`).
Judge scores the resulting Alpha objects, not raw search output.

## Summary

| Topic | Gemini | Linkup | Brave | Winner |
|---|---|---|---|---|
| Iran US ceasefire Strait of Hormuz | 0 | 15 | 9 | **linkup** |
| Federal Reserve interest rate decision August 2026 | 0 | 14 | 11 | **linkup** |
| EU AI Act enforcement 2026 | 0 | 16 | 10 | **linkup** |
| Bitcoin price August 2026 | 0 | 0 | 0 | **?** |
| Gaza ceasefire negotiations | 0 | 0 | 0 | **?** |
| **TOTAL** | **0** | **45** | **30** | |

## Alpha counts

| Topic | Gemini | Linkup | Brave |
|---|---|---|---|
| Iran US ceasefire Strait of Hormuz | 0 | 4 | 12 |
| Federal Reserve interest rate decision August 2026 | 0 | 3 | 6 |
| EU AI Act enforcement 2026 | 0 | 5 | 6 |
| Bitcoin price August 2026 | 0 | 4 | 9 |
| Gaza ceasefire negotiations | 0 | 3 | 8 |

## Per-Topic Results

### Iran US ceasefire Strait of Hormuz

| Axis | Gemini | Linkup | Brave |
|---|---|---|---|
| alpha_quality | 0 | 3 | 2 |
| freshness | 0 | 1 | 0 |
| fact_count | 0 | 2 | 1 |
| source_attribution | 0 | 3 | 3 |
| noise_free | 0 | 3 | 0 |
| topic_relevance | 0 | 3 | 3 |
| **TOTAL** | **0** | **15** | **9** |

**Winner:** linkup  |  **Finding:** LinkUp provided the most relevant and recent information on the Iran-US ceasefire and the Strait of Hormuz, despite a limited number of fresh facts.

**Gemini**: 0 alphas (0 fresh, 0 sourced) | collect 8.4s + extract 0.0s | Extraction failed due to grounding.
  EXTRACT ERROR: collect failed: Gemini grounded call failed on both primary (quota-exhausted) and backup (429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}]}}) for step 'gemini_search'.

**Linkup**: 4 alphas (4 fresh, 4 sourced) | collect 4.8s + extract 5.1s | Facts are high quality and on-topic, but only one is from the last 7 days.

**Brave**: 12 alphas (2 fresh, 12 sourced) | collect 2.4s + extract 7.2s | Most facts are background, and none are within the last 7 days.

<details><summary>Gemini Alphas (0)</summary>

Collect failed: Gemini grounded call failed on both primary (quota-exhausted) and backup (429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}]}}) for step 'gemini_search'.
</details>

<details><summary>Linkup Alphas (4)</summary>

1. **[2026-04-08]** [state_change] conf=0.95 | [https://politicsnigeria.com/2026/04/08/8473/](https://politicsnigeria.com/2026/04/08/8473/)  
   The United States and Iran agreed to a two-week ceasefire in April 2026.
2. **[2026-04-08]** [state_change] conf=0.95 | [https://munsifdaily.com/ceasefire-iran-fully-opens-strait-of-hormuz/](https://munsifdaily.com/ceasefire-iran-fully-opens-strait-of-hormuz/)  
   Iran confirmed it would allow safe passage through the Strait of Hormuz for a two-week period.
3. **[2026-04-08]** [development] conf=0.95 | [https://enews.hamariweb.com/trending/us-iran-ceasefire-announced-after-successful-mediation-from-pakistan-strait-of-hormuz-reopens/](https://enews.hamariweb.com/trending/us-iran-ceasefire-announced-after-successful-mediation-from-pakistan-strait-of-hormuz-reopens/)  
   The ceasefire agreement between the United States and Iran was mediated by Pakistan.
4. **[2026-04-08]** [development] conf=0.90 | [https://fullavantenews.com/u-s-irans-2-week-ceasefire-deal-to-reopen-strait-of-hormuz/](https://fullavantenews.com/u-s-irans-2-week-ceasefire-deal-to-reopen-strait-of-hormuz/)  
   Iran submitted a 10-point proposal including demands for the removal of US sanctions, recognition of its control over the Strait of Hormuz, and withdrawal of US forces from the region.
</details>

<details><summary>Brave Alphas (12)</summary>

1. **[2026-03-25]** [development] conf=0.95 BACKGROUND | [2026 Iran war ceasefire - Wikipedia](https://en.wikipedia.org/wiki/2026_Iran_war_ceasefire)  
   Pakistani officials delivered a 15-point proposal from the United States to Iran detailing a ceasefire plan.
2. **[2026-03-25]** [development] conf=0.95 BACKGROUND | [2026 Iran war ceasefire - Wikipedia](https://en.wikipedia.org/wiki/2026_Iran_war_ceasefire)  
   Iran issued a five-point counter-proposal regarding the conflict.
3. **[2026-03-31]** [development] conf=0.95 BACKGROUND | [2026 Iran war ceasefire - Wikipedia](https://en.wikipedia.org/wiki/2026_Iran_war_ceasefire)  
   Pakistan and China delivered a five-point initiative for peace calling for an end to hostilities.
4. **[2026-04-01]** [development] conf=0.95 BACKGROUND | [2026 Iran war ceasefire - Wikipedia](https://en.wikipedia.org/wiki/2026_Iran_war_ceasefire)  
   Donald Trump stated that Iran asked the United States for a ceasefire.
5. **[2026-04-08]** [state_change] conf=0.95 BACKGROUND | [2026 Iran war | Deal, Explained, United States, Israel, Strait of Hormuz, Map, & Conflict | Britannica](https://www.britannica.com/event/2026-Iran-war)  
   The United States and Iran agreed on a ceasefire that included Israel.
6. **[2026-06-19]** [state_change] conf=0.95 BACKGROUND | [2026 Strait of Hormuz crisis - Wikipedia](https://en.wikipedia.org/wiki/2026_Strait_of_Hormuz_crisis)  
   Donald Trump announced a renewed ceasefire between Israel and Hezbollah.
7. **[2026-06-20]** [escalation] conf=0.95 BACKGROUND | [2026 Strait of Hormuz crisis - Wikipedia](https://en.wikipedia.org/wiki/2026_Strait_of_Hormuz_crisis)  
   Iran stated that it closed the Strait of Hormuz again, citing Israeli actions in southern Lebanon as a violation.
8. **[2026-06-27]** [development] conf=0.95 BACKGROUND | [2026 Strait of Hormuz crisis - Wikipedia](https://en.wikipedia.org/wiki/2026_Strait_of_Hormuz_crisis)  
   The Joint Maritime Information Center announced a widened route through the Strait of Hormuz near Oman.
9. **[2026-06-28]** [state_change] conf=0.95 BACKGROUND | [2026 Iran war - Wikipedia](https://en.wikipedia.org/wiki/2026_Iran_war)  
   The United States and Iran agreed to cease their exchange of attacks.
10. **[2026-07-08]** [escalation] conf=0.95 BACKGROUND | [2026 Iran war - Wikipedia](https://en.wikipedia.org/wiki/2026_Iran_war)  
   The ceasefire deal between the United States and Iran collapsed after Iran attacked commercial vessels in the Strait of Hormuz.
11. **[2026-08-25]** [casualty] conf=0.90 | [Iran Ceasefire Status 2026: Is the US-Iran War Over? Live Tracker](https://militaryspend.org/iran-ceasefire-status)  
   Two projectile strikes disabled tankers off Oman near the Strait of Hormuz.
12. **[2026-08-27]** [development] conf=0.95 | [Iran Ceasefire Status 2026: Is the US-Iran War Over? Live Tracker](https://militaryspend.org/iran-ceasefire-status)  
   Qatari Prime Minister visited Tehran to push for de-escalation.
</details>

### Federal Reserve interest rate decision August 2026

| Axis | Gemini | Linkup | Brave |
|---|---|---|---|
| alpha_quality | 0 | 3 | 2 |
| freshness | 0 | 1 | 1 |
| fact_count | 0 | 2 | 2 |
| source_attribution | 0 | 3 | 3 |
| noise_free | 0 | 2 | 1 |
| topic_relevance | 0 | 3 | 2 |
| **TOTAL** | **0** | **14** | **11** |

**Winner:** linkup  |  **Finding:** Linkup provided the most relevant and high-quality facts regarding the actual August 2026 Federal Reserve interest rate decision, despite some minor freshness issues.

**Gemini**: 0 alphas (0 fresh, 0 sourced) | collect 4.1s + extract 0.0s | Extraction failed due to API issues.
  EXTRACT ERROR: collect failed: Gemini grounded call failed on both primary (quota-exhausted) and backup (429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}]}}) for step 'gemini_search'.

**Linkup**: 3 alphas (3 fresh, 3 sourced) | collect 3.1s + extract 4.7s | Two facts about the August 2026 decision (rate and dissenters) are factual and relevant, but one fact (date of decision) is from August 24th, predating the current week's 7-day window. The dissenters are tagged as development, not background.

**Brave**: 6 alphas (5 fresh, 6 sourced) | collect 1.6s + extract 5.6s | Only one fact (July 31st rate decision) is within the desired date range and relevant to the August decision. The other facts are about future meetings or unrelated developments. The July 31st fact is tagged as state_change (background) rather than development.

<details><summary>Gemini Alphas (0)</summary>

Collect failed: Gemini grounded call failed on both primary (quota-exhausted) and backup (429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}]}}) for step 'gemini_search'.
</details>

<details><summary>Linkup Alphas (3)</summary>

1. **[2026-08-24]** [state_change] conf=1.00 | [https://fedratecalc.com/fomc-meeting-schedule/](https://fedratecalc.com/fomc-meeting-schedule/)  
   The Federal Reserve held its benchmark interest rate steady at 3.5%–3.75% in its August 2026 decision.
2. **[2026-08-24]** [development] conf=1.00 | [https://fedratecalc.com/fomc-meeting-schedule/](https://fedratecalc.com/fomc-meeting-schedule/)  
   The Federal Reserve voted 9–3 to hold its benchmark interest rate steady at 3.5%–3.75%.
3. **[2026-08-24]** [development] conf=1.00 | [https://fedratecalc.com/fomc-meeting-schedule/](https://fedratecalc.com/fomc-meeting-schedule/)  
   Beth M Hammack, Neel Kashkari, and Lorie K Logan dissented from the Federal Reserve's August 2026 interest rate decision.
</details>

<details><summary>Brave Alphas (6)</summary>

1. **[2026-09-15]** [routine] conf=1.00 | [Next FOMC Meeting: September 15–16, 2026 Countdown | FedRateCalc](https://fedratecalc.com/next-fomc-meeting/)  
   The next Federal Open Market Committee meeting is scheduled for September 15-16, 2026.
2. **[2026-09-16]** [routine] conf=1.00 | [Next FOMC Meeting: September 15–16, 2026 Countdown | FedRateCalc](https://fedratecalc.com/next-fomc-meeting/)  
   The Federal Reserve is scheduled to announce its interest rate decision on September 16, 2026 at 2:00 PM Eastern Time.
3. **[2026-07-31]** [state_change] conf=1.00 BACKGROUND | [United States Fed Funds Interest Rate](https://tradingeconomics.com/united-states/interest-rate)  
   The Federal Reserve left the federal funds rate unchanged at 3.50% to 3.75% in July 2026.
4. **[2026-08-27]** [routine] conf=1.00 | [Federal Reserve Board - News & Events](https://www.federalreserve.gov/newsevents.htm)  
   Minutes from the Federal Reserve discount rate meetings on July 20 and July 29, 2026, were released on August 27, 2026.
5. **[2026-08-19]** [development] conf=1.00 | [Federal Reserve Board - News & Events](https://www.federalreserve.gov/newsevents.htm)  
   The Federal Reserve announced five task forces to examine areas central to the broad conduct of monetary policy on August 19, 2026.
6. **[2026-10-07]** [routine] conf=1.00 | [FOMC Minutes Release Schedule 2026: Dates & Times | FedRateCalc](https://fedratecalc.com/fomc-minutes-release-schedule/)  
   Minutes from the FOMC meeting are scheduled to be released on October 7, 2026, at 2:00 PM Eastern Time.
</details>

### EU AI Act enforcement 2026

| Axis | Gemini | Linkup | Brave |
|---|---|---|---|
| alpha_quality | 0 | 3 | 1 |
| freshness | 0 | 2 | 1 |
| fact_count | 0 | 2 | 2 |
| source_attribution | 0 | 3 | 2 |
| noise_free | 0 | 3 | 2 |
| topic_relevance | 0 | 3 | 2 |
| **TOTAL** | **0** | **16** | **10** |

**Winner:** linkup  |  **Finding:** Enforcement of the EU AI Act's transparency and high-risk provisions is a significant ongoing development, with key dates in August 2026 and active recruitment for enforcement roles.

**Gemini**: 0 alphas (0 fresh, 0 sourced) | collect 4.2s + extract 0.0s | Extraction failed for all facts.
  EXTRACT ERROR: collect failed: Gemini grounded call failed on both primary (quota-exhausted) and backup (429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}]}}) for step 'gemini_search'.

**Linkup**: 5 alphas (5 fresh, 5 sourced) | collect 6.0s + extract 6.3s | Mostly clean, factual sentences with good attribution. Two facts are from before the last 7 days. All non-background facts are relevant and new developments.

**Brave**: 6 alphas (3 fresh, 6 sourced) | collect 1.6s + extract 6.3s | Mixed quality due to background facts. Only 3 facts are fresh. Attribution is present but not always a URL. Some background facts are included.

<details><summary>Gemini Alphas (0)</summary>

Collect failed: Gemini grounded call failed on both primary (quota-exhausted) and backup (429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}]}}) for step 'gemini_search'.
</details>

<details><summary>Linkup Alphas (5)</summary>

1. **[2026-08-02]** [state_change] conf=1.00 | [https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines](https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines)  
   The European Commission's AI Office and national market surveillance authorities gained full enforcement powers over high-risk AI systems and general-purpose AI providers on August 2, 2026.
2. **[2026-08-02]** [development] conf=1.00 | [https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines](https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines)  
   Article 50 transparency requirements became fully enforceable on August 2, 2026.
3. **[2026-07-22]** [routine] conf=1.00 | [https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines](https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines)  
   July 22, 2026 served as the signatory cutoff date for Article 50 obligations.
4. **[2026-07-08]** [state_change] conf=1.00 | [https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines](https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines)  
   The Digital Omnibus on AI was signed on July 8, 2026.
5. **[2026-08-28]** [development] conf=0.90 | [https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines](https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines)  
   The European Commission launched a hiring call for approximately 40 contract agent posts dedicated to AI Act enforcement with applications due by September 8, 2026.
</details>

<details><summary>Brave Alphas (6)</summary>

1. **[2026-08-02]** [state_change] conf=0.95 | [The EU AI Act's New Transparency Rules Just Took Effect](Do US Companies Need to Comply? - Web Geekly — https://www.webgeekly.com/the-eu-ai-acts-new-transparency-rules-just-took-effect-do-us-companies-need-to-comply/)  
   The European Commission confirmed it has begun actively enforcing the transparency obligations under the EU AI Act.
2. **[2026-08-02]** [state_change] conf=0.95 | [The EU AI Act's High-Risk Rules Are Now Enforceable, and US Operations Are Not Exempt](https://www.lenet.com/blog/the-eu-ai-acts-high-risk-rules-are-now-enforceable-and-us-operations-are-not-exempt)  
   The EU AI Act's high-risk provisions under Annex III became binding and enforceable on August 2, 2026.
3. **[2026-08-14]** [development] conf=0.95 | [EXCLUSIVE: EU orders leading AI labs to detail security practices | Euractiv](https://www.euractiv.com/news/exclusive-eu-orders-leading-ai-labs-to-detail-security-practices/)  
   The European Union's AI Office asked more than 30 AI companies to detail how they comply with European copyright rules.
4. **[2025-01-01]** [development] conf=0.90 BACKGROUND | [EU AI Act explained: Rules, risks, and compliance | Proton](https://proton.me/blog/eu-ai-act)  
   Hungary passed a law allowing police to use live facial recognition to identify attendees at events.
5. **[2026-04-01]** [state_change] conf=0.95 BACKGROUND | [EU AI Act explained: Rules, risks, and compliance | Proton](https://proton.me/blog/eu-ai-act)  
   The European Union's top court ruled that Hungary violated LGBTQ people's fundamental rights.
6. **[2026-06-29]** [state_change] conf=0.95 BACKGROUND | [EU AI Act: What Actually Applies on 2 August 2026 - Technology Org](https://www.technology.org/2026/07/17/eu-ai-act-what-actually-applies-on-2-august-2026/)  
   The Council of the EU gave final green light to simplify and streamline rules under the AI Act.
</details>

### Bitcoin price August 2026

| Axis | Gemini | Linkup | Brave |
|---|---|---|---|
| alpha_quality | ? | ? | ? |
| freshness | ? | ? | ? |
| fact_count | ? | ? | ? |
| source_attribution | ? | ? | ? |
| noise_free | ? | ? | ? |
| topic_relevance | ? | ? | ? |
| **TOTAL** | **0** | **0** | **0** |

**Winner:** ?  |  **Finding:** —

**Gemini**: 0 alphas (0 fresh, 0 sourced) | collect 4.1s + extract 0.0s | —
  EXTRACT ERROR: collect failed: Gemini grounded call failed on both primary (quota-exhausted) and backup (429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}]}}) for step 'gemini_search'.

**Linkup**: 4 alphas (4 fresh, 4 sourced) | collect 3.1s + extract 4.7s | —

**Brave**: 9 alphas (9 fresh, 9 sourced) | collect 1.4s + extract 6.4s | —

<details><summary>Gemini Alphas (0)</summary>

Collect failed: Gemini grounded call failed on both primary (quota-exhausted) and backup (429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}]}}) for step 'gemini_search'.
</details>

<details><summary>Linkup Alphas (4)</summary>

1. **[2026-08-10]** [development] conf=0.95 | [https://isbitcoindead.com/bitcoin/current-price-of-bitcoin-for-august-11-2026/](https://isbitcoindead.com/bitcoin/current-price-of-bitcoin-for-august-11-2026/)  
   Bitcoin traded around $32,400 to $32,500.
2. **[2026-08-21]** [development] conf=0.95 | [https://fortune.com/article/price-of-bitcoin-08-20-2026/](https://fortune.com/article/price-of-bitcoin-08-20-2026/)  
   Bitcoin reached approximately $76,590 to $79,511.
3. **[2026-08-23]** [development] conf=0.95 | [https://intellectia.ai/blog/bitcoin-price-analysis-august-23-2026](https://intellectia.ai/blog/bitcoin-price-analysis-august-23-2026)  
   Bitcoin climbed to around $77,700 to $78,976.
4. **[2026-08-26]** [development] conf=0.95 | [https://fortune.com/article/price-of-bitcoin-08-26-2026/](https://fortune.com/article/price-of-bitcoin-08-26-2026/)  
   Bitcoin opened at $78,528 and reached approximately $78,746.
</details>

<details><summary>Brave Alphas (9)</summary>

1. **[2026-08-21]** [development] conf=1.00 | [Current price of Bitcoin for August 21, 2026](https://fortune.com/article/price-of-bitcoin-08-21-2026/)  
   At 8 a.m. Eastern Time on August 21, 2026, the market price for a single Bitcoin was $76,712.47.
2. **[2026-08-26]** [development] conf=1.00 | [Current price of Bitcoin for August 26, 2026](https://fortune.com/article/price-of-bitcoin-08-26-2026/)  
   At 7:15 a.m. Eastern Time on August 26, 2026, the market price for a single Bitcoin was $78,745.95.
3. **[2026-08-24]** [development] conf=1.00 | [Current price of Bitcoin for August 24, 2026](https://fortune.com/article/price-of-bitcoin-08-24-2026/)  
   At 9 a.m. Eastern Time on August 24, 2026, the market price for a single Bitcoin was $78,976.18.
4. **[2026-08-25]** [development] conf=1.00 | [Current price of Bitcoin for August 25, 2026](https://fortune.com/article/price-of-bitcoin-08-25-2026/)  
   At 8 a.m. Eastern Time on August 25, 2026, the market price for a single Bitcoin was $79,111.64.
5. **[2026-08-25]** [development] conf=1.00 | [What price will Bitcoin hit in August? Trading Odds & Predictions 2026 | Polymarket](https://polymarket.com/event/what-price-will-bitcoin-hit-in-august-2026)  
   On August 25, 2026, Bitcoin price surged to $80,894.
6. **[2026-08-27]** [routine] conf=1.00 | [What price will Bitcoin hit in August? Trading Odds & Predictions 2026 | Polymarket](https://polymarket.com/event/what-price-will-bitcoin-hit-in-august-2026)  
   The Bitcoin Asia 2026 conference took place on August 27 to August 28, 2026, in Hong Kong.
7. **[2026-08-28]** [development] conf=1.00 | [Current price of Bitcoin for August 28, 2026](https://fortune.com/article/price-of-bitcoin-08-28-2026/)  
   At 6:30 a.m. Eastern Time on August 28, 2026, the market price for a single Bitcoin was $79,132.61.
8. **[2026-08-24]** [development] conf=1.00 | [Bitcoin and ethereum prices today, Monday, August 24, 2026: Prices rising, as investors look for more Fed clues this week](https://finance.yahoo.com/personal-finance/investing/article/bitcoin-and-ethereum-prices-today-monday-august-24-2026-prices-rising-as-investors-look-for-more-fed-clues-this-week-130538704.html)  
   On August 24, 2026, Bitcoin opened at $77,727.62.
9. **[2026-08-24]** [development] conf=1.00 | [Bitcoin and ethereum prices today, Monday, August 24, 2026: Prices rising, as investors look for more Fed clues this week](https://finance.yahoo.com/personal-finance/investing/article/bitcoin-and-ethereum-prices-today-monday-august-24-2026-prices-rising-as-investors-look-for-more-fed-clues-this-week-130538704.html)  
   On August 24, 2026, the price of Bitcoin moved up to $79,106.77 during morning trading.
</details>

### Gaza ceasefire negotiations

| Axis | Gemini | Linkup | Brave |
|---|---|---|---|
| alpha_quality | ? | ? | ? |
| freshness | ? | ? | ? |
| fact_count | ? | ? | ? |
| source_attribution | ? | ? | ? |
| noise_free | ? | ? | ? |
| topic_relevance | ? | ? | ? |
| **TOTAL** | **0** | **0** | **0** |

**Winner:** ?  |  **Finding:** —

**Gemini**: 0 alphas (0 fresh, 0 sourced) | collect 4.3s + extract 0.0s | —
  EXTRACT ERROR: collect failed: Gemini grounded call failed on both primary (quota-exhausted) and backup (429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}]}}) for step 'gemini_search'.

**Linkup**: 3 alphas (2 fresh, 3 sourced) | collect 3.6s + extract 4.8s | —

**Brave**: 8 alphas (7 fresh, 8 sourced) | collect 1.8s + extract 6.3s | —

<details><summary>Gemini Alphas (0)</summary>

Collect failed: Gemini grounded call failed on both primary (quota-exhausted) and backup (429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}]}}) for step 'gemini_search'.
</details>

<details><summary>Linkup Alphas (3)</summary>

1. **[2025-01-01]** [state_change] conf=0.90 BACKGROUND | [https://www.everbridge.com/resource/gaza-ceasefire-update/](https://www.everbridge.com/resource/gaza-ceasefire-update/)  
   An initial ceasefire agreement for Gaza was brokered in January 2025.
2. **[2026-06-01]** [development] conf=0.95 | [https://www.everbridge.com/resource/gaza-ceasefire-update/](https://www.everbridge.com/resource/gaza-ceasefire-update/)  
   Talks resumed in Cairo in June 2026 between Egypt, Qatar, Turkey, and Palestinian factions.
3. **[2026-06-01]** [escalation] conf=0.90 | [https://www.everbridge.com/resource/gaza-ceasefire-update/](https://www.everbridge.com/resource/gaza-ceasefire-update/)  
   Hamas accused Israeli Prime Minister Netanyahu of undermining negotiations through strikes on Gaza City.
</details>

<details><summary>Brave Alphas (8)</summary>

1. **[2026-08-26]** [development] conf=0.95 | [Board of Peace's Gaza envoy criticises Israeli strikes and Hamas actions](https://www.bbc.com/news/articles/cew92l07kwzo)  
   Nikolay Mladenov criticized Israel for its attacks on the Palestinian territory during an address to the U.N. Security Council.
2. **[2026-08-26]** [development] conf=0.95 | [Official leading Trump's Gaza ceasefire effort criticizes Israel for its attacks](https://apnews.com/article/us-un-israel-palestinians-board-peace-gaza-6847b6e1ee06c7be1c1525a9f99538ae)  
   Nikolay Mladenov warned the U.N. Security Council that the alternative to the U.S. proposal is the next war.
3. **[2026-08-26]** [development] conf=0.95 | [Official leading Trump's Gaza ceasefire effort criticizes Israel for its attacks](https://apnews.com/article/us-un-israel-palestinians-board-peace-gaza-6847b6e1ee06c7be1c1525a9f99538ae)  
   Nikolay Mladenov stated that President Donald Trump's 20-point plan has moved from the negotiating table to the engineering table.
4. **[2026-08-26]** [casualty] conf=0.95 | [Israel's deadly Gaza strikes cast doubt on ceasefire progress days after Kushner visit](https://apnews.com/article/gaza-israel-war-kushner-talks-trump-netanyahu-8c8741e238c72bcbc45e1647afbde206)  
   At least 10 people were killed in two strikes in the Gaza Strip.
5. **[2026-08-26]** [escalation] conf=0.90 | [Israel's Latest Deadly Gaza Strikes Cast Doubt On Ceasefire Progress | HuffPost Latest News](https://www.huffpost.com/entry/israel-latest-gaza-strikes-doubt-ceasefire-progress-palestinians_n_6a8b0368e4b0a833ba42db5e)  
   Israeli troops crossed the ceasefire line in southern Gaza and detained a Hamas police colonel at dawn.
6. **[2026-08-24]** [development] conf=0.90 | [Israel's deadly Gaza strikes cast doubt on ceasefire progress days after Kushner visit](https://apnews.com/article/gaza-israel-war-kushner-talks-trump-netanyahu-8c8741e238c72bcbc45e1647afbde206)  
   U.S. negotiators asked Israel to draw down attacks in the Gaza Strip.
7. **[2026-08-26]** [development] conf=0.95 | [Board of Peace's Gaza envoy criticises Israeli strikes and Hamas actions](https://www.bbc.com/news/articles/cew92l07kwzo)  
   Nikolay Mladenov announced that he and Israeli Prime Minister Benjamin Netanyahu agreed at their last meeting on a mechanism to settle the government's remaining questions.
8. **[2026-08-26]** [tally] conf=0.90 BACKGROUND | [Board of Peace's Gaza envoy criticises Israeli strikes and Hamas actions](https://www.bbc.com/news/articles/cew92l07kwzo)  
   At least 1,303 Palestinians, including 300 children, have been killed in Israeli attacks in Gaza since the U.S.-brokered ceasefire began.
</details>
