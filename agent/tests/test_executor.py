"""Tests for executor module."""

import pytest
import pandas as pd
from datetime import date

from agent.agents.executor import _apply_session_filter


# =============================================================================
# Session Filter Tests
# =============================================================================

class TestApplySessionFilter:
    """Test session filtering with cross-midnight handling."""

    @pytest.fixture
    def minute_df(self):
        """DataFrame with time column spanning 24 hours."""
        # Create times from 00:00 to 23:30 in 30min intervals
        times = [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]
        return pd.DataFrame({
            "time": times,
            "close": [100 + i for i in range(len(times))],
        })

    def test_rth_session(self, minute_df):
        """RTH (09:30-17:00) uses AND logic."""
        result = _apply_session_filter(minute_df, "RTH", "NQ")

        # Should include 09:30 but not 17:00
        assert "09:30" in result["time"].values
        assert "10:00" in result["time"].values
        assert "16:30" in result["time"].values
        assert "17:00" not in result["time"].values
        assert "09:00" not in result["time"].values

    def test_morning_session(self, minute_df):
        """MORNING (09:30-12:30) uses AND logic."""
        result = _apply_session_filter(minute_df, "MORNING", "NQ")

        assert "09:30" in result["time"].values
        assert "12:00" in result["time"].values
        assert "12:30" not in result["time"].values
        assert "13:00" not in result["time"].values

    def test_overnight_session(self, minute_df):
        """OVERNIGHT (18:00-09:30) uses OR logic - crosses midnight."""
        result = _apply_session_filter(minute_df, "OVERNIGHT", "NQ")

        # Should include evening (>= 18:00) AND early morning (< 09:30)
        assert "18:00" in result["time"].values
        assert "23:00" in result["time"].values
        assert "00:00" in result["time"].values
        assert "09:00" in result["time"].values
        # Should NOT include RTH hours
        assert "09:30" not in result["time"].values
        assert "12:00" not in result["time"].values
        assert "17:00" not in result["time"].values

    def test_asian_session(self, minute_df):
        """ASIAN (18:00-03:00) uses OR logic - crosses midnight."""
        result = _apply_session_filter(minute_df, "ASIAN", "NQ")

        # Should include evening (>= 18:00) AND early morning (< 03:00)
        assert "18:00" in result["time"].values
        assert "23:00" in result["time"].values
        assert "00:00" in result["time"].values
        assert "02:30" in result["time"].values
        # Should NOT include after 03:00
        assert "03:00" not in result["time"].values
        assert "09:00" not in result["time"].values

    def test_eth_session(self, minute_df):
        """ETH (18:00-17:00) uses OR logic - almost 24 hours."""
        result = _apply_session_filter(minute_df, "ETH", "NQ")

        # Should include everything except 17:00-17:59
        assert "18:00" in result["time"].values
        assert "00:00" in result["time"].values
        assert "09:30" in result["time"].values
        assert "16:30" in result["time"].values
        # Should NOT include maintenance window
        assert "17:00" not in result["time"].values
        assert "17:30" not in result["time"].values

    def test_european_session(self, minute_df):
        """EUROPEAN (03:00-09:30) uses AND logic - same day."""
        result = _apply_session_filter(minute_df, "EUROPEAN", "NQ")

        assert "03:00" in result["time"].values
        assert "09:00" in result["time"].values
        assert "09:30" not in result["time"].values
        assert "02:30" not in result["time"].values

    def test_unknown_session(self, minute_df):
        """Unknown session returns unchanged DataFrame."""
        result = _apply_session_filter(minute_df, "UNKNOWN_SESSION", "NQ")
        assert len(result) == len(minute_df)

    def test_missing_time_column(self):
        """DataFrame without time column returns unchanged."""
        df = pd.DataFrame({"close": [100, 101, 102]})
        result = _apply_session_filter(df, "RTH", "NQ")
        assert len(result) == 3


# =============================================================================
# Session Filter Count Tests
# =============================================================================

class TestSessionFilterCounts:
    """Test that session filters return correct row counts."""

    @pytest.fixture
    def hourly_df(self):
        """DataFrame with hourly time column."""
        times = [f"{h:02d}:00" for h in range(24)]
        return pd.DataFrame({
            "time": times,
            "close": [100 + i for i in range(24)],
        })

    def test_overnight_count(self, hourly_df):
        """OVERNIGHT should include ~16 hours (18:00-23:00 + 00:00-09:00)."""
        result = _apply_session_filter(hourly_df, "OVERNIGHT", "NQ")
        # >= 18:00: 18,19,20,21,22,23 = 6 hours
        # < 09:30: 0,1,2,3,4,5,6,7,8,9 = 10 hours (09:00 < 09:30)
        # Total = 16
        assert len(result) == 16

    def test_rth_count(self, hourly_df):
        """RTH should include ~7.5 hours (09:30-17:00, but we have hourly so ~8)."""
        result = _apply_session_filter(hourly_df, "RTH", "NQ")
        # 09:30-17:00 with hourly data: 10, 11, 12, 13, 14, 15, 16 = 7 hours
        # (09:00 < 09:30, so not included; 17:00 not included)
        assert len(result) == 7

    def test_asian_count(self, hourly_df):
        """ASIAN should include ~9 hours (18:00-03:00)."""
        result = _apply_session_filter(hourly_df, "ASIAN", "NQ")
        # 18,19,20,21,22,23 + 0,1,2 = 6 + 3 = 9
        assert len(result) == 9
