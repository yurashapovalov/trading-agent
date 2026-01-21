"""
Unit tests for executor.py

Run: pytest agent/tests/test_executor.py -v

Note: These tests require the database with NQ data.
"""

import pytest
from datetime import date

from agent.executor import execute, _apply_filters, _get_timeframe, _build_params
from agent.types import ParsedQuery, Period
import pandas as pd


class TestNonDataIntents:
    """Test non-data intent handling."""

    def test_chitchat_intent(self):
        parsed = ParsedQuery(intent="chitchat")
        result = execute(parsed, "NQ", date(2025, 1, 15))
        
        assert result["intent"] == "chitchat"

    def test_concept_intent(self):
        parsed = ParsedQuery(intent="concept", what="OPEX")
        result = execute(parsed, "NQ", date(2025, 1, 15))
        
        assert result["intent"] == "concept"
        assert result["topic"] == "OPEX"

    def test_unclear_fields(self):
        parsed = ParsedQuery(intent="data", unclear=["period", "metric"])
        result = execute(parsed, "NQ", date(2025, 1, 15))
        
        assert result["intent"] == "clarification"
        assert result["unclear"] == ["period", "metric"]


class TestDataIntent:
    """Test data intent execution."""

    def test_year_query(self):
        parsed = ParsedQuery(
            intent="data",
            period=Period(type="year", value="2024"),
            operation="stats"
        )
        result = execute(parsed, "NQ", date(2025, 1, 15))
        
        assert result["intent"] == "data"
        assert result["operation"] == "stats"
        assert "result" in result
        assert result["row_count"] > 0

    def test_top_n_query(self):
        parsed = ParsedQuery(
            intent="data",
            period=Period(type="year", value="2024"),
            operation="top_n",
            top_n=5,
            sort_by="range"
        )
        result = execute(parsed, "NQ", date(2025, 1, 15))
        
        assert result["intent"] == "data"
        assert result["operation"] == "top_n"
        assert "rows" in result["result"]
        assert len(result["result"]["rows"]) == 5

    def test_weekday_filter(self):
        parsed = ParsedQuery(
            intent="data",
            period=Period(type="year", value="2024"),
            operation="stats",
            weekday_filter=["friday"]
        )
        result = execute(parsed, "NQ", date(2025, 1, 15))
        
        assert result["intent"] == "data"
        # Should have fewer rows than full year
        assert result["row_count"] < 252  # ~52 Fridays

    def test_no_data_returns_no_data_intent(self):
        parsed = ParsedQuery(
            intent="data",
            period=Period(type="year", value="1990"),  # No data for this year
            operation="stats"
        )
        result = execute(parsed, "NQ", date(2025, 1, 15))
        
        assert result["intent"] == "no_data"


class TestGetTimeframe:
    """Test timeframe determination."""

    def test_default_daily(self):
        parsed = ParsedQuery(intent="data")
        assert _get_timeframe(parsed) == "1D"

    def test_session_timeframe(self):
        parsed = ParsedQuery(intent="data", session="RTH")
        assert _get_timeframe(parsed) == "RTH"

    def test_hour_grouping(self):
        parsed = ParsedQuery(intent="data", group_by="hour")
        assert _get_timeframe(parsed) == "1H"


class TestApplyFilters:
    """Test filter application."""

    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=14, freq="D"),
            "weekday": [0, 1, 2, 3, 4, 5, 6, 0, 1, 2, 3, 4, 5, 6],  # 2 weeks
            "change_pct": [1, -1, 2, -2, 3, 0, 0, 1, -1, 2, -2, 3, 0, 0],
        })

    def test_weekday_filter(self, sample_df):
        parsed = ParsedQuery(intent="data", weekday_filter=["monday"])
        result = _apply_filters(sample_df, parsed)
        
        assert len(result) == 2  # 2 Mondays in 2 weeks
        assert all(result["weekday"] == 0)

    def test_multiple_weekdays(self, sample_df):
        parsed = ParsedQuery(intent="data", weekday_filter=["monday", "friday"])
        result = _apply_filters(sample_df, parsed)
        
        assert len(result) == 4  # 2 Mondays + 2 Fridays

    def test_condition_filter(self, sample_df):
        parsed = ParsedQuery(intent="data", condition="change_pct > 0")
        result = _apply_filters(sample_df, parsed)
        
        assert all(result["change_pct"] > 0)


class TestBuildParams:
    """Test parameter building."""

    def test_top_n_params(self):
        parsed = ParsedQuery(intent="data", top_n=10, sort_by="volume")
        params = _build_params(parsed, "top_n")
        
        assert params["n"] == 10
        assert params["by"] == "volume"

    def test_seasonality_params(self):
        parsed = ParsedQuery(intent="data", group_by="weekday")
        params = _build_params(parsed, "seasonality")
        
        assert params["group_by"] == "weekday"
        assert params["metric"] == "change_pct"  # default

    def test_compare_params(self):
        parsed = ParsedQuery(intent="data", compare=["2023", "2024"])
        params = _build_params(parsed, "compare")
        
        assert params["groups"] == ["2023", "2024"]
