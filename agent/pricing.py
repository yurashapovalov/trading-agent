"""LLM pricing constants for cost calculation.

Prices are per 1 million tokens. Update when provider pricing changes.

Supported models:
- Gemini 3 Flash Preview (gemini-3-flash-preview)
- Gemini 2.5 Flash Lite Preview (gemini-2.5-flash-lite-preview-09-2025)

Example:
    cost = calculate_cost(input_tokens=1000, output_tokens=500, model="gemini-2.5-flash-lite-preview-09-2025")
"""

# =============================================================================
# Pricing per model ($/1M tokens)
# =============================================================================

# Gemini 3 Flash Preview
GEMINI_3_FLASH = {
    "input": 0.50,
    "output": 3.00,
    "cached_input": 0.05,  # 90% discount
}

# Gemini 2.5 Flash Lite Preview
GEMINI_2_5_FLASH_LITE = {
    "input": 0.10,
    "output": 0.40,
    "cached_input": 0.01,  # 90% discount
}

# =============================================================================
# Model -> Pricing mapping
# =============================================================================

MODEL_PRICING = {
    "gemini-3-flash": GEMINI_3_FLASH,
    "gemini-2.5-flash-lite": GEMINI_2_5_FLASH_LITE,  # matches gemini-2.5-flash-lite-preview-09-2025
}

# Default fallback
DEFAULT_PRICING = GEMINI_3_FLASH


def get_pricing(model: str | None) -> dict:
    """Get pricing dict for model name (partial match).

    Args:
        model: Model name (e.g., "gemini-2.5-flash-lite", "gemini-3-flash-preview")

    Returns:
        Pricing dict with input/output/cached_input rates
    """
    if not model:
        return DEFAULT_PRICING

    model_lower = model.lower()
    for key, pricing in MODEL_PRICING.items():
        if key in model_lower:
            return pricing

    return DEFAULT_PRICING


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    thinking_tokens: int = 0,
    cached_tokens: int = 0,
    model: str | None = None,
) -> float:
    """Calculate cost in USD for a request.

    Args:
        input_tokens: Number of input/prompt tokens (total, including cached)
        output_tokens: Number of output/completion tokens
        thinking_tokens: Number of thinking tokens (billed as output)
        cached_tokens: Number of tokens served from cache (subset of input_tokens)
        model: Model name for pricing lookup

    Returns:
        Cost in USD
    """
    pricing = get_pricing(model)

    # Cached tokens are billed at reduced rate
    # input_tokens includes cached, so we subtract cached and add at cached rate
    non_cached_input = input_tokens - cached_tokens
    cached_input_cost = cached_tokens * pricing.get("cached_input", pricing["input"])
    regular_input_cost = non_cached_input * pricing["input"]

    # Thinking tokens are billed as output
    total_output = output_tokens + thinking_tokens
    output_cost = total_output * pricing["output"]

    cost = (regular_input_cost + cached_input_cost + output_cost) / 1_000_000

    return cost
