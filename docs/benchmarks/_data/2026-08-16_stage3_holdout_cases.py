"""
Stage 3 holdout adversarial set — 2026-08-16 "harsh hacker" check.

24 NEW cases, none reused from the original 131 (scripts/_integrity_redteam_cases.py),
none reusing that file's exact wording. Anchored against real, live known_facts rows on
the "iran war" topic (verified live via Supabase reads during this session) so retrieval
is realistic, but every attack sentence and every number/antonym/metric word choice is
new — specifically targeting number-words, antonym-pairs, and metric-words NOT exercised
by scripts/tests/test_number_normalizer.py or contradiction.py's ANTONYM_PAIRS/METRIC_KEYWORDS.

Singles run via judge_alpha(); H19/H20/H21 are same-batch pairs run via judge_alphas()
(no real DB anchor for these — same convention as C12 in the original redteam set).
"""
from datetime import datetime

TOPIC_ID = "dd67825c-552d-4606-bfdd-9bc538783fba"  # "iran war"


def d(s):
    return datetime.fromisoformat(s)


CASES = [
    # ── (a) spelled-out-number tally/duplicate — words NOT in test_number_normalizer.py ──
    dict(id="H1", category="HOLDOUT_SPELLED_NUMBER_DUP",
         alpha_text="The US military has redirected fifty-nine commercial vessels in total since reinstating its naval blockade on Iran.",
         entities=["US military", "Iran"], event_date=d("2026-08-13"), event_class="tally",
         expected_decision="DUPLICATE",
         note="Same tally value (59) as a real stored fact, spelled out as 'fifty-nine' — must not be missed as a real duplicate."),
    dict(id="H2", category="HOLDOUT_SPELLED_NUMBER_REVISION",
         alpha_text="The United States has halted nineteen vessels since reinstating its blockade on July 14, 2026.",
         entities=["United States"], event_date=d("2026-08-14"), event_class="tally",
         expected_decision="UPDATE",
         note="Real tally revision vs a stored 'three vessels' fact, new count spelled 'nineteen' — must register as a genuine change."),
    dict(id="H3", category="HOLDOUT_SPELLED_NUMBER_NEARDUP",
         alpha_text="Near the Strait of Hormuz, the US Navy redirected seventeen more commercial vessels.",
         entities=["US Navy", "Strait of Hormuz"], event_date=d("2026-08-13"), event_class="tally",
         expected_decision="UPDATE",
         note="Near-verbatim template match vs a stored 'four additional commercial vessels' fact, real count change spelled 'seventeen' — must not silently auto-merge as a duplicate."),
    dict(id="H4", category="HOLDOUT_SPELLED_NUMBER_SAMEDAY",
         alpha_text="The U.S. has deployed over ninety warships to the Middle East, officials confirmed.",
         entities=["U.S.", "Middle East"], event_date=d("2026-08-10"), event_class="tally",
         expected_decision="UPDATE",
         note="Same day as a stored 'over 20 warships' fact, real count change spelled 'ninety' — must not auto-merge on same-day+high-similarity alone."),
    dict(id="H5", category="HOLDOUT_SPELLED_NUMBER_DUP",
         alpha_text="The Houthi assault on al-Makha left seven dead and thirty injured.",
         entities=["Houthi", "al-Makha", "Yemen"], event_date=d("2026-08-10"), event_class="casualty",
         expected_decision="DUPLICATE",
         note="Same casualty counts (7 dead, 30 injured) as a stored fact, reworded/compressed — must be caught as a real duplicate."),

    # ── (b) antonym-style contradictions — word pairs NOT in ANTONYM_PAIRS ──────────────
    dict(id="H7", category="HOLDOUT_ANTONYM_GAP",
         alpha_text="Tehran's blockade on the Strait of Hormuz has fully subsided, with normal shipping traffic resuming.",
         entities=["Iran", "Washington"], event_date=d("2026-08-12"), event_class="state_change",
         expected_decision="NEW",
         note="Reversal of a stored 'will remain closed' claim — 'subsided'/'resuming' vs 'closed' is not an ANTONYM_PAIRS entry."),
    dict(id="H8", category="HOLDOUT_ANTONYM_GAP",
         alpha_text="Abbas Araghchi admitted Iran feels increasingly isolated and outmatched in its confrontation with the United States and Israel.",
         entities=["Abbas Araghchi", "Iran", "United States", "Israel"], event_date=d("2026-08-11"), event_class="state_change",
         expected_decision="NEW",
         note="Direct reversal of a stored 'invincible power' claim — 'isolated and outmatched' vs 'invincible' is not a listed pair."),
    dict(id="H9", category="HOLDOUT_ANTONYM_GAP",
         alpha_text="Iran's Supreme Leader stripped Ahmad Vahidi of his command over the IRGC.",
         entities=["Mojtaba Khamenei", "Ahmad Vahidi", "IRGC"], event_date=d("2026-08-10"), event_class="state_change",
         expected_decision="NEW",
         note="Reversal of a stored appointment of Vahidi as IRGC commander — 'stripped of command' vs 'appointed' is not hired/fired."),
    dict(id="H10", category="HOLDOUT_ANTONYM_GAP",
         alpha_text="Pakistan's Interior Minister Mohsin Naqvi abruptly canceled his planned visit to Tehran amid rising tensions.",
         entities=["Mohsin Naqvi", "Pakistan", "Tehran", "Iran"], event_date=d("2026-08-13"), event_class="state_change",
         expected_decision="NEW",
         note="Direct reversal of a stored fact that Naqvi visited Tehran — 'canceled his planned visit' vs 'visited' is not a listed pair."),
    dict(id="H11", category="HOLDOUT_ANTONYM_GAP",
         alpha_text="Iraqi Prime Minister Ali al-Zaidi's office confirmed the planned meeting with Admiral Brad Cooper never took place.",
         entities=["Ali al-Zaidi", "Brad Cooper", "U.S. Central Command"], event_date=d("2026-08-12"), event_class="state_change",
         expected_decision="NEW",
         note="Direct reversal of a stored meeting fact — 'never took place' vs 'met with' is not a listed pair."),
    dict(id="H12", category="HOLDOUT_ANTONYM_GAP",
         alpha_text="Shipping traffic in the Strait of Hormuz has come roaring back, hitting its busiest point in weeks.",
         entities=["Strait of Hormuz"], event_date=d("2026-08-12"), event_class="state_change",
         expected_decision="NEW",
         note="Reversal of a stored 'one-week low' claim — 'busiest point in weeks' vs 'low' is not a listed pair."),

    # ── (c) same-day near-identical, DIFFERENT subject — must not auto-merge ───────────
    dict(id="H13", category="HOLDOUT_SAMEDAY_DIFF_SUBJECT",
         alpha_text="The US Navy redirected four additional commercial vessels near the Bab el-Mandeb strait.",
         entities=["US Navy", "Bab el-Mandeb strait"], event_date=d("2026-08-13"), event_class="escalation",
         expected_decision="NEW",
         note="Same template/number as a stored Strait-of-Hormuz fact, different STRAIT, same day — must not merge on matching numbers alone."),
    dict(id="H14", category="HOLDOUT_SAMEDAY_DIFF_SUBJECT",
         alpha_text="Houthi rebels attacked the port city of Hodeidah, Yemen, killing seven people and wounding 30 others.",
         entities=["Houthi", "Hodeidah", "Yemen"], event_date=d("2026-08-10"), event_class="casualty",
         expected_decision="NEW",
         note="Same casualty counts as a stored al-Makha attack, different PORT CITY, same day — coincidental count match, not the same event."),
    dict(id="H15", category="HOLDOUT_SAMEDAY_DIFF_SUBJECT",
         alpha_text="The U.S. deployed over 20 warships to the Indo-Pacific.",
         entities=["U.S.", "Indo-Pacific"], event_date=d("2026-08-10"), event_class="escalation",
         expected_decision="NEW",
         note="Same count as a stored Middle-East warship deployment, different REGION, same day."),
    dict(id="H16", category="HOLDOUT_SAMEDAY_DIFF_SUBJECT",
         alpha_text="The number of vessels transiting the Bab el-Mandeb strait fell to eight.",
         entities=["Bab el-Mandeb strait"], event_date=d("2026-08-12"), event_class="tally",
         expected_decision="NEW",
         note="Same count (eight) as a stored Strait-of-Hormuz tally, different STRAIT, same day — entity-overlap guard must block the merge."),
    dict(id="H17", category="HOLDOUT_SAMEDAY_DIFF_SUBJECT",
         alpha_text="OPEC reduced its 2026 global oil-demand forecast by 1.6 million barrels per day.",
         entities=["OPEC"], event_date=d("2026-08-13"), event_class="development",
         expected_decision="NEW",
         note="Same figure as a stored IEA forecast, different ORGANIZATION making the claim, same day."),

    # ── (d) numeric conflicts using metric words NOT in METRIC_KEYWORDS ─────────────────
    dict(id="H18", category="HOLDOUT_METRIC_WORD_GAP",
         alpha_text="The U.S. has deployed forty-one warships to the Middle East, defense officials said Monday.",
         entities=["U.S.", "Middle East"], event_date=d("2026-08-10"), event_class="development",
         expected_decision="NEW",
         note="Conflicts with a stored 'over 20 warships' fact, same day — 'warships' is not a METRIC_KEYWORD, so IC4's keyword gate structurally cannot fire; this tests the Judge alone."),
]

# Batch pairs (no real DB anchor — same-batch-only conflict, mirrors C12's convention).
BATCH_CASES = [
    [
        dict(id="H19a", category="HOLDOUT_METRIC_WORD_GAP", batch_group="HB1", batch_order=1,
             alpha_text="Local officials said twelve detainees were released from the makeshift camp near the border on August 15, 2026.",
             entities=["Iran", "Israel"], event_date=d("2026-08-15"), event_class="development",
             expected_decision="NEW", note="First of a same-batch pair; nothing before it."),
        dict(id="H19b", category="HOLDOUT_METRIC_WORD_GAP", batch_group="HB1", batch_order=2,
             alpha_text="Local officials revised the number of detainees released from the SAME camp near the border to twenty-eight on August 15, 2026.",
             entities=["Iran", "Israel"], event_date=d("2026-08-15"), event_class="development",
             expected_decision="NEW",
             note="Same-day conflicting count on 'detainees' (not a METRIC_KEYWORD) for the SAME incident as H19a, in the SAME batch — must not be silently absorbed as an update of H19a."),
    ],
    [
        dict(id="H20a", category="HOLDOUT_METRIC_WORD_GAP", batch_group="HB2", batch_order=1,
             alpha_text="Air traffic authorities said six aircraft were grounded at the airbase following the incident on August 15, 2026.",
             entities=["Iran"], event_date=d("2026-08-15"), event_class="development",
             expected_decision="NEW", note="First of a same-batch pair; nothing before it."),
        dict(id="H20b", category="HOLDOUT_METRIC_WORD_GAP", batch_group="HB2", batch_order=2,
             alpha_text="Air traffic authorities said nineteen aircraft were grounded at the airbase following the SAME incident on August 15, 2026.",
             entities=["Iran"], event_date=d("2026-08-15"), event_class="development",
             expected_decision="NEW",
             note="Same-day conflicting count on 'aircraft' (not a METRIC_KEYWORD) for the SAME incident as H20a, in the SAME batch."),
    ],
    [
        dict(id="H21a", category="HOLDOUT_METRIC_WORD_GAP", batch_group="HB3", batch_order=1,
             alpha_text="Port officials said the tanker was carrying eighty thousand barrels of crude when it was intercepted on August 15, 2026.",
             entities=["Iran", "Strait of Hormuz"], event_date=d("2026-08-15"), event_class="development",
             expected_decision="NEW", note="First of a same-batch pair; nothing before it."),
        dict(id="H21b", category="HOLDOUT_METRIC_WORD_GAP", batch_group="HB3", batch_order=2,
             alpha_text="Port officials revised the SAME tanker's cargo estimate to one hundred forty thousand barrels of crude following the interception on August 15, 2026.",
             entities=["Iran", "Strait of Hormuz"], event_date=d("2026-08-15"), event_class="development",
             expected_decision="NEW",
             note="Same-day conflicting count on 'barrels' (bare, no 'million'/'billion' — not a METRIC_KEYWORD) for the SAME tanker as H21a, in the SAME batch."),
    ],
]
