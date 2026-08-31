# Search Layer Benchmark v3 — Pipeline Level
**Date:** 2026-08-30  |  **Topics:** 5  |  **Max score:** 90 per provider

Linkup and Brave run through the same 2-call pipeline (collect -> extract via `build_gemini_extract_prompt`).
Judge scores the resulting Alpha objects, not raw search output. Gemini excluded — quota exhausted.

## Summary

| Topic | Linkup | Brave | Winner |
|---|---|---|---|
| Iran US ceasefire Strait of Hormuz | 13 | 11 | **linkup** |
| Federal Reserve interest rate decision August 2026 | 16 | 12 | **linkup** |
| EU AI Act enforcement 2026 | 12 | 13 | **brave** |
| Bitcoin price August 2026 | 16 | 15 | **brave** |
| Gaza ceasefire negotiations | 13 | 17 | **brave** |
| **TOTAL** | **70** | **68** | |

## Alpha counts

| Topic | Linkup | Brave |
|---|---|---|
| Iran US ceasefire Strait of Hormuz | 6 | 13 |
| Federal Reserve interest rate decision August 2026 | 4 | 4 |
| EU AI Act enforcement 2026 | 5 | 7 |
| Bitcoin price August 2026 | 4 | 13 |
| Gaza ceasefire negotiations | 4 | 11 |

## Per-Topic Results

### Iran US ceasefire Strait of Hormuz

| Axis | Linkup | Brave |
|---|---|
| alpha_quality | 3 | 3 |
| freshness | 1 | 0 |
| fact_count | 1 | 0 |
| noise_free | 3 | 3 |
| topic_relevance | 3 | 2 |
| specificity | 2 | 3 |
| **TOTAL** | **13** | **11** |

**Winner:** linkup  |  **Finding:** Linkup provided a mix of recent and historical context, whereas Brave returned only outdated information from March and June, failing the freshness requirement entirely.

**Linkup**: 6 alphas (5 fresh, 6 sourced) | collect 3.5s + extract 9.7s | High quality and relevant facts, but severely lacking in freshness with only 2 out of 6 facts from the last 7 days.

**Brave**: 13 alphas (4 fresh, 13 sourced) | collect 2.1s + extract 9.9s | Highly specific and clean facts, but completely failed to retrieve any news from the last 7 days, rendering it useless for a current news pipeline.

<details><summary>Linkup Alphas (6)</summary>

1. **[2026-06-15]** [state_change] conf=0.95 | [https://www.informationng.com/2026/04/strait-of-hormus-reopens-as-us-iran-agree-two-week-ceasefire.html](https://www.informationng.com/2026/04/strait-of-hormus-reopens-as-us-iran-agree-two-week-ceasefire.html)  
   The United States and Iran reached a two-week ceasefire agreement.
2. **[2026-06-15]** [development] conf=0.95 | [https://www.newshub.co.uk/news/2026/06/15/trump-announces-us-iran-ceasefire-agreement-and-strait-of-hormuz-reopening/](https://www.newshub.co.uk/news/2026/06/15/trump-announces-us-iran-ceasefire-agreement-and-strait-of-hormuz-reopening/)  
   President Trump announced the U.S.-Iran ceasefire agreement and the reopening of the Strait of Hormuz.
3. **[2026-06-15]** [development] conf=0.95 | [https://www.informationng.com/2026/04/strait-of-hormus-reopens-as-us-iran-agree-two-week-ceasefire.html](https://www.informationng.com/2026/04/strait-of-hormus-reopens-as-us-iran-agree-two-week-ceasefire.html)  
   Iranian Foreign Minister Abbas Araghchi confirmed that the reopening of the Strait of Hormuz would be coordinated with Iranian military forces.
4. **[2026-06-14]** [escalation] conf=0.90 BACKGROUND | [https://www.informationng.com/2026/04/strait-of-hormus-reopens-as-us-iran-agree-two-week-ceasefire.html](https://www.informationng.com/2026/04/strait-of-hormus-reopens-as-us-iran-agree-two-week-ceasefire.html)  
   Iran blocked the Strait of Hormuz in response to weeks of U.S. and Israeli strikes.
5. **[2026-08-30]** [escalation] conf=0.90 | [https://www.informationng.com/2026/04/strait-of-hormus-reopens-as-us-iran-agree-two-week-ceasefire.html](https://www.informationng.com/2026/04/strait-of-hormus-reopens-as-us-iran-agree-two-week-ceasefire.html)  
   Iran reimposed restrictions on the Strait of Hormuz.
6. **[2026-08-30]** [routine] conf=0.90 | [https://www.informationng.com/2026/04/strait-of-hormus-reopens-as-us-iran-agree-two-week-ceasefire.html](https://www.informationng.com/2026/04/strait-of-hormus-reopens-as-us-iran-agree-two-week-ceasefire.html)  
   Talks to finalize a longer-term agreement between the United States and Iran are scheduled to begin in Pakistan.
</details>

<details><summary>Brave Alphas (13)</summary>

1. **[2026-03-25]** [development] conf=0.95 BACKGROUND | [2026 Iran war ceasefire - Wikipedia](https://en.wikipedia.org/wiki/2026_Iran_war_ceasefire)  
   Pakistani officials delivered a 15-point proposal from the United States to Iran detailing a ceasefire plan on March 25.
2. **[2026-03-25]** [development] conf=0.95 BACKGROUND | [2026 Iran war ceasefire - Wikipedia](https://en.wikipedia.org/wiki/2026_Iran_war_ceasefire)  
   Iran issued a 5-point counter-proposal responding to the United States ceasefire plan.
3. **[2026-03-31]** [development] conf=0.95 BACKGROUND | [2026 Iran war ceasefire - Wikipedia](https://en.wikipedia.org/wiki/2026_Iran_war_ceasefire)  
   Pakistan and China delivered a 5-point initiative for peace calling for an immediate end to all hostilities on March 31.
4. **[2026-04-01]** [development] conf=0.95 BACKGROUND | [2026 Iran war ceasefire - Wikipedia](https://en.wikipedia.org/wiki/2026_Iran_war_ceasefire)  
   Donald Trump stated on April 1 that Iran had asked the US for a ceasefire.
5. **[2026-06-19]** [state_change] conf=0.95 BACKGROUND | [2026 Strait of Hormuz crisis - Wikipedia](https://en.wikipedia.org/wiki/2026_Strait_of_Hormuz_crisis)  
   Donald Trump announced a renewed ceasefire between Israel and Hezbollah on June 19.
6. **[2026-06-20]** [escalation] conf=0.95 BACKGROUND | [2026 Strait of Hormuz crisis - Wikipedia](https://en.wikipedia.org/wiki/2026_Strait_of_Hormuz_crisis)  
   Iran declared that it closed the Strait of Hormuz again on June 20, citing Israeli strikes in southern Lebanon.
7. **[2026-06-27]** [development] conf=0.95 BACKGROUND | [2026 Strait of Hormuz crisis - Wikipedia](https://en.wikipedia.org/wiki/2026_Strait_of_Hormuz_crisis)  
   The Joint Maritime Information Center announced a widened route through the Strait of Hormuz near Oman on June 27.
8. **[2026-04-08]** [state_change] conf=0.95 BACKGROUND | [2026 Iran war | Deal, Explained, United States, Israel, Strait of Hormuz, Map, & Conflict | Britannica](https://www.britannica.com/event/2026-Iran-war)  
   The United States and Iran agreed to a ceasefire that included Israel between April 7 and April 8.
9. **[2026-08-26]** [state_change] conf=0.90 | [The US and Iran have agreed on a ceasefire and the reopening of the Strait of Hormuz – media reports](https://ukragroconsult.com/en/news/the-us-and-iran-have-agreed-to-a-ceasefire/)  
   Turkish news agency Anadolu reported on August 26 that the United States and Iran reached a ceasefire agreement including provisions for free navigation through the Strait of Hormuz.
10. **[2026-08-26]** [development] conf=0.90 | [Tehran engages in renewed diplomatic push, touts proposal to reopen Strait of Hormuz](https://www.cbsnews.com/live-updates/iran-war-us-strait-of-hormuz-sanctions/)  
   Iran's deputy foreign minister stated on August 26 that the Strait of Hormuz would not reopen until the United States changes its economic pressure.
11. **[2026-08-25]** [casualty] conf=0.90 | [Iran Ceasefire Status 2026: Is the US-Iran War Over? Live Tracker](https://militaryspend.org/iran-ceasefire-status)  
   Two unclaimed projectile strikes disabled tankers off Oman near the Strait of Hormuz between August 24 and August 25.
12. **[2026-08-27]** [development] conf=0.90 | [Iran Ceasefire Status 2026: Is the US-Iran War Over? Live Tracker](https://militaryspend.org/iran-ceasefire-status)  
   Qatar's Prime Minister visited Tehran on August 27 to discuss de-escalation.
13. **[2026-07-08]** [state_change] conf=0.95 BACKGROUND | [Islamabad Memorandum - Wikipedia](https://en.wikipedia.org/wiki/Islamabad_Memorandum)  
   Donald Trump indicated on July 8 that a memorandum of understanding with Iran was over after Iranian attacks on commercial vessels in the Strait of Hormuz.
</details>

### Federal Reserve interest rate decision August 2026

| Axis | Linkup | Brave |
|---|---|
| alpha_quality | 3 | 3 |
| freshness | 3 | 1 |
| fact_count | 1 | 0 |
| noise_free | 3 | 2 |
| topic_relevance | 3 | 3 |
| specificity | 3 | 3 |
| **TOTAL** | **16** | **12** |

**Winner:** linkup  |  **Finding:** Linkup successfully extracted the actual August 2026 decision event, whereas Brave returned only historical context and future schedules, missing the core current event.

**Linkup**: 4 alphas (3 fresh, 4 sourced) | collect 2.3s + extract 5.6s | High-quality, fresh, and specific facts regarding the August 24 decision, though the count of non-background facts is low.

**Brave**: 4 alphas (2 fresh, 4 sourced) | collect 1.3s + extract 5.6s | Facts are clean and specific but largely outdated (July) or future-scheduled (Sept/Oct), failing the freshness requirement for current news.

<details><summary>Linkup Alphas (4)</summary>

1. **[2026-08-24]** [state_change] conf=0.99 | [https://www.interactivecrypto.com/fed-funds-steady-amid-mixed-inflation-signals-and-market-jitters-ahead-of-jackson-hole-aug-2026](https://www.interactivecrypto.com/fed-funds-steady-amid-mixed-inflation-signals-and-market-jitters-ahead-of-jackson-hole-aug-2026)  
   The Federal Reserve held its benchmark interest rate steady at 3.5%–3.75% on August 24, 2026.
2. **[2026-08-24]** [development] conf=0.98 | [https://www.ahmedabadmirror.com/us-federal-reserve-holds-int-rates-steady/81918754.html](https://www.ahmedabadmirror.com/us-federal-reserve-holds-int-rates-steady/81918754.html)  
   The Federal Reserve voted 9 to 3 to hold its benchmark interest rate steady on August 24, 2026.
3. **[2026-08-24]** [development] conf=0.98 | [https://www.ahmedabadmirror.com/us-federal-reserve-holds-int-rates-steady/81918754.html](https://www.ahmedabadmirror.com/us-federal-reserve-holds-int-rates-steady/81918754.html)  
   Beth M Hammack, Neel Kashkari, and Lorie K Logan dissented from the Federal Reserve interest rate decision on August 24, 2026.
4. **[2026-08-24]** [state_change] conf=0.95 BACKGROUND | [https://saudipress.com/zmznmz-federal-reserve-holds-interest-rate-at-3-75-as-powell-faces-doj-criminal-investigation-during-2026-decision](https://saudipress.com/zmznmz-federal-reserve-holds-interest-rate-at-3-75-as-powell-faces-doj-criminal-investigation-during-2026-decision)  
   Jerome Powell is facing a Department of Justice criminal investigation regarding statements made to Congress about headquarters renovation costs.
</details>

<details><summary>Brave Alphas (4)</summary>

1. **[2026-07-31]** [state_change] conf=0.95 BACKGROUND | [United States Fed Funds Interest Rate](https://tradingeconomics.com/united-states/interest-rate)  
   The Federal Open Market Committee held the federal funds rate steady at 3.50%–3.75% for a fifth consecutive meeting in July 2026.
2. **[2026-09-16]** [routine] conf=1.00 | [Next FOMC Meeting: September 15–16, 2026 Countdown | FedRateCalc](https://fedratecalc.com/next-fomc-meeting/)  
   The Federal Reserve is scheduled to announce its next interest rate decision on Wednesday, September 16, 2026.
3. **[2026-10-07]** [routine] conf=1.00 | [FOMC Minutes Release Schedule 2026: Dates & Times | FedRateCalc](https://fedratecalc.com/fomc-minutes-release-schedule/)  
   Minutes from the September 15–16 FOMC meeting are scheduled for release on October 7, 2026 at 2:00 PM Eastern Time.
4. **[2026-08-19]** [routine] conf=1.00 BACKGROUND | [FOMC Minutes Release Schedule 2026: Dates & Times | FedRateCalc](https://fedratecalc.com/fomc-minutes-release-schedule/)  
   FOMC minutes from the previous meeting were released on August 19, 2026.
</details>

### EU AI Act enforcement 2026

| Axis | Linkup | Brave |
|---|---|
| alpha_quality | 3 | 3 |
| freshness | 0 | 0 |
| fact_count | 1 | 2 |
| noise_free | 2 | 2 |
| topic_relevance | 3 | 3 |
| specificity | 3 | 3 |
| **TOTAL** | **12** | **13** |

**Winner:** brave  |  **Finding:** Both providers failed the strict 7-day freshness window for this topic, but Brave provided a higher count of non-background facts (2 vs 1) and more granular details on specific enforcement actions.

**Linkup**: 5 alphas (3 fresh, 5 sourced) | collect 2.7s + extract 7.0s | Facts are clean and specific but all dates are older than 7 days, failing the freshness requirement.

**Brave**: 7 alphas (4 fresh, 7 sourced) | collect 1.4s + extract 7.0s | Facts are clean and specific but all dates are older than 7 days, failing the freshness requirement.

<details><summary>Linkup Alphas (5)</summary>

1. **[2026-08-02]** [state_change] conf=1.00 | [https://knowlearninghub.com/preparing-clients-for-eu-ai-act-enforcement/](https://knowlearninghub.com/preparing-clients-for-eu-ai-act-enforcement/)  
   EU AI Act enforcement began on August 2, 2026, marking the full enforcement of high-risk AI system obligations under Annex III and transparency requirements of Article 50.
2. **[2026-08-02]** [state_change] conf=1.00 | [https://knowlearninghub.com/preparing-clients-for-eu-ai-act-enforcement/](https://knowlearninghub.com/preparing-clients-for-eu-ai-act-enforcement/)  
   The European Commission's enforcement powers over general-purpose AI model providers became active on August 2, 2026.
3. **[2025-02-01]** [state_change] conf=1.00 BACKGROUND | [https://knowlearninghub.com/preparing-clients-for-eu-ai-act-enforcement/](https://knowlearninghub.com/preparing-clients-for-eu-ai-act-enforcement/)  
   Article 5 prohibitions against unacceptable AI practices went into effect in February 2025.
4. **[2025-08-01]** [state_change] conf=1.00 BACKGROUND | [https://knowlearninghub.com/preparing-clients-for-eu-ai-act-enforcement/](https://knowlearninghub.com/preparing-clients-for-eu-ai-act-enforcement/)  
   General-purpose AI obligations started in August 2025.
5. **[2026-08-02]** [state_change] conf=1.00 | [https://knowlearninghub.com/preparing-clients-for-eu-ai-act-enforcement/](https://knowlearninghub.com/preparing-clients-for-eu-ai-act-enforcement/)  
   High-risk rules under the EU AI Act were partially deferred to December 2, 2027, under the Digital Omnibus package.
</details>

<details><summary>Brave Alphas (7)</summary>

1. **[2026-08-02]** [state_change] conf=0.95 | [The enforcement framework of the AI Act | Shaping Europe’s digital future](https://digital-strategy.ec.europa.eu/en/policies/enforcement-ai-act)  
   The enforcement powers of the AI Office and national competent authorities of Member States became applicable on August 2, 2026.
2. **[2026-08-02]** [state_change] conf=0.95 | [EU AI Act: What Actually Applies on 2 August 2026 - Technology Org](https://www.technology.org/2026/07/17/eu-ai-act-what-actually-applies-on-2-august-2026/)  
   Article 50 general transparency requirements apply to any AI system placed on the EU market starting August 2, 2026.
3. **[2026-12-02]** [state_change] conf=0.95 | [The enforcement framework of the AI Act | Shaping Europe’s digital future](https://digital-strategy.ec.europa.eu/en/policies/enforcement-ai-act)  
   The prohibitions related to the generation or manipulation of non-consensual intimate material and child sexual abuse material apply from December 2, 2026.
4. **[2027-12-02]** [state_change] conf=0.95 BACKGROUND | [EU AI Act: What Actually Applies on 2 August 2026 - Technology Org](https://www.technology.org/2026/07/17/eu-ai-act-what-actually-applies-on-2-august-2026/)  
   The rules for high-risk AI systems listed in Annex III to the AI Act apply from December 2, 2027.
5. **[2028-08-02]** [state_change] conf=0.95 BACKGROUND | [EU AI Act Compliance Guide for Enterprises in 2026](https://www.solulab.com/eu-ai-act-compliance-checklist)  
   The rules for high-risk AI systems embedded into regulated products apply from August 2, 2028.
6. **[2026-07-27]** [state_change] conf=0.95 BACKGROUND | [Coding Model Ox Alpha Retains Every Prompt: You Cannot Name Company Holding Them](https://www.techtimes.com/articles/325244/20260823/coding-model-ox-alpha-retains-every-prompt-you-cannot-name-company-holding-them.htm)  
   EU Regulation 2026/1744, known as the Digital Omnibus on AI, entered into force on July 27, 2026.
7. **[2026-08-14]** [development] conf=0.90 | [EXCLUSIVE: EU orders leading AI labs to detail security practices | Euractiv](https://www.euractiv.com/news/exclusive-eu-orders-leading-ai-labs-to-detail-security-practices/)  
   EU enforcers asked more than 30 AI companies to detail how they comply with European copyright rules.
</details>

### Bitcoin price August 2026

| Axis | Linkup | Brave |
|---|---|
| alpha_quality | 3 | 3 |
| freshness | 2 | 2 |
| fact_count | 2 | 3 |
| noise_free | 3 | 2 |
| topic_relevance | 3 | 2 |
| specificity | 3 | 3 |
| **TOTAL** | **16** | **15** |

**Winner:** brave  |  **Finding:** Brave provided more fresh, high-confidence price points despite including some tangential noise, whereas Linkup was cleaner but had fewer recent data points.

**Linkup**: 4 alphas (4 fresh, 4 sourced) | collect 2.4s + extract 5.1s | Clean and specific facts, but only 3 of 4 fall within the last 7 days, limiting the fresh fact count.

**Brave**: 13 alphas (12 fresh, 13 sourced) | collect 1.3s + extract 8.2s | High specificity and fresh price data, but includes background noise (pizza) and tangential conference schedules.

<details><summary>Linkup Alphas (4)</summary>

1. **[2026-08-11]** [development] conf=0.95 | [https://isbitcoindead.com/bitcoin/current-price-of-bitcoin-for-august-11-2026/](https://isbitcoindead.com/bitcoin/current-price-of-bitcoin-for-august-11-2026/)  
   On August 11, 2026, Bitcoin was trading around $32,400.
2. **[2026-08-21]** [development] conf=0.95 | [https://fortune.com/article/price-of-bitcoin-08-21-2026/](https://fortune.com/article/price-of-bitcoin-08-21-2026/)  
   On August 21, 2026, Bitcoin surged to approximately $76,590.
3. **[2026-08-24]** [development] conf=0.95 | [https://fortune.com/article/price-of-bitcoin-08-25-2026/](https://fortune.com/article/price-of-bitcoin-08-25-2026/)  
   On August 24, 2026, Bitcoin prices reached near $78,976.
4. **[2026-08-26]** [development] conf=0.95 | [https://fortune.com/article/price-of-bitcoin-08-26-2026/](https://fortune.com/article/price-of-bitcoin-08-26-2026/)  
   On August 26, 2026, Bitcoin opened at $78,528 and rose to $78,585.
</details>

<details><summary>Brave Alphas (13)</summary>

1. **[2026-08-21]** [development] conf=1.00 | [Current price of Bitcoin for August 21, 2026](https://fortune.com/article/price-of-bitcoin-08-21-2026/)  
   The market price for a single Bitcoin was $76,712.47 at 8 a.m. Eastern Time on August 21, 2026.
2. **[2009-01-01]** [routine] conf=0.90 BACKGROUND | [Current price of Bitcoin for August 21, 2026](https://fortune.com/article/price-of-bitcoin-08-21-2026/)  
   Developer Laszlo Hanyecz famously spent 10,000 Bitcoins on pizza in the past.
3. **[2026-08-26]** [development] conf=1.00 | [Current price of Bitcoin for August 26, 2026](https://fortune.com/article/price-of-bitcoin-08-26-2026/)  
   At 7:15 a.m. Eastern Time on August 26, 2026, one Bitcoin was priced at $78,745.95.
4. **[2026-08-24]** [development] conf=1.00 | [Current price of Bitcoin for August 24, 2026](https://fortune.com/article/price-of-bitcoin-08-24-2026/)  
   At 9 a.m. Eastern Time on August 24, 2026, the price of one Bitcoin was $78,976.18.
5. **[2026-08-26]** [development] conf=0.95 | [What price will Bitcoin hit in August? Trading Odds & Predictions 2026 | Polymarket](https://polymarket.com/event/what-price-will-bitcoin-hit-in-august-2026)  
   Bitcoin traded around $78,700 on August 26, 2026, following a rally above $80,000.
6. **[2026-08-27]** [routine] conf=0.95 | [What price will Bitcoin hit in August? Trading Odds & Predictions 2026 | Polymarket](https://polymarket.com/event/what-price-will-bitcoin-hit-in-august-2026)  
   The Jackson Hole Symposium is scheduled for August 27-29, 2026.
7. **[2026-08-27]** [routine] conf=0.95 | [What price will Bitcoin hit in August? Trading Odds & Predictions 2026 | Polymarket](https://polymarket.com/event/what-price-will-bitcoin-hit-in-august-2026)  
   The Bitcoin Asia 2026 conference was scheduled for August 27-28 in Hong Kong.
8. **[2026-08-25]** [development] conf=1.00 | [Bitcoin and ethereum prices today, Tuesday, August 25, 2026: Highest opening for bitcoin in over three months](https://finance.yahoo.com/personal-finance/investing/article/bitcoin-and-ethereum-prices-today-tuesday-august-25-2026-highest-opening-for-bitcoin-in-over-three-months-123338376.html)  
   Bitcoin opened at $78,982.27 on Tuesday, August 25, 2026.
9. **[2026-08-25]** [development] conf=1.00 | [Bitcoin and ethereum prices today, Tuesday, August 25, 2026: Highest opening for bitcoin in over three months](https://finance.yahoo.com/personal-finance/investing/article/bitcoin-and-ethereum-prices-today-tuesday-august-25-2026-highest-opening-for-bitcoin-in-over-three-months-123338376.html)  
   Ethereum opened at $2,482.37 on Tuesday, August 25, 2026.
10. **[2026-08-26]** [development] conf=1.00 | [Bitcoin (BTC) Price Prediction: Daily, Weekly 2026 - 2040](https://coindcx.com/blog/price-predictions/bitcoin-price-weekly/)  
   Bitcoin was trading near $78,493 on August 26, 2026.
11. **[2026-08-24]** [development] conf=1.00 | [Bitcoin and ethereum prices today, Monday, August 24, 2026: Prices rising, as investors look for more Fed clues this week](https://finance.yahoo.com/personal-finance/investing/article/bitcoin-and-ethereum-prices-today-monday-august-24-2026-prices-rising-as-investors-look-for-more-fed-clues-this-week-130538704.html)  
   Ethereum opened at $2,463.09 on Monday, August 24, 2026.
12. **[2026-08-24]** [development] conf=1.00 | [Bitcoin and ethereum prices today, Monday, August 24, 2026: Prices rising, as investors look for more Fed clues this week](https://finance.yahoo.com/personal-finance/investing/article/bitcoin-and-ethereum-prices-today-monday-august-24-2026-prices-rising-as-investors-look-for-more-fed-clues-this-week-130538704.html)  
   Bitcoin opened at $77,727.62 on Monday, August 24, 2026.
13. **[2026-08-25]** [development] conf=1.00 | [Current price of Bitcoin for August 25, 2026](https://fortune.com/article/price-of-bitcoin-08-25-2026/)  
   At 8 a.m. Eastern Time on August 25, 2026, the price of Bitcoin was $79,111.64.
</details>

### Gaza ceasefire negotiations

| Axis | Linkup | Brave |
|---|---|
| alpha_quality | 3 | 3 |
| freshness | 0 | 2 |
| fact_count | 1 | 3 |
| noise_free | 3 | 3 |
| topic_relevance | 3 | 3 |
| specificity | 3 | 3 |
| **TOTAL** | **13** | **17** |

**Winner:** brave  |  **Finding:** Brave provided significantly fresher data with multiple events from the current week, whereas Linkup's results were entirely historical.

**Linkup**: 4 alphas (1 fresh, 4 sourced) | collect 2.8s + extract 5.8s | High quality and specific facts, but all are outdated (oldest 2025, newest 2026-06) with only one non-background fact.

**Brave**: 11 alphas (6 fresh, 11 sourced) | collect 1.4s + extract 7.7s | Contains 4 fresh facts from the last 7 days (2026-08-26) with high specificity and clean text, though one fact is from July.

<details><summary>Linkup Alphas (4)</summary>

1. **[2025-01-15]** [state_change] conf=0.95 BACKGROUND | [https://daysofpalestine.ps/gaza-on-the-brink-ceasefire-nears-collapse-as-israel-rejects-next-phase/](https://daysofpalestine.ps/gaza-on-the-brink-ceasefire-nears-collapse-as-israel-rejects-next-phase/)  
   Israeli and Hamas negotiators agreed to a six-week ceasefire deal featuring three phases in January 2025.
2. **[2025-12-31]** [escalation] conf=0.85 BACKGROUND | [https://daysofpalestine.ps/gaza-on-the-brink-ceasefire-nears-collapse-as-israel-rejects-next-phase/](https://daysofpalestine.ps/gaza-on-the-brink-ceasefire-nears-collapse-as-israel-rejects-next-phase/)  
   Israel violated the ceasefire nearly 600 times between October 2025 and December 2025.
3. **[2025-12-31]** [casualty] conf=0.90 BACKGROUND | [https://daysofpalestine.ps/gaza-on-the-brink-ceasefire-nears-collapse-as-israel-rejects-next-phase/](https://daysofpalestine.ps/gaza-on-the-brink-ceasefire-nears-collapse-as-israel-rejects-next-phase/)  
   Israeli military operations killed at least 356 Palestinians and injured over 900 people between October 2025 and December 2025.
4. **[2026-06-06]** [development] conf=0.95 | [https://egyptianstreets.com/2026/06/06/gaza-ceasefire-talks-resume-in-cairo/](https://egyptianstreets.com/2026/06/06/gaza-ceasefire-talks-resume-in-cairo/)  
   A new Hamas delegation arrived in Cairo for talks on advancing the ceasefire and discussing a transition to its next phase in June 2026.
</details>

<details><summary>Brave Alphas (11)</summary>

1. **[2026-08-26]** [escalation] conf=0.95 | [Board of Peace's Gaza envoy criticises Israeli strikes and Hamas actions](https://www.bbc.com/news/articles/cew92l07kwzo)  
   Nikolay Mladenov criticized Israel for its military attacks on the Palestinian territory.
2. **[2026-08-26]** [development] conf=0.95 | [Official leading Trump's Gaza ceasefire effort criticizes Israel for its attacks](https://apnews.com/article/us-un-israel-palestinians-board-peace-gaza-6847b6e1ee06c7be1c1525a9f99538ae)  
   Nikolay Mladenov stated to the U.N. Security Council that Trump's 20-point plan has moved from the negotiating table to the engineering table.
3. **[2024-05-31]** [state_change] conf=0.95 BACKGROUND | [Gaza war - Wikipedia](https://en.wikipedia.org/wiki/Gaza_war)  
   The United States announced a ceasefire framework on 31 May 2024.
4. **[2024-02-10]** [escalation] conf=0.95 BACKGROUND | [Gaza war - Wikipedia](https://en.wikipedia.org/wiki/Gaza_war)  
   Hamas suspended the release of Israeli hostages on 10 February.
5. **[2024-02-15]** [development] conf=0.95 BACKGROUND | [Gaza war - Wikipedia](https://en.wikipedia.org/wiki/Gaza_war)  
   Hamas resumed the release of hostages on 15 February.
6. **[2026-07-30]** [state_change] conf=0.95 BACKGROUND | [Israel-Hamas truce failure ‘point of no return’, envoy warns | Israel-Palestine conflict News | Al Jazeera](https://www.aljazeera.com/news/2026/8/26/israel-hamas-truce-failure-point-of-no-return-envoy-warns)  
   Donald Trump announced that the Board of Peace agreed to a deal with Hamas involving armed groups putting down their weapons.
7. **[2026-08-26]** [development] conf=0.90 | [Board of Peace's Gaza envoy criticises Israeli strikes and Hamas actions](https://www.bbc.com/news/articles/cew92l07kwzo)  
   Nickolay Mladenov and Benjamin Netanyahu agreed on a mechanism to resolve remaining questions during a meeting.
8. **[2026-08-26]** [tally] conf=0.90 BACKGROUND | [Board of Peace's Gaza envoy criticises Israeli strikes and Hamas actions](https://www.bbc.com/news/articles/cew92l07kwzo)  
   At least 1,303 Palestinians, including 300 children, were killed in Israeli attacks in Gaza since the US-brokered ceasefire began.
9. **[2026-08-28]** [escalation] conf=0.90 | [Israeli strikes kill 5 in Gaza, Iran touts Russian energy deal, and other news in the Middle East](https://apnews.com/article/middle-east-iran-israel-august-28-2026-6c8334dbec806f41666ff75e728768b8)  
   Israel has removed two Dutch diplomats from the ceasefire center.
10. **[2026-08-28]** [casualty] conf=0.95 | [Israeli strikes kill 5 in Gaza, Iran touts Russian energy deal, and other news in the Middle East](https://apnews.com/article/middle-east-iran-israel-august-28-2026-6c8334dbec806f41666ff75e728768b8)  
   Israeli airstrikes in Gaza killed five people.
11. **[2026-08-26]** [development] conf=0.90 | [UN envoy warns Gaza ceasefire plan could collapse as Israeli](https://egyptdailynews.com/un-envoy-warns-gaza-ceasefire-plan-could/)  
   Noa Furman stated that Israel continues to support Donald Trump's broader plan and cooperates to secure Hamas' disarmament.
</details>
