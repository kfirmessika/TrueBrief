# Benchmark: Iran War ceasefire deal
**Date:** 2026-06-21  |  **Models:** pipeline=gemini-2.5-flash-lite, judge=gemini-2.5-flash-lite

## Scores

| Axis | Ours | Reference |
|---|---|---|
| lede_quality | 7 | 9 |
| completeness | 8 | 9 |
| synthesis | 9 | 7 |
| noise_level | 7 | 8 |
| **TOTAL** | **31** | **33** |

**Verdict:** Brief B wins by a small margin due to its clearer lede and slightly better completeness, though Brief A offers a superior synthesis of the current state of play.

## Gaps in TrueBrief

- US-Iran talks in Switzerland are aimed at implementing their interim agreement to halt the war.
- US Central Command disputes Iran's claim about the Strait of Hormuz closure, stating traffic continues to flow.
- An emergency session on the Israel-Hezbollah conflict has been added to the Switzerland peace talks.
- Pakistan is playing a mediating role in the implementation of the US-Iran agreement, with Prime Minister Shehbaz Sharif and Army Chief Asim Munir attending the technical-level talks in Switzerland.
- The interim deal signed on June 17, 2026, included a cessation of hostilities on all fronts, an end to Iranian restrictions on the Strait of Hormuz, and a reduction of US military assets from the region, with a 60-day timeline for an agreement on Iran's nuclear program.
- The war began on February 28, 2026, with US-Israeli airstrikes targeting Iranian military and government sites, which resulted in the assassination of Supreme Leader Ali Khamenei. Iran retaliated with missile and drone strikes across the region, effectively blocking the Strait of Hormuz.

## False Positives in TrueBrief

- The Strait of Hormuz Authority will waive transit fees for ships for the next 60 days as part of the implementation of the broader U.S.-Iran deal.

## TrueBrief Output

```
STATE OF PLAY
Ceasefire negotiations between the United States and Iran are set to resume in Switzerland, despite persistent hostilities and the Iranian closure of the Strait of Hormuz. While multiple ceasefire agreements exist, ongoing military actions in Lebanon and drone launches indicate a highly volatile environment.
  - [postponed] U.S.-Iran Negotiations — Next phase of talks scheduled June 21, 2026.
  - [contested] Israel-Hezbollah Ceasefire — Violated by ongoing air strikes and drone launches.
  - [escalating] Strait of Hormuz — Closure announced by Iranian military June 20.
  - [contested] U.S.-Iran Interim Deal — Fragile deal signed June 18.

📋 TrueBrief | Iran-Israel Conflict Ceasefire | June 21, 2026

**📌 Bottom line:** The Iranian military has closed the Strait of Hormuz in response to the collapse of the recent U.S.-Iran ceasefire deal and escalating hostilities in Lebanon.

🆕 NEW STORIES (11)
━━━━━━━━━━━━━━━━━━━━━━━━━━
**Strait of Hormuz Closure**
• The Iranian military ordered the closure of the Strait of Hormuz, a critical escalation stemming from the breakdown of the U.S.-Iran peace framework and ongoing regional tensions. → Sources: [bbc.com](https://www.bbc.com/news/articles/cwyekkwm1mmo?at_medium=RSS&at_campaign=rss)

**Diplomatic Frameworks**
• President Trump and the United States have established an interim agreement with Iran, serving as the central, albeit fragile, mechanism for managing regional stability. → Sources: [nytimes.com](https://www.nytimes.com/2026/06/20/world/middleeast/israel-hezbollah-fighting-cease-fire.html), [nytimes.com](https://www.nytimes.com/2026/06/20/world/europe/world-iran-reaction.html)
• The U.S. and Iran signed an initial war-ending agreement covering Lebanon, which remains the primary site for monitoring the deal's viability (5 sources). → Sources: [bbc.com](https://www.bbc.com/news/articles/cwyekkwm1mmo?at_medium=RSS&at_campaign=rss), [nytimes.com](https://www.nytimes.com/2026/06/20/world/middleeast/israel-hezbollah-fighting-cease-fire.html)

**Ceasefire and Military Engagement**
• Israel and Hezbollah entered a mediated ceasefire on June 19, though both parties subsequently breached the agreement with Israeli air strikes and Hezbollah drone launches (4 sources). → Sources: [bbc.com](https://www.bbc.com/news/articles/cwyekkwm1mmo?at_medium=RSS&at_campaign=rss), [usatoday.com](https://www.usatoday.com/story/news/world/2026/06/19/iran-war-trump-peace-us-updates--live/90615139007/), [axios.com](https://www.axios.com/2026/06/19/israel-hezbollah-ceasefire-iran-talks), [politico.com](https://www.politico.com/news/2026/06/19/israel-and-hezbollah-agree-to-renew-their-ceasefire-officials-say-00968751)
• The IDF conducted over 150 strikes on Saturday, hitting 80 Hezbollah targets and killing dozens of militants, while Hezbollah remains engaged in active hostilities (4 sources). → Sources: [bbc.com](https://www.bbc.com/news/articles/cwyekkwm1mmo?at_medium=RSS&at_campaign=rss), [nbcnews.com](https://www.nbcnews.com/world/iran/us-iran-talks-postponed-vance-cancels-trip-israel-strikes-lebanon-rcna350830)
• Israel has published maps indicating an expanded military control zone in southern Lebanon, which conflicts with territorial sovereignty terms defined in the U.S.-Iran memorandum. → Sources: [nbcnews.com](https://www.nbcnews.com/world/iran/us-iran-talks-postponed-vance-cancels-trip-israel-strikes-lebanon-rcna350830)

**Diplomatic Stagnation**
• High-level talks in Switzerland, previously involving Vice President JD Vance and Iranian delegates, were postponed due to the ongoing violence in Lebanon (5 sources). → Sources: [politico.com](https://www.politico.com/news/2026/06/19/israel-and-hezbollah-agree-to-renew-their-ceasefire-officials-say-00968751), [nytimes.com](https://www.nytimes.com/live/2026/06/21/world/iran-us-trump-lebanon), [usatoday.com](https://www.usatoday.com/story/news/world/2026/06/19/iran-war-trump-peace-us-updates--live/90615139007/), [axios.com](https://www.axios.com/2026/06/19/israel-hezbollah-ceasefire-iran-talks), [nbcnews.com](https://www.nbcnews.com/world/iran/us-iran-talks-postponed-vance-cancels-trip-israel-strikes-lebanon-rcna350830)
• Iranian officials maintain that all military operations in Lebanon must cease as a prerequisite for resuming diplomatic negotiations. → Sources: [politico.com](https://www.politico.com/news/2026/06/19/israel-and-hezbollah-agree-to-renew-their-ceasefire-officials-say-00968751)
• Tehran formally accused Israel of violating the U.S.-Iran Memorandum of Understanding via ongoing strikes. → Sources: [axios.com](https://www.axios.com/2026/06/19/israel-hezbollah-ceasefire-iran-talks)
• The Strait of Hormuz Authority will waive transit fees for ships for the next 60 days as part of the implementation of the broader U.S.-Iran deal. → Sources: [nbcnews.com](https://www.nbcnews.com/world/iran/us-iran-talks-postponed-vance-cancels-trip-israel-strikes-lebanon-rcna350830)

**Humanitarian and Casualty Data**
• The conflict in Lebanon has resulted in at least 47 deaths since Friday and the injury of civilians such as Mona Khalil, while at least 4,057 people have died since the broader conflict resumed in March. → Sources: [bbc.com](https://www.bbc.com/news/articles/cwyekkwm1mmo?at_medium=RSS&at_campaign=rss), [nbcnews.com](https://www.nbcnews.com/world/iran/us-iran-talks-postponed-vance-cancels-trip-israel-strikes-lebanon-rcna350830)
• Despite the humanitarian benefits seen in Gaza—where food insecurity among households dropped from 92% to 36% since the October 2025 ceasefire—Israel continues to consolidate control over 70% of the territory. → Sources: [bbc.com](https://www.bbc.com/news/articles/c4gy26p6pwzo?at_medium=RSS&at_campaign=rss)
```

## Reference Output (Gemini Search)

```
As of June 21, 2026, the most significant current development is the commencement of US-Iran talks in Switzerland aimed at implementing their interim agreement to halt the war.

Here are other significant developments:

*   **Strait of Hormuz Closure and Disputes:** Iran announced on Saturday, June 20, 2026, that it had closed the Strait of Hormuz again, citing alleged violations of the memorandum of understanding by Israel and its failure to withdraw troops from southern Lebanon. The US, however, disputes Iran's claim, with US Central Command stating that traffic continues to flow and that US forces are monitoring the situation.
*   **Lebanon Ceasefire and Tensions:** A ceasefire agreement between Israel and Hezbollah, brokered by the US and regional countries, was reached on Friday, June 19, 2026. However, tensions remain, with Israel carrying out strikes in southern Lebanon on Saturday, June 20, and Hezbollah stating its right to respond. An emergency session on the Israel-Hezbollah conflict has been added to the Switzerland peace talks.
*   **US-Iran Negotiations Focus:** US Vice President JD Vance, part of the US delegation in Switzerland, stated that the talks would focus on Iran's nuclear program and the Lebanon ceasefire, calling these two issues "big things".
*   **Pakistan's Role:** Pakistan is playing a mediating role in the implementation of the US-Iran agreement, with Prime Minister Shehbaz Sharif and Army Chief Asim Munir attending the technical-level talks in Switzerland.
*   **Previous Ceasefire Agreement:** An interim deal to end the war was signed on June 17, 2026, by US President Donald Trump and Iran's President Masoud Pezeshkian. This deal included the cessation of hostilities on all fronts, an end to Iranian restrictions on the Strait of Hormuz, and a reduction of US military assets from the region, with a 60-day timeline for an agreement on Iran's nuclear program.
*   **Background to the Conflict:** The war began on February 28, 2026, with US-Israeli airstrikes targeting Iranian military and government sites, which resulted in the assassination of Supreme Leader Ali Khamenei. Iran retaliated with missile and drone strikes across the region, effectively blocking the Strait of Hormuz.
```

## Reference Sources

- [cbsnews.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGOKoCp0eW0mDWG-ROT_v9fGIeXulkVnGSRx2Se7mWoDtMfwkcwZssQLboSJyVjeKMbNXmDrNYQ1WZID6LCA8RmhFif87s17PYFz8qEy9QjVznOhacmdO9NWAgSRtDdY43T4pFo_pmuDAg4J664oeoS6ge5HclFtfw3Or34JoUDTl7SMRYHrTJ3mXrmZPioMmsgzeHjy1jBbj8mXkiRhtH-RN0vboZmtIg=)
- [timesofisrael.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHtW-DR4J7IyeTFdrrzD_MH9g4qJpiqH4_GfwBLeMV5YJ4uKyVVqn0GuW3e4tyuKMwoOpmzT9XYp28WMczphsBdtY_MdwVKJxc5EhJmixMg20DzKizcZ_HdQqM8ATKmbKvgSMeSy7G0ZUNCGptnq8R-A0TzQ5fFrJ8WGPFQx4PMNWLza-O6pCFT7V9Gbh_zgUDdu5L2WDGbKokIB_3PQg6YZh9troXi1kVMhjbN98jluekT5hx3)
- [ndtv.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEJ9Lf-4L5ennc4qGw2W-kWGbWqTZBYOheNqjA8T6fVsvDWEDcj_7y6Ea04vmCQQ7h0ni7uBvGV-48b6DxYvw8FLacFVl8xDlIeLwEb2CSSnBzSZ8syku489hWcu_vMB2UhkKg5hanzIzlEthXsiQlTmdilIAdWNpCsSiVfbBfD9f35qW7cerpgfu_IyPIZhkHGGX1G6Od5z-fPFgo8TEA9JEnslMD7FBJBmeVkLSUnGhmrINPfFgT1ElTdscbZcrAjrg35JsxP-M4-pbedpA==)
- [thehindu.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG_on0upEGizk63_vxCOfIj7KgyeU1-w1oOP-NJ5mw2wmJ7A1UWRyNpsMzVuCLsIN9VocpeRTNo5zefR0_cVB1yVgSLTFQ7Wz2fxIuZXcvJV_VYF0uHOrAuE7lFa5HD7G2bfremG8yq2xy_oNnrTlUVO5eLSnyN7ks3jyrXGJB8nTR0ZUMPZp7qMLlfynZp7p8SQpsMPfsKrNQ8646vu_cl9fP8Yqzr7gyYU22yXOR8IzhQZZh_Jl4crLzHVCWxjFfgtNGE9KH6ZEPqM8m9hQfKR86AdH2JTdtzJoGgLpAoikI3xV1ffikkasq6FGmzVaovi_6JxOsBbQge5qkOV4rQszOOAPWqHPlc)
- [aljazeera.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEiRQqDjfZ8R-rF3nCFKgvh4aBG0G7uuzeQEtAxVOT5iWTznwLuO3SIDtyX0R4bxXs_enWQ74btmhllwvI_AXs-2nzpErHxNeSqvC4Dp0AdqRWVjmzyi-b9xMkehYOg8Ys=)
- [timesleaderonline.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF14fZYwZwUTX_-E3uRVMkjW0PX-1mVjllyfDwXfWFvYgBUCtZCN2SNndMnDIb2n2JrVIOBAP-PgA4KZ7GUzm5vWgJG53tV6DN9WufcdYB9CVwPiqw5dP0ZidxTJTtexb7hQGI1kaXn3ENUfKac6tEbT1003Sqwa0eqSHwUjatlFFkYkBpmJqeVbeInEoq1Ii5sgunzey3eGgusmZGD4Caunbo_kEcaS_k26JP9iS8cCb3sqfucnc6q1hTC5CUZM68su-eBLnNXc2oESXeVlalV)
- [thehindu.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG5ZUsqgzXBh4KYykeW5y2CxO_PthzDt8t63Vsf42IPw360YmhAm0gWuOd9WKM5VKdQIrQXaneZVW2O_tp0p9yOCJduU2SWXZPMyviZmJw1sKbZ-5fXrYuDJB4mcrqUbkb-pJXcv39pihKiIyIpXjqCf4E2HjfdzCtF5cjgkHBo7eFR-vMEqX4a63W3ihPf3lwgcEt4rYIt9Wjvnf5Oe0C7DpRc9TxwFa4=)
- [britannica.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHOizJcEVFZFjUjRxoLwaXj3W32TkoK_1Su76IZRtfftiaVUb0PGecZ6BcEKRLNRlrfEF-xa_TViEJz2ugEd5qHBFF0seM9Xo9azrQhvyiMhbGfX-n2i15y_Z9vtPLPdWyDh7piuKQxmXw=)
- [wikipedia.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHAGh8ntYAzM61lEuWgwX0iv3XVeWGp5se0uu34q98ZDDeX-mD2z-Odg4nAys4EJvhVvFhuZtmlBcVkYlWfdQ7Sd25vbFvyP6IBbBp6par5F0d_kb4XSwQKOEgw3XwjSu27p1wVsTY=)
- [aa.com.tr](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHVG1h1SwlOmvgzva0HvLxz5IO5cGSgiZUn0q2Zw9peSPeLD9aRUyt_PN69lAT4jiV7cSmC9RcLO5bViqIpzQ6pSSLAuuTSwk_dlBrUBea8BGNu-QfAD-9XsSi5GYcoMECt6Na8x5ZEpYSS4Cs4HP-oMMvmstaQLaEZg-Dq6kg9M45P7oWA67x5_nNDR5fSFqBWYQmt72MI6dkBeZWCIa9mOXU1xsV-_GxJUc2ucfQ=)
