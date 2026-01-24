"""Tests for rules module (filters, metrics, operations, semantics)."""

import pytest

from agent.rules import (
    # Filters
    parse_filter,
    parse_filters,
    detect_filter_type,
    is_always_where,
    is_always_event,
    # Metrics
    get_column,
    requires_daily,
    # Operations
    get_operation,
    requires_full_data,
    get_atoms_range,
    get_default_params,
    # Semantics
    get_semantic,
    validate_combination,
)


# =============================================================================
# Filter Parsing Tests
# =============================================================================

class TestParseFilterComparison:
    """Test comparison filter parsing (change > 0, etc.)."""

    def test_change_greater_than_zero(self):
        result = parse_filter("change > 0")
        assert result["type"] == "comparison"
        assert result["metric"] == "change"
        assert result["op"] == ">"
        assert result["value"] == 0

    def test_change_less_than_zero(self):
        result = parse_filter("change < 0")
        assert result["type"] == "comparison"
        assert result["metric"] == "change"
        assert result["op"] == "<"
        assert result["value"] == 0

    def test_gap_greater_than_percent(self):
        result = parse_filter("gap > 1%")
        assert result["type"] == "comparison"
        assert result["metric"] == "gap"
        assert result["op"] == ">"
        assert result["value"] == 1

    def test_range_greater_equal(self):
        result = parse_filter("range >= 300")
        assert result["type"] == "comparison"
        assert result["metric"] == "range"
        assert result["op"] == ">="
        assert result["value"] == 300

    def test_volume_greater_than(self):
        result = parse_filter("volume > 1000000")
        assert result["type"] == "comparison"
        assert result["metric"] == "volume"
        assert result["op"] == ">"
        assert result["value"] == 1000000


class TestParseFilterCategorical:
    """Test categorical filter parsing (monday, session=MORNING)."""

    def test_weekday_monday(self):
        result = parse_filter("monday")
        assert result["type"] == "categorical"
        assert result["weekday"] == "monday"

    def test_weekday_friday(self):
        result = parse_filter("friday")
        assert result["type"] == "categorical"
        assert result["weekday"] == "friday"

    def test_session_morning(self):
        result = parse_filter("session = MORNING")
        assert result["type"] == "categorical"
        assert result["session"] == "MORNING"

    def test_session_rth(self):
        result = parse_filter("session = RTH")
        assert result["type"] == "categorical"
        assert result["session"] == "RTH"


class TestParseFilterConsecutive:
    """Test consecutive filter parsing (2+ red days)."""

    def test_consecutive_red(self):
        result = parse_filter("consecutive red >= 2")
        assert result["type"] == "consecutive"
        assert result["color"] == "red"
        assert result["op"] == ">="
        assert result["length"] == 2

    def test_consecutive_green(self):
        result = parse_filter("consecutive green >= 3")
        assert result["type"] == "consecutive"
        assert result["color"] == "green"
        assert result["op"] == ">="
        assert result["length"] == 3

    def test_consecutive_exact(self):
        result = parse_filter("consecutive red = 2")
        assert result["type"] == "consecutive"
        assert result["color"] == "red"
        assert result["op"] == "="
        assert result["length"] == 2


class TestParseFilterTime:
    """Test time filter parsing."""

    def test_time_after(self):
        result = parse_filter("time >= 09:30")
        assert result["type"] == "time"
        assert result["op"] == ">="
        assert result["value"] == "09:30"

    def test_time_before(self):
        result = parse_filter("time < 16:00")
        assert result["type"] == "time"
        assert result["op"] == "<"
        assert result["value"] == "16:00"


class TestParseFilterPattern:
    """Test pattern filter parsing."""

    def test_pattern_green(self):
        result = parse_filter("green")
        assert result["type"] == "pattern"
        assert result["pattern"] == "green"

    def test_pattern_red(self):
        result = parse_filter("red")
        assert result["type"] == "pattern"
        assert result["pattern"] == "red"

    def test_pattern_gap_fill(self):
        result = parse_filter("gap_fill")
        assert result["type"] == "pattern"
        assert result["pattern"] == "gap_fill"


class TestParseFiltersMultiple:
    """Test parsing multiple filters."""

    def test_multiple_filters(self):
        result = parse_filters("monday, change > 0")
        assert len(result) == 2
        assert result[0]["type"] == "categorical"
        assert result[1]["type"] == "comparison"

    def test_complex_filter_string(self):
        result = parse_filters("friday, gap > 0.5%, volume > 500000")
        assert len(result) == 3


class TestDetectFilterType:
    """Test filter type detection."""

    def test_detect_comparison(self):
        assert detect_filter_type("change > 0") == "comparison"

    def test_detect_categorical(self):
        assert detect_filter_type("monday") == "categorical"

    def test_detect_time(self):
        assert detect_filter_type("time >= 09:30") == "time"

    def test_detect_pattern(self):
        assert detect_filter_type("green") == "pattern"


# =============================================================================
# Metrics Tests
# =============================================================================

class TestGetColumn:
    """Test metric to column mapping."""

    def test_change(self):
        assert get_column("change") == "change"

    def test_range(self):
        assert get_column("range") == "range"

    def test_volume(self):
        assert get_column("volume") == "volume"

    def test_gap(self):
        assert get_column("gap") == "gap"

    def test_high(self):
        assert get_column("high") == "high"

    def test_low(self):
        assert get_column("low") == "low"

    def test_unknown_returns_same(self):
        """Unknown metric returns the same string."""
        assert get_column("unknown_metric") == "unknown_metric"


class TestRequiresDaily:
    """Test metrics that require daily data."""

    def test_gap_requires_daily(self):
        assert requires_daily("gap") is True

    def test_change_not_daily_only(self):
        assert requires_daily("change") is False

    def test_volume_not_daily_only(self):
        assert requires_daily("volume") is False




# =============================================================================
# Operations Tests
# =============================================================================

class TestGetOperation:
    """Test operation lookup."""

    def test_get_list(self):
        op = get_operation("list")
        assert op is not None
        assert isinstance(op, dict)
        assert "description" in op

    def test_get_compare(self):
        op = get_operation("compare")
        assert op is not None
        assert isinstance(op, dict)
        assert "description" in op

    def test_get_probability(self):
        op = get_operation("probability")
        assert op is not None

    def test_get_unknown_returns_none(self):
        assert get_operation("unknown_op") is None


class TestRequiresFullData:
    """Test operations that require full data before filtering."""

    def test_list_not_full(self):
        assert requires_full_data("list") is False

    def test_count_not_full(self):
        assert requires_full_data("count") is False

    def test_returns_bool(self):
        """All operations return boolean."""
        for op_name in ["list", "count", "compare", "probability", "around"]:
            result = requires_full_data(op_name)
            assert isinstance(result, bool)


class TestGetAtomsRange:
    """Test atoms count constraints."""

    def test_list_atoms(self):
        min_atoms, max_atoms = get_atoms_range("list")
        assert min_atoms == 1
        assert max_atoms >= 1

    def test_compare_atoms(self):
        min_atoms, max_atoms = get_atoms_range("compare")
        assert min_atoms >= 1
        assert max_atoms >= 2

    def test_correlation_atoms(self):
        min_atoms, max_atoms = get_atoms_range("correlation")
        assert min_atoms >= 1
        assert max_atoms >= 2


class TestGetDefaultParams:
    """Test default params for operations."""

    def test_list_defaults(self):
        defaults = get_default_params("list")
        assert "sort" in defaults or defaults == {}

    def test_probability_defaults(self):
        defaults = get_default_params("probability")
        # probability should have default outcome
        assert isinstance(defaults, dict)


# =============================================================================
# Semantics Tests
# =============================================================================

class TestGetSemantic:
    """Test semantic lookup for operation + filter combinations."""

    def test_list_with_comparison_is_where(self):
        sem = get_semantic("list", "comparison")
        assert sem == "where"

    def test_list_with_categorical_is_where(self):
        sem = get_semantic("list", "categorical")
        assert sem == "where"

    def test_probability_with_comparison(self):
        """Probability with comparison filter."""
        sem = get_semantic("probability", "comparison")
        assert sem in ("where", "condition", "event")

    def test_probability_with_consecutive(self):
        """Probability with consecutive filter."""
        sem = get_semantic("probability", "consecutive")
        assert sem in ("where", "condition", "event")


class TestValidateCombination:
    """Test filter + operation validation."""

    def test_list_comparison_valid(self):
        is_valid, _ = validate_combination("list", "comparison")
        assert is_valid is True

    def test_list_categorical_valid(self):
        is_valid, _ = validate_combination("list", "categorical")
        assert is_valid is True

    def test_formation_consecutive(self):
        # Formation with consecutive - check it returns a tuple
        is_valid, _ = validate_combination("formation", "consecutive")
        assert isinstance(is_valid, bool)


# =============================================================================
# Filter Semantic Properties
# =============================================================================

class TestFilterSemanticProperties:
    """Test filter semantic properties."""

    def test_categorical_always_where(self):
        """Categorical filters are always WHERE (pre-filter)."""
        assert is_always_where("categorical") is True

    def test_time_always_where(self):
        """Time filters are always WHERE."""
        assert is_always_where("time") is True

    def test_consecutive_always_event(self):
        """Consecutive filters are always EVENT (special handling)."""
        assert is_always_event("consecutive") is True

    def test_comparison_not_always_where(self):
        """Comparison filters depend on operation."""
        assert is_always_where("comparison") is False


# =============================================================================
# Pattern Timeframe Validation Tests
# =============================================================================

class TestPatternTimeframeValidation:
    """Test pattern filter timeframe validation."""

    def test_min_timeframe_for_pattern_filter_none(self):
        """No pattern filter returns None."""
        from agent.rules import get_min_timeframe_for_pattern_filter
        assert get_min_timeframe_for_pattern_filter("change > 0") is None
        assert get_min_timeframe_for_pattern_filter("monday") is None
        assert get_min_timeframe_for_pattern_filter("") is None
        assert get_min_timeframe_for_pattern_filter(None) is None

    def test_min_timeframe_for_legacy_pattern(self):
        """Legacy patterns (green, red) work on any timeframe."""
        from agent.rules import get_min_timeframe_for_pattern_filter
        assert get_min_timeframe_for_pattern_filter("green") is None
        assert get_min_timeframe_for_pattern_filter("red") is None

    def test_is_timeframe_valid_no_pattern(self):
        """Non-pattern filters are always valid for any timeframe."""
        from agent.rules import is_timeframe_valid_for_filter
        assert is_timeframe_valid_for_filter("1m", "change > 0") is True
        assert is_timeframe_valid_for_filter("1D", "monday") is True


# =============================================================================
# Pydantic Validator Tests — formation + pattern conflict
# =============================================================================

class TestFormationPatternConflict:
    """Test auto-fix for formation + candle pattern conflict."""

    def test_formation_with_candle_pattern_fixes_to_list(self):
        """Formation + candle pattern (min 1H+) → auto-fix to list."""
        from agent.types import Step, Atom

        step = Step(
            id="s1",
            operation="formation",
            atoms=[Atom(when="2024", what="high", filter="doji")]
        )
        assert step.operation == "list"
        assert step.atoms[0].timeframe == "1H"

    def test_formation_with_multi_candle_pattern_fixes_to_list(self):
        """Formation + 3-candle pattern (min 1D) → auto-fix to list."""
        from agent.types import Step, Atom

        step = Step(
            id="s1",
            operation="formation",
            atoms=[Atom(when="2024", what="high", filter="morning_star")]
        )
        assert step.operation == "list"
        assert step.atoms[0].timeframe == "1D"

    def test_formation_with_price_pattern_stays_formation(self):
        """Formation + price pattern (works on 1m) → stays formation."""
        from agent.types import Step, Atom

        step = Step(
            id="s1",
            operation="formation",
            atoms=[Atom(when="2024", what="high", filter="inside_bar")]
        )
        assert step.operation == "formation"
        assert step.atoms[0].timeframe == "1m"

    def test_formation_without_filter_stays_formation(self):
        """Formation without filter → stays formation."""
        from agent.types import Step, Atom

        step = Step(
            id="s1",
            operation="formation",
            atoms=[Atom(when="2024", what="high")]
        )
        assert step.operation == "formation"
        assert step.atoms[0].timeframe == "1m"

    def test_list_with_candle_pattern_stays_list(self):
        """List + candle pattern → stays list (no conflict)."""
        from agent.types import Step, Atom

        step = Step(
            id="s1",
            operation="list",
            atoms=[Atom(when="2024", what="change", filter="doji")]
        )
        assert step.operation == "list"
        # Default 1D is valid for doji (min 1H), so stays 1D
        assert step.atoms[0].timeframe == "1D"
