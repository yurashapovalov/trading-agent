"""
ChitchatResponder — handles greetings, thanks, goodbye.

Friendly, concise, professional. Like a colleague greeting a colleague.
Template-based, no LLM needed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from agent.molecules.query import MolecularQuery


@dataclass
class ChitchatResponse:
    """Response from ChitchatResponder."""

    text: str
    subtype: str  # greeting, thanks, goodbye


# Response templates — friendly, like a colleague
RESPONSES = {
    "greeting": {
        "ru": [
            "Привет! Чем помочь?",
            "Привет! Спрашивай про {symbol}.",
            "Здарова! Что смотрим?",
        ],
        "en": [
            "Hi! What can I help with?",
            "Hey! Ask about {symbol}.",
            "Hello! What are we looking at?",
        ],
    },
    "thanks": {
        "ru": [
            "Не за что!",
            "Всегда пожалуйста.",
            "Обращайся!",
        ],
        "en": [
            "No problem!",
            "Anytime.",
            "Sure thing!",
        ],
    },
    "goodbye": {
        "ru": [
            "Пока!",
            "До связи!",
            "Удачи!",
        ],
        "en": [
            "Bye!",
            "Later!",
            "Good luck!",
        ],
    },
}


def _detect_language(text: str) -> str:
    """Simple language detection based on character set."""
    cyrillic_count = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
    return "ru" if cyrillic_count > len(text) * 0.3 else "en"


class ChitchatResponder:
    """
    Handles greetings, thanks, goodbye.

    Friendly, concise — like a colleague.
    Template-based, matches user's language.

    Usage:
        responder = ChitchatResponder(symbol="NQ")
        result = responder.respond(query, original_question="Привет!")
        # → "Привет! Чем помочь?"
    """

    def __init__(self, symbol: str = "NQ"):
        self.symbol = symbol

    def respond(
        self,
        query: MolecularQuery,
        original_question: str = "",
    ) -> ChitchatResponse:
        """
        Generate chitchat response.

        Args:
            query: MolecularQuery with intent=CHITCHAT, summary=subtype
            original_question: User's original question for language detection

        Returns:
            ChitchatResponse with text and subtype
        """
        # Get subtype from query summary
        subtype = (query.summary or "greeting").lower()
        if subtype not in RESPONSES:
            subtype = "greeting"

        # Detect language
        lang = _detect_language(original_question)

        # Pick random response
        templates = RESPONSES[subtype][lang]
        template = random.choice(templates)

        # Format with symbol
        text = template.format(symbol=self.symbol)

        return ChitchatResponse(text=text, subtype=subtype)
