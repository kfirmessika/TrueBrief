# Search Layer Benchmark v3 — Pipeline Level
**Date:** 2026-08-28  |  **Topics:** 5  |  **Max score:** 90 per provider

All 3 providers run through the same 2-call pipeline (collect -> extract using `build_gemini_extract_prompt`).
Judge scores the resulting Alpha objects, not raw search output.

## Summary

| Topic | Gemini | Linkup | Brave | Winner |
|---|---|---|---|---|
| Iran US ceasefire Strait of Hormuz | 0 | 0 | 0 | **?** |
| Federal Reserve interest rate decision August 2026 | 0 | 11 | 9 | **linkup** |
| EU AI Act enforcement 2026 | 0 | 0 | 0 | **?** |
| Bitcoin price August 2026 | 0 | 0 | 0 | **?** |
| Gaza ceasefire negotiations | 0 | 8 | 11 | **brave** |
| **TOTAL** | **0** | **19** | **20** | |

## Alpha counts

| Topic | Gemini | Linkup | Brave |
|---|---|---|---|
| Iran US ceasefire Strait of Hormuz | 0 | 3 | 12 |
| Federal Reserve interest rate decision August 2026 | 0 | 3 | 6 |
| EU AI Act enforcement 2026 | 0 | 9 | 5 |
| Bitcoin price August 2026 | 0 | 4 | 8 |
| Gaza ceasefire negotiations | 0 | 3 | 12 |

## Per-Topic Results

### Iran US ceasefire Strait of Hormuz

| Axis | Gemini | Linkup | Brave |
|---|---|---|---|
| alpha_quality | ? | ? | ? |
| freshness | ? | ? | ? |
| fact_count | ? | ? | ? |
| noise_free | ? | ? | ? |
| topic_relevance | ? | ? | ? |
| specificity | ? | ? | ? |
| **TOTAL** | **0** | **0** | **0** |

**Winner:** ?  |  **Finding:** —

**Gemini**: 0 alphas (0 fresh, 0 sourced) | collect 7.1s + extract 0.0s | —
  EXTRACT ERROR: collect failed: Error code: 429 - {'error': {'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'code': 'too_many_requests'}}

**Linkup**: 3 alphas (3 fresh, 3 sourced) | collect 4.6s + extract 7.5s | —

**Brave**: 12 alphas (3 fresh, 12 sourced) | collect 2.4s + extract 8.2s | —

<details><summary>Gemini Alphas (0)</summary>

Collect failed: Error code: 429 - {'error': {'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'code': 'too_many_requests'}}
</details>

<details><summary>Linkup Alphas (3)</summary>

1. **[2026-04-08]** [state_change] conf=0.95 | [https://politicsnigeria.com/2026/04/08/8473/](https://politicsnigeria.com/2026/04/08/8473/)  
   The United States and Iran agreed to a two-week ceasefire in April 2026.
2. **[2026-04-08]** [state_change] conf=0.95 | [https://politicsnigeria.com/2026/04/08/8473/](https://politicsnigeria.com/2026/04/08/8473/)  
   Iran confirmed it would allow safe passage through the Strait of Hormuz for a two-week period.
3. **[2026-04-08]** [development] conf=0.90 | [https://politicsnigeria.com/2026/04/08/8473/](https://politicsnigeria.com/2026/04/08/8473/)  
   Iran submitted a 10-point proposal including demands for the removal of US sanctions, recognition of its control over the Strait of Hormuz, and the withdrawal of US forces from the region.
</details>

<details><summary>Brave Alphas (12)</summary>

1. **[2026-03-25]** [development] conf=0.95 BACKGROUND | [2026 Iran war ceasefire - Wikipedia](https://en.wikipedia.org/wiki/2026_Iran_war_ceasefire)  
   Pakistani officials delivered a 15-point proposal from the United States to Iran detailing a ceasefire plan on March 25.
2. **[2026-03-31]** [development] conf=0.95 BACKGROUND | [2026 Iran war ceasefire - Wikipedia](https://en.wikipedia.org/wiki/2026_Iran_war_ceasefire)  
   Pakistan and China delivered a 5-point initiative for peace calling for an immediate end to all hostilities on March 31.
3. **[2026-04-01]** [development] conf=0.95 BACKGROUND | [2026 Iran war ceasefire - Wikipedia](https://en.wikipedia.org/wiki/2026_Iran_war_ceasefire)  
   Donald Trump claimed that Iran had asked the United States for a ceasefire on April 1.
4. **[2026-04-07]** [state_change] conf=0.95 BACKGROUND | [2026 Iran war - Wikipedia](https://en.wikipedia.org/wiki/2026_Iran_war)  
   The United States and Iran agreed to a ceasefire that included Israel on April 7.
5. **[2026-06-19]** [state_change] conf=0.95 BACKGROUND | [2026 Strait of Hormuz crisis - Wikipedia](https://en.wikipedia.org/wiki/2026_Strait_of_Hormuz_crisis)  
   Donald Trump announced a renewed ceasefire between Israel and Hezbollah facilitated by the United States, Qatar, and Iran on June 19.
6. **[2026-06-20]** [escalation] conf=0.95 BACKGROUND | [2026 Strait of Hormuz crisis - Wikipedia](https://en.wikipedia.org/wiki/2026_Strait_of_Hormuz_crisis)  
   Iran stated that it closed the Strait of Hormuz again on June 20, citing Israeli strikes in southern Lebanon as a violation of the agreement.
7. **[2026-06-27]** [development] conf=0.95 BACKGROUND | [2026 Strait of Hormuz crisis - Wikipedia](https://en.wikipedia.org/wiki/2026_Strait_of_Hormuz_crisis)  
   The Joint Maritime Information Center overseen by the U.S. Navy announced a widened route through the Strait of Hormuz near Oman on June 27.
8. **[2026-06-28]** [state_change] conf=0.95 BACKGROUND | [2026 Iran war - Wikipedia](https://en.wikipedia.org/wiki/2026_Iran_war)  
   The United States and Iran agreed to cease their exchange of attacks on June 28.
9. **[2026-07-08]** [state_change] conf=0.95 BACKGROUND | [2026 Iran war - Wikipedia](https://en.wikipedia.org/wiki/2026_Iran_war)  
   The ceasefire deal between the United States and Iran collapsed on July 8 after Iran initiated attacks on commercial vessels in the Strait of Hormuz.
10. **[2026-08-25]** [casualty] conf=0.90 | [Iran Ceasefire Status 2026: Is the US-Iran War Over? Live Tracker](https://militaryspend.org/iran-ceasefire-status)  
   Two unclaimed projectile strikes disabled tankers off Oman near the Strait of Hormuz between August 24 and August 25.
11. **[2026-08-26]** [state_change] conf=0.90 | [The US and Iran have agreed on a ceasefire and the reopening of the Strait of Hormuz – media reports](https://ukragroconsult.com/en/news/the-us-and-iran-have-agreed-to-a-ceasefire/)  
   Turkish news agency Anadolu cited Pakistani and Iranian sources stating the United States and Iran reached a ceasefire agreement including provisions for free navigation through the Strait of Hormuz on August 26.
12. **[2026-08-27]** [development] conf=0.90 | [Iran Ceasefire Status 2026: Is the US-Iran War Over? Live Tracker](https://militaryspend.org/iran-ceasefire-status)  
   Qatari Prime Minister visited Tehran on August 27 to push for de-escalation.
</details>

### Federal Reserve interest rate decision August 2026

| Axis | Gemini | Linkup | Brave |
|---|---|---|---|
| alpha_quality | 0 | 3 | 2 |
| freshness | 0 | 1 | 1 |
| fact_count | 0 | 1 | 2 |
| noise_free | 0 | 3 | 1 |
| topic_relevance | 0 | 3 | 3 |
| specificity | ? | ? | ? |
| **TOTAL** | **0** | **11** | **9** |

**Winner:** linkup  |  **Finding:** LinkUp provided the most relevant and directly actionable facts regarding the Federal Reserve's August 2026 interest rate decision, despite the event date being slightly outside the freshness window.

**Gemini**: 0 alphas (0 fresh, 0 sourced) | collect 5.5s + extract 0.0s | Gemini failed to extract any alphas due to an API quota error.
  EXTRACT ERROR: collect failed: Error code: 429 - {'error': {'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'code': 'too_many_requests'}}

**Linkup**: 3 alphas (3 fresh, 3 sourced) | collect 2.7s + extract 4.8s | LinkUp provided 3 facts related to the August 2026 Fed decision, with event dates from Aug 24, which is outside the 7-day window.

**Brave**: 6 alphas (4 fresh, 6 sourced) | collect 1.7s + extract 5.7s | Brave provided 6 facts, with event dates ranging from July 31 to Sep 16. Facts 1 & 2 are background, and facts 4, 5, & 6 are routine or future events, not directly about the August decision.

<details><summary>Gemini Alphas (0)</summary>

Collect failed: Error code: 429 - {'error': {'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'code': 'too_many_requests'}}
</details>

<details><summary>Linkup Alphas (3)</summary>

1. **[2026-08-24]** [state_change] conf=1.00 | [https://fedratecalc.com/fomc-meeting-schedule/](https://fedratecalc.com/fomc-meeting-schedule/)  
   The Federal Reserve held its benchmark interest rate steady at 3.5%–3.75% in its August 2026 decision.
2. **[2026-08-24]** [development] conf=1.00 | [https://fedratecalc.com/fomc-meeting-schedule/](https://fedratecalc.com/fomc-meeting-schedule/)  
   The Federal Reserve voted 9–3 to hold its benchmark interest rate steady on August 24, 2026.
3. **[2026-08-24]** [development] conf=1.00 | [https://fedratecalc.com/fomc-meeting-schedule/](https://fedratecalc.com/fomc-meeting-schedule/)  
   Beth M Hammack, Neel Kashkari, and Lorie K Logan dissented from the Federal Reserve August 2026 interest rate decision.
</details>

<details><summary>Brave Alphas (6)</summary>

1. **[2026-07-31]** [state_change] conf=0.95 BACKGROUND | [United States Fed Funds Interest Rate](https://tradingeconomics.com/united-states/interest-rate)  
   The Federal Reserve left the federal funds rate unchanged at 3.50% to 3.75% for a fifth consecutive meeting in July 2026.
2. **[2026-07-31]** [development] conf=0.90 BACKGROUND | [United States Fed Funds Interest Rate](https://tradingeconomics.com/united-states/interest-rate)  
   Three FOMC members dissented from the July 2026 interest rate decision to vote for a rate hike.
3. **[2026-08-19]** [development] conf=0.95 | [Federal Reserve Board - News & Events](https://www.federalreserve.gov/newsevents.htm)  
   The Federal Reserve announced five task forces to examine areas central to the broad conduct of monetary policy.
4. **[2026-08-27]** [routine] conf=0.95 | [Federal Reserve Board - News & Events](https://www.federalreserve.gov/newsevents.htm)  
   The Federal Reserve released the minutes of the Board's discount rate meetings held on July 20 and July 29, 2026.
5. **[2026-09-15]** [routine] conf=1.00 | [Next FOMC Meeting: September 15–16, 2026 Countdown | FedRateCalc](https://fedratecalc.com/next-fomc-meeting/)  
   The next scheduled Federal Reserve FOMC meeting is September 15 to 16, 2026.
6. **[2026-09-16]** [routine] conf=1.00 | [Next FOMC Meeting: September 15–16, 2026 Countdown | FedRateCalc](https://fedratecalc.com/next-fomc-meeting/)  
   The Federal Reserve is scheduled to announce its interest rate decision on September 16, 2026 at 2:00 PM ET.
</details>

### EU AI Act enforcement 2026

| Axis | Gemini | Linkup | Brave |
|---|---|---|---|
| alpha_quality | ? | ? | ? |
| freshness | ? | ? | ? |
| fact_count | ? | ? | ? |
| noise_free | ? | ? | ? |
| topic_relevance | ? | ? | ? |
| specificity | ? | ? | ? |
| **TOTAL** | **0** | **0** | **0** |

**Winner:** ?  |  **Finding:** —

**Gemini**: 0 alphas (0 fresh, 0 sourced) | collect 5.2s + extract 0.0s | —
  EXTRACT ERROR: collect failed: Error code: 429 - {'error': {'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'code': 'too_many_requests'}}

**Linkup**: 9 alphas (9 fresh, 9 sourced) | collect 2.9s + extract 7.2s | —

**Brave**: 5 alphas (4 fresh, 5 sourced) | collect 1.6s + extract 5.5s | —

<details><summary>Gemini Alphas (0)</summary>

Collect failed: Error code: 429 - {'error': {'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'code': 'too_many_requests'}}
</details>

<details><summary>Linkup Alphas (9)</summary>

1. **[2026-08-02]** [state_change] conf=1.00 | [https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines](https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines)  
   EU AI Act enforcement began on August 2, 2026, marking the full application of high-risk AI obligations and transparency requirements.
2. **[2026-08-02]** [development] conf=1.00 | [https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines](https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines)  
   The European Commission's AI Office and national market surveillance authorities gained enforcement powers on August 2, 2026.
3. **[2026-08-02]** [development] conf=1.00 | [https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines](https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines)  
   Article 50 transparency rules, requiring chatbot disclosures, deepfake labeling, and machine-readable marking of synthetic content, became fully enforceable on August 2, 2026.
4. **[2026-08-02]** [development] conf=1.00 | [https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines](https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines)  
   The penalty regime for GPAI-specific violations reached up to €15 million or 3% of worldwide annual turnover, while more serious violations could reach €35 million or 7% of global turnover.
5. **[2026-07-22]** [development] conf=1.00 | [https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines](https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines)  
   A cutoff date of July 22, 2026, was applied to Article 50 obligations, after which businesses could no longer influence code of practice terms.
6. **[2026-08-02]** [development] conf=1.00 | [https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines](https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines)  
   High-risk AI rules were deferred to December 2, 2027.
7. **[2026-08-02]** [development] conf=1.00 | [https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines](https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines)  
   High-risk AI integrated into regulated products was deferred to August 2, 2028.
8. **[2026-08-02]** [development] conf=1.00 | [https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines](https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines)  
   The European Commission launched complaint and whistleblower tools to support EU AI Act enforcement.
9. **[2026-08-02]** [development] conf=1.00 | [https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines](https://beam.ai/agentic-insights/eu-ai-act-enforcement-august-2-2026-gpai-fines)  
   The European Commission opened a hiring call for approximately 40 contract agent positions to strengthen AI Act enforcement capacity.
</details>

<details><summary>Brave Alphas (5)</summary>

1. **[2026-08-02]** [state_change] conf=1.00 | [The enforcement framework of the AI Act | Shaping Europe’s digital future](https://digital-strategy.ec.europa.eu/en/policies/enforcement-ai-act)  
   The enforcement powers of the AI Office and national competent authorities of Member States apply to prohibited AI practices and transparency rules starting August 2, 2026.
2. **[2026-08-02]** [development] conf=1.00 | [The EU AI Act's New Transparency Rules Just Took Effect](Do US Companies Need to Comply? - Web Geekly — https://www.webgeekly.com/the-eu-ai-acts-new-transparency-rules-just-took-effect-do-us-companies-need-to-comply/)  
   The European Commission confirmed it has begun actively enforcing the transparency obligations of the AI Act as of August 2, 2026.
3. **[2026-08-14]** [development] conf=0.95 | [EXCLUSIVE: EU orders leading AI labs to detail security practices | Euractiv](https://www.euractiv.com/news/exclusive-eu-orders-leading-ai-labs-to-detail-security-practices/)  
   The EU's AI enforcers asked more than 30 AI companies to detail how they comply with European copyright rules regarding training model data summaries.
4. **[2026-08-02]** [state_change] conf=1.00 | [The EU AI Act's High-Risk Rules Are Now Enforceable, and US Operations Are Not Exempt](https://www.lenet.com/blog/the-eu-ai-acts-high-risk-rules-are-now-enforceable-and-us-operations-are-not-exempt)  
   The high-risk provisions for standalone Annex III AI systems became binding on August 2, 2026.
5. **[2026-04-01]** [development] conf=0.90 BACKGROUND | [EU AI Act explained: Rules, risks, and compliance | Proton](https://proton.me/blog/eu-ai-act)  
   The EU top court ruled that Hungary violated LGBTQ people's fundamental rights in April 2026.
</details>

### Bitcoin price August 2026

| Axis | Gemini | Linkup | Brave |
|---|---|---|---|
| alpha_quality | ? | ? | ? |
| freshness | ? | ? | ? |
| fact_count | ? | ? | ? |
| noise_free | ? | ? | ? |
| topic_relevance | ? | ? | ? |
| specificity | ? | ? | ? |
| **TOTAL** | **0** | **0** | **0** |

**Winner:** ?  |  **Finding:** —

**Gemini**: 0 alphas (0 fresh, 0 sourced) | collect 5.1s + extract 0.0s | —
  EXTRACT ERROR: collect failed: Error code: 429 - {'error': {'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'code': 'too_many_requests'}}

**Linkup**: 4 alphas (4 fresh, 4 sourced) | collect 3.2s + extract 5.0s | —

**Brave**: 8 alphas (8 fresh, 8 sourced) | collect 1.4s + extract 6.2s | —

<details><summary>Gemini Alphas (0)</summary>

Collect failed: Error code: 429 - {'error': {'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'code': 'too_many_requests'}}
</details>

<details><summary>Linkup Alphas (4)</summary>

1. **[2026-08-10]** [development] conf=0.95 | [https://isbitcoindead.com/bitcoin/current-price-of-bitcoin-for-august-11-2026/](https://isbitcoindead.com/bitcoin/current-price-of-bitcoin-for-august-11-2026/)  
   Bitcoin traded around $32,400 to $32,500 on August 10 and 11, 2026.
2. **[2026-08-21]** [development] conf=0.95 | [https://fortune.com/article/price-of-bitcoin-08-21-2026/](https://fortune.com/article/price-of-bitcoin-08-21-2026/)  
   Bitcoin reached approximately $76,590 to $79,511 by August 21, 2026.
3. **[2026-08-23]** [development] conf=0.95 | [https://intellectia.ai/blog/bitcoin-price-analysis-august-23-2026](https://intellectia.ai/blog/bitcoin-price-analysis-august-23-2026)  
   Bitcoin climbed to around $77,700 to $78,976 on August 23 and 24, 2026.
4. **[2026-08-26]** [development] conf=0.95 | [https://fortune.com/article/price-of-bitcoin-08-26-2026/](https://fortune.com/article/price-of-bitcoin-08-26-2026/)  
   Bitcoin opened at $78,528 and reached approximately $78,746 on August 26, 2026.
</details>

<details><summary>Brave Alphas (8)</summary>

1. **[2026-08-21]** [development] conf=1.00 | [Current price of Bitcoin for August 21, 2026](https://fortune.com/article/price-of-bitcoin-08-21-2026/)  
   At 8 a.m. Eastern Time on August 21, 2026, the market price for a single Bitcoin was $76,712.47.
2. **[2026-08-26]** [development] conf=1.00 | [Current price of Bitcoin for August 26, 2026](https://fortune.com/article/price-of-bitcoin-08-26-2026/)  
   At 7:15 a.m. Eastern Time on August 26, 2026, the market price for a single Bitcoin was $78,745.95.
3. **[2026-08-24]** [development] conf=1.00 | [Current price of Bitcoin for August 24, 2026](https://fortune.com/article/price-of-bitcoin-08-24-2026/)  
   At 9 a.m. Eastern Time on August 24, 2026, the price of Bitcoin was $78,976.18.
4. **[2026-08-25]** [development] conf=1.00 | [Current price of Bitcoin for August 25, 2026](https://fortune.com/article/price-of-bitcoin-08-25-2026/)  
   At 8 a.m. Eastern Time on August 25, 2026, the price of Bitcoin was $79,111.64.
5. **[2026-08-25]** [development] conf=0.95 | [What price will Bitcoin hit in August? Trading Odds & Predictions 2026 | Polymarket](https://polymarket.com/event/what-price-will-bitcoin-hit-in-august-2026)  
   On August 25, 2026, the price of Bitcoin surged to $80,894 following a Treasury-related buyback event.
6. **[2026-08-27]** [routine] conf=1.00 | [What price will Bitcoin hit in August? Trading Odds & Predictions 2026 | Polymarket](https://polymarket.com/event/what-price-will-bitcoin-hit-in-august-2026)  
   The Bitcoin Asia 2026 conference took place on August 27–28 in Hong Kong.
7. **[2026-08-28]** [development] conf=1.00 | [Current price of Bitcoin for August 28, 2026](https://fortune.com/article/price-of-bitcoin-08-28-2026/)  
   At 6:30 a.m. Eastern Time on August 28, 2026, the market price for a single Bitcoin was $79,132.61.
8. **[2026-08-24]** [development] conf=1.00 | [Bitcoin and ethereum prices today, Monday, August 24, 2026: Prices rising, as investors look for more Fed clues this week](https://finance.yahoo.com/personal-finance/investing/article/bitcoin-and-ethereum-prices-today-monday-august-24-2026-prices-rising-as-investors-look-for-more-fed-clues-this-week-130538704.html)  
   Bitcoin opened at $77,727.62 on Monday, August 24, 2026.
</details>

### Gaza ceasefire negotiations

| Axis | Gemini | Linkup | Brave |
|---|---|---|---|
| alpha_quality | 0 | 2 | 2 |
| freshness | 0 | 1 | 2 |
| fact_count | 0 | 1 | 2 |
| noise_free | 0 | 1 | 2 |
| topic_relevance | 0 | 3 | 3 |
| specificity | ? | ? | ? |
| **TOTAL** | **0** | **8** | **11** |

**Winner:** brave  |  **Finding:** Recent developments in Gaza ceasefire negotiations highlight ongoing diplomatic efforts and persistent challenges, with figures like Nikolay Mladenov playing a key role in mediating and commenting on the progress and risks of collapse.

**Gemini**: 0 alphas (0 fresh, 0 sourced) | collect 5.7s + extract 0.0s | Extraction failed due to quota limits.
  EXTRACT ERROR: collect failed: Error code: 429 - {'error': {'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'code': 'too_many_requests'}}

**Linkup**: 3 alphas (2 fresh, 3 sourced) | collect 3.0s + extract 4.5s | Fact 1 is background information. Facts 2 and 3 are recent but contain minor editorializing and lack specificity.

**Brave**: 12 alphas (9 fresh, 12 sourced) | collect 1.7s + extract 8.1s | Many facts are recent and specific, but some background facts are included, and there's a slight tendency towards editorializing.

<details><summary>Gemini Alphas (0)</summary>

Collect failed: Error code: 429 - {'error': {'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. ', 'code': 'too_many_requests'}}
</details>

<details><summary>Linkup Alphas (3)</summary>

1. **[2025-01-31]** [state_change] conf=0.90 BACKGROUND | [https://www.everbridge.com/resource/gaza-ceasefire-update/](https://www.everbridge.com/resource/gaza-ceasefire-update/)  
   An initial ceasefire agreement for Gaza was brokered in January 2025 following 96 hours of negotiations.
2. **[2026-06-06]** [development] conf=0.95 | [https://egyptianstreets.com/2026/06/06/gaza-ceasefire-talks-resume-in-cairo/](https://egyptianstreets.com/2026/06/06/gaza-ceasefire-talks-resume-in-cairo/)  
   Ceasefire talks resumed in Cairo in June 2026 involving mediators Egypt, Qatar, and Turkey along with Palestinian factions.
3. **[2026-06-06]** [escalation] conf=0.90 | [https://egyptianstreets.com/2026/06/06/gaza-ceasefire-talks-resume-in-cairo/](https://egyptianstreets.com/2026/06/06/gaza-ceasefire-talks-resume-in-cairo/)  
   Hamas accused Israeli Prime Minister Benjamin Netanyahu of undermining negotiations through strikes on Gaza City.
</details>

<details><summary>Brave Alphas (12)</summary>

1. **[2026-08-26]** [development] conf=0.95 | [Official leading Trump's Gaza ceasefire effort criticizes Israel for its attacks](https://apnews.com/article/us-un-israel-palestinians-board-peace-gaza-6847b6e1ee06c7be1c1525a9f99538ae)  
   Nikolay Mladenov criticized Israel for its attacks on the Palestinian territory.
2. **[2026-08-26]** [development] conf=0.95 | [Official leading Trump's Gaza ceasefire effort criticizes Israel for its attacks](https://apnews.com/article/us-un-israel-palestinians-board-peace-gaza-6847b6e1ee06c7be1c1525a9f99538ae)  
   Nikolay Mladenov warned that the alternative to the U.S. proposal is the next war.
3. **[2026-08-26]** [development] conf=0.95 | [Official leading Trump's Gaza ceasefire effort criticizes Israel for its attacks](https://apnews.com/article/us-un-israel-palestinians-board-peace-gaza-6847b6e1ee06c7be1c1525a9f99538ae)  
   Nikolay Mladenov stated that the 20-point plan has moved from the negotiating table to the engineering table.
4. **[2026-08-26]** [casualty] conf=0.95 | [Israel's Latest Deadly Gaza Strikes Cast Doubt On Ceasefire Progress | HuffPost Latest News](https://www.huffpost.com/entry/israel-latest-gaza-strikes-doubt-ceasefire-progress-palestinians_n_6a8b0368e4b0a833ba42db5e)  
   At least 10 people were killed in two strikes in the Gaza Strip.
5. **[2026-08-26]** [escalation] conf=0.90 | [Israel's Latest Deadly Gaza Strikes Cast Doubt On Ceasefire Progress | HuffPost Latest News](https://www.huffpost.com/entry/israel-latest-gaza-strikes-doubt-ceasefire-progress-palestinians_n_6a8b0368e4b0a833ba42db5e)  
   Israeli troops crossed the ceasefire line in southern Gaza and detained a Hamas police colonel.
6. **[2026-05-21]** [development] conf=0.95 BACKGROUND | [Board of Peace envoy Mladenov warns Gaza ceasefire risks ‘collapse’ | Gaza News | Al Jazeera](https://www.aljazeera.com/news/2026/8/28/board-of-peace-envoy-mladenov-warns-gaza-ceasefire-risks-collapse)  
   Nikolay Mladenov proposed a 15-point roadmap covering reconstruction, disarmament of Palestinian armed groups, an Israeli gradual withdrawal, and police restructuring.
7. **[2026-07-31]** [state_change] conf=0.95 BACKGROUND | [Board of Peace envoy Mladenov warns Gaza ceasefire risks ‘collapse’ | Gaza News | Al Jazeera](https://www.aljazeera.com/news/2026/8/28/board-of-peace-envoy-mladenov-warns-gaza-ceasefire-risks-collapse)  
   The Board of Peace announced that it reached an agreement on the roadmap for the ceasefire's next phase.
8. **[2026-08-28]** [development] conf=0.95 | [Board of Peace envoy Mladenov warns Gaza ceasefire risks ‘collapse’ | Gaza News | Al Jazeera](https://www.aljazeera.com/news/2026/8/28/board-of-peace-envoy-mladenov-warns-gaza-ceasefire-risks-collapse)  
   Nikolay Mladenov warned that the failure of both sides to adhere to the roadmap for peace threatens a collapse of the ceasefire in Gaza.
9. **[2026-08-26]** [development] conf=0.95 | [Board of Peace's Gaza envoy criticises Israeli strikes and Hamas actions](https://www.bbc.com/news/articles/cew92l07kwzo)  
   Nikolay Mladenov and Benjamin Netanyahu agreed at their last meeting on a mechanism through which remaining questions would be settled.
10. **[2026-08-26]** [tally] conf=0.90 BACKGROUND | [Board of Peace's Gaza envoy criticises Israeli strikes and Hamas actions](https://www.bbc.com/news/articles/cew92l07kwzo)  
   At least 1,303 Palestinians, including 300 children, have been killed in Israeli attacks in Gaza since the ceasefire began.
11. **[2026-08-26]** [development] conf=0.95 | [UN envoy warns Gaza ceasefire plan could collapse as Israeli](https://egyptdailynews.com/un-envoy-warns-gaza-ceasefire-plan-could/)  
   Noa Furman stated that Israel continued to support Trump's broader plan and was cooperating with Washington to secure Hamas' disarmament.
12. **[2026-08-26]** [state_change] conf=0.90 | [UN envoy warns Gaza ceasefire plan could collapse as Israeli](https://egyptdailynews.com/un-envoy-warns-gaza-ceasefire-plan-could/)  
   Nikolay Mladenov stated that Hamas accepted a central condition to disarm and surrender control of Gaza to a civilian administration.
</details>
