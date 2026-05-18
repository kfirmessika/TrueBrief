"""
LLM Pricing Constants - llm/pricing.py

Hard-coded per-token cost rates for each model we use.
Source: Google AI Studio pricing page (as of 2026-05-19).
Update when Google changes rates.

All costs are in USD per token.
"""

# Gemini 2.0 Flash Lite (production model — query_builder, harvester, arbiter, summarizer)
# Price tier: ≤128k context window
GEMINI_FLASH_LITE_INPUT_PER_TOKEN = 0.000_000_075   # $0.075 per 1M tokens
GEMINI_FLASH_LITE_OUTPUT_PER_TOKEN = 0.000_000_300  # $0.30 per 1M tokens

# Gemini 2.0 Flash (premium model — briefer)
GEMINI_FLASH_INPUT_PER_TOKEN = 0.000_000_100   # $0.10 per 1M tokens
GEMINI_FLASH_OUTPUT_PER_TOKEN = 0.000_000_400  # $0.40 per 1M tokens

# Gemini 1.5 Pro (fallback reference, not currently used in pipeline)
GEMINI_PRO_INPUT_PER_TOKEN = 0.000_001_250    # $1.25 per 1M tokens
GEMINI_PRO_OUTPUT_PER_TOKEN = 0.000_005_000   # $5.00 per 1M tokens

# text-embedding-004 / gemini-embedding-2 — free tier at this scale
GEMINI_EMBEDDING_PER_TOKEN = 0.0


_INPUT_RATES: dict[str, float] = {
    "gemini-2.0-flash-lite": GEMINI_FLASH_LITE_INPUT_PER_TOKEN,
    "gemini-2.0-flash-lite-001": GEMINI_FLASH_LITE_INPUT_PER_TOKEN,
    "gemini-2.0-flash": GEMINI_FLASH_INPUT_PER_TOKEN,
    "gemini-2.0-flash-001": GEMINI_FLASH_INPUT_PER_TOKEN,
    "gemini-1.5-pro": GEMINI_PRO_INPUT_PER_TOKEN,
    "models/gemini-embedding-2": GEMINI_EMBEDDING_PER_TOKEN,
    "models/text-embedding-004": GEMINI_EMBEDDING_PER_TOKEN,
}

_OUTPUT_RATES: dict[str, float] = {
    "gemini-2.0-flash-lite": GEMINI_FLASH_LITE_OUTPUT_PER_TOKEN,
    "gemini-2.0-flash-lite-001": GEMINI_FLASH_LITE_OUTPUT_PER_TOKEN,
    "gemini-2.0-flash": GEMINI_FLASH_OUTPUT_PER_TOKEN,
    "gemini-2.0-flash-001": GEMINI_FLASH_OUTPUT_PER_TOKEN,
    "gemini-1.5-pro": GEMINI_PRO_OUTPUT_PER_TOKEN,
    "models/gemini-embedding-2": GEMINI_EMBEDDING_PER_TOKEN,
    "models/text-embedding-004": GEMINI_EMBEDDING_PER_TOKEN,
}


def compute_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated USD cost for one LLM call. Returns 0.0 for unknown models."""
    in_rate = _INPUT_RATES.get(model, 0.0)
    out_rate = _OUTPUT_RATES.get(model, 0.0)
    return input_tokens * in_rate + output_tokens * out_rate
