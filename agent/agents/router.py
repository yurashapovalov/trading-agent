"""Router agent - classifies questions and decides routing."""

from google import genai
from google.genai import types

import config
from agent.base import BaseRoutingAgent
from agent.state import AgentState
from agent.prompts import get_prompt


class Router(BaseRoutingAgent):
    """
    Classifies user questions into categories.

    Routes:
    - "data" - needs database queries (statistics, patterns, backtests)
    - "concept" - explanation of trading concepts (what is RSI, MACD)
    - "hypothetical" - "what if" scenarios without real data
    """

    name = "router"
    agent_type = "routing"

    def __init__(self):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        # Use fast model for routing
        self.model = "gemini-2.0-flash"

    def decide(self, state: AgentState) -> str:
        """Classify the question and return route."""
        question = state.get("question", "")

        prompt = get_prompt("router", question=question)

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,  # Deterministic
                max_output_tokens=10,
            )
        )

        route = response.text.strip().lower()

        # Validate route
        valid_routes = ["data", "concept", "hypothetical"]
        if route not in valid_routes:
            # Default to data if unclear
            route = "data"

        return route
