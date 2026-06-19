# Benchmark — "Iran War" · TrueBrief vs GPT · 2026-06-19

> Head-to-head on the same topic, same day. Source of roadmap §2.5 (IC1–IC8) and architecture red light #5.
> This file is the **golden-set seed** for IC8 / A.2: the labeled failures at the bottom are the assertions the harness must enforce.

---

## Scorecard (neutral)

| Front | GPT | TrueBrief | Note |
|---|---|---|---|
| Lede / signal priority | 9 | 3 | GPT led with the signed US–Iran framework + ceasefire; TB led with "4 soldiers killed", framework never a headline |
| Noise control | 8 | 4 | TB surfaced cumulative casualty tallies as new deltas |
| Completeness of detail | 6 | 8 | TB carries exact dated/sourced specifics GPT lacks |
| Missing critical signal | 8 | 3 | TB missed/buried the headline (framework, ceasefire, 60-day track, IRGC-Iraq cells) |
| Accuracy / provenance / trust | 4 | 8 | **TB win** — every fact dated + sourced; GPT "reportedly", unsourced, may fabricate |
| Dedup (core moat) | 8 | 3 | **TB visible failure** — "4 soldiers killed" shown twice |
| Synthesis / "so what" | 9 | 2 | GPT's ✅/⚠️ checklist + risk line; TB none |
| Presentation | 8 | 5 | GPT separates arc from status; TB flat list, rigid labels, doubled chips |

**Verdict:** for a general reader GPT's brief was more useful today (lede + tight + synthesized). TB wins only on provenance/granularity — the *second* need, not the first. Goal is **not** to imitate GPT's ungrounded prose; it's GPT-style prioritization + a thin grounded synthesis layer **on top of** our sourced facts.

---

## GPT output (verbatim)

Iran War – Latest Major Updates (19 June 2026). Israel and Hezbollah agreed to a ceasefire scheduled to begin today 4:00 PM local, mediated by US and Qatar with Iran assistance. Broader US–Iran war in a diplomatic phase: June 17 US–Iran signed a memorandum to end hostilities + begin a 60-day negotiation (nuclear + sanctions). Tensions high despite the agreement; Israel unhappy, continued operations in Lebanon, friction with Washington. Iran reportedly re-closed the Strait of Hormuz today (conditions not met) — threatens oil shipping, disrupted talks. US–Iran nuclear talks today postponed/cancelled. Reuters: IRGC established covert armed cells in Iraq that carried out drone attacks on Gulf countries hosting US forces. War expanded beyond Israel/Iran — Iran claimed attacks on US bases in Kuwait, Bahrain, Jordan after US strikes inside Iran. Sporadic exchanges continue; Iran launched missiles toward Israel June 7 after an Israeli strike in Beirut.

Situation Summary: ✅ US–Iran peace framework signed · ✅ Israel–Hezbollah ceasefire announced today · ⚠️ Strait of Hormuz tensions escalating again · ⚠️ Nuclear talks delayed · ⚠️ Regional proxy activity in Iraq. Biggest risk: whether the new agreement survives the next few days without either side resuming major operations.

---

## TrueBrief output (verbatim, condensed structure)

- **Israeli Casualties in Lebanon** — Four Israeli soldiers killed in Lebanon, first Israeli fatalities since the US-Iran deal (deccanherald). · Four Israeli soldiers killed in combat vs Hezbollah on June 19, 2026 (bbc). ← **same event, two rows**
- **Lebanon Strike Impact** — ≥18 killed in Israeli strikes in S. Lebanon overnight Jun 18–19 (bbc).
- **US-Israel Diplomatic Friction** — VP JD Vance criticized Israeli cabinet (incl. Ben-Gvir) over opposition to the peace deal (bbc).
- **Conflict Casualty Estimates** — >7,300 killed in Iran+Lebanon since Feb 28 (bbc). · IRNA 3,468 Iranian deaths as of Apr 26; HRANA 3,636 as of May 18 (bbc). ← **tallies as "new"**
- **International / US Personnel Losses** — 7 UN peacekeepers killed (latest Jun 4) (bbc). · 13 US personnel killed as of Jun 2026 (bbc).
- **Strait of Hormuz and Diplomacy** — Oil tankers began moving through Hormuz after the US-Iran interim deal (deccanherald). ← **contradicts GPT's "re-closed"**
- **Hezbollah-Israel Combat** — Hezbollah reported destroying Israeli tanks in S. Lebanon (deccanherald).
- **High-Level Diplomatic Stalls** — White House confirmed Jun 18 that VP Vance won't travel to Switzerland (bbc).
- **Regional Casualty Updates** — Lebanon strike deaths reached 3,912; 60 killed in Israel as of Jun 18 (bbc). ← **another tally; conflicts with 7,300 combined**

---

## Labeled failures → golden-set assertions (IC8 / A.2)

1. **Buried lede** — the signed US–Iran framework + Israel–Hezbollah ceasefire must rank in the top items, above casualty counts. → IC2 (`event_class` ranking).
2. **Tally-noise** — the ≥5 cumulative casualty figures (7,300; 3,468; 3,636; 3,912; 60; 13; 7) must collapse to ≤1 living "toll" fact per metric, classed `tally`/background, never leading. → IC1.
3. **Dedup miss** — "4 Israeli soldiers killed" must be one fact (`verified_count=2`), not two rows. → IC3.
4. **Contradiction shown deadpan** — Hormuz "tankers moving through" vs (reality/GPT) "re-closed", and the non-reconciling toll figures, must be flagged, not listed flat. → IC4.
5. **No synthesis** — a grounded "state of play" header (status of open threads) must be present. → IC7.
6. **Presentation** — no `WHAT'S NEW/FULL CONTEXT` labels; one chip per outlet; importance hierarchy. → IC5/IC6.
