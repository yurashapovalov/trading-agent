"""
Pydantic models for Parser output.

Used as response_schema in Gemini.
Note: Gemini doesn't support additionalProperties, so no dict types.
"""

from typing import ClassVar, Literal
from pydantic import BaseModel, Field


class Period(BaseModel):
    """Date/time period specification."""
    type: Literal["relative", "year", "month", "date", "range", "quarter"] | None = None
    # For relative: yesterday, today, last_week, last_n_days, ytd, mtd, etc.
    # For year: "2024"
    # For month: "2024-01"
    # For date: "2024-05-15"
    value: str | None = None
    n: int | None = Field(default=None, description="For last_n_days, last_n_weeks")
    # For range type:
    start: str | None = Field(default=None, description="YYYY-MM-DD for range start")
    end: str | None = Field(default=None, description="YYYY-MM-DD for range end")
    # For quarter type:
    year: int | None = Field(default=None, description="Year for quarter")
    q: int | None = Field(default=None, description="Quarter number 1-4")


class TimeRange(BaseModel):
    """Intraday time range."""
    start: str = Field(description="HH:MM format")
    end: str = Field(description="HH:MM format")


class ParsedQuery(BaseModel):
    """Parser output — extracted entities from user question."""

    intent: Literal["data", "chitchat", "concept", "unsupported"] = "data"
    what: str = Field(default="", description="Brief description of what user wants")
    reason: str | None = Field(default=None, description="Why unsupported: cannot_predict, no_realtime, wrong_instrument")
    operation: Literal["stats", "compare", "top_n", "seasonality", "filter", "streak", "list"] | None = None

    period: Period | None = None
    time: TimeRange | None = None

    session: Literal["RTH", "ETH", "OVERNIGHT", "ASIAN", "EUROPEAN"] | None = None
    weekday_filter: list[str] | None = Field(default=None, description="e.g. Monday, Friday")
    event_filter: Literal["opex", "fomc", "nfp", "cpi", "quad_witching"] | None = None

    # Metric (what to measure)
    metric: Literal["range", "change", "volume", "green_pct", "gap"] | None = Field(
        default=None, description="What to measure: range/volatility, change/return, volume, win rate, gaps"
    )

    # Conditions and modifiers
    condition: str | None = Field(default=None, description="e.g. range > 300, close > open")
    top_n: int | None = Field(default=None, description="e.g. 10 for top 10")
    sort_by: str | None = Field(default=None, description="e.g. range, volume, change_pct")
    sort_order: Literal["asc", "desc"] | None = Field(default=None, description="asc or desc")
    group_by: Literal["hour", "weekday", "month", "quarter", "year"] | None = Field(default=None)

    compare: list[str] | None = Field(default=None, description="e.g. 2023, 2024")
    unclear: list[str] | None = Field(default=None, description="e.g. year")


class ClarificationOutput(BaseModel):
    """Output from Clarifier agent."""
    response: str = Field(description="Message to user in their language")
    clarified_query: str | None = Field(
        default=None,
        description="Reformulated query for Parser (only when clarification complete)"
    )


class Usage(BaseModel):
    """Token usage from Gemini API call."""
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cached_tokens: int = 0

    # Gemini pricing per 1M tokens (USD)
    # https://ai.google.dev/pricing
    PRICING: ClassVar[dict] = {
        # Gemini 2.5 Flash (full)
        "gemini-flash-latest": {"input": 0.30, "output": 2.50, "cached": 0.03},
        # Gemini 2.5 Flash Lite (cheap)
        "gemini-flash-lite-latest": {"input": 0.10, "output": 0.40, "cached": 0.01},
        # Default = lite (what we use)
        "default": {"input": 0.10, "output": 0.40, "cached": 0.01},
    }

    def __add__(self, other: "Usage") -> "Usage":
        """Aggregate usage from multiple calls."""
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            thinking_tokens=self.thinking_tokens + other.thinking_tokens,
            cached_tokens=self.cached_tokens + other.cached_tokens,
        )

    def cost(self, model: str = "default") -> float:
        """Calculate cost in USD."""
        prices = self.PRICING.get(model, self.PRICING["default"])
        # Non-cached input tokens (subtract cached)
        regular_input = max(0, self.input_tokens - self.cached_tokens)
        return (
            (regular_input / 1_000_000) * prices["input"]
            + (self.output_tokens / 1_000_000) * prices["output"]
            + (self.cached_tokens / 1_000_000) * prices["cached"]
        )

    @classmethod
    def from_response(cls, response) -> "Usage":
        """Extract usage from Gemini response."""
        meta = getattr(response, "usage_metadata", None)
        if not meta:
            return cls()
        return cls(
            input_tokens=getattr(meta, "prompt_token_count", 0) or 0,
            output_tokens=getattr(meta, "candidates_token_count", 0) or 0,
            thinking_tokens=getattr(meta, "thoughts_token_count", 0) or 0,
            cached_tokens=getattr(meta, "cached_content_token_count", 0) or 0,
        )
