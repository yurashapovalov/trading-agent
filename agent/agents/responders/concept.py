"""
ConceptResponder — explains trading terms and concepts.

Uses LLM with domain context to explain:
- Sessions: RTH, ETH, OVERNIGHT
- Events: OPEX, NFP, FOMC, CPI
- Patterns: hammer, doji, engulfing, morning_star
- Terms: gap, range, volatility
"""

from __future__ import annotations

from dataclasses import dataclass

from google import genai
from google.genai import types

import config
from agent.molecules.query import MolecularQuery
from agent.config.market import get_instrument, get_event_types_for_instrument
from agent.config.patterns import get_candle_pattern, get_price_pattern


@dataclass
class ConceptResponse:
    """Response from ConceptResponder."""

    text: str
    concept: str  # The term that was explained


def _format_domain_context(symbol: str) -> str:
    """Generate domain context for concept explanations."""
    instrument = get_instrument(symbol)
    if not instrument:
        return ""

    # Sessions
    sessions = instrument.get("sessions", {})
    session_lines = [
        f"- {name}: {times[0]}–{times[1]} ET"
        for name, times in sessions.items()
    ]

    # Events
    events = get_event_types_for_instrument(symbol)
    event_lines = [
        f"- {e.id.upper()}: {e.name} ({e.schedule})"
        for e in events
        if e.impact.value in ("high", "medium")
    ][:10]

    return f"""<domain>
Instrument: {symbol} ({instrument['name']})
Timezone: ET (Eastern Time)

Sessions:
{chr(10).join(session_lines)}

Events:
{chr(10).join(event_lines)}
</domain>"""


def _format_pattern_context(concept: str) -> str:
    """Get pattern knowledge if concept is a pattern."""
    # Try candle pattern
    pattern = get_candle_pattern(concept)
    if not pattern:
        pattern = get_price_pattern(concept)

    if not pattern:
        return ""

    signal = pattern.get("signal", "neutral")
    desc = pattern.get("description", "")
    related = pattern.get("related", [])
    reliability = pattern.get("reliability", 0)
    opposite = pattern.get("opposite")
    confirms = pattern.get("confirms", [])
    candles = pattern.get("candles", 1)

    lines = [
        f"<pattern_knowledge>",
        f"Pattern: {pattern['name']}",
        f"Signal: {signal}",
        f"Description: {desc}",
        f"Candles: {candles}",
    ]

    if reliability:
        lines.append(f"Reliability: {int(reliability * 100)}%")
    if related:
        lines.append(f"Related patterns: {', '.join(related)}")
    if opposite:
        lines.append(f"Opposite: {opposite}")
    if confirms:
        lines.append(f"Confirmed by: {', '.join(confirms)}")

    lines.append("</pattern_knowledge>")
    return "\n".join(lines)


SYSTEM_PROMPT = """<role>
You are a friendly, professional trading expert.
Tone: helpful, concise, knowledgeable. Like a colleague explaining to a colleague.
</role>

{domain_context}

{pattern_context}

<task>
Explain: {concept}

Response structure:
- Definition (1-2 sentences, clear)
- Example on {symbol} if applicable
- Why it matters for trading
- Max 80 words, no fluff

IMPORTANT: Same language as user's question.
</task>"""


class ConceptResponder:
    """
    Explains trading terms and concepts.

    Uses LLM with domain context for accurate explanations.

    Usage:
        responder = ConceptResponder(symbol="NQ")
        result = responder.respond(query, original_question="что такое RTH?")
    """

    def __init__(self, symbol: str = "NQ"):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = config.GEMINI_LITE_MODEL
        self.symbol = symbol

    def respond(
        self,
        query: MolecularQuery,
        original_question: str = "",
    ) -> ConceptResponse:
        """
        Generate concept explanation.

        Args:
            query: MolecularQuery with intent=CONCEPT, summary=term
            original_question: User's original question

        Returns:
            ConceptResponse with explanation text
        """
        concept = query.summary or "trading"

        # Build prompt
        domain_context = _format_domain_context(self.symbol)
        pattern_context = _format_pattern_context(concept)
        prompt = SYSTEM_PROMPT.format(
            domain_context=domain_context,
            pattern_context=pattern_context,
            concept=concept,
            symbol=self.symbol,
        )

        # Add user question for language detection
        full_prompt = f"{prompt}\n\nUser question: {original_question}"

        # Call LLM
        response = self.client.models.generate_content(
            model=self.model,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,  # Slightly creative for explanations
            ),
        )

        text = response.text.strip()

        return ConceptResponse(text=text, concept=concept)
