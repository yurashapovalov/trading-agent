"""
Responder agent — handles non-data queries.

Single responsibility: respond to anything that's not a data query,
always steering conversation back to the domain.

Handles:
- Greetings, thanks, goodbye
- Trading concept explanations
- Cancellations ("забей", "неважно")
- Off-topic redirects (politely declines, steers back)

Uses:
- prompts/responder.py for prompt constants
- Gemini for LLM calls
"""

from dataclasses import dataclass

from google import genai
from google.genai import types

import config
from agent.types import Usage
from agent.prompts.responder import SYSTEM_PROMPT, USER_PROMPT


@dataclass
class ResponderResult:
    """Responder result with usage."""
    text: str
    usage: Usage = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = Usage()


class Responder:
    """
    Handles non-data queries with domain focus.

    Always steers conversation back to trading/market analysis.
    Politely declines off-topic questions.

    Usage:
        responder = Responder()
        result = responder.respond("привет", lang="ru")
        # → "Привет! Могу помочь с анализом NQ..."
    """

    def __init__(self, symbol: str = "NQ", model: str | None = None):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = model or config.GEMINI_LITE_MODEL
        self.symbol = symbol

    def respond(self, question: str, lang: str = "en") -> ResponderResult:
        """
        Generate response for non-data query.

        Args:
            question: User's question
            lang: ISO 639-1 language code (en, ru, es, etc.)

        Returns:
            ResponderResult with text and usage
        """
        # Build prompts
        system = SYSTEM_PROMPT.format(symbol=self.symbol)
        user = USER_PROMPT.format(question=question, lang=lang)

        # Call LLM
        response = self.client.models.generate_content(
            model=self.model,
            contents=f"{system}\n\n{user}",
            config=types.GenerateContentConfig(
                temperature=0.7,  # Slightly creative for natural responses
                max_output_tokens=150,
            ),
        )

        usage = Usage.from_response(response)
        return ResponderResult(text=response.text.strip(), usage=usage)


# =============================================================================
# Simple API
# =============================================================================

def respond(question: str, lang: str = "en", symbol: str = "NQ") -> ResponderResult:
    """
    Generate response for non-data query.

    Simple wrapper for Responder class.

    Args:
        question: User's question
        lang: ISO 639-1 language code (en, ru, es, etc.)
        symbol: Trading symbol

    Returns:
        ResponderResult with text and usage
    """
    responder = Responder(symbol=symbol)
    return responder.respond(question, lang)
