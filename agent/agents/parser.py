"""
Semantic parser for trading questions.

Uses RAP (Retrieval-Augmented Prompting) with Pydantic schema.
"""

import json
import logging
from dataclasses import dataclass, field

from google import genai
from pydantic import ValidationError
from google.genai import types

import config
from agent.types import Usage, ParserOutput, Step
from agent.prompts.semantic_parser.rap import get_rap

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Parser result."""
    steps: list[Step] = field(default_factory=list)
    thoughts: str | None = None
    usage: Usage = field(default_factory=Usage)


class Parser:
    """
    Semantic parser for trading questions.

    Converts natural language to structured steps with operations.
    """

    def __init__(self, model: str | None = None):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = model or config.GEMINI_LITE_MODEL

    def parse(self, question: str) -> ParseResult:
        """Parse question into steps."""

        # Build prompt with relevant chunks via RAP
        rap = get_rap()
        base_prompt, chunk_ids = rap.build(question, top_k=5)
        logger.info(f"Using chunks: {chunk_ids}")

        prompt = f"{base_prompt}\n\nQuestion: {question}"

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=ParserOutput,
            ),
        )

        # Extract thoughts and response
        thoughts = None
        response_text = None

        for part in response.candidates[0].content.parts:
            if not part.text:
                continue
            if getattr(part, 'thought', False):
                thoughts = part.text
            else:
                response_text = part.text

        # Parse response with Pydantic
        steps = []
        if response_text:
            try:
                parsed = ParserOutput.model_validate_json(response_text)
                steps = parsed.steps
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from LLM: {e}")
                logger.debug(f"Response was: {response_text}")
            except ValidationError as e:
                logger.error(f"Schema validation failed: {e}")
                logger.debug(f"Response was: {response_text}")

        usage = Usage.from_response(response)

        return ParseResult(steps=steps, thoughts=thoughts, usage=usage)
