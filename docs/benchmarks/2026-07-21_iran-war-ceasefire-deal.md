# Benchmark: Iran War ceasefire deal
**Date:** 2026-07-21  |  **Models:** pipeline=gemini-2.5-flash-lite, judge=gemini-2.5-flash-lite

## Scores

| Axis | Ours | Reference |
|---|---|---|
| lede_quality | 6 | 8 |
| completeness | 7 | 9 |
| synthesis | 6 | 8 |
| noise_level ⚠️ | 5 | 8 |
| **TOTAL** | **24** | **33** |

**Verdict:** Brief B wins by a moderate margin due to its superior synthesis and significantly lower noise level, despite Brief A's slightly better coverage of past agreements; Brief A's main fixable issue is the inclusion of outdated and repetitive information about past agreements.

## Gaps in TrueBrief

- Mediators propose a 10-day ceasefire to revive the interim deal.
- President Trump is weighing options between this proposed truce and a full-scale military campaign alongside Israel.
- President Pezeshkian declared Iran is in a 'full-scale war' with the United States.
- Iran's Foreign Ministry spokesperson stated that mediators have presented new ideas for a peace process and emphasized that diplomacy is being pursued alongside military strength.
- The US military has deployed dozens of fighter jets and refueling aircraft to the region.
- A previous two-week ceasefire, brokered by Pakistan and agreed upon on April 8, 2026, was extended indefinitely by President Trump on April 21, but later declared over on July 8, 2026.

## False Positives in TrueBrief

- The United States and Iran reached an agreement to call for a ceasefire on all fronts.
- The United States and Iran reached a framework agreement to extend their ceasefire for 60 days.
- President Donald Trump announced the United States would lift its naval blockade.
- Iran's Supreme National Security Council announced that all military operations, including in Lebanon, will end immediately.
- The United States and Iran reached an agreement on June 14 to end the conflict concerning the Strait of Hormuz.
- The U.S. military will remove its naval blockade within thirty days of the agreement signing.
- US President Donald Trump and Iranian President Masoud Pezeshkian signed a Memorandum of Understanding (MOU) to end the conflict.
- The United States and Iran are scheduled to sign an agreement in Geneva on June 19.
- A senior U.S. official read the draft of the 14-point agreement to reporters on June 17.
- The United States and Iran have 60 days to reach a technical agreement regarding the down-blending of highly enriched uranium and the monitoring of Iran's nuclear program.
- Pakistani Prime Minister Shehbaz Sharif served as a mediator between the United States and Iran.
- Iranian Supreme Leader Mojtaba Khamenei authorized the Memorandum of Understanding after the Supreme National Security Council accepted responsibility for the deal.
- Pakistani Prime Minister Shehbaz Sharif announced the ceasefire framework on June 14.
- Washington will pursue a reconstruction and economic development plan for Iran worth at least $300 billion.
- Iran's deputy foreign minister Kazem Gharibabadi announced that Iran would begin fulfilling deal commitments following the Friday signing ceremony.
- A formal signing ceremony for the memorandum of understanding is scheduled for Friday, June 19.

## TrueBrief Output

```
📋 TrueBrief | Iran Ceasefire Negotiations | July 21, 2026

**📌 Bottom line:** Tehran announced that ceasefire negotiations have collapsed.

🆕 NEW STORIES (28)
━━━━━━━━━━━━━━━━━━━━━━━━━━
• Tehran announced that ceasefire negotiations have collapsed. → Sources: [bbc.co.uk](https://www.bbc.co.uk/news/articles/cx25wg2x26do?at_medium=RSS&at_campaign=rss)
• Iran's Revolutionary Guard announced that two oil tankers were stopped in the Strait of Hormuz after explosions caused fires. → Sources: [theguardian.com](https://www.theguardian.com/world/live/2026/jul/20/us-iran-war-live-updates-strikes-strait-of-hormuz-middle-east-crisis-latest-news)
• President Donald Trump declared the ceasefire deal with Iran was over. (2 reports) → Sources: [abcnews.com](https://abcnews.com/Politics/us-iran-ceasefire-mou-broke-timeline/story?id=134622392)
• The United States and Iran reached an agreement to call for a ceasefire on all fronts. (3 reports) → Sources: [understandingwar.org](https://understandingwar.org/research/middle-east/iran-update-special-report-june-14-2026/)
• The United States and Iran reached a framework agreement to extend their ceasefire for 60 days. (3 reports) → Sources: [axios.com](https://www.axios.com/2026/06/14/us-iran-ceasefire-extended-hormuz-reopen-trump)
• President Donald Trump announced the United States would lift its naval blockade. (3 reports) → Sources: [axios.com](https://www.axios.com/2026/06/14/us-iran-ceasefire-extended-hormuz-reopen-trump)
• Iran's Supreme National Security Council announced that all military operations, including in Lebanon, will end immediately. (3 reports) → Sources: [axios.com](https://www.axios.com/2026/06/14/us-iran-ceasefire-extended-hormuz-reopen-trump)
• The United States and Iran reached an agreement on June 14 to end the conflict concerning the Strait of Hormuz. (3 reports) → Sources: [cfr.org](https://www.cfr.org/articles/is-a-u-s-iran-deal-within-reach-six-key-issues-that-could-shape-a-ceasefire)
• The U.S. military will remove its naval blockade within thirty days of the agreement signing. (3 reports) → Sources: [cfr.org](https://www.cfr.org/articles/is-a-u-s-iran-deal-within-reach-six-key-issues-that-could-shape-a-ceasefire)
• US President Donald Trump and Iranian President Masoud Pezeshkian signed a Memorandum of Understanding (MOU) to end the conflict. (2 reports) → Sources: [bbc.co.uk](https://www.bbc.co.uk/news/articles/c932yqz8lggo?at_medium=RSS&at_campaign=rss)
• Mediators offered Iran a proposal for a 10-day ceasefire to revive the memorandum of understanding. → Sources: [theguardian.com](https://www.theguardian.com/world/2026/jul/20/us-strikes-iran-strait-of-hormuz-oil-prices)
• Marco Rubio stated that the US is still open to negotiations with Iran. → Sources: [theguardian.com](https://www.theguardian.com/world/2026/jul/20/us-strikes-iran-strait-of-hormuz-oil-prices)
• The United States rescinded Iran's license to sell oil internationally. → Sources: [abcnews.com](https://abcnews.com/Politics/us-iran-ceasefire-mou-broke-timeline/story?id=134622392)
• U.S. forces launched a round of strikes against Iran. → Sources: [usatoday.com](https://www.usatoday.com/story/news/world/2026/07/08/trump-iran-ceasefire-peace-deal-talks-memorandum/90847679007/)
• Iran targeted U.S. military sites in Bahrain and Kuwait. → Sources: [usatoday.com](https://www.usatoday.com/story/news/world/2026/07/08/trump-iran-ceasefire-peace-deal-talks-memorandum/90847679007/)
• Iran struck three vessels in the Strait of Hormuz. → Sources: [abcnews.com](https://abcnews.com/Politics/us-iran-ceasefire-mou-broke-timeline/story?id=134622392)
• Vice-President JD Vance stated the US expects Hezbollah will refrain from firing on Israel as part of the de facto ceasefire. (4 reports) → Sources: [bbc.co.uk](https://www.bbc.co.uk/news/articles/c932yqz8lggo?at_medium=RSS&at_campaign=rss)
• US President Donald Trump announced the authorization of a toll-free opening of the Strait of Hormuz and the removal of the United States naval blockade on Iranian ports. (4 reports) → Sources: [understandingwar.org](https://understandingwar.org/research/middle-east/iran-update-special-report-june-14-2026/)
• Trump stated that U.S. envoys Jared Kushner and Steve Witkoff can continue peace talks. (2 reports) → Sources: [usatoday.com](https://www.usatoday.com/story/news/world/2026/07/08/trump-iran-ceasefire-peace-deal-talks-memorandum/90847679007/)
• The United States and Iran are scheduled to sign an agreement in Geneva on June 19. (3 reports) → Sources: [understandingwar.org](https://understandingwar.org/research/middle-east/iran-update-special-report-june-14-2026/)
• A senior U.S. official read the draft of the 14-point agreement to reporters on June 17. (3 reports) → Sources: [cfr.org](https://www.cfr.org/articles/is-a-u-s-iran-deal-within-reach-six-key-issues-that-could-shape-a-ceasefire)
• The United States and Iran have 60 days to reach a technical agreement regarding the down-blending of highly enriched uranium and the monitoring of Iran's nuclear program. (3 reports) → Sources: [axios.com](https://www.axios.com/2026/06/14/us-iran-ceasefire-extended-hormuz-reopen-trump)
• Pakistani Prime Minister Shehbaz Sharif served as a mediator between the United States and Iran. (3 reports) → Sources: [cfr.org](https://www.cfr.org/articles/is-a-u-s-iran-deal-within-reach-six-key-issues-that-could-shape-a-ceasefire)
• Iranian Supreme Leader Mojtaba Khamenei authorized the Memorandum of Understanding after the Supreme National Security Council accepted responsibility for the deal. (2 reports) → Sources: [bbc.co.uk](https://www.bbc.co.uk/news/articles/c932yqz8lggo?at_medium=RSS&at_campaign=rss)
• Pakistani Prime Minister Shehbaz Sharif announced the ceasefire framework on June 14. (2 reports) → Sources: [axios.com](https://www.axios.com/2026/06/14/us-iran-ceasefire-extended-hormuz-reopen-trump)
• Washington will pursue a reconstruction and economic development plan for Iran worth at least $300 billion. → Sources: [bbc.co.uk](https://www.bbc.co.uk/news/articles/c932yqz8lggo?at_medium=RSS&at_campaign=rss)
• Iran's deputy foreign minister Kazem Gharibabadi announced that Iran would begin fulfilling deal commitments following the Friday signing ceremony. → Sources: [cfr.org](https://www.cfr.org/articles/is-a-u-s-iran-deal-within-reach-six-key-issues-that-could-shape-a-ceasefire)
• A formal signing ceremony for the memorandum of understanding is scheduled for Friday, June 19. → Sources: [axios.com](https://www.axios.com/2026/06/14/us-iran-ceasefire-extended-hormuz-reopen-trump)
```

## Reference Output (Gemini Search)

```
**Mediators propose 10-day ceasefire to revive interim deal amid escalating Iran conflict.**

Mediators have presented Iran with a proposal for a 10-day ceasefire aimed at salvaging a previously reached interim deal and paving the way for a lasting agreement to end the ongoing war. This diplomatic initiative comes as the conflict between the United States and Iran intensifies, with US President Trump reportedly weighing options between this proposed truce and a full-scale military campaign alongside Israel.

Key developments include:

*   **New Ceasefire Proposal:** Mediators have offered a 10-day ceasefire to de-escalate the war and revive the interim deal established last month.
*   **Iran's Stance:** Iran's Foreign Ministry spokesperson stated that mediators have presented new ideas for a peace process and emphasized that diplomacy is being pursued alongside military strength. President Masoud Pezeshkian declared Iran is in a "full-scale war" with the United States but acknowledged the need to accept the consequences of resistance.
*   **US Consideration:** The US administration is reportedly exploring the proposal while urging Israel to avoid actions that could jeopardize diplomatic channels.
*   **Escalating Military Actions:** Despite diplomatic efforts, the conflict has seen renewed fighting, including nine consecutive nights of US strikes on Iran and Iranian attacks on US military assets and allied nations. Iran's Revolutionary Guards have also reported explosions involving oil tankers attempting to transit the Strait of Hormuz.
*   **Strait of Hormuz Tensions:** The Strait of Hormuz remains a critical point of contention, with Iran seeking control over the waterway. The ongoing conflict has led to restricted passage through the strait.
*   **Past Ceasefire History:** A previous two-week ceasefire, brokered by Pakistan and agreed upon on April 8, 2026, was extended indefinitely by President Trump on April 21, but later declared over on July 8, 2026. A memorandum of understanding was signed on June 17, 2026, formalizing a process to end the war with a 60-day negotiation period.
*   **US Military Buildup:** The US military has deployed dozens of fighter jets and refueling aircraft to the region, signaling preparedness for a potential escalation.
```

## Reference Sources

- [indiatimes.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEOID-CsPZ0ZXyZ4ZrUkeIyOa2aXp0Ud0hfTrfTd9_oyWyBe88MIDUDKBbfRcR_CYBHKVttaOPQVPQe4dS-mlfe6QuiX4GJfqr3qu4UvKC3qzofYXcNdBW9rw71VjVg-OF9XnvlP1OC9La8vab6Nf-xrRgqFzjKxoaTTZbsz5o08iCjQxeLYiY1lQzHeOy94s9KE3m9Jvb1jAOf3npKASiNvWfVwmILgaRvL9icvrmfYUQFWI-33bGePwKQb9K6mW9oBoTKR-oWd1c4cNKurA==)
- [timesofisrael.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHQfmaboeytHKfMISsW1xfklWA580-oywoViT_i87BBp_R_xeZnOUhwTAjgmtEGJTsuVRaEqzfx7fs1zh-SjesNEORP5igDUC9b798V-7oHubw5XV_PEtyUPVktX5tFIQxsk2kQ6DyY_HLcTVjFu-9alByZ-oDYGTzLHQb-CyYv8UOnyADjm9FiYFQE2kw5Q9rCDaMgjWlbttJApcv1Jsntqdw=)
- [axios.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGoD78jcbTqW7hTyUDGDs0AraTv9JBWOeDuK6HOT3-Kh7_ZSSowrImxPLAJSW083EQR6Y-RH6urgZk2mVcOTAE_FdBlLDtod18WRbLpdcpGqA6zLlRek406yhHDpCE-dGzMP3Lw7FOO930BCzwNasLOE1uv3HyfUBP9_PISXvuMFhLvGw==)
- [investinglive.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGlmnkjRXI9AOxKJhpnr_uf_i9RaIxBxUGDQ5N9Un3Rqg6hDOSwVhCuUDZ3h7ci3Z48WaP1ACeq5d986l_KHLx-uftfk_I3pC_8btF44Wnjqp3lmQdKDIhG6T9IVgESDwDVP3VGv-csU4RbQZubCqYaXLxCHUNphLQnaiW74gfEIU1iaPr96e3hVTX722zur3sByjBj0UKtSfHwD3mFH3YjaY_f3ottn-zmpbTBbWFC9GTx1ztnng==)
- [jpost.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHywhaYPYpRCtsL3j6ql2w40tl_XEcxbZAVjuSdw5iXaopPf59X3HPd8fxjkppjPoIF-iwymm44-P1KZFSBrE1Hc45JTUmOV9_mfcMA_HGzm6EnOLjcfeXEy61DnXWcDOo5xG1CDNr-btHUKuKQO5y6dMXAVg==)
- [ynetnews.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFDGlfsL7i1xIUGGRp_Di9pxSx9xKV7seJmTTLgkdPGwVkocc4TebVn-yvZEbxrwKS8kUDk1IbejiSQsWj4v7gXgXOFVxQEmNccgnZ9Lqrj9OU0o0jP4270l_IeXmWE7QfZvNTE-w==)
- [kqed.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEvjN-sBPyP5skLdnGYGr00IbUuWWOnYAj4AdxqH0W01Ij1D-tVbPFnjYgQy6gdmNNGkrkWjr2YxMmDPl8lelvO-bbZVGgXn001LAq9_a5eRydhABv7niAfZy4AIQvSQK6kzqs3kVrqVX6DbRX6xLJLSVPLtvK-z_CG-YwzMsi2LnAvFLOkxp89N4DSlO17tg==)
- [britannica.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEskrnmI6vqYmozZGSDf4Z3UQrFvXXNQB0YN_V5uq0f6Zzv9itjziUtt5o9vMLDCfxUblR47OXRsBWN54tmJokf1b7BARNHqJ474dFBFz3q9Z9e4YN24Mcsglhv1hsoAgEFYYXDdecuRg==)
- [wikipedia.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGIPJJEOeL2_9MXT2LboTRqtS3JL86TJTRG9PadrPG_ou9XH4iV89Qz7-WBMIODMvNSkeCrbrU2FZ7pIgJTj2eFZDOqIy3iF1xAyQJuh13XY_LwjKMjT00KnK57Ydkja6m83P7nTNcADTqzhnrwSew=)
