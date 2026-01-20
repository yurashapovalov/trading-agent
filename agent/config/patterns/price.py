"""
Price pattern definitions.

Price patterns are structural patterns across multiple bars:
- Trend patterns (higher highs, lower lows)
- Breakout patterns (range breakout, high breakout)
- Consolidation patterns (inside bar, narrow range)
"""

PRICE_PATTERNS = {
    # =========================================================================
    # CONSOLIDATION
    # =========================================================================

    "inside_bar": {
        "name": "Inside Bar",
        "category": "consolidation",
        "signal": "neutral",

        "description": "Current bar's range is within previous bar's range. "
                       "Consolidation, potential breakout setup.",

        "related": ["outside_bar", "narrow_range"],
        "opposite": "outside_bar",

        "reliability": 0.55,

        "detection": {
            "high_below_prev_high": True,
            "low_above_prev_low": True,
        },
    },

    "outside_bar": {
        "name": "Outside Bar",
        "category": "reversal",
        "signal": "neutral",

        "description": "Current bar's range engulfs previous bar's range. "
                       "Volatility expansion, potential reversal or breakout.",

        "related": ["inside_bar", "bullish_engulfing", "bearish_engulfing"],
        "opposite": "inside_bar",

        "reliability": 0.55,

        "detection": {
            "high_above_prev_high": True,
            "low_below_prev_low": True,
        },
    },

    "narrow_range_4": {
        "name": "NR4 (Narrow Range 4)",
        "category": "consolidation",
        "signal": "neutral",

        "description": "Smallest range of last 4 bars. "
                       "Volatility contraction, breakout imminent.",

        "related": ["narrow_range_7", "inside_bar"],
        "opposite": None,

        "reliability": 0.60,

        "detection": {
            "smallest_range_in_n": 4,
        },
    },

    "narrow_range_7": {
        "name": "NR7 (Narrow Range 7)",
        "category": "consolidation",
        "signal": "neutral",

        "description": "Smallest range of last 7 bars. "
                       "Strong volatility contraction, significant breakout expected.",

        "related": ["narrow_range_4", "inside_bar"],
        "opposite": None,

        "reliability": 0.65,

        "detection": {
            "smallest_range_in_n": 7,
        },
    },

    # =========================================================================
    # TREND
    # =========================================================================

    "higher_high": {
        "name": "Higher High",
        "category": "trend",
        "signal": "bullish",

        "description": "Current high exceeds previous high. "
                       "Uptrend continuation signal.",

        "related": ["higher_low", "lower_high"],
        "opposite": "lower_high",

        "reliability": 0.55,

        "detection": {
            "high_above_prev_high": True,
        },
    },

    "higher_low": {
        "name": "Higher Low",
        "category": "trend",
        "signal": "bullish",

        "description": "Current low is above previous low. "
                       "Uptrend structure, buyers defending higher levels.",

        "related": ["higher_high", "lower_low"],
        "opposite": "lower_low",

        "reliability": 0.55,

        "detection": {
            "low_above_prev_low": True,
        },
    },

    "lower_low": {
        "name": "Lower Low",
        "category": "trend",
        "signal": "bearish",

        "description": "Current low is below previous low. "
                       "Downtrend continuation signal.",

        "related": ["lower_high", "higher_low"],
        "opposite": "higher_low",

        "reliability": 0.55,

        "detection": {
            "low_below_prev_low": True,
        },
    },

    "lower_high": {
        "name": "Lower High",
        "category": "trend",
        "signal": "bearish",

        "description": "Current high is below previous high. "
                       "Downtrend structure, sellers defending lower levels.",

        "related": ["lower_low", "higher_high"],
        "opposite": "higher_high",

        "reliability": 0.55,

        "detection": {
            "high_below_prev_high": True,
        },
    },

    # =========================================================================
    # BREAKOUT
    # =========================================================================

    "breakout_high": {
        "name": "Breakout High",
        "category": "breakout",
        "signal": "bullish",

        "description": "Price breaks above recent high (lookback period). "
                       "Potential trend start or continuation.",

        "related": ["breakout_low", "higher_high"],
        "opposite": "breakout_low",

        "reliability": 0.55,

        "detection": {
            "high_above_n_period_high": True,
            "default_lookback": 20,
        },
    },

    "breakout_low": {
        "name": "Breakout Low",
        "category": "breakout",
        "signal": "bearish",

        "description": "Price breaks below recent low (lookback period). "
                       "Potential trend start or continuation.",

        "related": ["breakout_high", "lower_low"],
        "opposite": "breakout_high",

        "reliability": 0.55,

        "detection": {
            "low_below_n_period_low": True,
            "default_lookback": 20,
        },
    },
}


# =============================================================================
# ACCESS FUNCTIONS
# =============================================================================


def get_price_pattern(name: str) -> dict | None:
    """Get pattern definition by name."""
    return PRICE_PATTERNS.get(name.lower())


def list_price_patterns() -> list[str]:
    """List all price pattern names."""
    return list(PRICE_PATTERNS.keys())


def get_price_patterns_by_category(category: str) -> list[str]:
    """Get patterns by category (consolidation, trend, breakout)."""
    return [
        name for name, p in PRICE_PATTERNS.items()
        if p["category"] == category.lower()
    ]
