"""
Pydantic models for Parser output.

Used as response_schema in Gemini.
Note: Gemini doesn't support additionalProperties, so no dict types.
"""

from typing import Literal
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

    intent: Literal["data", "chitchat", "concept"] = "data"
    what: str = Field(default="", description="Brief description of what user wants")
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
