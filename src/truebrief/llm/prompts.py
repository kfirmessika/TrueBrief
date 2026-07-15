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
# STAGE: collector / query_builder — Gemini flash-lite (cheap)
# ============================================================

QUERY_BUILDER_SYSTEM = "You are the TrueBrief Librarian. Your job is to analyze user tracking topics."


def build_query_builder_prompt(topic: str, rss_categories: list, today: str) -> str:
    """Construct the prompt for QueryBuilder.build().

    Args:
        topic: the raw user topic input.
        rss_categories: available RSS feed categories (e.g. loaded from rss_feeds.yaml).
        today: "%B %Y"-formatted current date string (e.g. "July 2026").
    """
    return f"""
Today's date: {today}. When a query benefits from a year, use the CURRENT year — never a past one.

The user wants to track breaking news for: '{topic}'

TASK:
1. Decide if the input is a legitimate news topic or gibberish/malicious. Reject the latter.
2. Formalize a clean 'short_name' (e.g. 'Israel-Hamas War', 'TSMC Semiconductors').
3. Split the topic into 3-4 DISTINCT DOMAINS — each covering a different facet.
   For each domain generate 2 search queries that surface articles OTHER domains wouldn't.
4. Choose relevant RSS categories from the list below.

AVAILABLE RSS CATEGORIES:
{rss_categories}

DOMAIN RULES (critical — read carefully):
- Each domain covers a DIFFERENT slice of the topic. No overlap.
- Queries within a domain are angle variations of the SAME facet.
- Queries ACROSS domains must be topically DIVERGENT: domain A queries must NOT return
  the same articles as domain B queries. Think "what stories would only appear under this facet?"
- Domain 0 is the PRIMARY facet (most direct match to user intent).
- Keep queries specific enough for news search but not so narrow they return nothing.
- Do NOT use site: operators or boolean syntax — plain keyword queries only.

EXAMPLES:

Topic "Israel":
  domain 0 "military_operations":
    queries: ["IDF Gaza offensive operations {today.split()[-1]}", "Hezbollah rocket attack Lebanon Israel"]
  domain 1 "diplomacy_ceasefire":
    queries: ["Gaza ceasefire negotiations mediators", "US Iran nuclear talks Middle East"]
  domain 2 "humanitarian_crisis":
    queries: ["Gaza civilian casualties aid delivery", "West Bank Palestinian refugees UN"]
  domain 3 "domestic_political":
    queries: ["Netanyahu government coalition protest", "Israel defense industry economy war"]

Topic "Shark attack Australia":
  domain 0 "incident_victim":
    queries: ["shark attack Queensland beach", "surfer bitten Australia coast fatality"]
  domain 1 "safety_response":
    queries: ["beach closure shark drumlines Queensland", "lifeguard aerial drone shark patrol"]
  domain 2 "ecology_science":
    queries: ["great white shark population Australia habitat", "shark species behavior attack research"]

IF INPUT IS GIBBERISH/INVALID/HARMFUL:
Return: {{"status": "REJECTED", "reason": "Explanation"}}

IF VALID, return ONLY this JSON (no markdown, no extra keys):
{{
  "status": "APPROVED",
  "short_name": "Clean Topic Name",
  "corrected_query": "spelling-fixed version of the user input, or identical if no errors",
  "rss_categories": ["category1", "category2"],
  "domains": [
    {{
      "name": "domain_slug",
      "description": "One sentence: what facet this covers",
      "queries": ["query one", "query two"]
    }}
  ]
}}

corrected_query rules: fix ONLY spelling errors. Do NOT expand, rename, or add words.
"isreal" -> "israel", "nvida" -> "nvidia", "iran war" -> "iran war", "us" -> "us".
Short abbreviations and proper nouns in any case are fine as-is.
"""


# ============================================================
# STAGE: harvester — Gemini flash-lite (cheap)
# ============================================================

HARVESTER_SYSTEM = (
    "You are a precision intelligence analyst. Extract every atomic, verifiable "
    "fact from this article into a structured JSON list."
)


def build_harvester_prompt(
    article_text: str,
    pub_date_str: str,
    topic_block: str,
    date_guard: bool,
) -> str:
    """Construct the prompt for Harvester.extract().

    Args:
        article_text: full extracted article text.
        pub_date_str: article published date, "%Y-%m-%d" or "Unknown".
        topic_block: pre-assembled "TOPIC FILTER: ..." block, or "" if no topic_context.
        date_guard: settings.V3_DATE_GUARD value at call time.
    """
    if date_guard:
        date_instruction = (
            'REQUIRED. The date the event HAPPENED in ISO format (YYYY-MM-DD).\n'
            '   Use the ARTICLE PUBLISHED DATE as the anchor. Relative phrases like "yesterday", "last month",\n'
            '   "on Tuesday", "June 7" MUST resolve to a date within 1 year of the article publish date.\n'
            '   The year MUST come from the publish date context — do NOT default to prior years.\n'
            '   If you cannot confidently determine the year from context, do NOT extract the fact.'
        )
    else:
        date_instruction = (
            'REQUIRED. The date the event HAPPENED in ISO format (YYYY-MM-DD).\n'
            '   Use the ARTICLE PUBLISHED DATE as anchor for relative phrases ("yesterday", "last quarter").\n'
            '   If the article does not anchor the event in time, do NOT extract the fact.\n'
            '   This field is non-optional — facts without a verifiable event date are not facts.'
        )

    return f"""
ARTICLE PUBLISHED DATE: {pub_date_str}
{topic_block}
ARTICLE TEXT:
{article_text}

TASK:
Extract every atomic, verifiable fact from this article into a structured JSON list.

A FACT is an observable, checkable event or state: who did what, when, where, how many.
NOT a fact: a writer's interpretation of meaning, cause, consequence, or significance.

STRIP THE EDITORIAL CLAUSE — keep only the verifiable core:
- BAD : "Khamenei's death has created a significant leadership vacuum and political instability."
  GOOD: "Iranian Supreme Leader Ali Khamenei died during U.S.-Israeli airstrikes."
  (drop "created a leadership vacuum and political instability" — that is analysis, not fact)
- BAD : "Israeli troops in Syria constitute a violation undermining established diplomatic norms."
  GOOD: "Israeli troops and tanks were present in the Syrian countryside near the 1974 buffer zone."
  (drop "constitute a violation undermining norms" — that is a judgement, not fact)
- BAD : "The IRGC closed the Strait of Hormuz, disrupting regional maritime security."
  GOOD: "The IRGC declared the Strait of Hormuz closed on June 20."
  (drop "disrupting regional maritime security" — that is a consequence the writer asserts)
- BAD : "The killing complicates current diplomatic efforts."  → DROP ENTIRELY (pure commentary).
- BAD : "Hamas is attempting to redevelop its rocket-firing capabilities."
  → an attempt/effort/goal is NOT a discrete checkable event. Either extract the OBSERVABLE action
  GOOD: "Hamas fired three rockets from northern Gaza on June 24." (if the article states it), or
  ATTRIBUTE it GOOD: "The IDF said Hamas is rebuilding its rocket capability." — otherwise DROP.
- BAD : "The ceasefire is likely to collapse within weeks."  → prediction; DROP unless attributed
  GOOD: "A senior Israeli official said the ceasefire is likely to collapse within weeks."
- BAD : "It was the deadliest strike since the war began."  → keep the verifiable core, drop the
  comparative-significance claim:  GOOD: "The strike killed 14 people on June 24."

ATTRIBUTION RULE — assessments, intentions, predictions, and significance claims are facts ONLY
when attributed to a named actor, and then the fact is that they SAID/ASSESS it:
- GOOD: "Hezbollah said the killing of two people in southern Lebanon violated the ceasefire."
- GOOD: "A UN commission report alleged Israeli actions in Gaza amount to genocidal intent."
- GOOD: "Iran announced it will enrich uranium to 60%."  (a discrete plan announced by a named actor)
- BAD : "The strike was a clear violation of international law."  (whose claim? → drop or attribute)

For each fact extract:
1. "alpha_text": The verifiable event as ONE clean standalone sentence — core event only,
   no causal/evaluative/predictive clause ("creating…", "undermining…", "which could…",
   "in a major shift…", "complicating…", "amid growing…").
2. "entities": List of named entities (companies, people, countries, products).
3. "event_date": {date_instruction}
4. "date_basis": How you determined event_date — EXACTLY ONE of:
   - "explicit"  — the article states an absolute date for this event.
   - "relative"  — you resolved it from "yesterday/last week/Tuesday" against the publish date.
   - "inferred"  — a weak guess; the article does not clearly date this event.
5. "is_background": true if this is NOT a fresh development reported today, but rather:
   - PAST CONTEXT referenced as background ("since the war began in March…", "after the
     leader's death months ago…"), OR
   - a STANDING STATE / ongoing condition / institutional fact with no new dated action this
     article: "X has been involved in a dispute since 1991", "the talks are ongoing", "X is
     engaged in…", "the unit was established [years ago]", "X continues to…".
   Set is_background=true for these. Only set it FALSE when the sentence reports a concrete
   action that happened on/near the article date. Do NOT present background or standing
   conditions as today's news.
6. "context": 20-40 words - why does this fact matter? What story does it belong to?
7. "confidence": How verifiable is this? (0.0-1.0)
8. "importance": How significant is this fact to the topic? (0.0-1.0)
   1.0 = decisive, topic-defining event (a state_change or escalation that directly changes the topic's status)
   0.7 = clearly relevant new development worth tracking
   0.4 = minor or supporting detail
   0.1 = tangential or routine; barely touches the topic
9. "event_class": The development type. Choose EXACTLY ONE:
   - "state_change"  — a discrete, durable, TOPIC-LEVEL status flip: ceasefire signed, treaty agreed,
                       court ruling issued, law passed, strait opened/closed, company acquired,
                       or a HEAD-OF-STATE / leadership change (a head of state or org leader dies/resigns).
   - "escalation"    — a new discrete aggressive or deteriorating act: strike, attack, front opens,
                       sanctions imposed, talks collapsed, troops deployed.
   - "casualty"      — an INDIVIDUAL person (or small group) killed, wounded, or detained in an
                       incident: "X was shot dead", "a contractor was killed", "two were wounded".
                       This is NOT a durable status flip — never the lede over a state_change.
   - "development"   — a discrete new fact inside an ongoing story that does not flip a status:
                       meeting held, statement issued, vote scheduled, person arrested.
   - "incremental"   — a follow-up or minor update: "X now says…", clarification, minor revision.
   - "tally"         — a cumulative running count or total that will be updated again:
                       death tolls, case counts, funding totals, damage estimates. Label even if the
                       number changed — it is NEVER the lede.
   - "routine"       — scheduling/logistics: press briefing scheduled, convoy arrived, ship docked.

RULES:
- ONLY extract facts relevant to the TOPIC FILTER above (if specified).
- NEVER extract opinions, predictions, analysis, or editorial commentary. If a sentence mixes a
  fact with interpretation, KEEP THE FACT, DROP THE INTERPRETATION (see STRIP examples above).
- An assessment/judgement is allowed ONLY when attributed to a named actor (ATTRIBUTION RULE above).
- NEVER extract meta-information about the article itself (download links, app info, copyright notices).
- Drop anything with confidence < 0.6.
- DROP any fact where you cannot determine a specific event_date — omit it entirely.
- Each fact must stand alone - a reader with no other context should understand it.
- Output ONLY a valid JSON list.

EXPECTED OUTPUT FORMAT:
[
  {{
    "alpha_text": "Fact sentence — verifiable event only, no editorial clause.",
    "entities": ["Entity1", "Entity2"],
    "event_date": "2026-04-15",
    "date_basis": "explicit",
    "is_background": false,
    "context": "Context string.",
    "confidence": 0.95,
    "importance": 0.9,
    "event_class": "state_change"
  }}
]
"""


# ============================================================
# STAGE: arbiter — Gemini flash-lite (cheap)
# ============================================================

ARBITER_SYSTEM = """\
You are a precision news intelligence arbiter. Your job is to determine whether a new fact
duplicates, updates, or is entirely different from known stored facts.

Rules (apply strictly):
1. A change in numbers (price, %, revenue, count, date) = UPDATE, never MERGE.
2. If the entities are different companies/people/products → lean NEW.
3. Editorial rephrasing of the exact same factual claim → MERGE.
4. When uncertain between UPDATE and MERGE → choose UPDATE (false negatives are worse).
5. Output ONLY valid JSON. No explanation outside the JSON object.
"""

ARBITER_CASE_BLOCK = """\
NEW FACT (just extracted from an article):
  "{new_fact}"
  Entities: {new_entities}
  Event date: {new_date}

CLOSEST KNOWN FACTS (from memory, ranked by similarity):
{matches_block}"""

ARBITER_SINGLE_INSTRUCTIONS = """

Choose exactly ONE decision and output ONLY valid JSON:

If MERGE (duplicate/trivial restatement - no new information):
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
# STAGE: state_of_play — Gemini 2.0-flash (main tier)
# ============================================================

STATE_OF_PLAY_SYSTEM = (
    "You are an intelligence analyst writing a grounded status board. "
    "You report ONLY what the facts establish. You never predict."
)


def build_state_of_play_prompt(topic_name: str, today: str, payload: str, max_threads: int) -> str:
    """Construct the prompt for StateOfPlayGenerator._get_prompt().

    Args:
        topic_name: human-readable topic name.
        today: "%B %d, %Y"-formatted current date string.
        payload: JSON-serialized list of fact dicts (fact/significance/date/source).
        max_threads: MAX_THREADS cap on the number of open threads to return.
    """
    return f"""
Build a "state of play" status board for this topic from the FACTS below — and ONLY
from those facts. This is a glanceable header that answers "where do things stand right now?"

TOPIC: {topic_name}
DATE: {today}

FACTS (most significant / recent first):
{payload}

Produce JSON with this EXACT shape:
{{
  "situation": "ONE sentence — the single most important reality right now. Write it the way
                a senior analyst would brief a colleague: direct, concrete, no jargon.
                Lead with the most significant state_change or escalation in the facts.
                Example style: 'A 90-day ceasefire was signed on Jun 17; both sides have
                pulled back, but artillery exchanges continue in the eastern corridor.'",
  "threads": [
    {{"label": "<short name of an open thread, 2–4 words>",
      "status": "<one of: agreed | contested | postponed | escalating>",
      "note": "<≤8 words anchoring it to a fact, e.g. 'signed Jun 17' or 'talks stalled'>"}}
  ]
}}

RULES:
- Use ONLY the facts provided. Do NOT add outside knowledge. Do NOT predict or speculate.
- "situation" must be ONE sentence, ≤40 words, grounded in the highest-significance fact.
- "status" MUST be exactly one of: agreed, contested, postponed, escalating.
    agreed     = settled / signed / in force.
    contested  = disputed, conflicting claims, or violated.
    postponed  = delayed, paused, awaiting.
    escalating = actively worsening / new hostilities.
- 3 to {max_threads} threads, the most consequential first. No filler threads.
- "note" must be short and tied to a fact (a date or a concrete detail). No prose.
- If a fact set supports no clear thread, omit it rather than inventing one.
- Output ONLY the JSON object. No markdown fences, no commentary.
"""


# ============================================================
# STAGE: story_summarizer — Gemini flash-lite (cheap)
# ============================================================

STORY_SUMMARIZER_SYSTEM = (
    "You are a concise intelligence analyst. "
    "Your job is to maintain an evolving summary of a news story. "
    "Output ONLY the updated summary paragraph - no headers, "
    "no labels, no formatting, no bullet points."
)


def build_story_summarizer_prompt(
    title: str,
    previous_summary: str,
    new_fact: str,
    new_fact_context: str,
    max_summary_length: int,
) -> str:
    """Construct the recursive-summary prompt for StorySummarizer._build_prompt().

    Args:
        title: the story's title.
        previous_summary: the story's current summary text.
        new_fact: the newly-added Alpha's alpha_text.
        new_fact_context: the newly-added Alpha's context, or "" if none.
        max_summary_length: MAX_SUMMARY_LENGTH cap (characters) enforced in the prompt text.
    """
    context_line = ""
    if new_fact_context:
        context_line = f"\nCONTEXT FOR NEW FACT: {new_fact_context}"

    return f"""You are maintaining an evolving summary for a news story.

STORY TITLE: {title}

CURRENT SUMMARY (what we know so far):
{previous_summary}

NEW FACT (just arrived):
{new_fact}{context_line}

TASK:
Write an updated summary that seamlessly incorporates the new fact into the
existing narrative.  The summary must:

1. Be a SINGLE coherent paragraph (3-5 sentences max).
2. Integrate the new fact naturally - don't just append it.
3. Preserve all important information from the current summary.
4. If the new fact contradicts the current summary, note both versions.
5. Stay under {max_summary_length} characters.
6. Use past/present tense appropriately based on the event timing.
7. Do NOT add any information not present in the inputs above.

Output ONLY the updated summary paragraph. No labels, no bullet points."""


# ============================================================
# STAGE: query_rotator — Gemini flash-lite (cheap)
# ============================================================

QUERY_ROTATOR_SYSTEM = "You are a professional news intelligence researcher."


def build_query_rotator_prompt(raw_query: str, existing_json: str, max_regen_variants: int) -> str:
    """Construct the prompt for QueryRotator._llm_generate_variants().

    Args:
        raw_query: the topic's raw query string.
        existing_json: json.dumps(existing, indent=2) of the exhausted query variants.
        max_regen_variants: MAX_REGEN_VARIANTS — how many fresh queries to request.
    """
    return f"""You are a news search strategist.

Topic: '{raw_query}'

The following search queries have been exhausted (finding no new facts):
{existing_json}

Generate {max_regen_variants} DIFFERENT search queries that approach this topic
from fresh angles (e.g. financial impact, geopolitical, technical, personnel, regional).
Each query must be meaningfully different from the exhausted ones above.

Return ONLY valid JSON: {{"queries": ["query1", "query2", "query3"]}}"""


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
        "open with a single declarative sentence naming the most consequential development; "
        "merge closely related facts into one sentence rather than listing them separately; "
        "signal the direction — is the situation escalating, stabilising, or resolved — using "
        "active verbs that show motion; "
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
        f"Write ONE sentence (max 18 words) connecting A to B. "
        f'Return JSON: {{"passage": "..."}}.'
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
        f"For each ADJACENT pair (1→2, 2→3, …), write ONE short bridge sentence "
        f"(max 18 words) that connects the earlier event to the later one — show how "
        f"the story moved from one to the next. Ground every bridge in the events; do "
        f'NOT invent facts. Return ONLY this JSON: {{"connectors": ["sentence1", "sentence2", ...]}} '
        f"with exactly {n_pairs} strings in the array, in order."
    )


if __name__ == "__main__":
    # Sanity check: run each builder with representative sample inputs and
    # print the result, so a human (or a future refactor) can eyeball that
    # the assembled prompt text still looks right. Not a pytest file.
    import sys as _sys
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8")  # prompts contain non-ASCII (→, —)

    print("=== build_query_builder_prompt ===")
    print(
        build_query_builder_prompt(
            topic="Israel",
            rss_categories=["general", "middle_east", "world"],
            today="July 2026",
        )
    )

    print("\n\n=== build_harvester_prompt (date_guard=True) ===")
    print(
        build_harvester_prompt(
            article_text="Tesla reported Q3 revenue of $25.2B yesterday, beating estimates.",
            pub_date_str="2026-04-16",
            topic_block="\nTOPIC FILTER: Tesla\nOnly extract facts directly relevant to this topic.\n\n",
            date_guard=True,
        )
    )

    print("\n\n=== build_harvester_prompt (date_guard=False) ===")
    print(
        build_harvester_prompt(
            article_text="Tesla reported Q3 revenue of $25.2B yesterday, beating estimates.",
            pub_date_str="Unknown",
            topic_block="",
            date_guard=False,
        )
    )

    print("\n\n=== ARBITER_CASE_BLOCK ===")
    print(
        ARBITER_CASE_BLOCK.format(
            new_fact="Company X acquired Company Y for $5B.",
            new_entities="Company X, Company Y",
            new_date="2026-07-01",
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

    print("\n\n=== build_state_of_play_prompt ===")
    print(
        build_state_of_play_prompt(
            topic_name="Middle East Conflict",
            today="July 15, 2026",
            payload='[\n  {"fact": "A ceasefire was signed on June 17.", "significance": "state_change", "date": "2026-06-17", "source": "reuters.com"}\n]',
            max_threads=6,
        )
    )

    print("\n\n=== build_story_summarizer_prompt ===")
    print(
        build_story_summarizer_prompt(
            title="Tesla Q3 Earnings",
            previous_summary="Tesla reported strong Q3 deliveries.",
            new_fact="Tesla stock rose 5% after the report.",
            new_fact_context="Investors reacted positively to delivery numbers.",
            max_summary_length=500,
        )
    )

    print("\n\n=== build_query_rotator_prompt ===")
    print(
        build_query_rotator_prompt(
            raw_query="Tesla stock",
            existing_json='[\n  "Tesla stock price",\n  "Tesla earnings report"\n]',
            max_regen_variants=3,
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
