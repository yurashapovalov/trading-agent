"""
Fast Intent Classifier — quick routing without thinking.

Single responsibility:
1. Classify intent (chitchat/concept/data)
2. Detect user's language (ISO 639-1)
3. Translate question to English

No thinking mode, minimal prompt, ~500ms.

Used before Parser to skip heavy parsing for simple queries.
Language flows to Responder for response in user's language.

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
    """Fast intent classification output with language detection."""
    intent: Literal["chitchat", "concept", "data"] = Field(
        description="chitchat=greetings/thanks, concept=explain trading term, data=query about market data"
    )
    lang: str = Field(
        description="ISO 639-1 language code (en, ru, es, de, zh, etc.)"
    )
    internal_query: str = Field(
        description="Question translated to English for inter-agent communication"
    )


@dataclass
class IntentResult:
    """Intent classification result with language info."""
    intent: Literal["chitchat", "concept", "data"]
    lang: str  # ISO 639-1 code
    internal_query: str  # Translated to English for inter-agent communication
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
            lang=output.lang,
            internal_query=output.internal_query,
            usage=usage,
        )


# Simple API
def classify_intent(question: str) -> IntentResult:
    """Classify intent quickly."""
    classifier = IntentClassifier()
    return classifier.classify(question)
