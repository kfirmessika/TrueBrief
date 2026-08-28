# Search Layer Benchmark: Iran war ceasefire negotiations
**Date:** 2026-08-27  |  **Judge model:** gemini-2.5-flash-lite

## Scores

| Axis | Gemini Grounding | Linkup | Brave News |
|---|---|---|---|
| lede_quality | 9 | 7 | 6 |
| completeness | 9 | 7 | 7 |
| source_quality | 9 | 8 | 8 |
| noise_level | 8 | 7 | 6 |
| **TOTAL** | **35** | **29** | **27** |

## Metadata

| | Gemini Grounding | Linkup | Brave News |
|---|---|---|---|
| Cost/call | ~$0.014 | ~$0.006 | ~$0.005 |
| Latency | 9.8s | 4.5s | 2.7s |
| Sources returned | 2 | 15 | 20 |
| Status | ✅ 9.8s  |  2 sources | ✅ 4.5s  |  15 sources | ✅ 2.7s  |  20 sources |

**Verdict:** Gemini is the best performer for this topic, offering the highest quality lede, completeness, and a clean output that directly maps to structured extraction. Its detailed reporting on the ceasefire suspension, Strait of Hormuz blockade, and specific details of previous agreements makes it the most valuable for a news intelligence product. Linkup is a decent second, providing a good overview but missing key details present in Gemini. Brave is the weakest due to its noisy output, lack of synthesis, and reliance on unverified date snippets, despite its lower cost.

**Paywall notes:** Brave's articles are from various sources and some may be paywalled, although the snippets provided do not explicitly indicate this. Linkup and Gemini appear to have broader access or summarize content in a way that avoids immediate paywall issues.

### Facts Gemini had that others missed

- Iran suspending ceasefire negotiations citing Israeli escalation in Lebanon.
- Iran announcing a renewed blockade of the Strait of Hormuz.
- Specific details on the Iran-Oman temporary shipping corridor deal.
- President Trump's conflicting statement on negotiations via Truth Social.
- Details about the specific "fighting while talking" strategy.

### Facts Linkup had that others missed

- Iran suspending ceasefire negotiations citing Israeli escalation in Lebanon.
- Iran announcing a renewed blockade of the Strait of Hormuz.
- President Trump's conflicting statement on negotiations via Truth Social.
- Israel reportedly taking control of Beaufort Castle in southern Lebanon.
- U.S. Treasury Department's expansion of sanctions to cover digital assets, technology, gold, aviation, and shipping.

### Facts Brave had that others missed

- Iran suspending ceasefire negotiations.
- Iran announcing a renewed blockade of the Strait of Hormuz.
- President Trump's conflicting statement on negotiations via Truth Social.
- Specific details on the Iran-Oman temporary shipping corridor deal.
- U.S. Treasury Department's expansion of sanctions to cover digital assets, technology, gold, aviation, and shipping.

## Gemini Grounding (V5 production) Output

```
**Iran Suspends Ceasefire Negotiations, Cites Israeli Escalation in Lebanon; Strait of Hormuz Blocked Again**

Iran has suspended its ceasefire negotiations with the United States, blaming Israel's escalating military actions in Lebanon. The Islamic Revolutionary Guard Corps also announced a renewed blockade of the Strait of Hormuz.

Here are the most significant other developments:

*   **Strait of Hormuz Blockade:** In addition to suspending peace talks, Iran has re-imposed a blockade on the Strait of Hormuz, an action that was to be lifted under a previous memorandum of understanding. Iran and Oman have agreed to a temporary shipping corridor in the strait, with Iran stating this deal would close the UN-authorized southern shipping corridor, which it opposes. However, Iran's Deputy Foreign Minister indicated the strait would not reopen to U.S. vessels until the U.S. fulfills its obligations under a June memorandum of understanding.
*   **Conflicting Statements on Negotiations:** While Iran announced the suspension of talks, President Trump stated on Truth Social that indirect negotiations were continuing at a "rapid pace." U.S. officials have previously described a pattern of striking Iranian targets, pausing, and then engaging in diplomatic dialogue, a strategy described as "fighting while talking."
*   **Escalation in Lebanon and Military Actions:** Iran cited Israel's "escalating military attacks in Lebanon" as the reason for suspending negotiations. Israel has reportedly taken control of Beaufort Castle in southern Lebanon, signifying advancement into the region.
*   **U.S. Economic Operations:** President Trump announced a "crushing economic operation" against Iran, described as "economic warfare." The U.S. Treasury Department has expanded sanctions to cover digital assets, technology, gold, aviation, and shipping.
*   **Previous Ceasefire and MOU:** A two-week ceasefire was initially agreed upon by the U.S. and Iran on April 7-8, 2026. This was followed by a 60-day interim deal mediated by Pakistan on June 14, 2026, which included reopening the Strait of Hormuz and a cessation of hostilities in Lebanon. However, both sides have accused each other of violating the terms of this agreement, and a comprehensive settlement remains uncertain. On August 18, 2026, discussions indicated that the memorandum of understanding's 60-day window was closing, with core disputes over Iran's nuclear program, the Strait of Hormuz, and sanctions relief unresolved.
```

**Sources (2):**

- [Iran war ceasefire negotiations latest news August 27 2026](google_search:Iran war ceasefire negotiations latest news August 27 2026)
- [Iran war ceasefire negotiations today](google_search:Iran war ceasefire negotiations today)

## Linkup Output

```
The U.S.-Iran ceasefire, which began over three months ago, is set to expire soon, with negotiations for a second round in Islamabad remaining uncertain. Iranian officials have refused to participate unless the U.S. lifts its naval blockade, and Tehran has rejected claims that the ceasefire was extended, arguing there was no formal start date. The 14-point memorandum of understanding includes commitments to reopen the Strait of Hormuz, release frozen Iranian assets worth $25 billion, and lift sanctions on Iranian oil trade. However, major disputes remain over Iran's nuclear program and the status of the original agreement. Iran's chief negotiator has warned of a "crushing" response if the U.S. resumes military action, while U.S. officials express cautious optimism about a possible deal. Regional tensions continue, with Israel and Iran exchanging fire and Hezbollah indicating Iran will support its activities.
```

**Sources (15):**

- [https://us.headtopics.com/news/iran-latest-new-negotiations-in-question-as-ceasefire-set-82486410](https://us.headtopics.com/news/iran-latest-new-negotiations-in-question-as-ceasefire-set-82486410)
- [https://sundayguardianlive.com/world/us-israel-iran-war-latest-news-global-leaders-from-germany-australia-japan-more-hail-new-us-iran-ceasefire-agreement-207289/](https://sundayguardianlive.com/world/us-israel-iran-war-latest-news-global-leaders-from-germany-australia-japan-more-hail-new-us-iran-ceasefire-agreement-207289/)
- [https://us.headtopics.com/news/iran-war-latest-ceasefire-appears-to-hold-after-us-strikes-83160424](https://us.headtopics.com/news/iran-war-latest-ceasefire-appears-to-hold-after-us-strikes-83160424)
- [https://sundayguardianlive.com/world/us-israel-iran-war-latest-live-news-nothing-to-extend-tehran-says-deal-had-no-start-date-as-mediators-struggle-to-revive-us-iran-negotiations-259696/](https://sundayguardianlive.com/world/us-israel-iran-war-latest-live-news-nothing-to-extend-tehran-says-deal-had-no-start-date-as-mediators-struggle-to-revive-us-iran-negotiations-259696/)
- [https://www.israelnationalnews.com/news/425744](https://www.israelnationalnews.com/news/425744)
- [https://sundayguardianlive.com/world/us-israel-iran-war-latest-live-news-iran-ceasefire-may-be-announced-soon-today-or-tomorrow-says-us-treasury-chief-as-middle-east-tensions-persist-255974/](https://sundayguardianlive.com/world/us-israel-iran-war-latest-live-news-iran-ceasefire-may-be-announced-soon-today-or-tomorrow-says-us-treasury-chief-as-middle-east-tensions-persist-255974/)
- [https://abcnews4.com/news/nation-world/us-iran-ceasefire-talks-loom-islamabad-pakistan-as-israel-opens-separate-lebanon-negotiations-hezbollah-netanyahu-president-trump-jd-vance-nuclear-weapons-uranium-strait-of-hormuz-gas-oil-prices](https://abcnews4.com/news/nation-world/us-iran-ceasefire-talks-loom-islamabad-pakistan-as-israel-opens-separate-lebanon-negotiations-hezbollah-netanyahu-president-trump-jd-vance-nuclear-weapons-uranium-strait-of-hormuz-gas-oil-prices)
- [https://us.headtopics.com/news/iran-latest-iran-israel-stand-down-after-first-major-84304275](https://us.headtopics.com/news/iran-latest-iran-israel-stand-down-after-first-major-84304275)
- [https://english.mathrubhumi.com/news/world/us-iran-talks-possible-breakthrough-middle-east-war-ceasefire-negotiations-fvdkl2s2](https://english.mathrubhumi.com/news/world/us-iran-talks-possible-breakthrough-middle-east-war-ceasefire-negotiations-fvdkl2s2)
- [https://www.ifi.today/govern/1951-U-S-and-Iran-Agree-to-Renew-Talks-and-Ceasefire-After-the-Latest-Escalation.html](https://www.ifi.today/govern/1951-U-S-and-Iran-Agree-to-Renew-Talks-and-Ceasefire-After-the-Latest-Escalation.html)
- [https://sundayguardianlive.com/world/us-israel-iran-war-latest-news-un-chief-antonio-guterres-welcomes-peace-deal-ending-107-day-war-calls-it-a-critical-step-toward-lasting-ceasefire-reopening-of-strait-of-hormuz-207340/](https://sundayguardianlive.com/world/us-israel-iran-war-latest-news-un-chief-antonio-guterres-welcomes-peace-deal-ending-107-day-war-calls-it-a-critical-step-toward-lasting-ceasefire-reopening-of-strait-of-hormuz-207340/)
- [https://www.opindia.com/news-updates/iran-rejects-us-ceasefire-offer-demands-permanent-end-to-regional-war/](https://www.opindia.com/news-updates/iran-rejects-us-ceasefire-offer-demands-permanent-end-to-regional-war/)
- [https://sundayguardianlive.com/world/us-iran-war-latest-news-why-did-donald-trump-suddenly-halt-us-envoys-pakistan-visit-after-iran-diplomat-left-islamabad-amid-ceasefire-efforts-186506/](https://sundayguardianlive.com/world/us-iran-war-latest-news-why-did-donald-trump-suddenly-halt-us-envoys-pakistan-visit-after-iran-diplomat-left-islamabad-amid-ceasefire-efforts-186506/)
- [https://politicstoday.org/iran-reviews-ceasefire-proposal-amid-conflicting-signals-from-washington/](https://politicstoday.org/iran-reviews-ceasefire-proposal-amid-conflicting-signals-from-washington/)
- [https://www.nationofchange.org/topics/ceasefire-negotiations/](https://www.nationofchange.org/topics/ceasefire-negotiations/)

## Brave News Search Output

```
- [2026-08-25] Iran war updates: Trump says US ‘not in a hurry’ over talks with Tehran | US-Israel war on Iran News | Al Jazeera: These were the updates on the US-Israel war on Iran, as well as Israel's attacks on Gaza, Lebanon, from August 26, 2026.
- [2026-08-24] Iran war updates: Tehran says Oman deal on Hormuz does not mean strait open | Donald Trump News | Al Jazeera: These were the updates on the US-Israel war on Iran from Tuesday, August 25, 2026.
- [2026-08-26] Iran War Updates: Tehran engages in renewed diplomatic push, touts proposal to reopen Strait of Hormuz: As U.S. economic pressure bites, Iran touts a plan with Oman to get ships moving through the Strait of Hormuz and suggests the next move is Trump's.
- [2026-08-25] Can Trump's economic war against Iran do what airstrikes and negotiations couldn't?: What a new round of U.S. sanctions could mean after nearly six months of war with Iran — and years of economic pressure on the country.
- [2026-08-26] August 26, 2026 – Iran war latest | CNN: US president claims the financial strength of the US will move the country “toward a very big victory” over Iran, adding that he does not believe Iran’s supreme leader is dead.
- [2026-08-24] U.S. to unveil 'greatest financial offensive' against Iran as Tehran threatens ship seizures: The escalation came as both sides have missed a 60-day ceasefire window to reach a deal, closing off the formal truce mechanism to end the six-month war.
- [2026-08-21] Iranian president says time to end war with US from ‘position of strength’ | US-Israel war on Iran News | Al Jazeera: Omani and Iranian foreign ministers hold a call as Washington prepares economic sanctions.
- [2026-08-23] Iran’s foreign minister calls threat of new US economic sanctions ‘desperate’ | US-Israel war on Iran | The Guardian: Rezaei also claimed Iran had more ... around Iran and elsewhere, and we will strike them,” he said in the interview, which was broadcast on Saturday. Trump’s efforts to finish the war he started along with Israel on 28 February have foundered after a ceasefire agreement ...
- [2026-08-25] Iran and Oman Hold Talks on Managing the Strait of Hormuz and Other News From Around the Middle East: The top diplomats of Iran and Oman met Tuesday to discuss a phased approach to managing ship traffic through the the Strait of Hormuz, which remains largely shut down nearly six months after the Iran war began.
- [2026-08-21] Iran updates: Tehran says US sanctions ‘declaration of war’ on all nations | Business and Economy News | Al Jazeera: These were the updates on 22 August 2026 · This live page has now been closed. You can continue to follow our coverage here
- [2026-08-23] Iran's president says U.S. memorandum is best path out of stalled war, and other Middle East news | PBS News: The new head of Iran's top security body warned Sunday that Tehran will see any country's support for new U.S. economic measures against the Islamic Republic as an “act of war,” while Iran's president defended a memorandum of understanding with the U.S. as the best way out of the stalled ...
- [2026-08-26] Six Months Into the Iran War, the United States Has No Good Options | Council on Foreign Relations: Operation Epic Fury failed to produce the quick victory that President Donald Trump predicted and may be remaking the political order in the Middle East.
- [2026-08-23] Can Iran retaliate against countries that join US ‘economic war’? | US-Israel war on Iran News | Al Jazeera: Iran warns that countries backing US economic sanctions will be considered an enemy of Tehran.
- [2026-08-26] US Iran War News Live Updates: US says no talks with Iran under way, ‘all options’ on table - The Times of India: A Gulf neighbour of Iran and a US ally, Qatar has served as a back-channel ​negotiator for the warring parties and played a direct role in securing the June ceasefire that briefly led to a cessation of hostilities.
- [2026-08-25] Finding an Offramp for the War in Iran | RealClearWorld: The war between the U.S. and Iran has now passed the five-month mark, and there is still no end in sight. The White House and the media have repeatedly teased imminent ceasefire agreements, only for it to become clear within days that the cycle of negotiation and conflict is returning directly ...
- [2026-08-24] Iran warns of harsh response as US announces new sanctions and other Middle East news | AP News: Israel says it targets Palestinian ... that sparked the war. Israel has announced targeted strikes on six of the seven days since U.S. negotiator Jared Kushner’s meeting with Israeli Prime Minister Benjamin Netanyahu last week hoping to push the ceasefire deal forwa...
- [2026-08-23] Iran official says support for new sanctions would be an 'act of war,' and other Middle East news - The Washington Post: The head of Iran’s top security body says Tehran will see any country’s support for new U_S_ economic measures against the Islamic Republic as an “act of war.”
- [2026-08-26] The Kremlin Says the CIA Director Held Talks in Moscow With His Intelligence Counterparts: Efforts to negotiate a peace deal have largely stalled, with U.S. attention turning to its war with Iran and both Moscow and Kyiv stepping up their long-range attacks on each other. Putin has rejected Ukrainian President Volodymyr Zelenskyy's push for an immediate ceasefire, arguing that Russia ...
- [2026-08-20] Top Iran official says U.S. focus on economic warfare shows it has failed militarily : NPR: The Iranian regime has dismissed President Trump's threats to crush Iran economically, saying that years of U.S. sanctions have failed.
- [2026-08-25] China hits out at 'illegal' new US sanctions on Iran and trading partners: The US has threatened to isolate nations that continue to do business with Tehran, which sells much of its oil to Beijing.
```

**Sources (20):**

- [Iran war updates: Trump says US ‘not in a hurry’ over talks with Tehran | US-Israel war on Iran News | Al Jazeera](https://www.aljazeera.com/news/liveblog/2026/8/26/iran-war-live-iran-says-hormuz-remains-closed-despite-oman-rout-deal)
- [Iran war updates: Tehran says Oman deal on Hormuz does not mean strait open | Donald Trump News | Al Jazeera](https://aljazeera.com/news/liveblog/2026/8/25/iran-war-live-drat)
- [Iran War Updates: Tehran engages in renewed diplomatic push, touts proposal to reopen Strait of Hormuz](https://cbsnews.com/live-updates/iran-war-us-strait-of-hormuz-sanctions)
- [Can Trump's economic war against Iran do what airstrikes and negotiations couldn't?](https://npr.org/2026/08/25/nx-s1-5943572/trump-iran-sanctions)
- [August 26, 2026 – Iran war latest | CNN](https://cnn.com/2026/08/26/world/live-news/iran-war-trump)
- [U.S. to unveil 'greatest financial offensive' against Iran as Tehran threatens ship seizures](https://cnbc.com/2026/08/24/us-iran-war-trump-hormuz-bessent-economic-sanctions-.html)
- [Iranian president says time to end war with US from ‘position of strength’ | US-Israel war on Iran News | Al Jazeera](https://www.aljazeera.com/news/2026/8/22/iranian-president-says-time-to-end-war-with-us-from-position-of)
- [Iran’s foreign minister calls threat of new US economic sanctions ‘desperate’ | US-Israel war on Iran | The Guardian](https://www.theguardian.com/world/2026/aug/23/iran-new-security-chief-trump-economic-war-enemies-mohsen-rezaei)
- [Iran and Oman Hold Talks on Managing the Strait of Hormuz and Other News From Around the Middle East](https://www.usnews.com/news/world/articles/2026-08-25/ship-disabled-by-attack-in-strait-of-hormuz-and-other-news-from-around-the-middle-east)
- [Iran updates: Tehran says US sanctions ‘declaration of war’ on all nations | Business and Economy News | Al Jazeera](https://www.aljazeera.com/news/liveblog/2026/8/22/iran-war-live-trump-says-tehran-not-ready-to-make-right-deal-to-end-war)
- [Iran's president says U.S. memorandum is best path out of stalled war, and other Middle East news | PBS News](https://www.pbs.org/newshour/world/irans-president-says-u-s-memorandum-is-best-path-out-of-stalled-war-and-other-middle-east-news)
- [Six Months Into the Iran War, the United States Has No Good Options | Council on Foreign Relations](https://cfr.org/articles/six-months-into-the-iran-war-the-united-states-has-no-good-options)
- [Can Iran retaliate against countries that join US ‘economic war’? | US-Israel war on Iran News | Al Jazeera](https://aljazeera.com/news/2026/8/23/can-iran-retaliate-against-countries-that-join-us-economic-war)
- [US Iran War News Live Updates: US says no talks with Iran under way, ‘all options’ on table - The Times of India](https://timesofindia.indiatimes.com/world/middle-east/us-iran-war-news-live-updates-donald-trump-warning-strait-of-hormuz-mines-cleared-middle-east-conflict-barron-trump-tehran-latest-news/liveblog/133527138.cms)
- [Finding an Offramp for the War in Iran | RealClearWorld](https://www.realclearworld.com/articles/2026/08/25/finding_an_offramp_for_the_war_in_iran_1202279.html)
- [Iran warns of harsh response as US announces new sanctions and other Middle East news | AP News](https://apnews.com/article/middle-east-iran-israel-syria-august-24-2026-4c37df8a725b49eae2ab1672b4ae4201)
- [Iran official says support for new sanctions would be an 'act of war,' and other Middle East news - The Washington Post](https://www.washingtonpost.com/national/2026/08/23/middle-east-iran-israel-west-bank-august-23-2026/addffcce-9ec9-11f1-9cc4-2dc9b46e2d5c_story.html)
- [The Kremlin Says the CIA Director Held Talks in Moscow With His Intelligence Counterparts](https://www.usnews.com/news/world/articles/2026-08-26/the-kremlin-says-the-cia-director-held-talks-in-moscow-with-his-intelligence-counterparts)
- [Top Iran official says U.S. focus on economic warfare shows it has failed militarily : NPR](https://npr.org/2026/08/21/nx-s1-5940610/iran-us-threat-economic-warfare)
- [China hits out at 'illegal' new US sanctions on Iran and trading partners](https://bbc.com/news/articles/clyl8965j5go)
