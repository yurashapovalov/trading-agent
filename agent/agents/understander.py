"""
Understander agent - parses user questions into structured Intent.

LLM decides WHAT data to fetch (Intent).
DataFetcher (code) executes HOW to fetch it.
"""

import json
from datetime import datetime, timedelta
from google import genai
from google.genai import types

import config
from agent.state import AgentState, Intent, PatternDef, UsageStats
from agent.pricing import calculate_cost, GEMINI_2_5_FLASH_LITE
from agent.capabilities import (
    get_capabilities_prompt,
    DEFAULT_SYMBOL,
    DEFAULT_GRANULARITY,
)
from agent.modules.sql import get_data_range
from agent.prompts.understander import get_understander_prompt


# =============================================================================
# Understander Agent
# =============================================================================

class Understander:
    """
    Parses user questions into structured Intent.

    Uses Gemini with JSON mode to return structured response.
    """

    name = "understander"
    agent_type = "routing"

    def __init__(self):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = config.GEMINI_LITE_MODEL
        self._last_usage = UsageStats(
            input_tokens=0,
            output_tokens=0,
            thinking_tokens=0,
            cost_usd=0.0
        )

    def __call__(self, state: AgentState) -> dict:
        """Parse question and return Intent."""
        question = state.get("question", "")
        chat_history = state.get("chat_history", [])

        # Check clarification limit
        if state.get("clarification_attempts", 0) >= 3:
            return {"intent": self._default_intent()}

        # Call LLM with JSON mode
        intent = self._parse_with_llm(question, chat_history)

        return {
            "intent": intent,
            "usage": self._last_usage,
            "agents_used": [self.name],
            "step_number": state.get("step_number", 0) + 1,
        }

    def _get_data_info(self) -> str:
        """Get available data info."""
        data_range = get_data_range("NQ")
        if data_range:
            return (
                f"Символ: NQ\n"
                f"Период данных: {data_range['start_date']} — {data_range['end_date']}\n"
                f"Торговых дней: {data_range['trading_days']}"
            )
        return "Данные: NQ"

    def _build_prompt(self, question: str, chat_history: list) -> str:
        """Build full prompt for LLM using external template."""
        # Format chat history
        history_str = ""
        if chat_history:
            for msg in chat_history[-10:]:
                role = "User" if msg.get("role") == "user" else "Assistant"
                history_str += f"{role}: {msg.get('content', '')}\n"

        return get_understander_prompt(
            capabilities=get_capabilities_prompt(),
            data_info=self._get_data_info(),
            today=datetime.now().strftime("%Y-%m-%d"),
            question=question,
            chat_history=history_str,
        )

    def _parse_with_llm(self, question: str, chat_history: list) -> Intent:
        """Call LLM and parse response into Intent."""
        try:
            prompt = self._build_prompt(question, chat_history)

            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema={
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["data", "pattern", "concept", "strategy", "chitchat", "out_of_scope"]
                            },
                            "symbol": {"type": "string"},
                            "period_start": {"type": "string"},
                            "period_end": {"type": "string"},
                            "granularity": {
                                "type": "string",
                                "enum": ["period", "daily", "hourly"]
                            },
                            "pattern_name": {"type": "string"},
                            "pattern_params": {"type": "string"},  # JSON string
                            "concept": {"type": "string"},
                            "response_text": {"type": "string"},  # For chitchat/out_of_scope
                            "needs_clarification": {"type": "boolean"},
                            "clarification_question": {"type": "string"},
                            "suggestions": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["type"]
                    }
                )
            )

            # Track usage
            if response.usage_metadata:
                input_tokens = response.usage_metadata.prompt_token_count or 0
                output_tokens = response.usage_metadata.candidates_token_count or 0
                cost = calculate_cost(input_tokens, output_tokens, 0, GEMINI_2_5_FLASH_LITE)
                self._last_usage = UsageStats(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    thinking_tokens=0,
                    cost_usd=cost
                )

            # Parse JSON response
            data = json.loads(response.text)
            return self._build_intent(data)

        except Exception as e:
            # Fallback to default intent on error
            print(f"Understander error: {e}")
            return self._default_intent()

    def _build_intent(self, data: dict) -> Intent:
        """Build Intent from parsed data."""
        intent_type = data.get("type", "data")

        intent: Intent = {
            "type": intent_type,
            "symbol": data.get("symbol") or DEFAULT_SYMBOL,
            "needs_clarification": data.get("needs_clarification", False),
            "clarification_question": data.get("clarification_question"),
            "suggestions": data.get("suggestions", []),
        }

        # Add type-specific fields
        if intent_type in ("data", "pattern"):
            intent["period_start"] = data.get("period_start")
            intent["period_end"] = data.get("period_end")

            # Default period if not specified
            if not intent["period_start"] or not intent["period_end"]:
                intent["period_start"], intent["period_end"] = self._default_period()

        if intent_type == "data":
            intent["granularity"] = data.get("granularity") or DEFAULT_GRANULARITY

        if intent_type == "pattern":
            # Parse pattern_params from JSON string
            pattern_params = {}
            if data.get("pattern_params"):
                try:
                    pattern_params = json.loads(data["pattern_params"])
                except json.JSONDecodeError:
                    pass

            intent["pattern"] = PatternDef(
                name=data.get("pattern_name", ""),
                params=pattern_params
            )

        if intent_type == "concept":
            intent["concept"] = data.get("concept", "")

        if intent_type in ("chitchat", "out_of_scope"):
            intent["response_text"] = data.get("response_text", "")

        return intent

    def _default_intent(self) -> Intent:
        """Return default intent for fallback."""
        start, end = self._default_period()
        return Intent(
            type="data",
            symbol=DEFAULT_SYMBOL,
            period_start=start,
            period_end=end,
            granularity=DEFAULT_GRANULARITY,
            needs_clarification=False,
        )

    def _default_period(self) -> tuple[str, str]:
        """Get default period (last month of available data)."""
        data_range = get_data_range("NQ")
        if data_range:
            end_date = datetime.strptime(data_range['end_date'], "%Y-%m-%d")
            start_date = end_date - timedelta(days=30)
            return start_date.strftime("%Y-%m-%d"), data_range['end_date']

        # Fallback
        today = datetime.now()
        month_ago = today - timedelta(days=30)
        return month_ago.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
