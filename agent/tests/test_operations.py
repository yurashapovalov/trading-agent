"""
Unit tests for operations/

Run: pytest agent/tests/test_operations.py -v
"""

import pytest
import pandas as pd
import numpy as np

from agent.operations.stats import op_stats
from agent.operations.top_n import op_top_n
from agent.operations.compare import op_compare
from agent.operations.seasonality import op_seasonality


@pytest.fixture
def sample_df():
    """Create sample trading data."""
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=10, freq="D"),
        "open": [100, 101, 99, 102, 100, 103, 101, 104, 102, 105],
        "high": [102, 103, 101, 104, 102, 105, 103, 106, 104, 107],
        "low": [99, 100, 98, 101, 99, 102, 100, 103, 101, 104],
        "close": [101, 99, 102, 100, 103, 101, 104, 102, 105, 103],
        "volume": [1000, 1200, 800, 1500, 1100, 900, 1300, 1000, 1400, 1100],
        "change_pct": [1.0, -2.0, 3.0, -2.0, 3.0, -2.0, 3.0, -2.0, 3.0, -2.0],
        "range": [3, 3, 3, 3, 3, 3, 3, 3, 3, 3],
        "range_pct": [3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0],
        "is_green": [True, False, True, False, True, False, True, False, True, False],
        "gap_pct": [0.5, -0.5, 0.3, -0.3, 0.4, -0.4, 0.2, -0.2, 0.6, -0.1],
        "weekday": [0, 1, 2, 3, 4, 5, 6, 0, 1, 2],  # Mon-Sun cycle
    })


class TestOpStats:
    """Tests for op_stats."""

    def test_basic_stats(self, sample_df):
        result = op_stats(sample_df, {})
        
        assert result["count"] == 10
        assert "avg_change_pct" in result
        assert "green_days" in result
        assert "red_days" in result

    def test_green_red_count(self, sample_df):
        result = op_stats(sample_df, {})
        
        assert result["green_days"] == 5
        assert result["red_days"] == 5
        assert result["green_pct"] == 50.0

    def test_volume_stats(self, sample_df):
        result = op_stats(sample_df, {})
        
        assert "avg_volume" in result
        assert "total_volume" in result
        assert result["total_volume"] == 11300

    def test_gap_stats(self, sample_df):
        result = op_stats(sample_df, {})
        
        assert "avg_gap_pct" in result
        assert "gap_up_count" in result
        assert "gap_down_count" in result
        assert result["gap_up_count"] == 5
        assert result["gap_down_count"] == 5

    def test_empty_df(self):
        result = op_stats(pd.DataFrame(), {})
        assert result == {"error": "No data"}


class TestOpTopN:
    """Tests for op_top_n."""

    def test_top_5_by_volume(self, sample_df):
        result = op_top_n(sample_df, {"n": 5, "by": "volume"})
        
        assert "rows" in result
        assert len(result["rows"]) == 5
        # First row should have highest volume
        assert result["rows"][0]["volume"] == 1500

    def test_top_3_by_change(self, sample_df):
        result = op_top_n(sample_df, {"n": 3, "by": "change_pct"})
        
        assert len(result["rows"]) == 3
        # All top 3 should have 3.0 change_pct
        assert result["rows"][0]["change_pct"] == 3.0

    def test_bottom_3_ascending(self, sample_df):
        result = op_top_n(sample_df, {"n": 3, "by": "change_pct", "ascending": True})
        
        assert len(result["rows"]) == 3
        # Bottom 3 should have -2.0 change_pct
        assert result["rows"][0]["change_pct"] == -2.0

    def test_with_aggregation(self, sample_df):
        result = op_top_n(sample_df, {
            "n": 5,
            "by": "volume",
            "then": {"metric": "change_pct", "agg": "mean"}
        })
        
        assert "agg_result" in result
        assert "agg_label" in result
        assert result["agg_label"] == "mean_change_pct"

    def test_missing_column(self, sample_df):
        result = op_top_n(sample_df, {"n": 5, "by": "nonexistent"})
        assert "error" in result

    def test_empty_df(self):
        result = op_top_n(pd.DataFrame(), {"n": 5, "by": "volume"})
        assert result == {"error": "No data"}


class TestOpCompare:
    """Tests for op_compare."""

    def test_compare_weekdays(self, sample_df):
        result = op_compare(sample_df, {
            "group_by": "weekday",
            "metric": "change_pct",
            "groups": [0, 1],  # Monday vs Tuesday
        })

        assert "data" in result
        assert "best" in result
        assert "worst" in result

    def test_empty_df(self):
        result = op_compare(pd.DataFrame(), {"group_by": "weekday", "metric": "change_pct"})
        assert result == {"error": "No data"}


class TestOpSeasonality:
    """Tests for op_seasonality."""

    def test_seasonality_by_weekday(self, sample_df):
        result = op_seasonality(sample_df, {
            "group_by": "weekday",
            "metric": "change_pct"
        })

        assert "data" in result
        assert "best" in result
        assert "worst" in result
        assert "best_label" in result

    def test_empty_df(self):
        result = op_seasonality(pd.DataFrame(), {"group_by": "weekday", "metric": "change_pct"})
        assert result == {"error": "No data"}


class TestEdgeCases:
    """Edge case tests."""

    def test_single_row_stats(self):
        df = pd.DataFrame({
            "change_pct": [2.5],
            "range": [5],
            "is_green": [True],
        })
        result = op_stats(df, {})
        
        assert result["count"] == 1
        assert result["green_days"] == 1
        assert result["green_pct"] == 100.0

    def test_all_nan_column(self, sample_df):
        df = sample_df.copy()
        df["gap_pct"] = np.nan
        result = op_stats(df, {})
        
        # Should not crash, gap stats should be absent or handle NaN
        assert "count" in result

    def test_top_n_larger_than_data(self, sample_df):
        result = op_top_n(sample_df, {"n": 100, "by": "volume"})
        
        # Should return all rows (10)
        assert len(result["rows"]) == 10
