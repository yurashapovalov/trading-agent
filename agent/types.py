"""
Pydantic models for Parser output.

Used as response_schema in Gemini.
Schema validators enforce rules from agent/rules/ — single source of truth.
"""

from typing import ClassVar, Literal
from pydantic import BaseModel, Field, model_validator

from agent.rules import (
    get_atoms_range,
    get_required_timeframe,
    get_default_params,
    requires_daily,
    detect_filter_type,
    parse_filters,
    validate_combination,
    get_min_timeframe_for_pattern_filter,
    is_timeframe_valid_for_filter,
    normalize_pattern_filter,
    get_metric,
)


# =============================================================================
# Parser Output Models
# =============================================================================

class Atom(BaseModel):
    """Data selection unit: when + what + optional filter/group/timeframe."""
    when: str = Field(description="Period: 2024, January, last week, Q1 2024")
    what: str = Field(description="Metric: change, range, volume, gap, high, low")
    filter: str | None = Field(default=None, description="Condition: change > 0, monday")
    group: str | None = Field(default=None, description="Grouping: by month, by weekday")
    timeframe: Literal["1m", "5m", "15m", "30m", "1H", "4H", "1D"] = Field(
        default="1D",
        description="Data granularity: 1D for daily, 1H for hourly, 1m for minute"
    )

    # -------------------------------------------------------------------------
    # Rule: normalize pattern aliases (inside_day → inside_bar)
    # -------------------------------------------------------------------------
    @model_validator(mode="after")
    def normalize_pattern_aliases(self):
        """Normalize pattern aliases to canonical names from config."""
        if self.filter:
            self.filter = normalize_pattern_filter(self.filter)
        return self

    # -------------------------------------------------------------------------
    # Rule: fix invalid metric (formation → change)
    # -------------------------------------------------------------------------
    @model_validator(mode="after")
    def fix_invalid_metric(self):
        """Fix invalid what field to default metric."""
        if not get_metric(self.what):
            self.what = "change"
        return self

    # -------------------------------------------------------------------------
    # Rule: session/time filter → intraday timeframe
    # -------------------------------------------------------------------------
    @model_validator(mode="after")
    def fix_timeframe_for_intraday_filter(self):
        """Session/time filters require time column → use 1H instead of 1D."""
        if not self.filter:
            return self

        filter_type = detect_filter_type(self.filter)

        # Time and categorical (session) filters need intraday data
        needs_intraday = filter_type == "time" or "session" in self.filter.lower()

        if needs_intraday and self.timeframe == "1D":
            self.timeframe = "1H"
        return self

    # -------------------------------------------------------------------------
    # Rule: gap + session filter = conflict (from rules/metrics.py)
    # -------------------------------------------------------------------------
    @model_validator(mode="after")
    def validate_gap_vs_intraday(self):
        """Gap metric requires daily data, session filter requires intraday — conflict."""
        if not requires_daily(self.what) or not self.filter:
            return self

        filter_type = detect_filter_type(self.filter)
        needs_intraday = filter_type == "time" or "session" in self.filter.lower()

        if needs_intraday:
            raise ValueError(
                f"Conflict: '{self.what}' requires daily data, "
                "but session/time filter requires intraday data. "
                "Use different metric (change, range, volume) with session filter, "
                f"or remove session filter when analyzing {self.what}."
            )
        return self

    # -------------------------------------------------------------------------
    # Rule: pattern filter → minimum timeframe (from rules/filters.py)
    # -------------------------------------------------------------------------
    _TF_ORDER: ClassVar[list[str]] = ["1m", "5m", "15m", "30m", "1H", "4H", "1D", "1W"]

    @model_validator(mode="after")
    def fix_timeframe_for_pattern_filter(self):
        """Pattern filters may require minimum timeframe — auto-fix if needed."""
        if not self.filter:
            return self

        min_tf = get_min_timeframe_for_pattern_filter(self.filter)
        if not min_tf:
            return self

        # Check if current timeframe is below minimum
        if min_tf not in self._TF_ORDER or self.timeframe not in self._TF_ORDER:
            return self

        current_idx = self._TF_ORDER.index(self.timeframe)
        min_idx = self._TF_ORDER.index(min_tf)

        if current_idx < min_idx:
            self.timeframe = min_tf

        return self


class StepParams(BaseModel):
    """Operation parameters."""
    n: int | None = Field(default=None, description="Limit to N items")
    sort: Literal["asc", "desc"] | None = Field(default=None, description="Sort order")
    outcome: str | None = Field(default=None, description="For probability: > 0, < 0")
    offset: int | None = Field(default=None, description="For around: +1 (after), -1 (before)")


class Step(BaseModel):
    """Single step in query plan."""
    id: str = Field(description="Step ID: s1, s2, s3")
    operation: Literal[
        "list", "count", "compare", "correlation",
        "around", "streak", "distribution", "probability", "formation"
    ] = Field(description="Operation type")
    atoms: list[Atom] = Field(description="Data atoms for this step")
    params: StepParams | None = Field(default=None, description="Operation parameters")
    from_step: str | None = Field(default=None, alias="from", description="Reference to previous step")

    # -------------------------------------------------------------------------
    # Rule: operation may require specific timeframe (from rules/operations.py)
    # -------------------------------------------------------------------------
    @model_validator(mode="after")
    def fix_timeframe_for_operation(self):
        """Some operations require specific timeframe (e.g. formation → 1m)."""
        required_tf = get_required_timeframe(self.operation)
        if required_tf:
            for atom in self.atoms:
                atom.timeframe = required_tf
        return self

    # -------------------------------------------------------------------------
    # Rule: operation timeframe vs filter timeframe conflict → fix operation
    # -------------------------------------------------------------------------
    @model_validator(mode="after")
    def fix_operation_filter_timeframe_conflict(self):
        """
        Fix impossible combination: operation requires timeframe X but filter requires Y.

        Example: formation (1m) + doji (min 1H) → change operation to list.
        """
        required_tf = get_required_timeframe(self.operation)
        if not required_tf:
            return self

        for atom in self.atoms:
            if not atom.filter:
                continue

            # Check if filter is compatible with operation's required timeframe
            if not is_timeframe_valid_for_filter(required_tf, atom.filter):
                # Conflict! Fix operation to list and restore proper timeframe
                self.operation = "list"
                # Re-apply pattern timeframe (was overwritten by formation)
                min_tf = get_min_timeframe_for_pattern_filter(atom.filter)
                if min_tf:
                    atom.timeframe = min_tf
                return self

        return self

    # -------------------------------------------------------------------------
    # Rule: validate atoms count (from rules/operations.py)
    # -------------------------------------------------------------------------
    @model_validator(mode="after")
    def validate_atoms_count(self):
        """Validate atoms count against operation rules."""
        min_atoms, max_atoms = get_atoms_range(self.operation)

        if len(self.atoms) < min_atoms:
            raise ValueError(
                f"'{self.operation}' requires at least {min_atoms} atom(s), "
                f"got {len(self.atoms)}"
            )

        if len(self.atoms) > max_atoms:
            raise ValueError(
                f"'{self.operation}' allows at most {max_atoms} atom(s), "
                f"got {len(self.atoms)}"
            )

        return self

    # -------------------------------------------------------------------------
    # Rule: validate filter + operation combinations (from rules/semantics.py)
    # -------------------------------------------------------------------------
    @model_validator(mode="after")
    def validate_filter_combinations(self):
        """Validate that filters are valid for this operation."""
        for atom in self.atoms:
            if not atom.filter:
                continue

            # Parse all filters in the string
            filters = parse_filters(atom.filter)

            for f in filters:
                filter_type = f.get("type")
                if not filter_type:
                    continue

                is_valid, error_msg = validate_combination(self.operation, filter_type)
                if not is_valid:
                    raise ValueError(error_msg)

        return self

    # -------------------------------------------------------------------------
    # Rule: set default params (from rules/operations.py)
    # -------------------------------------------------------------------------
    @model_validator(mode="after")
    def set_default_params(self):
        """Set sensible defaults for operation params from rules."""
        if self.params is None:
            self.params = StepParams()

        defaults = get_default_params(self.operation)

        # Apply defaults only if not already set
        if defaults.get("sort") and self.params.sort is None:
            self.params.sort = defaults["sort"]

        if defaults.get("offset") and self.params.offset is None:
            self.params.offset = defaults["offset"]

        if defaults.get("outcome") and self.params.outcome is None:
            self.params.outcome = defaults["outcome"]

        if defaults.get("n") and self.params.n is None:
            self.params.n = defaults["n"]

        return self


class ParserOutput(BaseModel):
    """Parser output — list of steps."""
    steps: list[Step] = Field(description="Query steps")


# =============================================================================
# Clarifier Output
# =============================================================================

class ClarificationOutput(BaseModel):
    """Clarifier output — formatted question for user."""
    question: str = Field(description="Natural, friendly question in user's language")


# =============================================================================
# Usage Tracking
# =============================================================================

class Usage(BaseModel):
    """Token usage from Gemini API call."""
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cached_tokens: int = 0

    PRICING: ClassVar[dict] = {
        "gemini-flash-latest": {"input": 0.30, "output": 2.50, "cached": 0.03},
        "gemini-flash-lite-latest": {"input": 0.10, "output": 0.40, "cached": 0.01},
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
