"""
Responder agent — handles chitchat and concept explanations.

Single responsibility: respond to non-data queries.

Handles:
- chitchat: greetings, thanks, goodbye
- concept: explain trading terms (OPEX, RTH, volatility, etc.)

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
    Handles casual conversation and concept explanations.

    For non-data queries: chitchat and trading concepts.
    Data presentation is handled by Presenter.

    Usage:
        responder = Responder()

        # Chitchat
        result = responder.respond("привет", intent="chitchat")
        # → "Привет! Чем помочь с анализом NQ?"

        # Concept
        result = responder.respond("что такое OPEX", intent="concept", topic="OPEX")
        # → "OPEX — день экспирации опционов..."
    """

    def __init__(self, symbol: str = "NQ", model: str | None = None):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = model or config.GEMINI_LITE_MODEL
        self.symbol = symbol

    def respond(
        self,
        question: str,
        intent: str = "chitchat",
        subtype: str = "greeting",
        topic: str = "",
    ) -> ResponderResult:
        """
        Generate response for chitchat or concept query.

        Args:
            question: User's question
            intent: "chitchat" or "concept"
            subtype: For chitchat - "greeting", "thanks", "goodbye"
            topic: For concept - the term to explain

        Returns:
            ResponderResult with text and usage
        """
        # Build prompts
        system = SYSTEM_PROMPT.format(symbol=self.symbol)
        user = USER_PROMPT.format(
            intent=intent,
            subtype=subtype,
            topic=topic or self._extract_topic(question),
            question=question,
        )

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

    def _extract_topic(self, question: str) -> str:
        """Extract topic from concept question."""
        # Simple extraction: remove common prefixes
        q = question.lower()
        for prefix in ["что такое ", "what is ", "what's ", "explain "]:
            if q.startswith(prefix):
                return question[len(prefix):].strip("?").strip()
        return question


# =============================================================================
# Simple API
# =============================================================================

def respond(
    question: str,
    intent: str = "chitchat",
    subtype: str = "greeting",
    topic: str = "",
    symbol: str = "NQ",
) -> ResponderResult:
    """
    Generate response for chitchat or concept.

    Simple wrapper for Responder class.

    Args:
        question: User's question
        intent: "chitchat" or "concept"
        subtype: For chitchat - "greeting", "thanks", "goodbye"
        topic: For concept - the term to explain
        symbol: Trading symbol

    Returns:
        ResponderResult with text and usage
    """
    responder = Responder(symbol=symbol)
    return responder.respond(question, intent, subtype, topic)
