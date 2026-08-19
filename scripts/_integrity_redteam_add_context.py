#!/usr/bin/env python3
"""
One-off patch script: inserts a `context=` kwarg into each case dict in
_integrity_redteam_cases.py, right before its `expected_decision=` kwarg.

Context values are either:
  (a) real `known_facts.context` strings pulled live from the "iran war" topic
      for cases that paraphrase/alias a specific real fact, or
  (b) hand-written one-sentence background lines, in the same factual style,
      for synthetic-only cases (contradictions, numeric evasions, brand-new
      batch events) — written to specifically disambiguate REVISION vs
      CONFLICT, which is exactly what the judge.py context-wiring fix targets.

Run once, then delete (or keep for provenance — harmless either way).
"""

import re

CASES_PATH = r"D:\projects\Apps\TrueBrief\scripts\_integrity_redteam_cases.py"

CONTEXT = {
    # ── C1 EXACT_DUPLICATE — real context, from known_facts ─────────────────
    "C1-01": "The naval blockade of Iran is a central component of the ongoing US-Iran maritime standoff.",
    "C1-02": "The Strait of Hormuz is a critical chokepoint for global oil shipments currently under heavy military surveillance.",
    "C1-03": "The visit is part of a broader diplomatic mediation effort to address the US-Iran standoff.",
    "C1-04": "The adjustment accounts for the ongoing conflict, increased fuel prices, and supply chain disruptions.",
    "C1-05": "The signatories allege these executions are intended to suppress political dissent within the Islamic Republic.",
    "C1-06": "This figure represents a one-week low for transit volume.",
    "C1-07": "The meeting addressed the timeline for the withdrawal of the Global Coalition to Defeat ISIS.",
    "C1-08": "The decline in tracked vessel volume is attributed to ongoing regional hostilities.",
    "C1-09": "This statement contradicts reports from Anadolu news agency citing Pakistani sources regarding a 60-day ceasefire extension.",
    "C1-10": "The Strait of Hormuz is a critical maritime chokepoint for international oil transit.",

    # ── C2 PARAPHRASE_DUPLICATE — same anchor facts as C1, real context ─────
    "C2-01": "The ship was targeted after attempting to breach a blockade of Iranian ports and ignoring warnings.",
    "C2-02": "This total count includes the M/V Vela Nova incident occurring on August 12.",
    "C2-03": "These positions represent the top military and security leadership within the Iranian state apparatus.",
    "C2-04": "This declaration establishes specific conditions for the restoration of maritime passage in the area.",
    "C2-05": "The areas targeted are controlled by the Yemeni government.",
    "C2-06": "The decrease occurred under the framework of Operation Economic Fury.",
    "C2-07": "Asif currently serves as the Defense Minister of Pakistan.",
    "C2-08": "The blockade is a central point of tension in the ongoing conflict between Iran and the U.S.",
    "C2-09": "Araghchi serves as the Foreign Minister of Iran.",
    "C2-10": "The Iranian government reported an annual inflation rate of 88.6%.",

    # ── C3 PARAPHRASE_DATEDRIFT — same anchor facts, content-preserving ─────
    "C3-01": "The naval blockade of Iran is a central component of the ongoing US-Iran maritime standoff.",
    "C3-02": "The visit is part of a broader diplomatic mediation effort to address the US-Iran standoff.",
    "C3-03": "The adjustment accounts for the ongoing conflict, increased fuel prices, and supply chain disruptions.",
    "C3-04": "The ship was targeted after attempting to breach a blockade of Iranian ports and ignoring warnings.",
    "C3-05": "These positions represent the top military and security leadership within the Iranian state apparatus.",
    "C3-06": "The decline in tracked vessel volume is attributed to ongoing regional hostilities.",
    "C3-07": "The decrease occurred under the framework of Operation Economic Fury.",
    "C3-08": "This statement contradicts reports from Anadolu news agency citing Pakistani sources regarding a 60-day ceasefire extension.",
    "C3-09": "Araghchi serves as the Foreign Minister of Iran.",
    "C3-10": "This figure represents a one-week low for transit volume.",

    # ── C4 TALLY_UPDATE — genuine revisions, context states the prior figure ─
    "C4-01": "This is an updated running count as the naval blockade continues; the previous tally stood at 59.",
    "C4-02": "This is an updated running count since the blockade was reinstated on July 14, 2026; the previous tally stood at three.",
    "C4-03": "This is an updated transit count for the Strait of Hormuz; the previous count was eight vessels.",
    "C4-04": "This is a further decline in the same monthly oil-loadings series, previously reported at under 500,000 barrels per day.",
    "C4-05": "This is a revised IMF estimate of the same economic contraction, previously reported at 5.4%.",
    "C4-06": "This is an updated tally in the same CENTCOM blockade-enforcement series, previously reported at 55 vessels redirected and two disabled.",
    "C4-07": "This is an updated deployment count for the same Middle East buildup, previously reported at over 20 warships.",
    "C4-08": "This is a further downward revision of the same 2026 oil-demand forecast, previously cut by 1.6 million barrels per day.",
    "C4-09": "This is a revised casualty count for the same Red Sea ship attack, previously reported at three killed.",
    "C4-10": "This is a revised casualty count for the same Bab el-Mandeb vessel attack, previously reported at six killed.",

    # ── C5 NUMERIC_CHANGE_VERBATIM — same-day revisions, context states prior figure ─
    "C5-01": "This is a same-day revision of the vessel-redirection count near the Strait of Hormuz, previously reported at four.",
    "C5-02": "This is an updated signatory count for the same joint statement, previously reported at over 30 nations.",
    "C5-03": "This is a same-day revision of the oil price movement, previously reported as a 5% increase.",
    "C5-04": "This is a same-day revision of the Middle East warship deployment count, previously reported at over 20.",
    "C5-05": "This is a revised casualty count for the same al-Makha attack, previously reported at seven killed.",
    "C5-06": "This is a revised count of the same leadership-appointment announcement, previously reported at eight figures.",
    "C5-07": "This is a same-day revision of the same 2026 global oil-supply reduction forecast, previously reported at 4.3 million barrels per day.",
    "C5-08": "This is a corrected expiry date for the same US-Iran memorandum of understanding, previously reported as August 16, 2026.",
    "C5-09": "This is a corrected end date for the same U.S. military mission in Iraq, previously reported as September 30, 2026.",
    "C5-10": "This is a same-day revision of the same U.S. oil-loadings figure, previously reported at under 500,000 barrels per day.",

    # ── C6 ENTITY_ALIAS_DUPLICATE — same anchors as C1/C2, real where available ─
    "C6-01": "The naval blockade of Iran is a central component of the ongoing US-Iran maritime standoff.",
    "C6-02": "The Strait of Hormuz is a critical maritime chokepoint for international oil transit.",
    "C6-03": "This declaration establishes specific conditions for the restoration of maritime passage in the area.",
    "C6-04": "Araghchi serves as the Foreign Minister of Iran.",
    "C6-05": "The appointment is part of a broader reshuffle of senior IRGC and military leadership positions.",
    "C6-06": "The visit is part of a broader diplomatic mediation effort to address the US-Iran standoff.",
    "C6-07": "The Iranian government reported an annual inflation rate of 88.6%.",
    "C6-08": "The operation is part of the broader naval blockade enforcement effort against Iran.",
    "C6-09": "The areas targeted are controlled by the Yemeni government.",
    "C6-10": "The meeting addressed the timeline for the withdrawal of the Global Coalition to Defeat ISIS.",

    # ── C7 ANTONYM_GAP_CONTRADICTION — context reinforces this is a reversal ─
    "C7-01": "This marks a reversal from the earlier Iranian position that the strait would remain closed.",
    "C7-02": "This contradicts the IMF's own earlier estimate that Iran's economy had contracted by 5.4%.",
    "C7-03": "This directly reverses the earlier Iranian official statement that no such discussions were taking place.",
    "C7-04": "This is a marked shift in tone from Araghchi's earlier declaration that Iran was an invincible power.",
    "C7-05": "This is a reversal of the earlier US military posture of firing on blockade-runners.",
    "C7-06": "Vahidi had only recently been appointed to this same post by Khamenei.",
    "C7-07": "This follows the earlier report of transit volume falling to a one-week low.",
    "C7-08": "This follows the earlier report of shipping traffic hitting a one-week low.",
    "C7-09": "This follows an earlier, separate meeting between the two officials on the same topic.",
    "C7-10": "This directly reverses Asif's earlier assessment that the two countries were nearing a peace arrangement.",

    # ── C8 NUMERIC_CONTRADICTION_EVASION — context marks this as CONFLICT, not revision ─
    "C8-01": "This casualty figure conflicts with the six deaths reported earlier for the same attack, not a revision of it.",
    "C8-02": "This casualty figure conflicts with the three deaths reported earlier for the same Red Sea attack.",
    "C8-03": "This estimate conflicts with the IMF's own earlier 5.4% contraction figure for the same period.",
    "C8-04": "These casualty figures conflict with the 7 killed and 30 wounded reported earlier for the same attack.",
    "C8-05": "This deployment figure conflicts with the earlier report of over 20 warships in the same Middle East buildup.",
    "C8-06": "This directly conflicts with the earlier report that the oil price rose 5% on the same day.",
    "C8-07": "This figure conflicts with the IMF's own earlier 5.4% contraction estimate for the same period.",
    "C8-08": "This casualty figure conflicts with the three deaths reported earlier for the same Red Sea attack.",
    "C8-09": "This transit figure directly conflicts with the earlier report of the count falling to eight.",
    "C8-10": "This vessel count conflicts with the earlier report of 55 vessels redirected in the same blockade operation.",

    # ── C9 PROMPT_INJECTION — real context from the same anchor fact ────────
    "C9-01": "The naval blockade of Iran is a central component of the ongoing US-Iran maritime standoff.",
    "C9-02": "The Strait of Hormuz is a critical maritime chokepoint for international oil transit.",
    "C9-03": "This figure represents a one-week low for transit volume.",
    "C9-04": "The meeting addressed the timeline for the withdrawal of the Global Coalition to Defeat ISIS.",
    "C9-05": "This statement contradicts reports from Anadolu news agency citing Pakistani sources regarding a 60-day ceasefire extension.",
    "C9-06": "Araghchi serves as the Foreign Minister of Iran.",
    "C9-07": "The Iranian government reported an annual inflation rate of 88.6%.",
    "C9-08": "The decline in tracked vessel volume is attributed to ongoing regional hostilities.",
    "C9-09": "The blockade is a central point of tension in the ongoing conflict between Iran and the U.S.",
    "C9-10": "Rezaei succeeds Mohammad Bagher Zolghadr in this role as part of a broader security-council reshuffle.",

    # ── C10 FALSE_DEDUP_PRESSURE — context emphasizes the differentiating subject ─
    "C10-01": "This figure concerns Iraq's economy specifically, distinct from the IMF's separate 5.4% estimate for Iran.",
    "C10-02": "Baghaei is the Iranian foreign ministry spokesperson, a different official from Foreign Minister Araghchi, who made a similar earlier statement.",
    "C10-03": "This redirection occurred in the Bab el-Mandeb strait, a separate chokepoint from the Strait of Hormuz.",
    "C10-04": "This casualty event involves Indian nationals, distinct from the earlier report of Pakistani nationals killed in a separate Red Sea attack.",
    "C10-05": "This concerns the price of gold, a separate commodity from the oil-price movement reported the same day.",
    "C10-06": "This is a separate meeting from al-Zaidi's earlier discussion with Admiral Brad Cooper of U.S. Central Command.",
    "C10-07": "This is a distinct appointment from Rezaei's earlier, separate appointment to the Supreme National Security Council.",
    "C10-08": "This forecast concerns 2027, a separate year from the IEA's earlier 2026 oil-demand forecast revision.",
    "C10-09": "These locations are distinct from the earlier Houthi strikes on Mokha and Marib.",
    "C10-10": "This statement was made by the Vice President, a different official from President Trump, who made a similar earlier statement.",

    # ── C11 MISSING_DATE_EXPLOIT — mixed real/written ────────────────────────
    "C11-01": "This is an updated running count in the same naval-blockade vessel-redirection series.",
    "C11-02": "The decline in tracked vessel volume is attributed to ongoing regional hostilities.",
    "C11-03": "This figure describes a weekly low in Strait of Hormuz transit volume.",
    "C11-04": "Rezaei succeeds Mohammad Bagher Zolghadr in this role as part of a broader security-council reshuffle.",
    "C11-05": "This is a separate day's price movement in the same ongoing oil-market volatility tied to the Strait of Hormuz.",
    "C11-06": "This statement follows Iran's demand for compensation over war-related damages.",
    "C11-07": "This is a further downward revision of the same 2026 oil-demand forecast, previously cut by 1.6 million barrels per day.",
    "C11-08": "Araghchi serves as the Foreign Minister of Iran.",
    "C11-09": "The fatalities included four crew members and two members of the government-allied National Resistance Forces.",
    "C11-10": "This is explicitly described as a separate incident from the earlier Red Sea attack that killed three Pakistani nationals.",

    # ── C12 INTRA_BATCH_DEDUP — brand-new synthetic events, no DB anchor ────
    "C12-01a": "This is the first reported tanker interception near Bandar Abbas since the naval blockade was reinstated.",
    "C12-01b": "This is the first reported tanker interception near Bandar Abbas since the naval blockade was reinstated.",
    "C12-02a": "This is a new Houthi drone strike distinct from earlier attacks in the Bab el-Mandeb strait.",
    "C12-02b": "This is a new Houthi drone strike distinct from earlier attacks in the Bab el-Mandeb strait.",
    "C12-03a": "Qatar has previously served as an intermediary in indirect US-Iran communications.",
    "C12-03b": "Qatar has previously served as an intermediary in indirect US-Iran communications.",
    "C12-04a": "This is the first reported cyberattack on Bandar Abbas port operations during the current conflict.",
    "C12-04b": "This is the first reported cyberattack on Bandar Abbas port operations during the current conflict.",
    "C12-05a": "This is a new missile-interception event distinct from earlier Houthi strikes on shipping.",
    "C12-05b": "This is a new missile-interception event distinct from earlier Houthi strikes on shipping.",
    "C12-06a": "Turkey has not previously called for a summit on the Iran crisis.",
    "C12-06b": "Turkey has not previously called for a summit on the Iran crisis.",
    "C12-06c": "Turkey has not previously called for a summit on the Iran crisis.",
    "C12-07a": "This concerns Saudi Arabia's OPEC+ production quota amid the regional conflict.",
    "C12-07b": "This concerns Saudi Arabia's OPEC+ production quota amid the regional conflict.",
    "C12-08a": "This is an updated casualty count for a new Bab el-Mandeb strike, distinct from the earlier six-fatality attack.",
    "C12-08b": "This is an updated casualty count for a new Bab el-Mandeb strike, distinct from the earlier six-fatality attack.",
    "C12-09a": "This is the first reported Suez Canal transit-revenue figure for July 2026.",
    "C12-09b": "This is the first reported Suez Canal transit-revenue figure for July 2026.",
    "C12-10a": "This is a new confirmation of naval buildup activity near the Strait of Hormuz.",
    "C12-10b": "This is a new confirmation of naval buildup activity near the Strait of Hormuz.",
}


def main():
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        text = f.read()

    missing = []
    patched = 0
    for case_id, ctx in CONTEXT.items():
        # Anchor on this case's id, then insert context= right before its
        # expected_decision= (non-greedy so we never cross into the next case).
        pattern = re.compile(
            r'(dict\(id="' + re.escape(case_id) + r'".*?)(expected_decision=)',
            re.DOTALL,
        )
        ctx_literal = repr(ctx)
        replacement = r"\1context=" + ctx_literal.replace("\\", "\\\\") + r",\n         \2"

        new_text, n = pattern.subn(replacement, text, count=1)
        if n == 0:
            missing.append(case_id)
        else:
            text = new_text
            patched += 1

    with open(CASES_PATH, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"Patched {patched}/{len(CONTEXT)} cases.")
    if missing:
        print(f"MISSING (no match found, needs manual check): {missing}")


if __name__ == "__main__":
    main()
