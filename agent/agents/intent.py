"""
Fast Intent Classifier — quick routing without thinking.

Single responsibility: classify intent (chitchat/concept/data) fast.
No thinking mode, minimal prompt, ~200-400ms.

Used before Parser to skip heavy parsing for simple queries.
"""

from dataclasses import dataclass
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

import config
from agent.types import Usage


class IntentOutput(BaseModel):
    """Fast intent classification output."""
    intent: Literal["chitchat", "concept", "data"] = Field(
        description="chitchat=greetings/thanks, concept=explain trading term, data=query about market data"
    )
    topic: str | None = Field(
        default=None,
        description="For concept: the trading term to explain. For chitchat: greeting/thanks/goodbye"
    )


SYSTEM_PROMPT = """You are a fast intent classifier for a trading assistant.

Classify user message into ONE of:
- chitchat: greetings (hi, hello, привет), thanks (спасибо, thanks), goodbye (пока, bye)
- concept: asking to explain a trading term (what is OPEX, что такое гэп, explain volatility)
- data: any question about market data, statistics, analysis (volatility 2024, average range, compare months)

Be fast. Just classify, don't overthink.

Examples:
- "привет" → chitchat, topic="greeting"
- "спасибо" → chitchat, topic="thanks"
- "что такое OPEX" → concept, topic="OPEX"
- "explain gap" → concept, topic="gap"
- "volatility 2024" → data
- "средний рейндж по понедельникам" → data
- "сравни январь и февраль" → data
"""


@dataclass
class IntentResult:
    """Intent classification result."""
    intent: Literal["chitchat", "concept", "data"]
    topic: str | None = None
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
        response = self.client.models.generate_content(
            model=self.model,
            contents=f"{SYSTEM_PROMPT}\n\nUser: {question}",
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
            topic=output.topic,
            usage=usage,
        )


# Simple API
def classify_intent(question: str) -> IntentResult:
    """Classify intent quickly."""
    classifier = IntentClassifier()
    return classifier.classify(question)
