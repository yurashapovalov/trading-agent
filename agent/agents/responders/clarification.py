"""
ClarificationResponder — asks user for missing information.

Friendly, concise, professional. Like a colleague asking a colleague.

Clarifies:
- year: which year for the analysis
- session: which trading session (RTH, ETH, etc.)
- period: time range
"""

from __future__ import annotations

from dataclasses import dataclass

from agent.molecules.query import MolecularQuery
from agent.config.market import get_instrument


@dataclass
class ClarificationResponse:
    """Response from ClarificationResponder."""

    text: str
    fields: list[str]  # Fields that need clarification


def _detect_language(text: str) -> str:
    """Simple language detection based on character set."""
    cyrillic_count = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
    return "ru" if cyrillic_count > len(text) * 0.3 else "en"


def _format_sessions(instrument: dict) -> str:
    """Format available sessions from instrument config."""
    sessions = instrument.get("sessions", {})
    if not sessions:
        return "RTH, ETH"

    # Format: RTH (09:30–17:00), ETH (18:00–17:00)
    parts = [
        f"{name} ({times[0]}–{times[1]})"
        for name, times in sessions.items()
    ]
    return ", ".join(parts[:3])  # Show first 3 main sessions


class ClarificationResponder:
    """
    Asks user for missing information.

    Friendly, concise, professional — like a colleague.
    Template-based, no LLM needed.

    Usage:
        responder = ClarificationResponder(symbol="NQ")
        result = responder.respond(query, original_question="что было 10 января")
        # → "За какой год? Данные есть с 2008 по 2026."
    """

    def __init__(self, symbol: str = "NQ"):
        self.symbol = symbol
        self.instrument = get_instrument(symbol) or {}

    def respond(
        self,
        query: MolecularQuery,
        original_question: str = "",
    ) -> ClarificationResponse:
        """
        Generate clarification request.

        Args:
            query: MolecularQuery with unclear fields
            original_question: User's original question

        Returns:
            ClarificationResponse with question text
        """
        fields = query.unclear or ["question"]
        lang = _detect_language(original_question)

        # Get data range from instrument
        data_start = self.instrument.get("data_start", "2008")[:4]
        data_end = self.instrument.get("data_end", "2026")[:4]
        sessions_str = _format_sessions(self.instrument)

        # Templates by field and language
        # Friendly, concise — like a colleague asking a colleague
        templates = {
            "year": {
                "ru": f"За какой год? Данные есть с {data_start} по {data_end}.",
                "en": f"Which year? Got data from {data_start} to {data_end}.",
            },
            "session": {
                "ru": f"Какая сессия? {sessions_str}",
                "en": f"Which session? {sessions_str}",
            },
            "symbol": {
                "ru": f"Какой инструмент? Сейчас на {self.symbol}.",
                "en": f"Which instrument? Currently on {self.symbol}.",
            },
            "period": {
                "ru": "За какой период?",
                "en": "What period?",
            },
            "question": {
                "ru": "Уточни вопрос?",
                "en": "Could you clarify?",
            },
        }

        # Build clarification text for each field
        parts = []
        for field in fields:
            field_templates = templates.get(field, templates["question"])
            parts.append(field_templates[lang])

        return ClarificationResponse(
            text=" ".join(parts),
            fields=fields,
        )
