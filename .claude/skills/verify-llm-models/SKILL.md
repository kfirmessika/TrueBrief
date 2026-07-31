---
description: MANDATORY before writing, editing, or suggesting ANY LLM model ID string anywhere in this repo (config/settings.py LLM_CONFIG, src/truebrief/llm/pricing.py, GROQ_FALLBACK_MODEL, a benchmark script, a prompt, anywhere). Use whenever you're about to type a model name from memory/training data, when the user names a specific model to use, when a 429/quota error names a model, or when adding a new LLM_CONFIG entry. Never skip this because the model name "looks right" or "worked before."
---

# Verify LLM model IDs before using them

## The failure this prevents

`config/settings.py` had `briefer` and `state_of_play` hardcoded to `gemini-2.0-flash` —
a deprecated model with **zero provisioned quota** on this project's billing (not a daily
cap, `limit: 0`). Every real briefer call silently fell through to an expensive Groq
fallback (`llama-3.3-70b-versatile`, $0.59/$0.79 per 1M) for months, and the agent kept
reporting "quota exhausted" as if it were normal cycling instead of checking whether the
configured model was even real anymore. Fixed 2026-07-30 → `gemini-3.5-flash-lite`.

**Do not repeat this.** Training data has a knowledge cutoff; Google/Groq/OpenAI ship new
model names constantly. A model name that "sounds current" from memory is a guess, not a
fact.

## The rule

1. **The user names a model → use that exact string. Do not substitute a name you
   recognize instead.** If the user says "Gemini 3.5 Flash Lite" and you don't know the
   literal API model ID, that is not license to write `gemini-2.0-flash` or any other
   model you *do* recognize. Go get the real string (step 2).
2. **Never type a model ID from memory into code.** Before it lands in `LLM_CONFIG`,
   `GROQ_FALLBACK_MODEL`, `pricing.py`, or any prompt/script, verify it via one of:
   - `WebFetch` against `https://ai.google.dev/gemini-api/docs/pricing` (Gemini) or
     `https://groq.com/pricing` (Groq) — ask for the literal model ID string, not the
     marketing name.
   - A live test call through `LLMClient._call_gemini_instrumented` /
     `_call_groq_instrumented` with that exact string, confirming it returns text and
     not a 404/`RESOURCE_EXHAUSTED` on model-not-found.
3. **A 429/quota error does not always mean "wait and retry."** Read the error body.
   `limit: 0` on a specific model/metric means that model isn't provisioned on this
   billing account at all — retrying forever won't fix it. A nonzero limit that's simply
   used up is a normal daily/minute cap.
4. **After adding or changing any model in `LLM_CONFIG`**, add/update its rate in
   `src/truebrief/llm/pricing.py` (`_INPUT_RATES`/`_OUTPUT_RATES`), then run
   `pytest tests/test_pricing_coverage.py` — it guards against a model silently costing
   $0.000000 in telemetry.
5. **Do a real test call before wiring a new model into production config.** A model ID
   being real and priced doesn't mean it has quota on this specific project — confirm
   with one live call first (see step 2's second bullet), the same way this fix did
   before touching `LLM_CONFIG`.

## Where model IDs live in this repo

| File | What |
|---|---|
| `config/settings.py` → `LLM_CONFIG` | Single source of truth: step name → provider + model |
| `config/settings.py` → `GROQ_FALLBACK_MODEL` / `GROQ_FALLBACK_CHEAP_MODEL` | Emergency Groq fallback when both Gemini keys are quota-exhausted |
| `src/truebrief/llm/pricing.py` | Per-token rates, keyed by exact model ID string — must match `LLM_CONFIG` exactly or the call prices at $0 |
| `src/truebrief/llm/client.py` line ~210 | Hardcoded reverse-fallback model (Groq→Gemini) — also subject to this rule |

Never hand-edit a model string in more than one of these without checking the others —
a typo'd or stale ID in `pricing.py` alone is invisible until someone audits real spend.
