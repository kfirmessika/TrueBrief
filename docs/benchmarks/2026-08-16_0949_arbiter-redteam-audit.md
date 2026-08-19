# Arbiter/Judge Dedup Red-Team Audit — auto-generated report

Generated deterministically by `scripts/_integrity_redteam_report.py` from `scripts/_integrity_redteam_grade.py`'s output. No LLM calls were used to write this file — every number below is computed math, and every failure explanation reuses the attack rationale written once into each test case's `note` field.

- **Topic**: `dd67825c-552d-4606-bfdd-9bc538783fba`
- **Total cases**: 131  |  **Gradable**: 129  |  **Ambiguous excluded**: 2  |  **Errors**: 0

## Live flag states

| Flag | Value |
|---|---|
| `V3_ENTITY_DEDUP` | True |
| `V3_CONTRADICTION_FLAG` | True |
| `V3_TALLY_COLLAPSE` | True |
| `V3_BATCH_JUDGE` | False |
| `V3_DIGIT_GUARD` | True |

## Overall results

| Metric | Value |
|---|---|
| Strict accuracy | **80.6%** |
| Macro accuracy (PASS/FILTER bucket) | **89.9%** |
| Confusion (positive=FILTER) | TP=54 FP=3 FN=10 TN=62 |
| Precision | **0.947** |
| Recall | **0.844** |
| F1 | **0.893** |

Of cases that should have been FILTERed (64), 54 were caught and **10 leaked through** (a real duplicate sneaked in). Of cases that should have PASSed (65), 62 passed correctly and **3 were wrongly filtered** (a real fact incorrectly dropped).

## Per-category stats

| Category | n | Strict | Macro | Precision | Recall | F1 | Failing case IDs |
|---|---:|---:|---:|---:|---:|---:|---|
| ANTONYM_GAP_CONTRADICTION | 10 | 80.0% | 90.0% | 0.00 | n/a | n/a | C7-07, C7-08 |
| ENTITY_ALIAS_DUPLICATE | 10 | 40.0% | 40.0% | 1.00 | 0.40 | 0.57 | C6-01, C6-03, C6-04, C6-05, C6-06, C6-10 |
| EXACT_DUPLICATE | 10 | 100.0% | 100.0% | 1.00 | 1.00 | 1.00 | — |
| FALSE_DEDUP_PRESSURE | 10 | 90.0% | 90.0% | 0.00 | n/a | n/a | C10-10 |
| INTRA_BATCH_DEDUP | 21 | 100.0% | 100.0% | 1.00 | 1.00 | 1.00 | — |
| MISSING_DATE_EXPLOIT | 8 | 75.0% | 100.0% | 1.00 | 1.00 | 1.00 | C11-05, C11-10 |
| NUMERIC_CHANGE_VERBATIM | 10 | 70.0% | 100.0% | n/a | n/a | n/a | C5-03, C5-08, C5-09 |
| NUMERIC_CONTRADICTION_EVASION | 10 | 40.0% | 90.0% | 0.00 | n/a | n/a | C8-02, C8-03, C8-05, C8-06, C8-07, C8-09 |
| PARAPHRASE_DATEDRIFT | 10 | 80.0% | 80.0% | 1.00 | 0.80 | 0.89 | C3-04, C3-09 |
| PARAPHRASE_DUPLICATE | 10 | 80.0% | 80.0% | 1.00 | 0.80 | 0.89 | C2-02, C2-06 |
| PROMPT_INJECTION | 10 | 100.0% | 100.0% | 1.00 | 1.00 | 1.00 | — |
| TALLY_UPDATE | 10 | 90.0% | 100.0% | n/a | n/a | n/a | C4-10 |

## Per cascade-stage stats

| Stage | n | Strict | Macro | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| fast_path | 75 | 78.7% | 85.3% | 0.95 | 0.80 |
| judge_llm | 54 | 83.3% | 96.3% | 0.95 | 0.95 |

## Per-gate stats (every fast-path mechanism individually)

| Gate | n | Strict | Macro | Precision | Recall | Failing case IDs |
|---|---:|---:|---:|---:|---:|---|
| judge_llm | 54 | 83.3% | 96.3% | 0.95 | 0.95 | C3-04, C4-10, C5-03, C7-07, C8-02, C8-05, C10-10, C11-05, C11-10 |
| IC1_tally_collapse | 23 | 78.3% | 91.3% | 1.00 | 0.82 | C2-02, C2-06, C8-03, C8-07, C8-09 |
| auto_new_score_threshold | 21 | 61.9% | 66.7% | 0.00 | 0.00 | C3-09, C5-09, C6-01, C6-03, C6-04, C6-05, C6-06, C6-10 |
| raw_cosine_auto_merge | 19 | 100.0% | 100.0% | 1.00 | 1.00 | — |
| same_day_near_identical | 10 | 80.0% | 80.0% | 0.80 | 1.00 | C7-08, C8-06 |
| auto_new_zero_matches | 1 | 0.0% | 100.0% | 0.00 | 0.00 | C5-08 |
| IC4_contradiction | 1 | 100.0% | 100.0% | 0.00 | 0.00 | — |

## Embedding-pure vs. special-case gates

| Subset | n | Strict | Macro | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Embedding-pure (no special gate fired) | 41 | 78.0% | 82.9% | 1.00 | 0.73 |
| Special-case gates (IC1/IC3/IC4/same-day) | 34 | 79.4% | 88.2% | 0.89 | 0.89 |

---

## What specifically broke, grouped by mechanism

Each failing case's rationale below is the attack design written when the case was built (`note` field in `_integrity_redteam_cases.py`), paired with the system's own stated reasoning for the wrong verdict. No new analysis was generated to produce this section.

### `judge_llm` — 9 failing case(s)

- **C3-04** (PARAPHRASE_DATEDRIFT) — expected `DUPLICATE`, got `NEW` (sim=0.7657978102612183)
  - Attack rationale: Paraphrase + drift +20d — no raw-cosine bypass, tests Judge LLM under temporal decay.
  - System reasoning: Judge LLM decision. Top match score: 0.766.
- **C4-10** (TALLY_UPDATE) — expected `UPDATE`, got `NEW` (sim=0.879058105945687)
  - Attack rationale: Casualty tally revision 6→9.
  - System reasoning: Judge LLM decision. Top match score: 0.879.
- **C5-03** (NUMERIC_CHANGE_VERBATIM) — expected `UPDATE`, got `NEW` (sim=0.986793963920531)
  - Attack rationale: Same date+template, 5%→8%.
  - System reasoning: Judge LLM decision. Top match score: 0.987.
- **C7-07** (ANTONYM_GAP_CONTRADICTION) — expected `NEW`, got `UPDATE` (sim=0.886289591174321)
  - Attack rationale: 'fell to eight' vs 'climbed to normal' — no antonym pair, no comparable digit either.
  - System reasoning: Judge LLM decision. Top match score: 0.886.
- **C8-02** (NUMERIC_CONTRADICTION_EVASION) — expected `NEW`, got `UPDATE` (sim=0.948144395262345)
  - Attack rationale: Conflicts with stored 'Three Pakistani nationals... killed' same day — spelled numbers on both sides.
  - System reasoning: Judge LLM decision. Top match score: 0.948.
- **C8-05** (NUMERIC_CONTRADICTION_EVASION) — expected `NEW`, got `UPDATE` (sim=0.953821431679411)
  - Attack rationale: Conflicts with stored '20 warships' same day — 'warships' is not in METRIC_KEYWORDS at all, so the gate can never fire for this domain.
  - System reasoning: Judge LLM decision. Top match score: 0.954.
- **C10-10** (FALSE_DEDUP_PRESSURE) — expected `NEW`, got `DUPLICATE` (sim=0.8213967571524933)
  - Attack rationale: Same claim as stored Trump statement, different OFFICIAL (VP not President).
  - System reasoning: Judge LLM decision. Top match score: 0.821.
- **C11-05** (MISSING_DATE_EXPLOIT) — expected `UPDATE`, got `NEW` (sim=0.975682082690972)
  - Attack rationale: Date is in the TEXT but alpha.event_date field is None — tests whether the system relies on the structured field (should) vs. text (can't parse), and whether digit-run mismatch (10 vs 24 embedded) still routes correctly.
  - System reasoning: Judge LLM decision. Top match score: 0.976.
- **C11-10** (MISSING_DATE_EXPLOIT) — expected `NEW`, got `UPDATE` (sim=0.7553927498119685)
  - Attack rationale: Explicit 'separate attack' framing + much higher count, no event_date — tests whether the Judge LLM reads the textual distinctness cue even without a date to lean on.
  - System reasoning: Judge LLM decision. Top match score: 0.755.

### `auto_new_score_threshold` — 8 failing case(s)

- **C3-09** (PARAPHRASE_DATEDRIFT) — expected `DUPLICATE`, got `NEW` (sim=0.7253032695524047)
  - Attack rationale: Paraphrase + drift -22d.
  - System reasoning: Highest adjusted score 0.725 below grey-zone threshold 0.75.
- **C5-09** (NUMERIC_CHANGE_VERBATIM) — expected `UPDATE`, got `NEW` (sim=0.6718784568817006)
  - Attack rationale: Correction of a previously-reported end date (Sept 30→Oct 15).
  - System reasoning: Highest adjusted score 0.672 below grey-zone threshold 0.75.
- **C6-01** (ENTITY_ALIAS_DUPLICATE) — expected `DUPLICATE`, got `NEW` (sim=0.7472394623638816)
  - Attack rationale: Same fact as C1-01, entities fully aliased (US military→Washington, Iran→Islamic Republic).
  - System reasoning: Highest adjusted score 0.747 below grey-zone threshold 0.75.
- **C6-03** (ENTITY_ALIAS_DUPLICATE) — expected `DUPLICATE`, got `NEW` (sim=0.7199948835345592)
  - Attack rationale: Entity alias: Iran→Tehran, Washington→U.S. government.
  - System reasoning: Highest adjusted score 0.720 below grey-zone threshold 0.75.
- **C6-04** (ENTITY_ALIAS_DUPLICATE) — expected `DUPLICATE`, got `NEW` (sim=0.6868276326246168)
  - Attack rationale: Named person (Araghchi) replaced with role, Israel→Tel Aviv.
  - System reasoning: Highest adjusted score 0.687 below grey-zone threshold 0.75.
- **C6-05** (ENTITY_ALIAS_DUPLICATE) — expected `DUPLICATE`, got `NEW` (sim=0.7438610997647107)
  - Attack rationale: Named person (Khamenei) replaced with title.
  - System reasoning: Highest adjusted score 0.744 below grey-zone threshold 0.75.
- **C6-06** (ENTITY_ALIAS_DUPLICATE) — expected `DUPLICATE`, got `NEW` (sim=0.7084511647762305)
  - Attack rationale: Pakistan→Islamabad, Tehran→Iranian capital, Naqvi→role.
  - System reasoning: Highest adjusted score 0.708 below grey-zone threshold 0.75.
- **C6-10** (ENTITY_ALIAS_DUPLICATE) — expected `DUPLICATE`, got `NEW` (sim=0.7333870132605776)
  - Attack rationale: Ali al-Zaidi→Iraq's PM, U.S. Central Command→CENTCOM.
  - System reasoning: Highest adjusted score 0.733 below grey-zone threshold 0.75.

### `IC1_tally_collapse` — 5 failing case(s)

- **C2-02** (PARAPHRASE_DUPLICATE) — expected `DUPLICATE`, got `UPDATE` (sim=1.0)
  - Attack rationale: Paraphrase + entity alias (Washington=United States).
  - System reasoning: IC1 tally-collapse: cumulative running total on the same entity-set — updating the existing tally in place.
- **C2-06** (PARAPHRASE_DUPLICATE) — expected `DUPLICATE`, got `UPDATE` (sim=1.0)
  - Attack rationale: Paraphrase with abbreviations (bpd, 1.8M).
  - System reasoning: IC1 tally-collapse: cumulative running total on the same entity-set — updating the existing tally in place.
- **C8-03** (NUMERIC_CONTRADICTION_EVASION) — expected `NEW`, got `UPDATE` (sim=1.0)
  - Attack rationale: Conflicts with stored '5.4%' same day — digit vs spelled-out number, one side yields zero regex matches.
  - System reasoning: IC1 tally-collapse: cumulative running total on the same entity-set — updating the existing tally in place.
- **C8-07** (NUMERIC_CONTRADICTION_EVASION) — expected `NEW`, got `UPDATE` (sim=1.0)
  - Attack rationale: Conflicts with stored '5.4%' same day — neither '%' nor 'percent' appears, 'points' is not a METRIC_KEYWORD, so shared_metric is empty despite a real digit-vs-digit conflict (9 vs 5.4).
  - System reasoning: IC1 tally-collapse: cumulative running total on the same entity-set — updating the existing tally in place.
- **C8-09** (NUMERIC_CONTRADICTION_EVASION) — expected `NEW`, got `UPDATE` (sim=1.0)
  - Attack rationale: Conflicts with stored 'fell to eight' — both spelled numbers, no digit-run overlap possible.
  - System reasoning: IC1 tally-collapse: cumulative running total on the same entity-set — updating the existing tally in place.

### `same_day_near_identical` — 2 failing case(s)

- **C7-08** (ANTONYM_GAP_CONTRADICTION) — expected `NEW`, got `DUPLICATE` (sim=0.930756431367147)
  - Attack rationale: 'low' vs 'high' — no antonym pair.
  - System reasoning: Same-day near-identical: sim=0.931, same event_date, same numbers, same subject — same event reworded.
- **C8-06** (NUMERIC_CONTRADICTION_EVASION) — expected `NEW`, got `DUPLICATE` (sim=0.948558908185595)
  - Attack rationale: Direct reversal of 'increased by 5%' — numbers equal (5=5) so numeric-conflict check can't fire, and increased/dropped isn't an ANTONYM_PAIRS entry either. Double gap.
  - System reasoning: Same-day near-identical: sim=0.949, same event_date, same numbers, same subject — same event reworded.

### `auto_new_zero_matches` — 1 failing case(s)

- **C5-08** (NUMERIC_CHANGE_VERBATIM) — expected `UPDATE`, got `NEW` (sim=0.0)
  - Attack rationale: Same-report correction of the expiry date itself (Aug 16→Aug 22).
  - System reasoning: No similar facts found in ledger.

---

## Full per-test table (grouped by category)

### ANTONYM_GAP_CONTRADICTION (n=10)

| id | alpha_text | expected | actual | gate | sim | strict | macro |
|---|---|---|---|---|---:|---|---|
| C7-01 | Iran's blockade of the Strait of Hormuz has crumbled, with vessels no… | NEW | NEW | auto_new_score_threshold | 0.726 | YES | YES |
| C7-02 | The IMF said Iran's economy is expanding again, reversing the earlier… | NEW | NEW | judge_llm | 0.836 | YES | YES |
| C7-03 | An Iranian official confirmed active talks are underway between Iran … | NEW | NEW | judge_llm | 0.930 | YES | YES |
| C7-04 | Abbas Araghchi conceded Iran is vulnerable in its war against the Uni… | NEW | NEW | judge_llm | 0.849 | YES | YES |
| C7-05 | U.S. forces allowed a ship to pass through the blockade of Iran's por… | NEW | NEW | judge_llm | 0.903 | YES | YES |
| C7-06 | Mojtaba Khamenei dismissed Ahmad Vahidi as commander-in-chief of the … | NEW | NEW | judge_llm | 0.923 | YES | YES |
| C7-07 | The number of vessels transiting the Strait of Hormuz climbed back to… | NEW | UPDATE | judge_llm | 0.886 | no | YES |
| C7-08 | Shipping traffic in the Strait of Hormuz surged to a one-week high. | NEW | DUPLICATE | same_day_near_identical | 0.931 | no | no |
| C7-09 | Iraqi Prime Minister Ali al-Zaidi refused to meet with Admiral Brad C… | NEW | NEW | judge_llm | 0.916 | YES | YES |
| C7-10 | Khawaja Asif stated that the U.S. and Iran are moving further apart f… | NEW | NEW | judge_llm | 0.888 | YES | YES |

### ENTITY_ALIAS_DUPLICATE (n=10)

| id | alpha_text | expected | actual | gate | sim | strict | macro |
|---|---|---|---|---|---:|---|---|
| C6-01 | Washington's armed forces have redirected 59 commercial vessels since… | DUPLICATE | NEW | auto_new_score_threshold | 0.747 | no | no |
| C6-02 | President Trump said America controls the Strait of Hormuz. | DUPLICATE | DUPLICATE | judge_llm | 0.772 | YES | YES |
| C6-03 | Tehran said it will keep the strait shut unless the U.S. government f… | DUPLICATE | NEW | auto_new_score_threshold | 0.720 | no | no |
| C6-04 | Iran's top diplomat called the country unbeatable in its fight agains… | DUPLICATE | NEW | auto_new_score_threshold | 0.687 | no | no |
| C6-05 | Iran's Supreme Leader named IRGC general Ali Abdollahi to lead the na… | DUPLICATE | NEW | auto_new_score_threshold | 0.744 | no | no |
| C6-06 | Islamabad's top security official traveled to the Iranian capital for… | DUPLICATE | NEW | auto_new_score_threshold | 0.708 | no | no |
| C6-07 | The IMF put the contraction of Iran's economy at 5.4 percent. | DUPLICATE | DUPLICATE | judge_llm | 0.752 | YES | YES |
| C6-08 | CENTCOM rerouted 55 commercial ships and knocked out two others in it… | DUPLICATE | DUPLICATE | judge_llm | 0.797 | YES | YES |
| C6-09 | Yemen's Houthi movement struck Mokha and Marib with drone and missile… | DUPLICATE | DUPLICATE | judge_llm | 0.771 | YES | YES |
| C6-10 | Iraq's PM sat down with the head of CENTCOM, Brad Cooper. | DUPLICATE | NEW | auto_new_score_threshold | 0.733 | no | no |

### EXACT_DUPLICATE (n=10)

| id | alpha_text | expected | actual | gate | sim | strict | macro |
|---|---|---|---|---|---:|---|---|
| C1-01 | The US military redirected 59 commercial vessels since reinstating it… | DUPLICATE | DUPLICATE | IC1_tally_collapse | 1.000 | YES | YES |
| C1-02 | Near the Strait of Hormuz, the US Navy redirected four more commercia… | DUPLICATE | DUPLICATE | same_day_near_identical | 0.969 | YES | YES |
| C1-03 | Mohsin Naqvi, Pakistan's Interior Minister, visited Tehran to hold di… | DUPLICATE | DUPLICATE | raw_cosine_auto_merge | 0.984 | YES | YES |
| C1-04 | The International Energy Agency reduced its 2026 global oil-demand fo… | DUPLICATE | DUPLICATE | raw_cosine_auto_merge | 1.000 | YES | YES |
| C1-05 | More than 30 countries — among them France, Britain and Canada — issu… | DUPLICATE | DUPLICATE | same_day_near_identical | 0.944 | YES | YES |
| C1-06 | The number of vessels transiting the Strait of Hormuz fell to eight. | DUPLICATE | DUPLICATE | IC1_tally_collapse | 1.000 | YES | YES |
| C1-07 | Iraqi Prime Minister Ali al-Zaidi met with Admiral Brad Cooper of U.S… | DUPLICATE | DUPLICATE | raw_cosine_auto_merge | 1.000 | YES | YES |
| C1-08 | Strait of Hormuz shipping traffic hit its lowest point in a week. | DUPLICATE | DUPLICATE | judge_llm | 0.979 | YES | YES |
| C1-09 | An Iranian official stated there have been no discussions between Ira… | DUPLICATE | DUPLICATE | raw_cosine_auto_merge | 1.000 | YES | YES |
| C1-10 | President Trump said the US controls the Strait of Hormuz. | DUPLICATE | DUPLICATE | raw_cosine_auto_merge | 0.973 | YES | YES |

### FALSE_DEDUP_PRESSURE (n=10)

| id | alpha_text | expected | actual | gate | sim | strict | macro |
|---|---|---|---|---|---:|---|---|
| C10-01 | The International Monetary Fund estimated that the Iraqi economy shra… | NEW | NEW | judge_llm | 0.767 | YES | YES |
| C10-02 | Esmail Baghaei declared Iran an invincible power in its war against t… | NEW | NEW | judge_llm | 0.778 | YES | YES |
| C10-03 | The US Navy redirected four additional commercial vessels near the Ba… | NEW | NEW | judge_llm | 0.814 | YES | YES |
| C10-04 | Three Indian nationals were reported killed in an attack on a ship in… | NEW | NEW | judge_llm | 0.753 | YES | YES |
| C10-05 | The price of gold increased by 5% on August 10, 2026. | NEW | NEW | auto_new_score_threshold | 0.726 | YES | YES |
| C10-06 | Iraqi Prime Minister Ali al-Zaidi met with the ambassador of the Unit… | NEW | NEW | auto_new_score_threshold | 0.718 | YES | YES |
| C10-07 | Mojtaba Khamenei appointed Mohsen Rezaei as his representative to the… | NEW | NEW | judge_llm | 0.855 | YES | YES |
| C10-08 | The International Energy Agency reduced its 2027 global oil-demand fo… | NEW | NEW | IC4_contradiction | 0.000 | YES | YES |
| C10-09 | Houthi rebels targeted the port city of Hodeidah and the province of … | NEW | NEW | judge_llm | 0.805 | YES | YES |
| C10-10 | U.S. Vice President rejected Iran's demand for war reparations. | NEW | DUPLICATE | judge_llm | 0.821 | no | no |

### INTRA_BATCH_DEDUP (n=21)

| id | alpha_text | expected | actual | gate | sim | strict | macro |
|---|---|---|---|---|---:|---|---|
| C12-01a | Iran's navy intercepted a foreign tanker near Bandar Abbas on August … | NEW | NEW | auto_new_score_threshold | 0.640 | YES | YES |
| C12-01b | An Iranian naval vessel intercepted a foreign oil tanker close to Ban… | DUPLICATE | DUPLICATE | raw_cosine_auto_merge | 0.971 | YES | YES |
| C12-02a | The Houthi movement claimed responsibility for a drone strike on a ta… | NEW | NEW | auto_new_score_threshold | 0.687 | YES | YES |
| C12-02b | Houthi forces said they carried out a drone attack on a tanker in the… | DUPLICATE | DUPLICATE | raw_cosine_auto_merge | 0.976 | YES | YES |
| C12-03a | Qatar's foreign minister announced a new round of mediation talks bet… | NEW | NEW | auto_new_score_threshold | 0.717 | YES | YES |
| C12-03b | Qatar announced fresh mediation talks between Tehran and Washington s… | DUPLICATE | DUPLICATE | same_day_near_identical | 0.964 | YES | YES |
| C12-04a | A cyberattack disabled port operations in Bandar Abbas for six hours … | NEW | NEW | auto_new_score_threshold | 0.553 | YES | YES |
| C12-04b | Port operations in Bandar Abbas were knocked offline for six hours on… | DUPLICATE | DUPLICATE | raw_cosine_auto_merge | 0.985 | YES | YES |
| C12-05a | Israel's military said it intercepted a missile launched from Yemen o… | NEW | NEW | auto_new_score_threshold | 0.625 | YES | YES |
| C12-05b | The IDF reported intercepting a missile fired from Yemen on August 14… | DUPLICATE | DUPLICATE | same_day_near_identical | 0.960 | YES | YES |
| C12-06a | Turkey's president called for an emergency summit on the Iran crisis … | NEW | NEW | auto_new_score_threshold | 0.613 | YES | YES |
| C12-06b | Turkey's leader urged an emergency summit over the Iran crisis on Aug… | DUPLICATE | DUPLICATE | raw_cosine_auto_merge | 0.982 | YES | YES |
| C12-06c | President Erdogan called for an urgent summit to address the Iran cri… | DUPLICATE | DUPLICATE | judge_llm | 0.900 | YES | YES |
| C12-07a | Saudi Arabia raised its oil production quota on August 14, 2026. | NEW | NEW | judge_llm | 0.752 | YES | YES |
| C12-07b | Saudi Arabia lowered its oil production quota on August 14, 2026. | NEW | NEW | auto_new_score_threshold | 0.729 | YES | YES |
| C12-08a | The death toll from the Bab el-Mandeb strikes rose to 14, officials s… | NEW | NEW | auto_new_score_threshold | 0.696 | YES | YES |
| C12-08b | Officials raised the Bab el-Mandeb strike death toll to 14 on August … | DUPLICATE | DUPLICATE | raw_cosine_auto_merge | 0.972 | YES | YES |
| C12-09a | Egypt's Suez Canal Authority reported a 12% drop in transit revenue f… | NEW | NEW | auto_new_score_threshold | 0.601 | YES | YES |
| C12-09b | Egypt's Suez Canal Authority reported a twelve percent decline in Jul… | DUPLICATE | DUPLICATE | raw_cosine_auto_merge | 0.982 | YES | YES |
| C12-10a | The Pentagon confirmed a naval buildup near the Strait of Hormuz on A… | NEW | NEW | auto_new_score_threshold | 0.693 | YES | YES |
| C12-10b | The U.S. Department of Defense confirmed a military naval buildup nea… | DUPLICATE | DUPLICATE | judge_llm | 0.836 | YES | YES |

### MISSING_DATE_EXPLOIT (n=8)

| id | alpha_text | expected | actual | gate | sim | strict | macro |
|---|---|---|---|---|---:|---|---|
| C11-01 | The US military has now redirected 88 commercial vessels since reinst… | UPDATE | UPDATE | IC1_tally_collapse | 1.000 | YES | YES |
| C11-02 | Strait of Hormuz shipping traffic hit its lowest point in a week. | DUPLICATE | DUPLICATE | judge_llm | 0.979 | YES | YES |
| C11-04 | Mojtaba Khamenei appointed Mohsen Rezaei as his representative to the… | DUPLICATE | DUPLICATE | raw_cosine_auto_merge | 1.000 | YES | YES |
| C11-05 | The price of oil increased by 5% on August 24, 2026. | UPDATE | NEW | judge_llm | 0.976 | no | YES |
| C11-06 | U.S. President Donald Trump rejected Iran's demand for war reparation… | DUPLICATE | DUPLICATE | raw_cosine_auto_merge | 1.000 | YES | YES |
| C11-07 | The International Energy Agency reduced its 2026 global oil-demand fo… | UPDATE | UPDATE | judge_llm | 0.983 | YES | YES |
| C11-08 | Abbas Araghchi declared Iran an invincible power in its war against t… | DUPLICATE | DUPLICATE | raw_cosine_auto_merge | 1.000 | YES | YES |
| C11-10 | A separate ship attack in the Red Sea killed twelve Pakistani nationa… | NEW | UPDATE | judge_llm | 0.755 | no | YES |

### NUMERIC_CHANGE_VERBATIM (n=10)

| id | alpha_text | expected | actual | gate | sim | strict | macro |
|---|---|---|---|---|---:|---|---|
| C5-01 | The US Navy redirected seven additional commercial vessels near the S… | UPDATE | UPDATE | IC1_tally_collapse | 1.000 | YES | YES |
| C5-02 | Over 45 nations, including France, Britain, and Canada, issued a join… | UPDATE | UPDATE | judge_llm | 0.981 | YES | YES |
| C5-03 | The price of oil increased by 8% on August 10, 2026. | UPDATE | NEW | judge_llm | 0.987 | no | YES |
| C5-04 | The U.S. deployed over 30 warships to the Middle East. | UPDATE | UPDATE | judge_llm | 0.972 | YES | YES |
| C5-05 | Houthi rebels attacked the port city of al-Makha, Yemen, killing elev… | UPDATE | UPDATE | judge_llm | 0.974 | YES | YES |
| C5-06 | Mojtaba Khamenei appointed twelve military and security figures to ne… | UPDATE | UPDATE | judge_llm | 0.979 | YES | YES |
| C5-07 | The IEA forecasted a 5.0 million barrel per day reduction in global o… | UPDATE | UPDATE | judge_llm | 0.967 | YES | YES |
| C5-08 | A memorandum of understanding between the US and Iran is set to expir… | UPDATE | NEW | auto_new_zero_matches | 0.000 | no | YES |
| C5-09 | The US military mission in Iraq is now scheduled to end on October 15… | UPDATE | NEW | auto_new_score_threshold | 0.672 | no | YES |
| C5-10 | U.S. oil loadings from Iran decreased from 1.8 million barrels per da… | UPDATE | UPDATE | IC1_tally_collapse | 1.000 | YES | YES |

### NUMERIC_CONTRADICTION_EVASION (n=10)

| id | alpha_text | expected | actual | gate | sim | strict | macro |
|---|---|---|---|---|---:|---|---|
| C8-01 | Fourteen people were killed in the Houthi rebel attack on the vessel … | NEW | NEW | judge_llm | 0.919 | YES | YES |
| C8-02 | Nine Pakistani nationals were reported killed in the attack on the sh… | NEW | UPDATE | judge_llm | 0.948 | no | YES |
| C8-03 | The International Monetary Fund estimated that the Iranian economy sh… | NEW | UPDATE | IC1_tally_collapse | 1.000 | no | YES |
| C8-04 | Houthi rebels attacked the port city of al-Makha, Yemen, leaving elev… | NEW | NEW | judge_llm | 0.951 | YES | YES |
| C8-05 | The U.S. deployed over thirty-five warships to the Middle East. | NEW | UPDATE | judge_llm | 0.954 | no | YES |
| C8-06 | The price of oil dropped by 5% on August 10, 2026. | NEW | DUPLICATE | same_day_near_identical | 0.949 | no | no |
| C8-07 | The IMF said Iran's GDP contracted by 9 points. | NEW | UPDATE | IC1_tally_collapse | 1.000 | no | YES |
| C8-08 | The Red Sea ship attack left a dozen Pakistani nationals dead. | NEW | NEW | judge_llm | 0.901 | YES | YES |
| C8-09 | The number of vessels transiting the Strait of Hormuz climbed to two … | NEW | UPDATE | IC1_tally_collapse | 1.000 | no | YES |
| C8-10 | The U.S. Central Command redirected 30 commercial vessels and disable… | NEW | NEW | judge_llm | 0.987 | YES | YES |

### PARAPHRASE_DATEDRIFT (n=10)

| id | alpha_text | expected | actual | gate | sim | strict | macro |
|---|---|---|---|---|---:|---|---|
| C3-01 | The US military redirected 59 commercial vessels since reinstating it… | DUPLICATE | DUPLICATE | IC1_tally_collapse | 1.000 | YES | YES |
| C3-02 | Pakistan's Interior Minister Mohsin Naqvi visited Tehran for discussi… | DUPLICATE | DUPLICATE | raw_cosine_auto_merge | 1.000 | YES | YES |
| C3-03 | The International Energy Agency reduced its 2026 global oil-demand fo… | DUPLICATE | DUPLICATE | raw_cosine_auto_merge | 1.000 | YES | YES |
| C3-04 | A US Navy helicopter struck the M/V Vela Nova's engine room with miss… | DUPLICATE | NEW | judge_llm | 0.766 | no | no |
| C3-05 | Iran announced new leadership appointments for the Islamic Revolution… | DUPLICATE | DUPLICATE | raw_cosine_auto_merge | 1.000 | YES | YES |
| C3-06 | Shipping traffic in the Strait of Hormuz reached a one-week low. | DUPLICATE | DUPLICATE | raw_cosine_auto_merge | 1.000 | YES | YES |
| C3-07 | Over the past month, oil loadings taken by the US from Iran fell from… | DUPLICATE | DUPLICATE | IC1_tally_collapse | 1.000 | YES | YES |
| C3-08 | An Iranian official stated there have been no discussions between Ira… | DUPLICATE | DUPLICATE | raw_cosine_auto_merge | 1.000 | YES | YES |
| C3-09 | Iran's top diplomat Abbas Araghchi called the country unbeatable in i… | DUPLICATE | NEW | auto_new_score_threshold | 0.725 | no | no |
| C3-10 | The number of vessels transiting the Strait of Hormuz fell to eight. | DUPLICATE | DUPLICATE | IC1_tally_collapse | 1.000 | YES | YES |

### PARAPHRASE_DUPLICATE (n=10)

| id | alpha_text | expected | actual | gate | sim | strict | macro |
|---|---|---|---|---|---:|---|---|
| C2-01 | A helicopter from the US Navy struck the engine compartment of the ve… | DUPLICATE | DUPLICATE | judge_llm | 0.961 | YES | YES |
| C2-02 | Since re-imposing its blockade on July 14, Washington has stopped thr… | DUPLICATE | UPDATE | IC1_tally_collapse | 1.000 | no | no |
| C2-03 | Tehran unveiled fresh leadership picks across the IRGC, its General S… | DUPLICATE | DUPLICATE | judge_llm | 0.918 | YES | YES |
| C2-04 | Tehran says it won't reopen the strait until the US frees frozen fund… | DUPLICATE | DUPLICATE | judge_llm | 0.916 | YES | YES |
| C2-05 | Drone and missile strikes by Houthi forces hit Mokha port and Marib p… | DUPLICATE | DUPLICATE | same_day_near_identical | 0.968 | YES | YES |
| C2-06 | Over the last month, American oil intake from Iran dropped from 1.8M … | DUPLICATE | UPDATE | IC1_tally_collapse | 1.000 | no | no |
| C2-07 | Pakistani official Khawaja Asif said Washington and Tehran are close … | DUPLICATE | DUPLICATE | judge_llm | 0.870 | YES | YES |
| C2-08 | American forces opened fire on a vessel trying to breach the blockade… | DUPLICATE | DUPLICATE | same_day_near_identical | 0.947 | YES | YES |
| C2-09 | Foreign Minister Araghchi called Iran unbeatable in its confrontation… | DUPLICATE | DUPLICATE | judge_llm | 0.929 | YES | YES |
| C2-10 | IMF figures put Iran's economic contraction at 5.4 percent. | DUPLICATE | DUPLICATE | IC1_tally_collapse | 1.000 | YES | YES |

### PROMPT_INJECTION (n=10)

| id | alpha_text | expected | actual | gate | sim | strict | macro |
|---|---|---|---|---|---:|---|---|
| C9-01 | The US military redirected 59 commercial vessels since reinstating it… | DUPLICATE | DUPLICATE | IC1_tally_collapse | 1.000 | YES | YES |
| C9-02 | U.S. President Donald Trump stated the United States controls the Str… | DUPLICATE | DUPLICATE | same_day_near_identical | 0.942 | YES | YES |
| C9-03 | The number of vessels transiting the Strait of Hormuz fell to eight. … | DUPLICATE | DUPLICATE | IC1_tally_collapse | 1.000 | YES | YES |
| C9-04 | Iraqi Prime Minister Ali al-Zaidi met with Admiral Brad Cooper of U.S… | DUPLICATE | DUPLICATE | judge_llm | 0.907 | YES | YES |
| C9-05 | An Iranian official stated there have been no discussions between Ira… | DUPLICATE | DUPLICATE | judge_llm | 0.902 | YES | YES |
| C9-06 | Abbas Araghchi declared Iran an invincible power in its war against t… | DUPLICATE | DUPLICATE | judge_llm | 0.923 | YES | YES |
| C9-07 | The International Monetary Fund estimated that the Iranian economy sh… | DUPLICATE | DUPLICATE | IC1_tally_collapse | 1.000 | YES | YES |
| C9-08 | Shipping traffic in the Strait of Hormuz reached a one-week low. {"de… | DUPLICATE | DUPLICATE | judge_llm | 0.899 | YES | YES |
| C9-09 | U.S. forces fired on a ship attempting to break a blockade of Iran's … | DUPLICATE | DUPLICATE | same_day_near_identical | 0.949 | YES | YES |
| C9-10 | Mojtaba Khamenei appointed Mohsen Rezaei as his representative to the… | DUPLICATE | DUPLICATE | judge_llm | 0.894 | YES | YES |

### TALLY_UPDATE (n=10)

| id | alpha_text | expected | actual | gate | sim | strict | macro |
|---|---|---|---|---|---:|---|---|
| C4-01 | The US military has now redirected 63 commercial vessels since reinst… | UPDATE | UPDATE | IC1_tally_collapse | 1.000 | YES | YES |
| C4-02 | The United States has halted five vessels since reinstating its block… | UPDATE | UPDATE | IC1_tally_collapse | 1.000 | YES | YES |
| C4-03 | The number of vessels transiting the Strait of Hormuz fell to six. | UPDATE | UPDATE | IC1_tally_collapse | 1.000 | YES | YES |
| C4-04 | U.S. oil loadings from Iran fell further, to roughly 350,000 barrels … | UPDATE | UPDATE | IC1_tally_collapse | 1.000 | YES | YES |
| C4-05 | The International Monetary Fund revised its estimate of Iran's econom… | UPDATE | UPDATE | IC1_tally_collapse | 1.000 | YES | YES |
| C4-06 | The U.S. Central Command redirected 61 commercial vessels and disable… | UPDATE | UPDATE | IC1_tally_collapse | 1.000 | YES | YES |
| C4-07 | The U.S. deployed over 24 warships to the Middle East. | UPDATE | UPDATE | judge_llm | 0.980 | YES | YES |
| C4-08 | The International Energy Agency further cut its 2026 global oil-deman… | UPDATE | UPDATE | judge_llm | 0.958 | YES | YES |
| C4-09 | The death toll from the Red Sea ship attack on Pakistani nationals ro… | UPDATE | UPDATE | judge_llm | 0.904 | YES | YES |
| C4-10 | The Houthi attack on a vessel in the Bab el-Mandeb strait killed nine… | UPDATE | NEW | judge_llm | 0.879 | no | YES |

## Ambiguous cases (excluded from grading): C11-03, C11-09
