# Benchmark: Iran War ceasefire deal
**Date:** 2026-07-26  |  **Models:** search/judge=gemini-2.5-flash-lite

## Scores (V4 = old pipeline, V5 = Gemini Search + memory/dedup, Reference = simple unstructured Gemini ask)

| Axis | V4 | V5 | Reference |
|---|---|---|---|
| lede_quality | 0 | 9 | 8 |
| completeness ⚠️ | 0 | 6 | 9 |
| synthesis | 0 | 7 | 8 |
| noise_level | 0 | 8 | 5 |
| **TOTAL** | **0** | **30** | **30** |

**Verdict:** V5 is a significant improvement over V4, successfully identifying the main story and providing a coherent synthesis. It also does a better job of filtering noise than the Reference brief. However, V5 misses several important contextual details covered in the Reference brief, such as the ongoing US strikes, regional escalations, diplomatic statements, and economic impacts, leading to lower completeness and synthesis scores. The Reference brief, while noisier, provides a more comprehensive overview of the situation. V5's weakest axis is completeness, as it omits crucial background and related developments. The most fixable reason for V5's weakness is its limited scope in identifying and integrating related news items beyond the immediate ceasefire rejection.

## Gaps in V5

- U.S. strikes on Iranian targets for 13 consecutive nights
- Iran-backed Houthis escalating conflict with Saudi Arabia
- Egypt and Qatar calling for resumption of negotiations
- US Secretary of State Marco Rubio's statement on Iran's seriousness for talks
- Oil prices surging to over $100 per barrel
- Details on the collapse of the June 17 MOU

## False Positives in V5

- Iran and the United States denied reports that either country had rejected a proposed ceasefire, following reports that Tehran had rejected a ceasefire proposal brought by Iraqi Prime Minister Ali al-Zaidi.

## V4 Output (old pipeline)

```
(V4 FAILED: V4 pipeline did not finish within 300s (likely dead/quota-exhausted search dependencies))
```

## V5 Output (Gemini Search + memory/dedup)

```
📋 TrueBrief | Iran War ceasefire deal | July 26, 2026

**📌 Bottom line:** Iran has rejected a ceasefire proposal brought by Iraqi Prime Minister Ali al-Zaidi, citing the proposal's failure to address control over the Strait of Hormuz.

🆕 NEW STORIES (4)
━━━━━━━━━━━━━━━━━━━━━━━━━━
**Ceasefire Proposal Rejected**
• Iran rejected a ceasefire proposal brought to Tehran by Iraqi Prime Minister Ali al-Zaidi, as the proposal did not address control over the Strait of Hormuz, a key issue for Iranian officials. → Sources: [jpost.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFaWvBtxqG5HEUlABnnNAinIH7orNb5VC1ZLBz4nxwOdBq7UvB_WBBu21j5rR9vtxJRivOftx4YPii3k_EdQcUeGdst9KSPH1hh2GDaUYy-6-b7oYAWy3XKuq9WXahVWqpjS84uc1yGrCGls-S9stLVNexeUtU=)
• Mediators had proposed a 10-day ceasefire to Iran, intending to de-escalate the war and potentially revive an interim deal reached the previous month. → Sources: [jpost.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGOcw3CzHUU4PPxx3f0wseVhSNHpC69AF-RfGCRuixM_9VNvQubJ9WoDqfwQNIWqcDSgyu66E3HcAdnOmlXE0eiw4wSQA-YuUUSPfpdzA_XlMtBYgen_w4buuhjkVoqaG1OtqC6LimAaXXwq4tN9usqj2K53Ic=)
• Iran announced the suspension of all ceasefire-related commitments under its Memorandum of Understanding with the United States, which was originally signed on June 17 to reduce hostilities and ensure shipping safety. → Sources: [opindia.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHKWdpo5H-uUb_5TWgikUSbiFgYBOec3LTwPKIdY8eOfWXy3wnz-kZY3Y30hrrgf08RQNXwQyVACgx_NuvRB2iu6g0qJaeQpCPsYG0jbyPrDicA70K1pUwtONvKL2DMlxbEECgPXVPPHnf6yEgfmZIhB8M5BnQbR1tlf4CASvTcBCsofZw1YdzYGn6Nu-NhQL_gSSZ2qfjdd6wU0GG5kheAZ0ofA9DMPyNJ86lrsA==)
• Iran and the United States denied reports that either country had rejected a proposed ceasefire, following reports that Tehran had rejected a ceasefire proposal brought by Iraqi Prime Minister Ali al-Zaidi. → Sources: [youtube.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHsOHfyqQ_g5Tkq3GArheufB048SVhbo8CQ_zNTGM0_nKUTqxw1J7jyB-hcre0xIwSgbCumYmTDlUpjzLktlmFMQqcQg1-VShNkfHMAJ5le8OpRDZ-R1Q5zCG6TmfJ-jHm4c-r9L4Y=)

📈 UPDATES (0)
```

## Reference Output (simple, unstructured Gemini Search ask)

```
The most significant current development regarding an Iran war ceasefire deal is that on July 23, 2026, Iran rejected an American ceasefire proposal relayed by Iraqi Prime Minister Ali al-Zaidi. Iranian officials stated that while it was the only offer on the table, Tehran was not interested in a temporary agreement that left control of the Strait of Hormuz unresolved.

Other significant developments include:

*   **Continued U.S. Strikes and Iranian Rejection of Further Ceasefire:** On July 23, 2026, U.S. forces conducted the 13th consecutive night of strikes against Iranian targets, including military command centers and drone storage facilities. Concurrently, Iran reportedly rejected a U.S. ceasefire proposal.
*   **Escalation in Regional Conflicts:** Iran-backed Houthis have escalated their conflict with Saudi Arabia by targeting oil facilities. This follows a naval blockade on Saudi Arabia announced by the Houthis.
*   **Strait of Hormuz Dispute:** The ongoing dispute over control of the Strait of Hormuz remains a key obstacle to a lasting ceasefire, with Iran seeking to assert control and collect fees. This has led to increased security threat levels in the Strait and surrounding waters.
*   **Diplomatic Efforts Continue Amidst Standoff:** Egypt and Qatar have called for the resumption of negotiations between the United States and Iran, urging regional de-escalation and a return to diplomacy. However, U.S. Secretary of State Marco Rubio stated on July 22, 2026, that while the U.S. is open to negotiating an end to the crisis, Iran is not serious about talks.
*   **Economic Impact:** The conflict has caused oil prices to surge, with Brent crude oil prices breaking $100 per barrel again on July 24, 2026. Global trade and travel have been disrupted, with shipping reroutes to avoid the Strait of Hormuz and the Red Sea.
*   **Previous Ceasefire Agreement and its Collapse:** A Memorandum of Understanding (MOU) was signed on June 17, 2026, by the U.S. and Iran, aiming to end the war and reopen the Strait of Hormuz. However, by July 8, 2026, President Trump declared the MOU "over," and both sides resumed exchanging fire. The vagueness of the MOU's 14 points has been cited as a reason for its collapse.
```

## Reference Sources

- [jinsa.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGA0AVSu9rG0mfxhl-pb2_rXwGS1pBUL5zEQk3f8lK_fgBFDmVzSOu92LGrCgo3WlfZXBwkBv9sm4-l87engAPeqU_c7_No2xNN5xwFk8BOhkC93ZdLqwHxGS8knHg2i8dJ3q7e2P_UVOBeEAVzhrgyBtDmYaybc8OalR_BOUEPW2rTbw==)
- [youtube.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFBFnu81_VrTLZqgeu54Ughl49_SxlcNoeWPxuN-21pLp_hwC7EZ2rM_356kLc-9P1fEqTYcoHeprnhGA1sAIwVHpniKFIULJEbEIr3kPjnBFE99mmQOhLkzjV7JX11g1VtHGmgdMI=)
- [cbsnews.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGuGkqJ4jx5Zt3t0zT82k-Z8Xkovsg7XCwR2mQ81R8lCXrnOdeyvV6zStmV5BFOqlx11SdmZjpsOM9Eombfd1amUhkEQojKgLtT8NCH1SGvuxtdzS_cAMfKiQvQ6Im1yW--HscVBDuu09XcjrMySeFNpDynSseCvjOdXwG0IF9-KzZiWVEC63OHNiWvng==)
- [jpost.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH7-duZMAheewQa-7VGTDQ0PvGU3u6_-lVvvNBkkQYvB6sV6E6iXk6AedbXQhHFgOqLq8-lVb21LYRN1QnGNH6_Lz43d7rGxO-C5RvbHpUrwZA1Wo3Hqf2288kJYWiOUYAp54XwdiZ337-tDKeMefgPuJf64FY=)
- [britannica.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGkn10akJMr9Ew8Y_P_8qUhBCIUAniErxYJsdaerEIRZqOZ6BEpu9fGH8Bd15u5bKHBDwSfqcIjJA9vF1hpab1_LoLBE4tHVD-is83UQ-2wm6h2WIvzXCsSle4xg9CzvC2UKSW93-2JmFs=)
- [gvwire.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGBO1SwNb_G_4Fa5wUdD2DLWHOFVo2IAlhVOLGI6Yx8PIj0hNGcl8_EaILn8_irC9HgJrXNzghBVPD80Y4u2TY4yemXKYsfNJZ956ABJD79XQ5qFDpklWO-bgESp6QlGkfPvMWzZ4mW1geBI0SLw7ES0lpq9sQsntiXIcaqtCj02MRSgEXCejwMLJJpBJVcxfcN4D_lyuPYizwWD6M=)
- [acleddata.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGpYc2NaL7eAl-zC2QM0m5Di3R7nr3PVtFp3UDpUenBSitoQxWIY5ytBzBlsmFbny5kDTSMVZGFC9rNOtdFC67NCeIoVBuUi_sgVJp_W4qnPceO61FUE6mAKOnb6mvf_4le58atWbKiMF_fcq3jW_9oxejWzAcq)
- [egypttoday.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF5TFSqE7FNpPNWNxrGZ_4mMLggyWpa7erp_yWDZ2EmCeo32LZpwkQ80AYLQ5V8U8NXVh_mtflUi0hoXWov-SVegiStIvds3bYFt7Vorf8xjukULW1_F--k7wHZ6yHsumWhrfXyoYd9zXDkQ-nVcZf0dxLu72uIMIn3C2jTNkS3gqWNzDPKZ7r4bICO9FDecLbiKqEV1cavi6IujMekEodrkvpr-w==)
- [securitycouncilreport.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGfIy2taaUgkPpHEHbqsuF9BVRFdpGig4FSI7HsJFH1Xk8Yl082CLPr1bGBtTXInxNNRL62DJzL1hcTslAkT_uR9S7Ft-jRNGWQQhd2AYcquKYsugPhQJGzja5kyXQ5tyiSSG7VfAYQGY7nZGWl56D-qZB3yYg2ES4fyO75rrsGKdsIR1kRKJRLSqS81fyeuEUEU-bWYke55WpMWEqMF1ZvoKxIOBzLnuuFjGXwsmG6dWxpJg==)
