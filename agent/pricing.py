"""LLM Pricing Constants

Update these values when pricing changes.
All prices are per 1 million tokens.
"""

# Gemini 3 Flash Preview
GEMINI_3_FLASH = {
    "input": 0.50,      # $/1M tokens (text/image/video)
    "output": 3.00,     # $/1M tokens (includes thinking)
    "audio_input": 1.00,  # $/1M tokens
    "cached_input": 0.05,  # $/1M tokens
}

# Gemini 2.0 Flash
GEMINI_2_FLASH = {
    "input": 0.10,      # $/1M tokens
    "output": 0.40,     # $/1M tokens
}

# Gemini 2.5 Flash Lite (cheapest option)
GEMINI_2_5_FLASH_LITE = {
    "input": 0.10,      # $/1M tokens (text/image/video)
    "output": 0.40,     # $/1M tokens (including thinking)
}

# Claude Haiku 4.5
CLAUDE_HAIKU = {
    "input": 1.00,      # $/1M tokens
    "output": 5.00,     # $/1M tokens
}

# Claude Sonnet 4.5
CLAUDE_SONNET = {
    "input": 3.00,      # $/1M tokens
    "output": 15.00,    # $/1M tokens
}

# Default pricing (used by current model)
CURRENT_MODEL_PRICING = GEMINI_3_FLASH


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    thinking_tokens: int = 0,
    pricing: dict = None
) -> float:
    """Calculate cost in USD for a request.

    Args:
        input_tokens: Number of input/prompt tokens
        output_tokens: Number of output/completion tokens
        thinking_tokens: Number of thinking tokens (Gemini 3)
        pricing: Pricing dict (defaults to CURRENT_MODEL_PRICING)

    Returns:
        Cost in USD
    """
    if pricing is None:
        pricing = CURRENT_MODEL_PRICING

    # Thinking tokens are billed as output
    total_output = output_tokens + thinking_tokens

    cost = (
        input_tokens * pricing["input"] +
        total_output * pricing["output"]
    ) / 1_000_000

    return cost
