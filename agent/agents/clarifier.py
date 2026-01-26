"""
Clarifier agent — formulates beautiful questions from Understander's tezises.

Single responsibility: take structured clarification tezises → return natural question.

Input: Understander's need_clarification (required, optional, context)
Output: Friendly question in user's language
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from google import genai
from google.genai import types

import config
from agent.types import ClarificationOutput, Usage
from agent.prompts.clarification import SYSTEM_PROMPT, USER_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class ClarifierResult:
    """Clarifier result."""
    question: str
    usage: Usage = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = Usage()


class Clarifier:
    """
    Formulates clarification questions from Understander's tezises.

    Takes structured tezises (required/optional items with reasons and options),
    returns a natural, friendly question in user's language.
    """

    def __init__(self, model: str | None = None):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = model or config.GEMINI_LITE_MODEL  # lite is enough for formatting

    def clarify(
        self,
        required: list[dict],
        optional: list[dict],
        context: str,
        question: str,
        lang: str = "en",
        memory_context: str | None = None,
    ) -> ClarifierResult:
        """
        Formulate clarification question from tezises.

        Args:
            required: List of required clarification items from Understander
            optional: List of optional clarification items
            context: What Understander already understood
            question: User's question that triggered clarification
            lang: User's language code (e.g., "ru", "en")
            memory_context: Known facts from conversation memory (to avoid redundant questions)

        Returns:
            ClarifierResult with formatted question and usage
        """
        # Build user prompt
        user_prompt = USER_PROMPT.format(
            required=required,
            optional=optional,
            context=context or "None",
            question=question,
            lang=lang,
            memory_context=memory_context or "None",
        )

        # Call LLM
        response = self.client.models.generate_content(
            model=self.model,
            contents=f"{SYSTEM_PROMPT}\n\n{user_prompt}",
            config=types.GenerateContentConfig(
                temperature=0.3,  # Slight creativity for natural phrasing
                response_mime_type="application/json",
                response_schema=ClarificationOutput,
            ),
        )

        # Parse response
        output = ClarificationOutput.model_validate_json(response.text)
        usage = Usage.from_response(response)

        logger.info(f"Clarifier: formatted question for lang={lang}")

        return ClarifierResult(
            question=output.question,
            usage=usage,
        )


# =============================================================================
# Simple API
# =============================================================================

def clarify(
    required: list[dict],
    optional: list[dict],
    context: str,
    question: str,
    lang: str = "en",
    memory_context: str | None = None,
) -> ClarifierResult:
    """
    Formulate clarification question from tezises.

    Simple wrapper for Clarifier class.
    """
    clarifier = Clarifier()
    return clarifier.clarify(required, optional, context, question, lang, memory_context)
