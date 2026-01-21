"""
Fast Intent Classifier — quick routing without thinking.

Single responsibility: classify intent (chitchat/concept/data) fast.
No thinking mode, minimal prompt, ~500ms.

Used before Parser to skip heavy parsing for simple queries.

Uses:
- prompts/intent.py for prompt constants
"""

from dataclasses import dataclass
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

import config
from agent.types import Usage
from agent.prompts.intent import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE


class IntentOutput(BaseModel):
    """Fast intent classification output."""
    intent: Literal["chitchat", "concept", "data"] = Field(
        description="chitchat=greetings/thanks, concept=explain trading term, data=query about market data"
    )


@dataclass
class IntentResult:
    """Intent classification result."""
    intent: Literal["chitchat", "concept", "data"]
    usage: Usage = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = Usage()


class IntentClassifier:
    """
    Fast intent classifier without thinking.

    ~200-400ms vs ~3500ms for full Parser with thinking.
    """

    def __init__(self, model: str | None = None):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = model or config.GEMINI_LITE_MODEL

    def classify(self, question: str) -> IntentResult:
        """
        Quickly classify intent.

        Args:
            question: User message

        Returns:
            IntentResult with intent and optional topic
        """
        user_prompt = USER_PROMPT_TEMPLATE.format(question=question)

        response = self.client.models.generate_content(
            model=self.model,
            contents=f"{SYSTEM_PROMPT}\n\n{user_prompt}",
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=IntentOutput,
            ),
        )

        output = IntentOutput.model_validate_json(response.text)
        usage = Usage.from_response(response)

        return IntentResult(
            intent=output.intent,
            usage=usage,
        )


# Simple API
def classify_intent(question: str) -> IntentResult:
    """Classify intent quickly."""
    classifier = IntentClassifier()
    return classifier.classify(question)
