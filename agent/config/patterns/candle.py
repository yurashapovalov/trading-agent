"""
Candle pattern definitions.

Each pattern contains:
- name: Display name
- category: reversal, continuation, neutral
- signal: bullish, bearish, neutral
- importance: high (always mention), medium (mention if several), low (skip in summary)
- description: What the pattern means (for Responder)
- related: Similar/related patterns
- opposite: Mirror pattern (e.g., hammer ↔ hanging_man)
- confirms: Patterns that strengthen the signal
- reliability: Historical success rate (0.0-1.0)
- candles: Number of candles in pattern (1, 2, 3)
- detection: Parameters for SQL expression generation
"""

CANDLE_PATTERNS = {
    # =========================================================================
    # SINGLE CANDLE — BULLISH
    # =========================================================================

    "hammer": {
        "name": "Hammer",
        "category": "reversal",
        "signal": "bullish",
        "importance": "medium",
        "candles": 1,

        "description": "Long lower shadow, small body at top. "
                       "Buyers rejected lower prices. Most reliable after downtrend.",

        "related": ["hanging_man", "inverted_hammer", "dragonfly_doji"],
        "opposite": "hanging_man",
        "confirms": ["morning_star", "bullish_engulfing"],

        "reliability": 0.60,

        "detection": {
            "body_ratio_max": 0.3,
            "lower_shadow_ratio_min": 0.6,
            "upper_shadow_ratio_max": 0.1,
        },
    },

    "inverted_hammer": {
        "name": "Inverted Hammer",
        "category": "reversal",
        "signal": "bullish",
        "importance": "low",
        "candles": 1,

        "description": "Long upper shadow, small body at bottom. "
                       "Buying attempt that faced resistance. Needs confirmation.",

        "related": ["hammer", "shooting_star"],
        "opposite": "shooting_star",
        "confirms": ["bullish_engulfing"],

        "reliability": 0.55,

        "detection": {
            "body_ratio_max": 0.3,
            "upper_shadow_ratio_min": 0.6,
            "lower_shadow_ratio_max": 0.1,
        },
    },

    "dragonfly_doji": {
        "name": "Dragonfly Doji",
        "category": "reversal",
        "signal": "bullish",
        "importance": "medium",
        "candles": 1,

        "description": "No body, long lower shadow, no upper shadow. "
                       "Strong rejection of lower prices. Bullish after downtrend.",

        "related": ["hammer", "doji", "gravestone_doji"],
        "opposite": "gravestone_doji",
        "confirms": ["morning_star"],

        "reliability": 0.60,

        "detection": {
            "body_ratio_max": 0.05,
            "lower_shadow_ratio_min": 0.7,
            "upper_shadow_ratio_max": 0.05,
        },
    },

    # =========================================================================
    # SINGLE CANDLE — BEARISH
    # =========================================================================

    "hanging_man": {
        "name": "Hanging Man",
        "category": "reversal",
        "signal": "bearish",
        "importance": "medium",
        "candles": 1,

        "description": "Same shape as hammer but after uptrend. "
                       "Sellers starting to appear despite recovery.",

        "related": ["hammer", "shooting_star"],
        "opposite": "hammer",
        "confirms": ["evening_star", "bearish_engulfing"],

        "reliability": 0.55,

        "detection": {
            "body_ratio_max": 0.3,
            "lower_shadow_ratio_min": 0.6,
            "upper_shadow_ratio_max": 0.1,
        },
    },

    "shooting_star": {
        "name": "Shooting Star",
        "category": "reversal",
        "signal": "bearish",
        "importance": "medium",
        "candles": 1,

        "description": "Long upper shadow, small body at bottom. "
                       "Buyers pushed up but sellers took over.",

        "related": ["inverted_hammer", "hanging_man", "gravestone_doji"],
        "opposite": "inverted_hammer",
        "confirms": ["evening_star", "bearish_engulfing"],

        "reliability": 0.60,

        "detection": {
            "body_ratio_max": 0.3,
            "upper_shadow_ratio_min": 0.6,
            "lower_shadow_ratio_max": 0.1,
        },
    },

    "gravestone_doji": {
        "name": "Gravestone Doji",
        "category": "reversal",
        "signal": "bearish",
        "importance": "medium",
        "candles": 1,

        "description": "No body, long upper shadow, no lower shadow. "
                       "Strong rejection of higher prices. Bearish after uptrend.",

        "related": ["shooting_star", "doji", "dragonfly_doji"],
        "opposite": "dragonfly_doji",
        "confirms": ["evening_star"],

        "reliability": 0.60,

        "detection": {
            "body_ratio_max": 0.05,
            "upper_shadow_ratio_min": 0.7,
            "lower_shadow_ratio_max": 0.05,
        },
    },

    # =========================================================================
    # SINGLE CANDLE — NEUTRAL
    # =========================================================================

    "doji": {
        "name": "Doji",
        "category": "neutral",
        "signal": "indecision",
        "importance": "medium",
        "candles": 1,

        "description": "Open ≈ Close with shadows. Market indecision, "
                       "potential reversal. Needs confirmation from next candle.",

        "related": ["spinning_top", "dragonfly_doji", "gravestone_doji"],
        "opposite": None,
        "confirms": [],

        "reliability": 0.50,

        "detection": {
            "body_ratio_max": 0.1,
        },
    },

    "spinning_top": {
        "name": "Spinning Top",
        "category": "neutral",
        "signal": "indecision",
        "importance": "low",
        "candles": 1,

        "description": "Small body with long shadows on both sides. "
                       "Neither buyers nor sellers in control.",

        "related": ["doji"],
        "opposite": None,
        "confirms": [],

        "reliability": 0.45,

        "detection": {
            "body_ratio_max": 0.3,
            "lower_shadow_ratio_min": 0.25,
            "upper_shadow_ratio_min": 0.25,
        },
    },

    # =========================================================================
    # SINGLE CANDLE — MOMENTUM
    # =========================================================================

    "marubozu_bullish": {
        "name": "Bullish Marubozu",
        "category": "continuation",
        "signal": "bullish",
        "importance": "low",
        "candles": 1,

        "description": "Full body, no shadows. Strong buying pressure "
                       "from open to close. Momentum signal.",

        "related": ["marubozu_bearish", "three_white_soldiers"],
        "opposite": "marubozu_bearish",
        "confirms": [],

        "reliability": 0.65,

        "detection": {
            "body_ratio_min": 0.9,
            "is_green": True,
        },
    },

    "marubozu_bearish": {
        "name": "Bearish Marubozu",
        "category": "continuation",
        "signal": "bearish",
        "importance": "low",
        "candles": 1,

        "description": "Full body, no shadows. Strong selling pressure "
                       "from open to close. Momentum signal.",

        "related": ["marubozu_bullish", "three_black_crows"],
        "opposite": "marubozu_bullish",
        "confirms": [],

        "reliability": 0.65,

        "detection": {
            "body_ratio_min": 0.9,
            "is_red": True,
        },
    },

    # =========================================================================
    # TWO CANDLE — BULLISH
    # =========================================================================

    "bullish_engulfing": {
        "name": "Bullish Engulfing",
        "category": "reversal",
        "signal": "bullish",
        "importance": "high",
        "candles": 2,

        "description": "Green candle completely engulfs previous red candle. "
                       "Strong reversal signal after downtrend.",

        "related": ["bearish_engulfing", "piercing_line"],
        "opposite": "bearish_engulfing",
        "confirms": ["hammer", "morning_star"],

        "reliability": 0.65,

        "detection": {
            "prev_red": True,
            "curr_green": True,
            "curr_body_engulfs_prev": True,
        },
    },

    "piercing_line": {
        "name": "Piercing Line",
        "category": "reversal",
        "signal": "bullish",
        "importance": "medium",
        "candles": 2,

        "description": "Green candle opens below prev low, closes above prev midpoint. "
                       "Buyers stepping in after gap down.",

        "related": ["bullish_engulfing", "dark_cloud_cover"],
        "opposite": "dark_cloud_cover",
        "confirms": ["hammer"],

        "reliability": 0.60,

        "detection": {
            "prev_red": True,
            "curr_green": True,
            "curr_opens_below_prev_low": True,
            "curr_closes_above_prev_midpoint": True,
        },
    },

    "tweezer_bottom": {
        "name": "Tweezer Bottom",
        "category": "reversal",
        "signal": "bullish",
        "importance": "low",
        "candles": 2,

        "description": "Two candles with matching lows. Strong support level, "
                       "potential reversal point.",

        "related": ["tweezer_top", "double_bottom"],
        "opposite": "tweezer_top",
        "confirms": ["hammer", "bullish_engulfing"],

        "reliability": 0.55,

        "detection": {
            "lows_match": True,
            "tolerance": 0.001,
        },
    },

    # =========================================================================
    # TWO CANDLE — BEARISH
    # =========================================================================

    "bearish_engulfing": {
        "name": "Bearish Engulfing",
        "category": "reversal",
        "signal": "bearish",
        "importance": "high",
        "candles": 2,

        "description": "Red candle completely engulfs previous green candle. "
                       "Strong reversal signal after uptrend.",

        "related": ["bullish_engulfing", "dark_cloud_cover"],
        "opposite": "bullish_engulfing",
        "confirms": ["shooting_star", "evening_star"],

        "reliability": 0.65,

        "detection": {
            "prev_green": True,
            "curr_red": True,
            "curr_body_engulfs_prev": True,
        },
    },

    "dark_cloud_cover": {
        "name": "Dark Cloud Cover",
        "category": "reversal",
        "signal": "bearish",
        "importance": "medium",
        "candles": 2,

        "description": "Red candle opens above prev high, closes below prev midpoint. "
                       "Sellers taking over after gap up.",

        "related": ["bearish_engulfing", "piercing_line"],
        "opposite": "piercing_line",
        "confirms": ["shooting_star"],

        "reliability": 0.60,

        "detection": {
            "prev_green": True,
            "curr_red": True,
            "curr_opens_above_prev_high": True,
            "curr_closes_below_prev_midpoint": True,
        },
    },

    "tweezer_top": {
        "name": "Tweezer Top",
        "category": "reversal",
        "signal": "bearish",
        "importance": "low",
        "candles": 2,

        "description": "Two candles with matching highs. Strong resistance level, "
                       "potential reversal point.",

        "related": ["tweezer_bottom", "double_top"],
        "opposite": "tweezer_bottom",
        "confirms": ["shooting_star", "bearish_engulfing"],

        "reliability": 0.55,

        "detection": {
            "highs_match": True,
            "tolerance": 0.001,
        },
    },

    # =========================================================================
    # THREE CANDLE — BULLISH
    # =========================================================================

    "morning_star": {
        "name": "Morning Star",
        "category": "reversal",
        "signal": "bullish",
        "importance": "high",
        "candles": 3,

        "description": "Red candle, small body (indecision), green candle closing "
                       "above first's midpoint. Strong bullish reversal.",

        "related": ["evening_star", "three_white_soldiers"],
        "opposite": "evening_star",
        "confirms": ["hammer", "bullish_engulfing"],

        "reliability": 0.70,

        "detection": {
            "first_red": True,
            "first_body_ratio_min": 0.5,
            "second_body_ratio_max": 0.3,
            "third_green": True,
            "third_closes_above_first_midpoint": True,
        },
    },

    "three_white_soldiers": {
        "name": "Three White Soldiers",
        "category": "reversal",
        "signal": "bullish",
        "importance": "high",
        "candles": 3,

        "description": "Three consecutive green candles, each closing higher. "
                       "Strong bullish momentum, trend reversal confirmed.",

        "related": ["three_black_crows", "morning_star"],
        "opposite": "three_black_crows",
        "confirms": [],

        "reliability": 0.75,

        "detection": {
            "all_green": True,
            "each_closes_higher": True,
            "each_opens_within_prev_body": True,
        },
    },

    # =========================================================================
    # THREE CANDLE — BEARISH
    # =========================================================================

    "evening_star": {
        "name": "Evening Star",
        "category": "reversal",
        "signal": "bearish",
        "importance": "high",
        "candles": 3,

        "description": "Green candle, small body (indecision), red candle closing "
                       "below first's midpoint. Strong bearish reversal.",

        "related": ["morning_star", "three_black_crows"],
        "opposite": "morning_star",
        "confirms": ["shooting_star", "bearish_engulfing"],

        "reliability": 0.70,

        "detection": {
            "first_green": True,
            "first_body_ratio_min": 0.5,
            "second_body_ratio_max": 0.3,
            "third_red": True,
            "third_closes_below_first_midpoint": True,
        },
    },

    "three_black_crows": {
        "name": "Three Black Crows",
        "category": "reversal",
        "signal": "bearish",
        "importance": "high",
        "candles": 3,

        "description": "Three consecutive red candles, each closing lower. "
                       "Strong bearish momentum, trend reversal confirmed.",

        "related": ["three_white_soldiers", "evening_star"],
        "opposite": "three_white_soldiers",
        "confirms": [],

        "reliability": 0.75,

        "detection": {
            "all_red": True,
            "each_closes_lower": True,
            "each_opens_within_prev_body": True,
        },
    },
}


# =============================================================================
# ACCESS FUNCTIONS
# =============================================================================


def get_candle_pattern(name: str) -> dict | None:
    """Get pattern definition by name."""
    return CANDLE_PATTERNS.get(name.lower())


def list_candle_patterns() -> list[str]:
    """List all candle pattern names."""
    return list(CANDLE_PATTERNS.keys())


def get_candle_patterns_by_signal(signal: str) -> list[str]:
    """Get patterns by signal type (bullish, bearish, neutral, indecision)."""
    return [
        name for name, p in CANDLE_PATTERNS.items()
        if p["signal"] == signal.lower()
    ]


def get_candle_patterns_by_category(category: str) -> list[str]:
    """Get patterns by category (reversal, continuation, neutral)."""
    return [
        name for name, p in CANDLE_PATTERNS.items()
        if p["category"] == category.lower()
    ]


def get_candle_pattern_description(name: str) -> str | None:
    """Get pattern description for Responder."""
    pattern = get_candle_pattern(name)
    return pattern["description"] if pattern else None


def get_related_patterns(name: str) -> list[str]:
    """Get related patterns."""
    pattern = get_candle_pattern(name)
    return pattern.get("related", []) if pattern else []


# Timeframe functions moved to __init__.py for DRY (unified access for all pattern types)
