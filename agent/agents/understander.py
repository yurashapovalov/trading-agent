"""
Understander — understand what user wants before parsing.

Expands vague questions into clear, unambiguous queries for Parser.
Asks clarifying questions when needed.

Uses GEMINI_MODEL (flash) — needs more reasoning than lite.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

import config
from agent.types import Usage
from agent.config.market.instruments import get_instrument
from agent.config.market.events import get_event_types_for_instrument
from agent.config.patterns import CANDLE_PATTERNS, PRICE_PATTERNS

logger = logging.getLogger(__name__)

# Prompt path
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "understander" / "base.md"


class ClarificationItem(BaseModel):
    """Single item that needs clarification."""
    field: str = Field(description="What needs clarification: goal, period, metric, operation, etc.")
    reason: str = Field(description="Why this is unclear or needed")
    options: list[str] | None = Field(default=None, description="Suggested options if applicable")


class ClarificationRequest(BaseModel):
    """Structured clarification request for Clarifier."""
    required: list[ClarificationItem] = Field(
        default_factory=list,
        description="Must clarify — cannot answer without these"
    )
    optional: list[ClarificationItem] = Field(
        default_factory=list,
        description="Nice to have — can use defaults but better to know"
    )
    context: str | None = Field(
        default=None,
        description="What we already understood (for Clarifier context)"
    )


class UnderstanderOutput(BaseModel):
    """Understander structured output."""
    intent: Literal["data", "chitchat", "concept"] = Field(
        description="data=query about market, chitchat=greeting/thanks, concept=explain term"
    )
    goal: str | None = Field(
        default=None,
        description="Why user needs this: sizing stops, compare days, check pattern, etc."
    )
    understood: bool = Field(
        description="True if query is clear enough for Parser"
    )
    expanded_query: str | None = Field(
        default=None,
        description="Clear, unambiguous query for Parser. Include operation, metric, period, filters."
    )
    need_clarification: ClarificationRequest | None = Field(
        default=None,
        description="If understood=false, what to ask"
    )


@dataclass
class UnderstanderResult:
    """Understander result."""
    intent: Literal["data", "chitchat", "concept"]
    goal: str | None = None
    understood: bool = False
    expanded_query: str | None = None
    need_clarification: ClarificationRequest | None = None
    usage: Usage = field(default_factory=Usage)


class Understander:
    """
    Understand what user wants before parsing.

    Expands vague questions into clear queries.
    Asks clarifying questions via Clarifier when needed.
    """

    def __init__(self, model: str | None = None):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = model or config.GEMINI_MODEL  # flash, not lite
        self._base_prompt = None

    def _load_base_prompt(self) -> str:
        """Load base prompt from file."""
        if self._base_prompt is None:
            self._base_prompt = PROMPT_PATH.read_text(encoding="utf-8")
        return self._base_prompt

    def _build_instrument_context(self, instrument: str) -> str:
        """Build instrument context from config."""
        cfg = get_instrument(instrument)
        if not cfg:
            return ""

        sessions = list(cfg.get("sessions", {}).keys())

        lines = [
            "<instrument>",
            f"Symbol: {instrument}",
            f"Sessions: {', '.join(sessions)}",
            f"Default session: {cfg.get('default_session', 'RTH')}",
        ]

        # Add events
        events = get_event_types_for_instrument(instrument)
        if events:
            event_ids = [e.id for e in events]
            lines.append(f"Events: {', '.join(event_ids)}")

        lines.append("</instrument>")
        return "\n".join(lines)

    def _build_patterns_context(self) -> str:
        """Build patterns context from config."""
        candle = list(CANDLE_PATTERNS.keys())
        price = list(PRICE_PATTERNS.keys())

        return f"""<available_patterns>
Candle: {', '.join(candle)}
Price: {', '.join(price)}
</available_patterns>"""

    def _build_operations_context(self) -> str:
        """Build operations context."""
        return """<available_operations>
- list: show top N items (top 10 by volume)
- count: aggregate stats (how many, average)
- compare: compare groups (mondays vs fridays)
- distribution: histogram/percentiles (typical range)
- around: before/after event (what happens after gap up)
- probability: chance of outcome (probability of green after doji)
- streak: consecutive patterns (3 red days in a row)
- correlation: relationship between metrics
- formation: when high/low forms during day
</available_operations>"""

    def _build_prompt(self, question: str, instrument: str = "NQ", lang: str = "en") -> str:
        """Build full prompt with context."""
        base = self._load_base_prompt()
        instrument_ctx = self._build_instrument_context(instrument)
        patterns_ctx = self._build_patterns_context()
        operations_ctx = self._build_operations_context()

        return f"""{base}

{instrument_ctx}

{patterns_ctx}

{operations_ctx}

<user_language>
{lang}
</user_language>

<user_question>
{question}
</user_question>"""

    def understand(self, question: str, instrument: str = "NQ", lang: str = "en") -> UnderstanderResult:
        """
        Understand user question.

        Args:
            question: User question (in English, from Intent)
            instrument: Trading instrument
            lang: User's language for clarification questions (e.g., "ru", "en")

        Returns:
            UnderstanderResult with goal, expanded_query or need_clarification
        """
        prompt = self._build_prompt(question, instrument, lang)

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=UnderstanderOutput,
            ),
        )

        # Parse response
        output = UnderstanderOutput.model_validate_json(response.text)
        usage = Usage.from_response(response)

        logger.info(
            f"Understander: intent={output.intent}, "
            f"understood={output.understood}, "
            f"goal={output.goal}"
        )

        return UnderstanderResult(
            intent=output.intent,
            goal=output.goal,
            understood=output.understood,
            expanded_query=output.expanded_query,
            need_clarification=output.need_clarification,
            usage=usage,
        )


# Simple API
def understand(question: str, instrument: str = "NQ", lang: str = "en") -> UnderstanderResult:
    """Understand user question."""
    understander = Understander()
    return understander.understand(question, instrument, lang)
