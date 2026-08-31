"""
Guards against the exact bug found 2026-07-22: a model gets added to LLM_CONFIG (or as
GROQ_FALLBACK_MODEL) without a matching entry in llm/pricing.py, so every call using it
silently computes cost_usd=0.0 forever, with no error anywhere.

Checks every model any step could resolve to (both branches of GROQ_API_KEY-conditional
routing), not just whichever branch happens to be active in this environment.
"""
from truebrief.llm import pricing

# Models that are legitimately free (self-hosted / free-tier embeddings) — not a pricing gap.
_FREE_ALLOWLIST = {
    "models/gemini-embedding-2",
    "models/text-embedding-004",
}

# Every model any LLM_CONFIG step could resolve to, across both the Groq-present and
# Groq-absent branches, plus the last-resort cross-provider fallback model.
_ALL_POSSIBLE_MODELS = {
    "gemini-3.1-flash-lite",
    "gemini-2.0-flash",
    "llama-3.1-8b-instant",   # dashboard_summary / story_stitch when GROQ_API_KEY is set
    "llama-3.3-70b-versatile",  # signal_scorer when GROQ_API_KEY is set; GROQ_FALLBACK_MODEL
    "text-embedding-3-small",  # embedding when EMBED_PROVIDER=openai
    "text-embedding-3-large",
}


def test_every_possible_model_has_a_priced_rate():
    unpriced = []
    for model in _ALL_POSSIBLE_MODELS:
        if model in _FREE_ALLOWLIST:
            continue
        in_rate = pricing._INPUT_RATES.get(model)
        out_rate = pricing._OUTPUT_RATES.get(model)
        if not in_rate or not out_rate:
            unpriced.append((model, in_rate, out_rate))
    assert not unpriced, (
        f"Model(s) with no (or zero) pricing entry — every call would silently log "
        f"cost_usd=0.0: {unpriced}. Add rates to llm/pricing.py's _INPUT_RATES/_OUTPUT_RATES "
        f"(or add to _FREE_ALLOWLIST above if genuinely free)."
    )


def test_groq_fallback_model_is_priced():
    from config.settings import settings

    fallback = settings.GROQ_FALLBACK_MODEL
    assert fallback in pricing._INPUT_RATES and fallback in pricing._OUTPUT_RATES, (
        f"GROQ_FALLBACK_MODEL={fallback!r} has no pricing entry — every fallback call "
        f"(fired when both Gemini keys are quota-exhausted) would silently cost $0."
    )


def test_compute_cost_usd_is_nonzero_for_a_real_call_shape():
    """Sanity check compute_cost_usd itself, not just the rate dicts."""
    cost = pricing.compute_cost_usd("gemini-3.1-flash-lite", input_tokens=1000, output_tokens=200)
    assert cost > 0, "compute_cost_usd returned 0 for a priced model with nonzero tokens."

    cost = pricing.compute_cost_usd("llama-3.3-70b-versatile", input_tokens=1000, output_tokens=200)
    assert cost > 0, "compute_cost_usd returned 0 for llama-3.3-70b-versatile — the exact bug this file guards against."
