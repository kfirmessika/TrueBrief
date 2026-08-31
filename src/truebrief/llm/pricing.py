"""
LLM Pricing Constants - llm/pricing.py

Hard-coded per-token cost rates for each model we use.
Source: Google AI Studio pricing page (as of 2026-05-19).
Update when Google changes rates.

All costs are in USD per token.
"""

# Gemini 2.0 Flash Lite (production model — arbiter, embeddings)
# Price tier: ≤128k context window
GEMINI_FLASH_LITE_INPUT_PER_TOKEN = 0.000_000_075   # $0.075 per 1M tokens
GEMINI_FLASH_LITE_OUTPUT_PER_TOKEN = 0.000_000_300  # $0.30 per 1M tokens

# Gemini 2.0 Flash (premium model — briefer)
GEMINI_FLASH_INPUT_PER_TOKEN = 0.000_000_100   # $0.10 per 1M tokens
GEMINI_FLASH_OUTPUT_PER_TOKEN = 0.000_000_400  # $0.40 per 1M tokens

# Gemini 1.5 Pro (fallback reference, not currently used in pipeline)
GEMINI_PRO_INPUT_PER_TOKEN = 0.000_001_250    # $1.25 per 1M tokens
GEMINI_PRO_OUTPUT_PER_TOKEN = 0.000_005_000   # $5.00 per 1M tokens

# Gemini 2.5 Flash Lite — V5's gemini_search step (Google Search grounding tool).
# Verified as of 2026-07-22 (ai.google.dev/gemini-api/docs/pricing, standard tier).
GEMINI_25_FLASH_LITE_INPUT_PER_TOKEN = 0.000_000_100   # $0.10 per 1M tokens
GEMINI_25_FLASH_LITE_OUTPUT_PER_TOKEN = 0.000_000_400  # $0.40 per 1M tokens

# Gemini 3.5 Flash Lite — briefer. Verified 2026-07-30 (ai.google.dev
# /gemini-api/docs/pricing, standard tier). Do not swap this for an older name from
# training data — always confirm the current model ID against this same page first.
GEMINI_35_FLASH_LITE_INPUT_PER_TOKEN = 0.000_000_300   # $0.30 per 1M tokens
GEMINI_35_FLASH_LITE_OUTPUT_PER_TOKEN = 0.000_002_500  # $2.50 per 1M tokens

# text-embedding-004 / gemini-embedding-2 — free tier at this scale
GEMINI_EMBEDDING_PER_TOKEN = 0.0

# Local embeddings (EMBED_PROVIDER=local, llm/local_embedder.py) — sentence-transformers
# running on-device, no external API call, genuinely free (not "free tier", actually $0
# forever). llm/client.py logs these under model="local/<LOCAL_EMBED_MODEL>" so they can't
# be confused with billed Gemini embedding usage in llm_call_log / cost-by-stage. Entry here
# is for config/settings.py's default LOCAL_EMBED_MODEL; a custom LOCAL_EMBED_MODEL value
# still resolves to $0 via compute_cost_usd's unknown-model fallback below.
LOCAL_EMBEDDING_PER_TOKEN = 0.0

# OpenAI text-embedding-3-small ($0.02 per 1M tokens)
OPENAI_EMBED_3_SMALL_PER_TOKEN = 0.000_000_020
# OpenAI text-embedding-3-large ($0.13 per 1M tokens)
OPENAI_EMBED_3_LARGE_PER_TOKEN = 0.000_000_130
# OpenAI text-embedding-ada-002 ($0.10 per 1M tokens)
OPENAI_EMBED_ADA_002_PER_TOKEN = 0.000_000_100

# Groq — Llama 3.1 8B Instant. Used for story_stitch and dashboard_summary steps.
# Source: Groq pricing (llama-3.1-8b-instant), as of 2026-07.
GROQ_LLAMA8B_INPUT_PER_TOKEN = 0.000_000_050   # $0.05 per 1M tokens
GROQ_LLAMA8B_OUTPUT_PER_TOKEN = 0.000_000_080  # $0.08 per 1M tokens

# Groq — Llama 3.3 70B Versatile. Used as GROQ_FALLBACK_MODEL (config/settings.py)
# for any step when Gemini keys are quota-exhausted.
# Was missing here entirely, causing those calls to silently cost $0 in llm_call_log — see
# tests/test_pricing_coverage.py, which now guards against this recurring.
# Source: Groq pricing (llama-3.3-70b-versatile), verified 2026-07-22.
GROQ_LLAMA70B_INPUT_PER_TOKEN = 0.000_000_590   # $0.59 per 1M tokens
GROQ_LLAMA70B_OUTPUT_PER_TOKEN = 0.000_000_790  # $0.79 per 1M tokens


_INPUT_RATES: dict[str, float] = {
    "gemini-3.1-flash-lite-preview": GEMINI_FLASH_LITE_INPUT_PER_TOKEN,
    "gemini-3.1-flash-lite": GEMINI_FLASH_LITE_INPUT_PER_TOKEN,
    "gemini-2.0-flash-lite": GEMINI_FLASH_LITE_INPUT_PER_TOKEN,
    "gemini-2.0-flash-lite-001": GEMINI_FLASH_LITE_INPUT_PER_TOKEN,
    "gemini-2.0-flash": GEMINI_FLASH_INPUT_PER_TOKEN,
    "gemini-2.0-flash-001": GEMINI_FLASH_INPUT_PER_TOKEN,
    "gemini-1.5-pro": GEMINI_PRO_INPUT_PER_TOKEN,
    "models/gemini-embedding-2": GEMINI_EMBEDDING_PER_TOKEN,
    "models/text-embedding-004": GEMINI_EMBEDDING_PER_TOKEN,
    "local/BAAI/bge-base-en-v1.5": LOCAL_EMBEDDING_PER_TOKEN,
    "text-embedding-3-small": OPENAI_EMBED_3_SMALL_PER_TOKEN,
    "text-embedding-3-large": OPENAI_EMBED_3_LARGE_PER_TOKEN,
    "text-embedding-ada-002": OPENAI_EMBED_ADA_002_PER_TOKEN,
    "llama-3.1-8b-instant": GROQ_LLAMA8B_INPUT_PER_TOKEN,
    "llama-3.3-70b-versatile": GROQ_LLAMA70B_INPUT_PER_TOKEN,
    "gemini-2.5-flash-lite": GEMINI_25_FLASH_LITE_INPUT_PER_TOKEN,
    "gemini-3.5-flash-lite": GEMINI_35_FLASH_LITE_INPUT_PER_TOKEN,
}

_OUTPUT_RATES: dict[str, float] = {
    "gemini-3.1-flash-lite-preview": GEMINI_FLASH_LITE_OUTPUT_PER_TOKEN,
    "gemini-3.1-flash-lite": GEMINI_FLASH_LITE_OUTPUT_PER_TOKEN,
    "gemini-2.0-flash-lite": GEMINI_FLASH_LITE_OUTPUT_PER_TOKEN,
    "gemini-2.0-flash-lite-001": GEMINI_FLASH_LITE_OUTPUT_PER_TOKEN,
    "gemini-2.0-flash": GEMINI_FLASH_OUTPUT_PER_TOKEN,
    "gemini-2.0-flash-001": GEMINI_FLASH_OUTPUT_PER_TOKEN,
    "gemini-1.5-pro": GEMINI_PRO_OUTPUT_PER_TOKEN,
    "models/gemini-embedding-2": GEMINI_EMBEDDING_PER_TOKEN,
    "models/text-embedding-004": GEMINI_EMBEDDING_PER_TOKEN,
    "local/BAAI/bge-base-en-v1.5": LOCAL_EMBEDDING_PER_TOKEN,
    "text-embedding-3-small": OPENAI_EMBED_3_SMALL_PER_TOKEN,
    "text-embedding-3-large": OPENAI_EMBED_3_LARGE_PER_TOKEN,
    "text-embedding-ada-002": OPENAI_EMBED_ADA_002_PER_TOKEN,
    "llama-3.1-8b-instant": GROQ_LLAMA8B_OUTPUT_PER_TOKEN,
    "llama-3.3-70b-versatile": GROQ_LLAMA70B_OUTPUT_PER_TOKEN,
    "gemini-2.5-flash-lite": GEMINI_25_FLASH_LITE_OUTPUT_PER_TOKEN,
    "gemini-3.5-flash-lite": GEMINI_35_FLASH_LITE_OUTPUT_PER_TOKEN,
}

# V4 steps that we bill at Groq rates regardless of the model actually serving them.
# When we move these to real Groq, drop the override — the model name will price itself.
_COST_AS_GROQ_STEPS: set[str] = {"dashboard_summary", "story_stitch"}


def compute_cost_usd(
    model: str, input_tokens: int, output_tokens: int, stage: str | None = None
) -> float:
    """Return estimated USD cost for one LLM call. Returns 0.0 for unknown models.

    If `stage` is one of the V4 cheap-LLM steps, cost is computed at Groq Llama-3.1-8B
    rates instead of the serving model's — so the projection reflects the target
    provider even while we prototype on Gemini's free tier.
    """
    if stage in _COST_AS_GROQ_STEPS:
        return (
            input_tokens * GROQ_LLAMA8B_INPUT_PER_TOKEN
            + output_tokens * GROQ_LLAMA8B_OUTPUT_PER_TOKEN
        )
    in_rate = _INPUT_RATES.get(model, 0.0)
    out_rate = _OUTPUT_RATES.get(model, 0.0)
    return input_tokens * in_rate + output_tokens * out_rate
