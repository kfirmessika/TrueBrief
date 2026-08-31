"""
All LLM prompts used across the TrueBrief pipeline, in one place.
Grouped by pipeline stage. Each section notes the model tier it runs on
(see config/settings.py LLM_CONFIG for the authoritative step_name -> model mapping).

Static prompts are string constants. Prompts assembled with interpolation or
conditional logic are build_<stage>_prompt(...) functions that take plain
strings/primitives only — never domain objects — so this module has zero
imports from the rest of truebrief and can't create circular imports.
"""


# ============================================================
# STAGE: topic_finisher (experimental, scripts/topic_finisher_experiment.py) —
# Gemini flash-lite (cheap). NOT wired into any pipeline stage or route.
# ============================================================
# topics.raw_query is currently stored verbatim and used BOTH as the UI display name
# AND as the literal search prompt fed to Gemini Search grounding (build_gemini_search_
# prompt's topic_name arg) — there is no cleanup step today. These three candidate
# strategies are being evaluated (see scripts/topic_finisher_experiment.py) to fix that,
# without touching the live gemini_search / query_builder call sites.

# --- Strategy A: one combined call -> {"name": ..., "search_prompt": ...} ---

TOPIC_FINISHER_COMBINED_SYSTEM = (
    "You are the TrueBrief Topic Finisher. Given a user's messy topic-tracking input, "
    "produce a short display name and a well-formed search query, both faithful to what "
    "the user actually meant."
)


def build_topic_finisher_combined_prompt(raw_query: str) -> str:
    """Strategy A: single call returns both the UI name and the search prompt.

    Args:
        raw_query: the user's raw, possibly messy topic-creation text.
    """
    return f"""
The user typed this into a "track this topic" box: '{raw_query}'

TASK:
1. "name": a short 2-5 word UI display name for this topic — clean, human-readable,
   Title Case, not truncated garbage, not overly generic (avoid bare words like "News"
   or "Topic"). Fix spelling but do NOT invent a narrower or broader topic than intended.
2. "search_prompt": a well-formed search query/prompt suitable for a live web search
   grounded on recent news — fix spelling and grammar, disambiguate if the input is
   terse or ambiguous, but stay faithful to the user's original intent. Do not pad it
   with unrelated keywords.

Return ONLY this JSON (no markdown, no extra keys):
{{
  "name": "Short Display Name",
  "search_prompt": "well-formed search query text"
}}
"""


# --- Strategy B: two separate cheap calls (name only, then search_prompt only) ---

TOPIC_FINISHER_NAME_SYSTEM = (
    "You are the TrueBrief Topic Finisher. Given a user's messy topic-tracking input, "
    "produce ONLY a short display name for it."
)


def build_topic_finisher_name_prompt(raw_query: str) -> str:
    """Strategy B, call 1 of 2: produce ONLY the short UI display name."""
    return f"""
The user typed this into a "track this topic" box: '{raw_query}'

Produce a short 2-5 word UI display name for this topic — clean, human-readable, Title
Case, not truncated garbage, not overly generic (avoid bare words like "News" or
"Topic"). Fix spelling but do NOT invent a narrower or broader topic than intended.

Return ONLY this JSON (no markdown, no extra keys):
{{"name": "Short Display Name"}}
"""


TOPIC_FINISHER_SEARCH_SYSTEM = (
    "You are the TrueBrief Topic Finisher. Given a user's messy topic-tracking input, "
    "produce ONLY a well-formed search query for it."
)


def build_topic_finisher_search_prompt(raw_query: str) -> str:
    """Strategy B, call 2 of 2: produce ONLY the search prompt."""
    return f"""
The user typed this into a "track this topic" box: '{raw_query}'

Produce a well-formed search query/prompt suitable for a live web search grounded on
recent news — fix spelling and grammar, disambiguate if the input is terse or
ambiguous, but stay faithful to the user's original intent. Do not pad it with
unrelated keywords.

Return ONLY this JSON (no markdown, no extra keys):
{{"search_prompt": "well-formed search query text"}}
"""


# --- Strategy C: one call, one corrected string reused as both name and search_prompt ---

TOPIC_FINISHER_CORRECTED_SYSTEM = (
    "You are the TrueBrief Topic Finisher. Given a user's messy topic-tracking input, "
    "fix ONLY spelling/grammar errors — do not expand, rename, or add words."
)


def build_topic_finisher_corrected_prompt(raw_query: str) -> str:
    """Strategy C: single output, reused as both UI name and search prompt.

    Minimal cleanup of the raw user input — no rewriting.
    """
    return f"""
The user typed this into a "track this topic" box: '{raw_query}'

Fix ONLY spelling and grammar errors. Do NOT expand, rename, or add words. Do NOT
change what the topic is about. If there are no errors, return the input unchanged
(only trim stray whitespace).
Examples: "isreal" -> "israel", "nvida stok" -> "nvidia stock", "us" -> "us".

Return ONLY this JSON (no markdown, no extra keys):
{{"corrected_query": "cleaned version of the input"}}
"""



# ============================================================
# STAGE: arbiter — Gemini flash-lite (cheap)
# ============================================================

ARBITER_SYSTEM = """\
You are a precision news intelligence arbiter. Your job is to determine whether a new fact
duplicates, updates, or is entirely different from known stored facts.

Rules (apply strictly):
1. A change in numbers is either a REVISION or a CONFLICT — decide which before choosing UPDATE:
   - REVISION (-> UPDATE): the new fact is a LATER report of the SAME cumulative/running
     measurement continuing forward from the known fact (a death toll climbing from 20 to 25
     over time, a vessel count growing day over day). The new number must be a genuinely new
     figure, not the same one re-stated or a subset of it.
   - CONFLICT (-> NEW, never UPDATE, never MERGE): the new fact and the known fact both describe
     the SAME specific moment or incident, but report DIFFERENT, incompatible numbers for it (the
     SAME attack described as killing both "6" and "14" people; the SAME economic estimate given
     as both "5.4%" and "12%"). This is two sources disagreeing about one event, not a running
     total moving forward — do not silently average, pick one, or treat the higher number as an
     "update." Output NEW so both conflicting reports surface; a human or later source can
     resolve which is right.
   - If you genuinely cannot tell whether it's a later continuation or a same-moment conflict,
     prefer CONFLICT (NEW) — a false NEW costs a slightly noisier brief; a false UPDATE silently
     erases a real disagreement between sources.
2. A fact asserting a status/state that is the DIRECT OPPOSITE of what the known fact asserted
   about the SAME subject at essentially the SAME time (a blockade "crumbled" vs. "will remain
   closed"; "active talks underway" vs. "no discussions"; an economy "expanding" vs. "shrank";
   someone reported "vulnerable" vs. earlier "invincible") is also a CONFLICT, not a correction —
   output NEW, even when the exact words aren't a fixed antonym pair. Only treat a reversal as a
   legitimate UPDATE/correction when the new fact explicitly frames itself as fixing an error in
   the earlier report ("officials later clarified...", "the previous figure was mistaken; it has
   been corrected to...").
3. If the entities are different companies/people/products → lean NEW.
4. Editorial rephrasing of the exact same factual claim → MERGE.
5. Be a skeptical editor, not an eager one. Do NOT invent significance that isn't there.
   MERGE (not UPDATE) whenever the new fact:
   - restates the known fact with a vacuous or filler clause ("...according to a later
     report", "...officials confirmed", "...it was noted") that adds no verifiable detail, or
   - is a strict SUBSET of what's already known (e.g. the known fact lists strikes on
     "X, Y, Z, W" and the new fact only mentions "X, Y, Z" — that is LESS information, not new
     information).
   Before choosing UPDATE, you must be able to name the SPECIFIC new number, name, date, or
   status the new fact adds that the known fact does not already contain. If you cannot name
   one, the correct decision is MERGE.
6. When genuinely uncertain between UPDATE and MERGE — i.e. there IS a real, nameable new
   detail, just a minor one — choose UPDATE (false negatives on real information are worse
   than a minor update). This is different from rule 5's fabricated-detail case, and different
   from rule 1/2's CONFLICT case (a conflict is never MERGE or UPDATE, it is always NEW).
7. Output ONLY valid JSON. No explanation outside the JSON object.

Examples:
- Known: "US strikes hit Iranian sites in X, Y, Z, and W." New: "US strikes hit Iranian sites
  in X, Y, and Z." -> MERGE (subset, no new information — rule 5).
- Known: "Iran reported over 50 killed." New: "Iran reported 50 killed and over 500 injured
  between June 27 and July 18." -> UPDATE (delta: "over 500 injuries recorded between June 27
  and July 18" — a genuinely new, nameable figure, and a continuation not a conflict — rule 1).
- Known: "4 people were killed in the strike." New: "4 people were killed in the strike,
  according to an updated report released the following week." -> MERGE (the added clause
  names no new fact — rule 5).
- Known: "The death toll from the attack was 6, officials said." New: "The death toll from
  the SAME attack was 14, officials said." -> NEW (same specific incident, incompatible
  counts — rule 1 CONFLICT, not a running tally).
- Known: "Iran says the strait will remain closed." New: "The blockade has crumbled, with
  vessels now moving freely." -> NEW (opposite state about the same subject, same time —
  rule 2 CONFLICT).
"""

ARBITER_CASE_BLOCK = """\
NEW FACT (just extracted from an article):
  "{new_fact}"
  Entities: {new_entities}
  Event date: {new_date}{new_context_line}

CLOSEST KNOWN FACTS (from memory, ranked by similarity):
{matches_block}"""

ARBITER_SINGLE_INSTRUCTIONS = """

Before deciding, ask: can I name the specific new number, name, date, or status this fact
adds that the known fact doesn't already have? If no, the answer is MERGE — do not fabricate
significance from a subset of known information or a vacuous filler clause.

Choose exactly ONE decision and output ONLY valid JSON:

If MERGE (duplicate/trivial restatement, a subset of known information, or padding with no
new verifiable detail):
  {{"decision": "MERGE"}}

If UPDATE (new information that extends or corrects a known fact):
  {{"decision": "UPDATE", "delta": "One sentence stating exactly the new verifiable fact."}}
  The delta must be a FACT, not characterization: state what changed (the new status, number,
  or action), NOT a read of its trajectory or significance. Do NOT use evaluative verbs like
  "progressed/advanced/improved/worsened/escalated" or phrases like "in a major step".
  BAD : "Talks have progressed to peace-specific negotiations."
  GOOD: "Lebanon and Israel held a round of negotiations focused on a peace agreement on June 25."

If NEW (no existing knowledge matches - brand new information):
  {{"decision": "NEW"}}
"""

# Batch prompt — N self-contained cases judged in one call (V3_BATCH_JUDGE).
# Safe to batch because each case is independent (no shared state between facts).
ARBITER_BATCH_INSTRUCTIONS = """\

==============================================================================
You are given {n} INDEPENDENT cases above, numbered CASE 1 .. CASE {n}.
For EACH case choose exactly ONE decision: MERGE, UPDATE, or NEW (same rules as
a single case). Output ONLY a valid JSON array with exactly {n} objects, one per
case, in order. Each object MUST include its 1-based "case" number:

[
  {{"case": 1, "decision": "MERGE"}},
  {{"case": 2, "decision": "UPDATE", "delta": "One sentence on what is new."}},
  {{"case": 3, "decision": "NEW"}}
]
"""


# ============================================================
# STAGE: briefer — Gemini 2.0-flash (main tier)
# ============================================================

BRIEFER_SYSTEM = (
    "You are an elite intelligence briefer. Your job is to format raw facts into "
    "a scannable, highly readable report."
)


def build_briefer_prompt(topic_name: str, today: str, situation_hint: str, payload: str) -> str:
    """Construct the prompt for Briefer._get_prompt().

    Args:
        topic_name: human-readable topic name.
        today: "%B %d, %Y"-formatted current date string.
        situation_hint: pre-assembled "\nCURRENT SITUATION..." block, or "" if no situation.
        payload: JSON-serialized {"NEW_STORIES": [...], "UPDATES": [...]} string.
    """
    return f"""
Generate a clean, professional intelligence brief based ONLY on the provided facts.
Maximize signal-to-noise: lead with the single most important development, group
related facts, and never repeat the same point.

TOPIC: {topic_name}
DATE: {today}{situation_hint}
INPUT FACTS (already ordered most-significant first; "significance" ranks them:
state_change > escalation > development > incremental > tally > routine):
{payload}

FORMAT — follow this EXACT structure:

📋 TrueBrief | [Topic Name] | [Date]

**📌 Bottom line:** [ONE sentence naming the single most important CURRENT development across all facts — this is the lede a reader sees first.]

🆕 NEW STORIES ([Count])
━━━━━━━━━━━━━━━━━━━━━━━━━━
**Story Title**
• The fact, with its context woven in as natural prose (one flowing sentence or two — NOT labelled fragments). → Sources: [domain.com](url)

📈 UPDATES ([Count])
━━━━━━━━━━━━━━━━━━━━━━━━━━
**Story Title**
• What changed, stated directly, with the prior situation woven in as prose. → Sources: [domain.com](url)

RULES:
- Do NOT hallucinate. Use ONLY the facts in the JSON payload.
- LEAD WITH THE LEDE: the "📌 Bottom line" must name the most consequential current
  development (prefer a state_change / escalation over a tally or routine item).
- PRESERVE the given order — the most significant facts come first; render them first.
- WEAVE context as prose. Do NOT prefix bullets with rigid all-caps labels (no
  "whats-new" / "full-context" style tags) — write flowing sentences instead.
- COLLAPSE running tallies: if several facts are successive counts of the same metric
  (casualty totals, fund sizes), render ONE bullet with the latest figure — not one per update.
- Group closely related facts from the same story under one **heading**, each its own bullet.
- EVERY bullet ends with → Sources: [domain.com](url) using the exact url from that fact's
  "source" field. Use the markdown link format [name](url).
- ONE chip per OUTLET: if a bullet draws on several articles from the SAME domain, cite that
  domain ONCE. Only list multiple sources when they are DIFFERENT outlets.
- If a fact has corroborating_sources > 1, you may append " (N sources)" to the bullet text.
- If a section (NEW STORIES or UPDATES) has 0 items, omit that section AND its header entirely.
- Concise, punchy, professional. NO filler.
"""



# ============================================================
# STAGE: dashboard_summary — cheap tier (Groq llama-3.1-8b-instant when
# GROQ_API_KEY is set, else Gemini flash-lite; see config/settings.py LLM_CONFIG)
# ============================================================

DASHBOARD_SUMMARY_SYSTEM = "You are a news analyst. Write a tight executive summary."


def build_dashboard_summary_prompt(raw_query: str, bullet_list: str, s_min: int, s_max: int) -> str:
    """Construct the adaptive editorial-summary prompt for POST /topics/{id}/summary.

    Args:
        raw_query: the topic's raw_query string.
        bullet_list: "- fact\\n- fact\\n..." of the salience-selected facts.
        s_min: minimum sentence count from the adaptive window.
        s_max: maximum sentence count from the adaptive window.
    """
    shape = (
        f"Write {s_min}–{s_max} sentences of plain prose — no bullets, no lists, no line breaks. "
        "You are a news editor writing a tight situational update: "
        "open with a single declarative sentence naming the most consequential development that "
        "has ALREADY HAPPENED — never lead with a prediction, forecast, or probability estimate; "
        "those belong later in the summary, if at all; "
        "merge closely related facts into one sentence rather than listing them separately; "
        "signal the direction — is the situation escalating, stabilising, or resolved — using "
        "active verbs that show motion; "
        "when two cumulative totals (deaths, strikes, funds) are anchored to DIFFERENT start "
        "dates, do not merge them into one clause as if simultaneous — keep them in separate "
        "sentences or name each anchor, so the reader isn't misled about the timeframe; "
        "ruthlessly drop minor, routine, or repetitive items; "
        "do not pad to reach the sentence target — if fewer sentences capture everything, use fewer."
    )

    return (
        f"Topic: {raw_query}\n\n"
        f"New facts (these are the ONLY facts you may reference):\n{bullet_list}\n\n"
        f"{shape} "
        "Reference ONLY facts listed above — do not add background, context, or information not in the list. "
        "Be direct and specific — no fluff, no \"based on the above\", no \"in summary\"."
    )


# ============================================================
# STAGE: story_stitch — cheap tier (Groq llama-3.1-8b-instant when
# GROQ_API_KEY is set, else Gemini flash-lite; see config/settings.py LLM_CONFIG)
# ============================================================

STORY_STITCH_SYSTEM = "You are a news analyst writing terse connective narration."


def build_story_stitch_pair_prompt(topic_name: str, fact_a: str, fact_b: str) -> str:
    """Construct the single-pair story-stitch prompt.

    Shared by VectorStore._maybe_stitch_pairs (ledger) and the
    /topics/{id}/story-connectors cache-miss fallback in api/routes.py.

    Args:
        topic_name: human-readable topic/raw_query string.
        fact_a: the earlier ("before") fact's alpha_text.
        fact_b: the later ("after") fact's alpha_text.
    """
    return (
        f"Topic: {topic_name}\n"
        f"Fact A: {fact_a}\n"
        f"Fact B: {fact_b}\n\n"
        "Write ONE sentence (max 18 words) stating the RELATIONSHIP between Fact A and "
        "Fact B — is B a consequence, a response, an escalation, a reversal, or simply "
        "the next event in the same story? Rules:\n"
        "- Do NOT restate or closely paraphrase either fact — say how they connect, not "
        "what they say.\n"
        "- Only state a cause, consequence, or response if A and B describe the SAME "
        "specific chain of events. Two facts that merely share a topic (e.g. a military "
        "strike and an unrelated market-price move) are NOT causally linked — do not "
        "connect them with 'response to', 'linked to', 'led to', 'coincided with', or "
        "similar, and do not hedge with 'appears to', 'likely', 'may have' to smuggle in "
        "a link the facts don't establish. If in doubt, the link does not exist.\n"
        "- Do NOT use empty wrapper filler that adds no information: 'is the next event "
        "in this story', 'is part of the same ongoing conflict', 'contributed to' when no "
        "mechanism is stated. If you have nothing concrete to add, that means there is no "
        "real bridge — leave it empty (see below), don't dress up a non-bridge in vague "
        "phrasing.\n"
        "- Do NOT introduce any number, date, or name that is not already present in "
        "Fact A or Fact B.\n"
        "- If there is no real narrative link between A and B, the passage value must be "
        'the literal empty string "" — do NOT write a sentence explaining that they are '
        "unrelated or separate developments. Just leave it empty.\n"
        "GOOD  A: \"The IRGC declared the Strait of Hormuz closed.\" "
        "B: \"Brent crude prices rose 8 percent.\"\n"
        "      passage: \"\" (the article never states the price rose BECAUSE of the "
        "closure — a plausible guess is still a fabrication)\n"
        "GOOD  A: \"Congress passed a war-powers resolution restricting the president.\" "
        "B: \"The White House said the president would veto the resolution.\"\n"
        "      passage: \"The White House responded to the resolution by vowing a veto.\" "
        "(the article explicitly frames B as a reaction to A)\n"
        'Return JSON: {"passage": "..."}.'
    )


def build_story_stitch_batch_prompt(topic_name: str, numbered_facts: str, n_pairs: int) -> str:
    """Construct the legacy all-pairs-in-one-call story-stitch prompt for POST /topics/{id}/story.

    Used when V4_STORY_STITCHING is off or the caller didn't supply fact_ids
    (so the per-pair cache path can't run).

    Args:
        topic_name: the topic's raw_query string.
        numbered_facts: "1. fact\\n2. fact\\n..." of the chronological facts.
        n_pairs: number of adjacent-pair bridge sentences requested (len(facts) - 1).
    """
    return (
        f"Topic: {topic_name}\n\n"
        f"These {n_pairs + 1} events are listed in chronological order:\n{numbered_facts}\n\n"
        f"For each ADJACENT pair (1→2, 2→3, …), write ONE short bridge sentence (max 18 "
        f"words) stating the RELATIONSHIP between the two events — is the later one a "
        f"consequence, a response, an escalation, a reversal, or simply the next event? "
        f"Rules:\n"
        f"- Do NOT restate or closely paraphrase either event — say how they connect, "
        f"not what they say.\n"
        f"- Do NOT invent a cause, motive, or link the two events don't establish.\n"
        f"- Do NOT introduce any number, date, or name not already present in the pair.\n"
        f"- If a pair has no real narrative link, use an empty string \"\" for that pair "
        f"— an empty bridge beats a fabricated one.\n"
        f'Return ONLY this JSON: {{"connectors": ["sentence1", "sentence2", ...]}} '
        f"with exactly {n_pairs} strings in the array, in order (each may be empty)."
    )


# ============================================================
# STAGE: gemini_search — Gemini 2.5 flash-lite, Google Search grounding (V5)
# ============================================================
# Two calls, not one — verified live 2026-07-22 that forcing JSON output on the SAME
# call that uses the search tool suppresses grounding_metadata entirely (empty
# grounding_chunks/supports) and makes the model fabricate a plausible-looking-but-fake
# source URL when a JSON schema asks for one. So: call 1 asks for plain grounded prose
# (real grounding_chunks/supports come back correctly); the collector then inserts
# citation markers into that prose using the *verified* segment offsets and passes the
# cited text to call 2, a cheap non-grounded restructuring call that returns citation
# INDICES (never a URL) — the real URL is substituted afterward from grounding_chunks.

GEMINI_SEARCH_SYSTEM = (
    "You are a news research assistant. Search the web and report factual, dated "
    "developments in plain prose. Do not use JSON or markdown formatting."
)


def build_gemini_search_prompt(
    topic_name: str,
    last_run_date: str,
    today: str,
    known_facts: list[str] | None = None,
) -> str:
    """Construct the grounded-search prompt (call 1 of 2).

    Args:
        topic_name: human-readable topic name.
        last_run_date: "%Y-%m-%d" of the last successful run, or "" for a first-ever run
            (in which case the window is "the last 7 days" instead of an exact range).
        today: "%Y-%m-%d" of the current date.
        known_facts: optional list of already-known fact strings to inject into the
            prompt so Gemini skips re-surfacing them on same-day rescans. When empty or
            None the prompt is identical to the original (no behaviour change for normal
            scans).
    """
    window = (
        f"from {last_run_date} to {today}"
        if last_run_date
        else f"in the last 7 days (today is {today})"
    )
    prompt = (
        f"Search the web for developments on '{topic_name}' {window}.\n\n"
        "List every distinct development you find, each as its own item with an explicit "
        "date. Be specific — include names, numbers, and locations. Do not include your own "
        "analysis, predictions, or significance judgments — report what happened, not what "
        "it means. If nothing new happened in this window, say so plainly."
    )
    if known_facts:
        known_block = "\n".join(f"- {f}" for f in known_facts)
        prompt += (
            f"\n\nThe following developments are already known as of the last scan — "
            f"do not re-report them unless something about them has materially changed:\n"
            f"{known_block}\n"
            f"Only report what is genuinely new since the last scan."
        )
    return prompt


def build_search_query(topic_name: str, last_run_date: str = "", today: str = "") -> str:
    """Recency-anchored question for the API-search grounding providers (Linkup, Brave).

    NOT just "{topic} latest news" — verified live 2026-08-31 that a bare topic
    query makes Linkup dredge up month-old releases with no dates. Phrasing it as
    a dated question ("what was reported between X and Y? give each date; exclude
    older items") makes Linkup honor the window, attach dates, and honestly answer
    "nothing significant this week" instead of padding with stale news. The
    fromDate/toDate request params are also sent, but the query text is what
    actually steers the sourcedAnswer.
    """
    topic = (topic_name or "").strip() or "current events"
    if last_run_date and today:
        window = f"between {last_run_date} and {today}"
    elif today:
        window = f"in the 7 days up to {today}"
    else:
        window = "in the past 7 days"
    return (
        f'What genuinely new, newsworthy developments about "{topic}" were reported {window}? '
        f"For each one, state exactly what happened and its precise date (YYYY-MM-DD). "
        f"Only include events that actually occurred within that window — exclude older "
        f"product releases, background, and anything you cannot date. If nothing "
        f"significant happened in that window, say so plainly."
    )


GEMINI_EXTRACT_SYSTEM = (
    "You are a precision intelligence analyst. Extract every atomic, verifiable fact from "
    "this cited text into a structured JSON list."
)


def build_gemini_extract_prompt(
    cited_text: str,
    source_legend: str,
    topic_name: str,
    today: str,
    news_window_start: str = "",
) -> str:
    """Construct the restructuring prompt (call 2 of 2) — ports the harvester's fact-quality
    rules (STRIP THE EDITORIAL CLAUSE, ATTRIBUTION RULE, event_class taxonomy, additive-only
    context) onto multi-source grounded prose instead of a single article.

    Args:
        cited_text: the grounded response text with inline [N] / [N,M] markers inserted at
            each grounding_supports segment boundary (built by the collector, not the LLM).
        source_legend: "[0] uniindia.com\\n[1] justsecurity.org\\n..." — numbered index into
            the SAME real, verified grounding_chunks the markers reference.
        topic_name: human-readable topic name, for the TOPIC FILTER.
        today: "%Y-%m-%d" — the anchor for RELATIVE phrases ("yesterday") only.
        news_window_start: "%Y-%m-%d" — start of the reporting window. Events before this
            are background, not news (Linkup/Brave mix stale releases into "latest news"
            prose; without this guard the model stamps them all with `today`).
    """
    window_block = ""
    if news_window_start:
        window_block = f"""
NEWS WINDOW: {news_window_start} to {today}. This brief reports ONLY what is new in
this window. For any development:
- If it clearly happened BEFORE {news_window_start} → set "is_background": true if it
  is essential context for a fresh development, otherwise DROP it.
- Do NOT assign event_date {today} to an undated item just because the search is
  "recent". If the text does not let you place the event on a specific date within
  {news_window_start}–{today}, DROP it (or is_background:true if it is context).
- A months-old product release described in present tense ("X offers…", "Y is
  available") is NOT news — drop it.
"""
    return f"""
TODAY: {today}
TOPIC FILTER: {topic_name}
Only extract facts directly relevant to this topic.
{window_block}

SOURCE LEGEND (numbered — cite ONLY these numbers, never write a URL yourself):
{source_legend}

CITED TEXT (bracketed numbers mark which source(s) back each passage):
{cited_text}

TASK:
Extract every atomic, verifiable fact from the cited text into a structured JSON list.

A FACT is an observable, checkable event or state: who did what, when, where, how many.
NOT a fact: a writer's interpretation of meaning, cause, consequence, or significance.

STRIP THE EDITORIAL CLAUSE — keep only the verifiable core:
- BAD : "Khamenei's death has created a significant leadership vacuum and political instability."
  GOOD: "Iranian Supreme Leader Ali Khamenei died during U.S.-Israeli airstrikes."
- BAD : "The IRGC closed the Strait of Hormuz, disrupting regional maritime security."
  GOOD: "The IRGC declared the Strait of Hormuz closed on June 20."
- BAD : "The ceasefire is likely to collapse within weeks."  → prediction; DROP unless attributed
  GOOD: "A senior Israeli official said the ceasefire is likely to collapse within weeks."

ATTRIBUTION RULE — assessments, intentions, predictions, and significance claims are facts ONLY
when attributed to a named actor, and then the fact is that they SAID/ASSESS it:
- GOOD: "Iran announced it will enrich uranium to 60%."  (a discrete plan announced by a named actor)
- BAD : "The strike was a clear violation of international law."  (whose claim? → drop or attribute)

For each fact extract:
1. "alpha_text": The verifiable event as ONE clean standalone sentence — core event only,
   no causal/evaluative/predictive clause ("creating…", "undermining…", "which could…",
   "in a major shift…", "complicating…", "amid growing…").
2. "entities": List of named entities (companies, people, countries, products).
3. "event_date": REQUIRED, ISO format (YYYY-MM-DD). Anchor relative phrases ("yesterday",
   "last week") to TODAY ({today}), not to any date mentioned inside a quoted source. If the
   SAME event appears more than once in the text, use the SAME event_date every time — do not
   let re-reporting drift the date. If you cannot confidently date an event, DROP it.
4. "date_basis": EXACTLY ONE of "explicit" (text states an absolute date) | "relative"
   (resolved from "yesterday"/"last week" against TODAY) | "inferred" (weak guess).
5. "is_background": true if this is PAST CONTEXT or a STANDING STATE with no new dated action
   in this window ("the war has continued since March", "talks are ongoing"), not a fresh
   development. Do NOT present background as today's news.
6. "context": ONE sentence of BACKGROUND that helps a reader understand the fact — information
   NOT already stated in alpha_text (a prior related event, the earlier status this fact
   changes, figures/dates/parties the bare fact leaves out). Do NOT restate alpha_text. Do NOT
   open with "This event…"/"This reflects…"/similar meta-reference. If there is no genuine
   background beyond the fact itself, return "" — empty beats a restatement.
7. "confidence": How verifiable is this? (0.0-1.0). Drop anything below 0.6.
8. "importance": How significant to the topic? (0.0-1.0). 1.0 = decisive/topic-defining,
   0.7 = clearly relevant, 0.4 = minor/supporting, 0.1 = tangential.
9. "event_class": EXACTLY ONE of "state_change" (durable topic-level status flip: ceasefire
   signed, treaty agreed, leadership change) | "escalation" (new aggressive/deteriorating act)
   | "casualty" (individual(s) newly killed, wounded, captured, or detained — something bad
   happening TO them; never the lede over a state_change) | "development" (discrete new fact,
   no status flip — including a person being RELEASED, freed, or exchanged: that reverses a
   casualty, it is not one) | "incremental" (minor follow-up)
   | "tally" (a cumulative running count/total — never the lede) | "routine" (scheduling/logistics).
10. "citation_indices": list of integers from the SOURCE LEGEND above — the bracketed
   number(s) attached to the passage this fact was drawn from. Copy them exactly; do not
   invent a number not present in the legend. Empty list if no marker covers this passage.

RULES:
- ONLY extract facts relevant to the TOPIC FILTER above.
- NEVER extract opinions, predictions, analysis, or editorial commentary.
- NEVER write a URL, domain, or source name yourself — cite only by legend number.
- Drop anything with confidence < 0.6 or without a determinable event_date.
- Each fact must stand alone — a reader with no other context should understand it.
- Output ONLY a valid JSON list, no markdown fences.

EXPECTED OUTPUT FORMAT:
[
  {{
    "alpha_text": "Fact sentence — verifiable event only, no editorial clause.",
    "entities": ["Entity1", "Entity2"],
    "event_date": "{today}",
    "date_basis": "explicit",
    "is_background": false,
    "context": "Context string.",
    "confidence": 0.95,
    "importance": 0.9,
    "event_class": "state_change",
    "citation_indices": [0, 2]
  }}
]
"""


if __name__ == "__main__":
    # Sanity check: run each builder with representative sample inputs and
    # print the result, so a human (or a future refactor) can eyeball that
    # the assembled prompt text still looks right. Not a pytest file.
    import sys as _sys
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8")  # prompts contain non-ASCII (→, —)

    print("=== ARBITER_CASE_BLOCK ===")
    print(
        ARBITER_CASE_BLOCK.format(
            new_fact="Company X acquired Company Y for $5B.",
            new_entities="Company X, Company Y",
            new_date="2026-07-01",
            new_context_line="",
            matches_block='  1. [STRONG_MATCH 0.82] "Company X agreed to acquire Company Y."\n'
            "     Entities: Company X, Company Y | Event date: 2026-06-28",
        )
    )

    print("\n\n=== ARBITER_SINGLE_INSTRUCTIONS ===")
    print(ARBITER_SINGLE_INSTRUCTIONS)

    print("\n\n=== ARBITER_BATCH_INSTRUCTIONS ===")
    print(ARBITER_BATCH_INSTRUCTIONS.format(n=2))

    print("\n\n=== build_briefer_prompt (no situation) ===")
    print(
        build_briefer_prompt(
            topic_name="Tesla & EVs",
            today="July 15, 2026",
            situation_hint="",
            payload='{\n  "NEW_STORIES": [],\n  "UPDATES": []\n}',
        )
    )

    print("\n\n=== build_briefer_prompt (with situation) ===")
    print(
        build_briefer_prompt(
            topic_name="Tesla & EVs",
            today="July 15, 2026",
            situation_hint=(
                '\nCURRENT SITUATION (IC7 anchor — use this as the basis for your '
                '"📌 Bottom line"; the new facts below update it):\n'
                "Tesla is expanding aggressively into Southeast Asia.\n"
            ),
            payload='{\n  "NEW_STORIES": [],\n  "UPDATES": []\n}',
        )
    )

    print("\n\n=== build_story_stitch_pair_prompt ===")
    print(
        build_story_stitch_pair_prompt(
            topic_name="Tesla & EVs",
            fact_a="Tesla reported record deliveries.",
            fact_b="Tesla stock rose 5 percent.",
        )
    )

    print("\n\n=== build_dashboard_summary_prompt ===")
    print(
        build_dashboard_summary_prompt(
            raw_query="Israel-Hamas War",
            bullet_list=(
                "- A ceasefire was signed on June 17.\n"
                "- Artillery exchanges continued in the eastern corridor."
            ),
            s_min=3,
            s_max=7,
        )
    )

    print("\n\n=== build_story_stitch_batch_prompt ===")
    print(
        build_story_stitch_batch_prompt(
            topic_name="Tesla & EVs",
            numbered_facts=(
                "1. Tesla reported record deliveries.\n"
                "2. Tesla stock rose 5 percent.\n"
                "3. Tesla announced a new factory in Texas."
            ),
            n_pairs=2,
        )
    )

    print("\n\n=== build_gemini_search_prompt ===")
    print(build_gemini_search_prompt("Iran War", "2026-07-20", "2026-07-22"))

    print("\n\n=== build_gemini_extract_prompt ===")
    print(
        build_gemini_extract_prompt(
            cited_text="Iran proposed a 10-day ceasefire.[0] The U.S. reviewed the offer.[1,0]",
            source_legend="[0] reuters.com\n[1] apnews.com",
            topic_name="Iran War",
            today="2026-07-22",
        )
    )
