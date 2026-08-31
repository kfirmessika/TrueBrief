# Benchmark: Iran War ceasefire deal
**Date:** 2026-08-31  |  **Models:** search/judge=gemini-2.5-flash-lite

## Scores (V4 = old pipeline, V5 = Gemini Search + memory/dedup, Reference = simple unstructured Gemini ask)

| Axis | V4 | V5 | Reference |
|---|---|---|---|
| lede_quality | 9 | 8 | 2 |
| completeness | 8 | 9 | 6 |
| synthesis | 9 | 8 | 4 |
| noise_level | 8 | 7 | 5 |
| **TOTAL** | **34** | **32** | **17** |

**Verdict:** Brief V4 is the strongest, followed closely by V5, with Reference significantly lagging behind. V4's lede is superior as it immediately captures the core development of a permanent ceasefire agreement. V5's lede is slightly weaker as it omits the 'permanent' aspect. V4 also exhibits slightly better synthesis and lower noise. V5's main weakness lies in its completeness and synthesis, as it misses several key details present in V4 and Reference, particularly regarding the specific terms of the maritime and financial agreements, and the ongoing Israeli operations in Lebanon. The most fixable reason for V5's weakest axis (completeness and synthesis) would be to ensure it incorporates all distinct factual points mentioned in V4, rather than just merging similar concepts. V5 does not beat the simple Reference ask directly, as Reference provides a different, more recent (though less comprehensive on the ceasefire itself) snapshot of events. However, V4 and V5 both provide a much better overall picture of the ceasefire deal than the Reference ask alone.

## Gaps in V5

- V4 mentioned the ceasefire superseding an initial two-week truce that had expired on April 22, 2026.
- V4 specified the maritime and financial terms, including toll-free navigation on the Strait of Hormuz, removal of the US naval blockade, and release of frozen Iranian assets valued between $12 billion and $25 billion.
- V4 mentioned the signing ceremony was scheduled for June 19, 2026, in Geneva, Switzerland.
- V4 specified that Israel continued military operations in Lebanon despite the ceasefire, prompting Iranian insistence on a halt to these attacks.
- Reference mentioned the US and Iran trading strikes for the first time in a month, reigniting hostilities, and that this exchange began with the US striking Iranian rocket launchers on Larak Island.
- Reference mentioned Iran's retaliation with ballistic missile attacks on two US military air bases in Jordan and targeting US military personnel at an air base in the UAE.
- Reference mentioned the UAE's Ministry of Defence denying Iran's claims of being targeted.
- Reference mentioned a supertanker catching fire after hitting two naval mines in the southern Strait of Hormuz.
- Reference mentioned the US shifting its strategy towards 'economic warfare' and imposing new sanctions.
- Reference mentioned a separate Israel-Greece defense deal worth over NIS 10 billion.

## False Positives in V5

- An initial two-week ceasefire between the US and Iran expired, which had been extended indefinitely the day before its expiration.
- Iran considered the June 17 memorandum of understanding expired with no extension agreed, following earlier ceasefire arrangements between the two nations.

## V4 Output (old pipeline)

```
📋 TrueBrief | Iran War Ceasefire Deal | August 31, 2026

**📌 Bottom line:** The United States and Iran have reached an immediate and permanent ceasefire agreement mediated by Pakistan following over three months of conflict.

🆕 NEW STORIES (2)
━━━━━━━━━━━━━━━━━━━━━━━━━━
**US-Iran Ceasefire Agreement**
• The United States and Iran reached an immediate and permanent ceasefire agreement after over three months of conflict between the two nations, superseding an initial two-week truce that had expired on April 22, 2026. → Sources: [sundayguardianlive.com](https://sundayguardianlive.com/world/us-israel-iran-war-latest-news-global-leaders-from-germany-australia-japan-more-hail-new-us-iran-ceasefire-agreement-207289/)

**Nuclear Program Negotiations**
• During negotiations, the United States proposed a 20-year freeze on the Iranian nuclear program, while Iran stated its willingness to pause uranium enrichment for five years instead. → Sources: [bhaskarenglish.in](https://www.bhaskarenglish.in/originals/news/us-iran-nuclear-controversy-war-ceasefire-deal-uranium-enrichment-ban-137711997.html)

📈 UPDATES (4)
━━━━━━━━━━━━━━━━━━━━━━━━━━
**Maritime and Financial Terms**
• The Pakistan-mediated ceasefire agreement includes the reopening of the Strait of Hormuz with toll-free navigation, the removal of the United States naval blockade on Iranian ports, and the release of frozen Iranian assets valued between $12 billion and $25 billion. → Sources: [sundayguardianlive.com](https://sundayguardianlive.com/world/us-israel-iran-war-latest-news-global-leaders-from-germany-australia-japan-more-hail-new-us-iran-ceasefire-agreement-207289/)

**Signing Ceremony**
• An official signing ceremony for the agreement was scheduled for June 19, 2026, in Geneva, Switzerland, to mark the end of over three months of conflict. → Sources: [sundayguardianlive.com](https://sundayguardianlive.com/world/us-israel-iran-war-latest-news-global-leaders-from-germany-australia-japan-more-hail-new-us-iran-ceasefire-agreement-207289/)

**Regional Military Operations**
• Israel continued military operations in Lebanon despite the ceasefire between the United States and Iran, prompting Iranian insistence that any final agreement must include a halt to these attacks. → Sources: [sundayguardianlive.com](https://sundayguardianlive.com/world/us-israel-iran-war-latest-news-global-leaders-from-germany-australia-japan-more-hail-new-us-iran-ceasefire-agreement-207289/)
```

## V5 Output (Gemini Search + memory/dedup)

```
📋 TrueBrief | Iran War ceasefire deal | August 31, 2026

**📌 Bottom line:** The United States and Iran have reached a ceasefire agreement mediated by Pakistan following over three months of conflict.

🆕 NEW STORIES (5)
━━━━━━━━━━━━━━━━━━━━━━━━━━
**US-Iran Ceasefire Agreement**
• The United States and Iran reached a ceasefire agreement, mediated by Pakistan and following over three months of conflict. → Sources: [sundayguardianlive.com](https://sundayguardianlive.com/world/us-israel-iran-war-latest-news-global-leaders-from-germany-australia-japan-more-hail-new-us-iran-ceasefire-agreement-207289/)
• An initial two-week ceasefire between the US and Iran expired, which had been extended indefinitely the day before its expiration. → Sources: [thepolypost.com](https://thepolypost.com/news/2026/04/18/u-s-iran-broker-ceasefire-deal/)
• Iran considered the June 17 memorandum of understanding expired with no extension agreed, following earlier ceasefire arrangements between the two nations. → Sources: [sundayguardianlive.com](https://sundayguardianlive.com/world/us-israel-iran-war-latest-news-global-leaders-from-germany-australia-japan-more-hail-new-us-iran-ceasefire-agreement-207289/)

**Nuclear Program and Regional Conflict**
• Iran declared that it is willing to pause uranium enrichment for five years, while the United States continues pushing for a 20-year freeze on the contentious nuclear program. → Sources: [bhaskarenglish.in](https://www.bhaskarenglish.in/originals/news/us-iran-nuclear-controversy-war-ceasefire-deal-uranium-enrichment-ban-137711997.html)
• At least 254 people died in Israel's military attacks on Lebanon, which continued despite the broader ceasefire agreement. → Sources: [sundayguardianlive.com](https://sundayguardianlive.com/world/us-israel-iran-war-latest-news-global-leaders-from-germany-australia-japan-more-hail-new-us-iran-ceasefire-agreement-207289/)

📈 UPDATES (2)
━━━━━━━━━━━━━━━━━━━━━━━━━━
**Diplomatic and Market Developments**
• An official signing ceremony for the ceasefire deal was scheduled to take place in Geneva, Switzerland, featuring provisions for the reopening of the Strait of Hormuz and the release of frozen Iranian assets. → Sources: [sundayguardianlive.com](https://sundayguardianlive.com/world/us-israel-iran-war-latest-news-global-leaders-from-germany-australia-japan-more-hail-new-us-iran-ceasefire-agreement-207289/)
• Oil prices fell 15% following the ceasefire agreement, providing relief to global energy markets previously disrupted by the military conflict. → Sources: [eaglecliff.co.uk](https://eaglecliff.co.uk/industry-news-iran-war-latest-ceasefire-relieves-energy-prices-for-now/)
```

## Reference Output (simple, unstructured Gemini Search ask)

```
The most significant current development is that the US and Iran have traded strikes for the first time in a month, reigniting hostilities. This exchange began with the US striking Iranian rocket launchers on Larak Island in the Strait of Hormuz, which Iran claims was in retaliation for a "US-Israeli" attack on its Larak Island that killed and wounded Iranian personnel.

Here are six other significant facts:

*   **Iran's Retaliation:** In response to the US strike, Iran launched ballistic missile attacks on two US military air bases in Jordan, claiming "heavy damage." Iran also stated it targeted US military personnel at an air base in the United Arab Emirates.
*   **UAE Denial:** The UAE's Ministry of Defence denied Iran's claims that its Al Minhad airbase was targeted, stating that media reports were false, although they did confirm their air force responded to a drone over its territorial waters.
*   **Supertanker Incident:** A supertanker caught fire and halted after hitting two naval mines in the southern Strait of Hormuz. Iran's Revolutionary Guard Corps (IRGC) claimed the tanker was attempting to pass through the waterway illegally.
*   **Ceasefire Status:** While a ceasefire was agreed in April and a memorandum of understanding for a peace deal was signed in June, no final agreement has been reached. Sporadic attacks, particularly around the Strait of Hormuz, have continued to dim prospects for a lasting peace.
*   **US Economic Warfare:** The US administration has shifted its strategy towards "economic warfare," imposing new sanctions on Iran to break the conflict's stalemate and isolate Iran economically.
*   **Israel-Greece Defense Deal:** Separately, Israel and Greece signed a significant defense deal worth over NIS 10 billion, which includes building a multi-layered defense system for Greece and selling drone dome systems, potentially signaling broader regional security realignments.
```

## Reference Sources

- [ndtv.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHXL5UduxpDyf4MxYjPGDNHIwuv451hwc4pUFyrhOITDwWPaFFRGrYnsrHstduFz9k9d4ongLDwTdSnn6rVLQmSj_tyAOAYCBHNh5e028ZwpVSLdBwg_Owumczp56O-h2Gwb4_oQH815_AtrFodrnIHq8aVdFxFo-GHgYhIvJSo244RRjqbzMFqi0y-OQe55DmTKWSNk4KzYNVdeSfx3JWizrE=)
- [cbsnews.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFwatdABs7MPbKNwowG0417UvKH_wY3zXa90ej7ILfNtlEXtz92Bhulvt43csPmhi3t24lyRrSW2BBPnQHORbhhYwCa1-AA_STnJv927ABmHAywd6FXI3JLJja2eQpHTpg-5Jg2VtmHPjYY4CT2cmTPsLK48ZPVti00uK_kSQD1-3BfgoavJBkSOjjdNJF1tdU1yQ==)
- [theguardian.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFMAdXMv7DgS4C2A3HhM3Yw_5e3Zk3l0FvsVC7ckEeN2AiwbUCdNk2R2viSzivO9hWsBntT-6XEwe4aQyCFJC8SIMlQ8180WTJgPuPHChHQ89X4tmD0q-gBPoPJ_QkwsDSRI5yo0PnA-YrccTpuPVmRH28YFFxdEOLuEjYVDrno_X8Nm5F8wVDrBgds6a6LIpJGisusH9_uETdZzuSve4i5OoA3SjUYqDSBuimYssEQ1fydJqygyOPxaD2sJSCW2r3Pwxp4uTDb)
- [aljazeera.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFLRWaEPVg9bdA3CtHjz8Yvu6v5ec5p0Q-DtnZbAIAFdJaj7kjFCrE3iZ2KWev_2eOb3-2U1b5Qy412M2sQmEOAx34mGq7Gr3GJpyNK2_vP1UOM1zCe7Z-lW1gwyePJNpYNmpNOQxSzzP4-QLkUd--EiRDRW8Lq5GVNS3jasKBE5M0GJ9SQNjvwTif3kelRHhSEv2u7eXyC_a62fXpUsRuAEGdg-UYOxgJyYP0ua4CxSDY6pCYADQ==)
- [al-monitor.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFrXPTfjcc7FsT45cz46I2_ffo92dT0JQQ1lNbZFWv-hgXsHQZCS7ERxmutmt7MQc7fAIM02-4o3W7FVs611uortE9KJkqEPqPwTT3bHVIDfSHhTAkjDNCZ4_-sCf8mJulvlrPxAClsDQ2kUQN3EpMxGjzY9UgTuKvwbXIQgrFQ_Cr9mdSRY4yJvw==)
- [cbsnews.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFO-ZWC7eH_SmIVAHhkKk2NUxdamLC2OA-sHvOcCCMbg9CPQba2Ez_dQmW-CsrKbvFlcoXaNzUiR2s6Xhz8iNlbFixQe-Kqt_kjs9RxrvVw_397I8UFl6z6Y5AAU8PO7VJ3Fufv-SctWN1xvbxjTuEGJ3t4O060NjfyVk_U7LxQBot-vy8EjgxOIA0gJ_sJzqkWT3s86a2uiAm_VMM=)
- [al-monitor.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH4GKhDjGXO6vHOEWW-R3Gi8duZEkIwnOiJUl23MEnRDJH0Y9eTgc7YKmD46z0k4iu6auLf1UubMYHvTICn1q9uTRsBX1p_QL_Jmr3vcEgQW3t7Z2ulxYDvosCyB37cLpJc-ChtmhHHVkhEd6CkZ6SyC8ilrolLinTDJRH-2wh25QLQUxmmNfLIiegZqL4TnQ==)
- [inquirer.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE4jcX0hCXy2Nhheb9FBkr1J61unQmR8LIHr-s9rjvhdND_kaQJsOVfgWOR7txepmweUPok7oscw0u_D1GtaZzlCX28ezSidaJEvweiEOmMJ5spwKsSbrrej6nllqLk6IHe2fEnfp13_TS7D7Ef3zQEV2TkTKZp51YSZ7NRiV3IwqpswBfPNLPExlxmyn8m_qckuP1pOQ==)
- [iranintl.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF5uYtxdr_Zn_gOGod1T0klZ7BBMYyqmZBdl0LBBZg8YFeOsB6FsY15PgLDRf0WNePqVKNMUKGuL0fXjPZYgWt3W5JAY5qi-Pdud_3TxhS8-lsck-kdodYk4VN09S-Zwh5vOLc=)
- [jpost.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHA_Ww5Q4kfj0NQ4ap-gvAq_6cui-py_B4zBUcYR6Cy-vCDEMLbwVM2-BTBugAdiI7E340bIKhUUfSVqFIaCHGYuCA9pAYYeRXfxUJA8uL-Pa8j4B1WAPjikpr5qTTX7SvR8CNPMU6N8OCC484AnsDZ8bcSpNhT_zWvP7Pii69MNrLMr8Pl)
