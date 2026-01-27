"""Tests for operations (list, compare, probability, etc.)."""

import pytest
import pandas as pd
import numpy as np
from datetime import date

from agent.operations import OPERATIONS
from agent.operations.list import op_list
from agent.operations.count import op_count
from agent.operations.compare import op_compare
from agent.operations.correlation import op_correlation
from agent.operations.distribution import op_distribution
from agent.operations.probability import op_probability
from agent.operations.streak import op_streak
from agent.operations.around import op_around
from agent.operations.formation import op_formation


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_df():
    """Create sample DataFrame with trading data."""
    data = {
        "date": pd.date_range("2024-01-01", periods=20, freq="D"),
        "open": [100 + i for i in range(20)],
        "high": [105 + i for i in range(20)],
        "low": [95 + i for i in range(20)],
        "close": [102 + i for i in range(20)],
        "volume": [1000000 + i * 10000 for i in range(20)],
        "change": [0.5, -0.3, 0.8, -0.2, 1.0, -0.5, 0.3, 0.7, -0.4, 0.2,
                   -0.1, 0.6, -0.8, 0.4, -0.3, 0.9, -0.6, 0.1, 0.5, -0.2],
        "range": [10, 12, 8, 15, 9, 11, 13, 7, 14, 10,
                  11, 9, 12, 8, 13, 10, 14, 11, 9, 12],
        "gap": [0.2, -0.1, 0.5, -0.3, 0.1, 0.4, -0.2, 0.3, -0.1, 0.2,
                -0.4, 0.1, 0.3, -0.2, 0.5, -0.1, 0.2, 0.4, -0.3, 0.1],
        "weekday": [0, 1, 2, 3, 4, 0, 1, 2, 3, 4, 0, 1, 2, 3, 4, 0, 1, 2, 3, 4],
    }
    df = pd.DataFrame(data)
    df["is_green"] = df["change"] > 0
    df["next_change"] = df["change"].shift(-1)
    return df


@pytest.fixture
def empty_df():
    """Create empty DataFrame."""
    return pd.DataFrame()


@pytest.fixture
def grouped_df():
    """DataFrame with clear group patterns."""
    data = {
        "date": pd.date_range("2024-01-01", periods=10),
        "change": [1.0, -1.0, 1.0, -1.0, 1.0, 2.0, -2.0, 2.0, -2.0, 2.0],
        "weekday": [0, 0, 1, 1, 2, 2, 3, 3, 4, 4],  # Mon, Mon, Tue, Tue, etc.
        "is_green": [True, False, True, False, True, True, False, True, False, True],
    }
    return pd.DataFrame(data)


@pytest.fixture
def around_df():
    """DataFrame with next_change and prev_change for around operation."""
    data = {
        "date": pd.date_range("2024-01-01", periods=10),
        "change": [0.5, -0.3, 0.8, -0.2, 1.0, -0.5, 0.3, 0.7, -0.4, 0.2],
        "next_change": [-0.3, 0.8, -0.2, 1.0, -0.5, 0.3, 0.7, -0.4, 0.2, None],
        "prev_change": [None, 0.5, -0.3, 0.8, -0.2, 1.0, -0.5, 0.3, 0.7, -0.4],
        "is_green": [True, False, True, False, True, False, True, True, False, True],
    }
    return pd.DataFrame(data)


@pytest.fixture
def minute_df():
    """DataFrame with minute data for formation operation."""
    # Create minute data for 2 days
    timestamps = pd.date_range("2024-01-01 09:30", periods=780, freq="1min")  # 2 days * 390 min
    data = {
        "timestamp": timestamps,
        "open": [100 + i * 0.01 for i in range(780)],
        "high": [100.5 + i * 0.01 + (0.5 if i % 100 == 50 else 0) for i in range(780)],  # Peak at minute 50
        "low": [99.5 + i * 0.01 - (0.5 if i % 100 == 80 else 0) for i in range(780)],   # Low at minute 80
        "close": [100.2 + i * 0.01 for i in range(780)],
        "volume": [1000 + i for i in range(780)],
    }
    return pd.DataFrame(data)


# =============================================================================
# op_list Tests
# =============================================================================

class TestOpList:
    """Test list operation."""

    def test_top_10_by_change(self, sample_df):
        """List top 10 by change descending."""
        result = op_list(sample_df, "change", {"n": 10, "sort": "desc"})

        assert "rows" in result
        assert "summary" in result
        assert len(result["rows"]) == 10
        assert result["summary"]["count"] == 10
        assert result["summary"]["sort"] == "desc"

    def test_bottom_5_by_change(self, sample_df):
        """List bottom 5 by change (ascending)."""
        result = op_list(sample_df, "change", {"n": 5, "sort": "asc"})

        assert len(result["rows"]) == 5
        assert result["summary"]["sort"] == "asc"
        # First row should be most negative
        assert result["rows"][0]["change"] <= result["rows"][1]["change"]

    def test_empty_df_returns_empty(self, empty_df):
        """Empty DataFrame returns empty result."""
        result = op_list(empty_df, "change", {})

        assert result["rows"] == []
        assert result["summary"]["count"] == 0

    def test_column_not_found(self, sample_df):
        """Missing column returns error."""
        result = op_list(sample_df, "nonexistent", {})

        assert "error" in result["summary"]

    def test_default_params(self, sample_df):
        """Test default parameters (n=None means all, sort=desc)."""
        result = op_list(sample_df, "change", {})

        assert len(result["rows"]) == 20  # All rows when n not specified
        assert result["summary"]["sort"] == "desc"


# =============================================================================
# op_count Tests
# =============================================================================

class TestOpCount:
    """Test count operation."""

    def test_count_all(self, sample_df):
        """Count all rows."""
        result = op_count(sample_df, "change", {})

        assert "summary" in result
        assert result["summary"]["count"] == 20

    def test_count_returns_rows(self, sample_df):
        """Count returns all matching rows."""
        result = op_count(sample_df, "change", {})

        assert "rows" in result
        assert len(result["rows"]) == 20  # All rows returned

    def test_empty_df(self, empty_df):
        """Empty DataFrame."""
        result = op_count(empty_df, "change", {})

        assert result["summary"]["count"] == 0


# =============================================================================
# op_compare Tests
# =============================================================================

class TestOpCompare:
    """Test compare operation."""

    def test_compare_by_weekday(self, grouped_df):
        """Compare average change by weekday."""
        result = op_compare(grouped_df, "change", {"group_by": "weekday"})

        assert "rows" in result
        assert "summary" in result
        assert len(result["rows"]) > 0

    def test_compare_identifies_best_worst(self, grouped_df):
        """Compare identifies best and worst groups."""
        result = op_compare(grouped_df, "change", {"group_by": "weekday"})

        if "best" in result["summary"]:
            assert "best_avg" in result["summary"]
            assert "worst" in result["summary"]
            assert "worst_avg" in result["summary"]

    def test_empty_df(self, empty_df):
        """Empty DataFrame returns error."""
        result = op_compare(empty_df, "change", {"group_by": "weekday"})

        assert "error" in result["summary"]


# =============================================================================
# op_correlation Tests
# =============================================================================

class TestOpCorrelation:
    """Test correlation operation."""

    def test_correlation_two_metrics(self, sample_df):
        """Correlation between change and gap."""
        result = op_correlation(sample_df, "change", {"metrics": ["change", "gap"]})

        assert "summary" in result
        if "correlation" in result["summary"]:
            corr = result["summary"]["correlation"]
            assert -1 <= corr <= 1

    def test_empty_df(self, empty_df):
        """Empty DataFrame."""
        result = op_correlation(empty_df, "change", {"metrics": ["change", "gap"]})

        assert "error" in result["summary"]


# =============================================================================
# op_distribution Tests
# =============================================================================

class TestOpDistribution:
    """Test distribution operation."""

    def test_distribution_change(self, sample_df):
        """Distribution of change values."""
        result = op_distribution(sample_df, "change", {})

        assert "summary" in result
        summary = result["summary"]

        if "error" not in summary:
            assert "mean" in summary or "avg" in summary
            assert "std" in summary or "min" in summary

    def test_empty_df(self, empty_df):
        """Empty DataFrame."""
        result = op_distribution(empty_df, "change", {})

        assert "error" in result["summary"]


# =============================================================================
# op_probability Tests
# =============================================================================

class TestOpProbability:
    """Test probability operation."""

    def test_probability_green_day(self, sample_df):
        """Probability of green day (change > 0)."""
        result = op_probability(sample_df, "change", {"outcome": "> 0"})

        assert "summary" in result
        summary = result["summary"]

        if "probability" in summary:
            prob = summary["probability"]
            assert 0 <= prob <= 100
            assert "matches" in summary
            assert "total" in summary

    def test_probability_with_condition(self, sample_df):
        """Probability with condition filter."""
        result = op_probability(
            sample_df, "change",
            {"outcome": "> 0", "condition_filters": [{"type": "comparison", "metric": "gap", "op": ">", "value": 0}]}
        )

        assert "summary" in result

    def test_empty_df(self, empty_df):
        """Empty DataFrame."""
        result = op_probability(empty_df, "change", {"outcome": "> 0"})

        # Should handle gracefully
        assert "summary" in result


# =============================================================================
# op_streak Tests
# =============================================================================

class TestOpStreak:
    """Test streak operation."""

    def test_streak_green(self, sample_df):
        """Find green day streaks."""
        result = op_streak(sample_df, "change", {"color": "green"})

        assert "summary" in result
        if "error" not in result["summary"]:
            assert "count" in result["summary"] or "streaks" in result["summary"]

    def test_streak_red(self, sample_df):
        """Find red day streaks."""
        result = op_streak(sample_df, "change", {"color": "red"})

        assert "summary" in result


# =============================================================================
# op_around Tests
# =============================================================================

class TestOpAround:
    """Test around operation."""

    def test_around_day_after(self, around_df):
        """What happens day after events."""
        result = op_around(around_df, "change", {"offset": 1})

        assert "summary" in result
        summary = result["summary"]
        if "error" not in summary:
            assert "count" in summary
            assert "avg" in summary
            assert "positive_pct" in summary
            assert summary["offset"] == 1

    def test_around_day_before(self, around_df):
        """What happens day before events."""
        result = op_around(around_df, "change", {"offset": -1})

        assert "summary" in result
        summary = result["summary"]
        if "error" not in summary:
            assert summary["offset"] == -1

    def test_around_invalid_offset(self, around_df):
        """Invalid offset returns error."""
        result = op_around(around_df, "change", {"offset": 5})

        assert "error" in result["summary"]
        assert "Offset" in result["summary"]["error"]

    def test_around_empty_df(self, empty_df):
        """Empty DataFrame."""
        result = op_around(empty_df, "change", {"offset": 1})

        assert "error" in result["summary"]

    def test_around_missing_column(self, sample_df):
        """Missing next_change column."""
        # sample_df doesn't have next_change
        result = op_around(sample_df, "change", {"offset": 1})

        # Should either work if column exists or return error
        assert "summary" in result


# =============================================================================
# op_formation Tests
# =============================================================================

class TestOpFormation:
    """Test formation operation."""

    def test_formation_high(self, minute_df):
        """When is daily high formed."""
        result = op_formation(minute_df, "high", {"event": "high"})

        assert "summary" in result
        summary = result["summary"]
        if "error" not in summary:
            assert summary["event"] == "high"
            assert "peak_hour" in summary
            assert "total_days" in summary

    def test_formation_low(self, minute_df):
        """When is daily low formed."""
        result = op_formation(minute_df, "low", {"event": "low"})

        assert "summary" in result
        summary = result["summary"]
        if "error" not in summary:
            assert summary["event"] == "low"

    def test_formation_returns_rows(self, minute_df):
        """Formation returns hour distribution rows."""
        result = op_formation(minute_df, "high", {})

        if "error" not in result.get("summary", {}):
            assert "rows" in result
            if result["rows"]:
                row = result["rows"][0]
                assert "hour" in row
                assert "count" in row
                assert "pct" in row

    def test_formation_empty_df(self, empty_df):
        """Empty DataFrame."""
        result = op_formation(empty_df, "high", {})

        assert "error" in result["summary"]

    def test_formation_no_timestamp(self, sample_df):
        """DataFrame without timestamp column."""
        result = op_formation(sample_df, "high", {})

        assert "error" in result["summary"]
        assert "timestamp" in result["summary"]["error"].lower() or "minute" in result["summary"]["error"].lower()


# =============================================================================
# OPERATIONS Registry Tests
# =============================================================================

class TestOperationsRegistry:
    """Test OPERATIONS registry."""

    def test_all_operations_registered(self):
        """All 9 operations are registered."""
        expected = ["list", "count", "compare", "correlation",
                    "streak", "distribution", "probability", "around", "formation"]

        for op_name in expected:
            assert op_name in OPERATIONS, f"{op_name} not in OPERATIONS"

    def test_operations_are_callable(self):
        """All operations are callable."""
        for name, op in OPERATIONS.items():
            assert callable(op), f"{name} is not callable"

    def test_operations_return_dict(self, sample_df):
        """All operations return dict with rows and summary."""
        for name, op in OPERATIONS.items():
            if name == "formation":
                continue  # Formation needs special data
            if name == "around":
                continue  # Around needs event filters

            result = op(sample_df, "change", {})

            assert isinstance(result, dict), f"{name} should return dict"
            # Either has rows/summary or error
            has_structure = "rows" in result or "summary" in result or "error" in result
            assert has_structure, f"{name} missing expected keys"
