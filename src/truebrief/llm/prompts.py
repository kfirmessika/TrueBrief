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
