# Benchmark: Iran War ceasefire deal
**Date:** 2026-07-05  |  **Models:** pipeline=gemini-2.5-flash-lite, judge=gemini-2.5-flash-lite

## Scores

| Axis | Ours | Reference |
|---|---|---|
| lede_quality ⚠️ | 2 | 9 |
| completeness ⚠️ | 7 | 10 |
| synthesis ⚠️ | 3 | 9 |
| noise_level ⚠️ | 5 | 8 |
| **TOTAL** | **17** | **36** |

**Verdict:** Brief B wins by a significant margin because it accurately captures the most important current development regarding the Iran War ceasefire deal and provides essential context, while Brief A is misleading and focuses on tangential peace deals.

## Gaps in TrueBrief

- Strait of Hormuz Flashpoint and ongoing tension testing the MOU
- Specific recent hostilities in the Strait of Hormuz on June 25 and subsequent exchange of fire
- US-Iran talks paused due to funeral procession for Ayatollah Ali Khamenei
- Details of the June 17 MOU: signed by Trump and Pezeshkian, 60-day timeline, nuclear program, reaffirmation not to pursue nuclear weapons
- Previous ceasefire efforts: April 8 initial ceasefire, April 21 extension, June 12 new conditions
- Iran's post-war stance: regime emboldened, new generation of leaders considered savvier and more hard-line

## False Positives in TrueBrief

- Israel and Lebanon signed a peace deal brokered by the United States.
- Israel and Lebanon signed a framework agreement following US-mediated talks.
- The government of Lebanon, Israel, and the United States signed a trilateral peace deal in Washington.
- Hezbollah officially rejected the ceasefire agreement between Israel and Lebanon.
- The United States government acknowledged Iran's involvement in Lebanon.

## TrueBrief Output

```
📋 TrueBrief | Iran Ceasefire Negotiations | July 05, 2026

**📌 Bottom line:** Israel and Lebanon signed a peace deal brokered by the United States.

🆕 NEW STORIES (19)
━━━━━━━━━━━━━━━━━━━━━━━━━━
• Israel and Lebanon signed a peace deal brokered by the United States. → Sources: [military.com](https://www.military.com/lebanon-israel-pact-fragile-after-hezbollahs-vow-of-disruption)
• Israel and Lebanon signed a framework agreement following US-mediated talks. → Sources: [jpost.com](https://www.jpost.com/middle-east/article-900731)
• Iranian forces conducted strikes on two US military bases. → Sources: [easternherald.com](https://easternherald.com/2026/07/03/iran-ever-lovely-kiku-bahrain-kuwait-june-2026-ceasefire-exchange)
• The United States and Iran signed a memorandum of understanding. → Sources: [jpost.com](https://www.jpost.com/israel-news/defense-news/article-900741)
• The government of Lebanon, Israel, and the United States signed a trilateral peace deal in Washington. → Sources: [ft.com](https://www.ft.com/content/a00c2606-330d-4192-94f5-caf6ad8067a7)
• Israel and Lebanon reached a new conditional ceasefire agreement. → Sources: [geopoliticalmonitor.com](https://www.geopoliticalmonitor.com/iran-war-ceasefire-frays-taiwan-china-south-china-sea-standoff-el-nino-geopolitics-weekly/)
• Qatar and Pakistan reported that positive progress was made during indirect talks between the United States and Iran in Doha. (3 reports) → Sources: [thewashingtonstandard.com](https://thewashingtonstandard.com/trump-claims-progress-in-indirect-peace-meetings-again/)
• The United States and Iran held technical talks in Doha. (2 reports) → Sources: [independent.co.uk](https://www.independent.co.uk/news/world/middle-east/iran-us-war-live-trump-qatar-peace-talks-hormuz-oil-prices-b3006373.html)
• U.S. and Iranian negotiators held talks via mediators in Doha on July 1, 2026. (2 reports) → Sources: [cbsnews.com](https://www.cbsnews.com/live-updates/us-iran-war-trump-negotiations-pause-ayatollah-funeral/)
• Iran launched missiles at Israel. → Sources: [geopoliticalmonitor.com](https://www.geopoliticalmonitor.com/iran-war-ceasefire-frays-taiwan-china-south-china-sea-standoff-el-nino-geopolitics-weekly/)
• Hezbollah officially rejected the ceasefire agreement between Israel and Lebanon. → Sources: [geopoliticalmonitor.com](https://www.geopoliticalmonitor.com/iran-war-ceasefire-frays-taiwan-china-south-china-sea-standoff-el-nino-geopolitics-weekly/)
• Iran launched drones and missiles against targets in Bahrain and Kuwait. → Sources: [geopoliticalmonitor.com](https://www.geopoliticalmonitor.com/iran-war-ceasefire-frays-taiwan-china-south-china-sea-standoff-el-nino-geopolitics-weekly/)
• Iranian authorities suspended bilateral negotiations with the United States. → Sources: [geopoliticalmonitor.com](https://www.geopoliticalmonitor.com/iran-war-ceasefire-frays-taiwan-china-south-china-sea-standoff-el-nino-geopolitics-weekly/)
• Tehran stated that Israel must stop attacking Hezbollah before a final peace deal can be reached. → Sources: [military.com](https://www.military.com/lebanon-israel-pact-fragile-after-hezbollahs-vow-of-disruption)
• Qatari and Pakistani mediators announced that positive progress was made in the negotiations between the U.S. and Iran. (3 reports) → Sources: [cbsnews.com](https://www.cbsnews.com/live-updates/us-iran-war-trump-negotiations-pause-ayatollah-funeral/)
• The United States government acknowledged Iran's involvement in Lebanon. → Sources: [jpost.com](https://www.jpost.com/israel-news/defense-news/article-900741)
• Iran stated that no direct peace talks are taking place. → Sources: [independent.co.uk](https://www.independent.co.uk/news/world/middle-east/iran-us-war-live-trump-qatar-peace-talks-hormuz-oil-prices-b3006373.html)
• President Donald Trump stated that the denuclearization of Iran is moving along well. → Sources: [cbsnews.com](https://www.cbsnews.com/live-updates/us-iran-war-trump-negotiations-pause-ayatollah-funeral/)
• Qatari and Pakistani mediators stated that future meetings between U.S. and Iranian negotiators will be scheduled after funeral commemorations for Iran's former supreme leader. (3 reports) → Sources: [cbsnews.com](https://www.cbsnews.com/live-updates/us-iran-war-trump-negotiations-pause-ayatollah-funeral/)
```

## Reference Output (Gemini Search)

```
As of July 5, 2026, the most significant current development regarding an Iran War ceasefire deal is the ongoing tension surrounding the Strait of Hormuz, which is testing the fragile Memorandum of Understanding (MOU) signed between the US and Iran on June 17.

Here are 4-6 other significant facts:

*   **Strait of Hormuz Flashpoint:** The Strait of Hormuz has become a focal point for disputes over the implementation of the June 17 MOU, with ongoing military pressure and clashes.
*   **Recent Hostilities in the Strait:** On June 25, Iran struck the Singapore-flagged Ever Lovely as it exited the strait. This led to a four-day exchange of fire, including US strikes on Iranian infrastructure and Iranian drone and missile attacks targeting US-linked sites.
*   **US-Iran Talks Paused:** Peace negotiations between the US and Iran, which were being held in Doha, Qatar, were paused on Saturday, July 4, due to Iran's mass funeral procession for the recently deceased Supreme Leader Ayatollah Ali Khamenei.
*   **MOU Signed June 17:** The MOU, signed by US President Donald Trump and Iranian President Masoud Pezeshkian, established a 60-day timeline to negotiate an agreement on Iran's nuclear program, while securing Iran's reaffirmation that it would not pursue nuclear weapons.
*   **Previous Ceasefire Efforts:** An initial two-week ceasefire was agreed upon on April 8, 2026, mediated by Pakistan. This was later extended indefinitely on April 21 by President Trump. New ceasefire conditions for a 60-day period were agreed upon on June 12, leading to the June 17 MOU.
*   **Iran's Post-War Stance:** Despite the initial strikes by the US and Israel in February 2026, Iran's regime has emerged emboldened, with a new generation of leaders considered savvier and more hard-line.
```

## Reference Sources

- [acleddata.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFcC5e-ghyAd4vphXdGJUEtK3KKo1ZhPBVDhR6P9HaWBbNdPLEdXC8tWAQavb3aq5SQ8Ds2xRZacqaAQy4iKeJJlEt1sepT5xAyM-4M39dqK1fBb4Ud6CZ09S6zk-EgKqqFs5EMfdsgjxiYh0sWf7GjjCVSkPcA)
- [un.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEP_kaWRNNWEuncDpMDQnTw6sco2vKKk5iu_KOZg2rivVJ8KCvwG40RrjG0UBNnTRzaKXmOazSBHweCnPhDcXWJR6D6bko4qnGUfnElPGd7ZxtaWcg5zmJqxEGgpAyAlxjgB2bm80Dr)
- [foxnews.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHxYOP8lXnU27MQByPz7AlIA3IlnCl7vp3Lt6SwN4kb9d0aq_yX305tM6IhmrUnjMfoxOhS3o4LEAeNPH07ScaE4e-sSo2ZLhrQ4R6QliYvcrpykfJR1f4kMRhGIPWRueQxb7rV1J16KmRyeYLuisawI-zT042H2P7wYfB78i36fx2D)
- [britannica.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHEr6-sT1N3cn1GUeMz_6TYipUNoDzpUTZui_PE6OFX0i88yeMv4VJEZm1o4WE5s4MKFxbArgMOGS_9k-mkaqzpNynMh2hXqHdRDc54ta3lvFVpIOSR65AsYh-AgYRBV4oYohrSJAp17BA=)
- [wikipedia.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFVTu-txxsb7mOoHKIoC57PapnDCNMRGaeisHbeWzFUTuqRldMFK5IcwIYbe371oKPkTXsWA1BkxRhRZW49ZFt5yRcZsMjr98TBHQx8IlOjVVkiEUcg33jbYMraKNNnRGRbYHgy-5X4z5VPWZpzs98A)
- [washingtonpost.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFTKyYgUyeuzUA_-vBun2ZAzQPOPlzxHNHQhjPUL8MeTaRIk22vTGFGJsttqMcbmT7rtHHPy8Eln-X79-aDuTccLWzWCLwtGycjfWJUXLBhSDQ6ihysq5ul0mVnJ4t5EwpL_DPwpznEH2U0AAsoV9vcLRuMrvvYX64gbtb2mqi0Fj4EnS-d8AAJU4xHIJPEi70T9dIkDY6KVmj5HldhC_wQ8MR51I5ncEjyRAuibdyp)
