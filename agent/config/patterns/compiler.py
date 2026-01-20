"""
Pattern compiler — converts pattern config to SQL expression / Computed atom.

This is the bridge between declarative pattern definitions and SQL generation.
"""

from __future__ import annotations

from agent.atoms.data import Computed
from agent.config.patterns.candle import CANDLE_PATTERNS
from agent.config.patterns.price import PRICE_PATTERNS


def pattern_to_expr(pattern_name: str) -> str | None:
    """
    Convert pattern to SQL CASE expression.

    Returns expression like:
        CASE WHEN <conditions> THEN 1 ELSE 0 END
    """
    # Try candle patterns first
    pattern = CANDLE_PATTERNS.get(pattern_name.lower())
    if pattern:
        return _build_candle_expr(pattern)

    # Try price patterns
    pattern = PRICE_PATTERNS.get(pattern_name.lower())
    if pattern:
        return _build_price_expr(pattern)

    return None


def pattern_to_computed(pattern_name: str, alias: str = None) -> Computed | None:
    """
    Convert pattern to Computed atom.

    Args:
        pattern_name: Pattern name (e.g., "hammer", "doji")
        alias: Optional column alias (default: is_{pattern_name})

    Returns:
        Computed atom ready for DataBuilder
    """
    expr = pattern_to_expr(pattern_name)
    if not expr:
        return None

    alias = alias or f"is_{pattern_name}"
    return Computed(expr=expr, alias=alias)


# =============================================================================
# CANDLE PATTERN EXPRESSIONS
# =============================================================================


def _build_candle_expr(pattern: dict) -> str:
    """Build SQL expression for candle pattern."""
    detection = pattern.get("detection", {})
    candles = pattern.get("candles", 1)

    if candles == 1:
        conditions = _single_candle_conditions(detection)
    elif candles == 2:
        conditions = _two_candle_conditions(detection)
    elif candles == 3:
        conditions = _three_candle_conditions(detection)
    else:
        return "0"  # Unsupported

    if not conditions:
        return "0"

    return f"CASE WHEN {' AND '.join(conditions)} THEN 1 ELSE 0 END"


def _single_candle_conditions(detection: dict) -> list[str]:
    """Build conditions for single-candle pattern."""
    conds = []

    # Body ratio: abs(close - open) / range
    if "body_ratio_max" in detection:
        conds.append(
            f"ABS(close - open) / NULLIF(high - low, 0) < {detection['body_ratio_max']}"
        )
    if "body_ratio_min" in detection:
        conds.append(
            f"ABS(close - open) / NULLIF(high - low, 0) > {detection['body_ratio_min']}"
        )

    # Lower shadow ratio: (min(open,close) - low) / range
    if "lower_shadow_ratio_min" in detection:
        conds.append(
            f"(LEAST(close, open) - low) / NULLIF(high - low, 0) > {detection['lower_shadow_ratio_min']}"
        )
    if "lower_shadow_ratio_max" in detection:
        conds.append(
            f"(LEAST(close, open) - low) / NULLIF(high - low, 0) < {detection['lower_shadow_ratio_max']}"
        )

    # Upper shadow ratio: (high - max(open,close)) / range
    if "upper_shadow_ratio_min" in detection:
        conds.append(
            f"(high - GREATEST(close, open)) / NULLIF(high - low, 0) > {detection['upper_shadow_ratio_min']}"
        )
    if "upper_shadow_ratio_max" in detection:
        conds.append(
            f"(high - GREATEST(close, open)) / NULLIF(high - low, 0) < {detection['upper_shadow_ratio_max']}"
        )

    # Color
    if detection.get("is_green"):
        conds.append("close > open")
    if detection.get("is_red"):
        conds.append("close < open")

    return conds


def _two_candle_conditions(detection: dict) -> list[str]:
    """Build conditions for two-candle pattern (uses LAG)."""
    conds = []

    # Previous candle color
    if detection.get("prev_red"):
        conds.append("LAG(close) OVER (ORDER BY ts) < LAG(open) OVER (ORDER BY ts)")
    if detection.get("prev_green"):
        conds.append("LAG(close) OVER (ORDER BY ts) > LAG(open) OVER (ORDER BY ts)")

    # Current candle color
    if detection.get("curr_red"):
        conds.append("close < open")
    if detection.get("curr_green"):
        conds.append("close > open")

    # Engulfing: current body engulfs previous body
    if detection.get("curr_body_engulfs_prev"):
        conds.append("open <= LAG(close) OVER (ORDER BY ts)")
        conds.append("close >= LAG(open) OVER (ORDER BY ts)")

    # Piercing line / Dark cloud cover
    if detection.get("curr_opens_below_prev_low"):
        conds.append("open < LAG(low) OVER (ORDER BY ts)")
    if detection.get("curr_opens_above_prev_high"):
        conds.append("open > LAG(high) OVER (ORDER BY ts)")
    if detection.get("curr_closes_above_prev_midpoint"):
        conds.append(
            "close > (LAG(open) OVER (ORDER BY ts) + LAG(close) OVER (ORDER BY ts)) / 2"
        )
    if detection.get("curr_closes_below_prev_midpoint"):
        conds.append(
            "close < (LAG(open) OVER (ORDER BY ts) + LAG(close) OVER (ORDER BY ts)) / 2"
        )

    # Tweezer patterns
    if detection.get("highs_match"):
        tolerance = detection.get("tolerance", 0.001)
        conds.append(
            f"ABS(high - LAG(high) OVER (ORDER BY ts)) / NULLIF(high, 0) < {tolerance}"
        )
    if detection.get("lows_match"):
        tolerance = detection.get("tolerance", 0.001)
        conds.append(
            f"ABS(low - LAG(low) OVER (ORDER BY ts)) / NULLIF(low, 0) < {tolerance}"
        )

    return conds


def _three_candle_conditions(detection: dict) -> list[str]:
    """Build conditions for three-candle pattern (uses LAG with offset)."""
    conds = []

    # First candle (2 bars ago)
    if detection.get("first_red"):
        conds.append("LAG(close, 2) OVER (ORDER BY ts) < LAG(open, 2) OVER (ORDER BY ts)")
    if detection.get("first_green"):
        conds.append("LAG(close, 2) OVER (ORDER BY ts) > LAG(open, 2) OVER (ORDER BY ts)")
    if "first_body_ratio_min" in detection:
        conds.append(
            f"ABS(LAG(close, 2) OVER (ORDER BY ts) - LAG(open, 2) OVER (ORDER BY ts)) / "
            f"NULLIF(LAG(high, 2) OVER (ORDER BY ts) - LAG(low, 2) OVER (ORDER BY ts), 0) "
            f"> {detection['first_body_ratio_min']}"
        )

    # Second candle (1 bar ago) - small body
    if "second_body_ratio_max" in detection:
        conds.append(
            f"ABS(LAG(close, 1) OVER (ORDER BY ts) - LAG(open, 1) OVER (ORDER BY ts)) / "
            f"NULLIF(LAG(high, 1) OVER (ORDER BY ts) - LAG(low, 1) OVER (ORDER BY ts), 0) "
            f"< {detection['second_body_ratio_max']}"
        )

    # Third candle (current)
    if detection.get("third_red"):
        conds.append("close < open")
    if detection.get("third_green"):
        conds.append("close > open")

    # Third closes above/below first's midpoint
    if detection.get("third_closes_above_first_midpoint"):
        conds.append(
            "close > (LAG(open, 2) OVER (ORDER BY ts) + LAG(close, 2) OVER (ORDER BY ts)) / 2"
        )
    if detection.get("third_closes_below_first_midpoint"):
        conds.append(
            "close < (LAG(open, 2) OVER (ORDER BY ts) + LAG(close, 2) OVER (ORDER BY ts)) / 2"
        )

    # Three white soldiers / three black crows
    if detection.get("all_green"):
        conds.append("close > open")
        conds.append("LAG(close, 1) OVER (ORDER BY ts) > LAG(open, 1) OVER (ORDER BY ts)")
        conds.append("LAG(close, 2) OVER (ORDER BY ts) > LAG(open, 2) OVER (ORDER BY ts)")
    if detection.get("all_red"):
        conds.append("close < open")
        conds.append("LAG(close, 1) OVER (ORDER BY ts) < LAG(open, 1) OVER (ORDER BY ts)")
        conds.append("LAG(close, 2) OVER (ORDER BY ts) < LAG(open, 2) OVER (ORDER BY ts)")

    if detection.get("each_closes_higher"):
        conds.append("close > LAG(close, 1) OVER (ORDER BY ts)")
        conds.append("LAG(close, 1) OVER (ORDER BY ts) > LAG(close, 2) OVER (ORDER BY ts)")
    if detection.get("each_closes_lower"):
        conds.append("close < LAG(close, 1) OVER (ORDER BY ts)")
        conds.append("LAG(close, 1) OVER (ORDER BY ts) < LAG(close, 2) OVER (ORDER BY ts)")

    return conds


# =============================================================================
# PRICE PATTERN EXPRESSIONS
# =============================================================================


def _build_price_expr(pattern: dict) -> str:
    """Build SQL expression for price pattern."""
    detection = pattern.get("detection", {})
    conds = []

    # Inside bar
    if detection.get("high_below_prev_high") and detection.get("low_above_prev_low"):
        conds.append("high < LAG(high) OVER (ORDER BY ts)")
        conds.append("low > LAG(low) OVER (ORDER BY ts)")

    # Outside bar
    if detection.get("high_above_prev_high") and detection.get("low_below_prev_low"):
        conds.append("high > LAG(high) OVER (ORDER BY ts)")
        conds.append("low < LAG(low) OVER (ORDER BY ts)")

    # Simple high/low comparisons
    if detection.get("high_above_prev_high") and not detection.get("low_below_prev_low"):
        conds.append("high > LAG(high) OVER (ORDER BY ts)")
    if detection.get("low_below_prev_low") and not detection.get("high_above_prev_high"):
        conds.append("low < LAG(low) OVER (ORDER BY ts)")
    if detection.get("high_below_prev_high") and not detection.get("low_above_prev_low"):
        conds.append("high < LAG(high) OVER (ORDER BY ts)")
    if detection.get("low_above_prev_low") and not detection.get("high_below_prev_high"):
        conds.append("low > LAG(low) OVER (ORDER BY ts)")

    # Narrow range (NR4, NR7)
    if "smallest_range_in_n" in detection:
        n = detection["smallest_range_in_n"]
        # This is complex - would need window function with MIN over last N
        # Simplified: just check if range is small
        conds.append(
            f"(high - low) < MIN(high - low) OVER (ORDER BY ts ROWS BETWEEN {n-1} PRECEDING AND 1 PRECEDING)"
        )

    # Breakout patterns with lookback
    if detection.get("high_above_n_period_high"):
        lookback = detection.get("default_lookback", 20)
        conds.append(
            f"high > MAX(high) OVER (ORDER BY ts ROWS BETWEEN {lookback} PRECEDING AND 1 PRECEDING)"
        )
    if detection.get("low_below_n_period_low"):
        lookback = detection.get("default_lookback", 20)
        conds.append(
            f"low < MIN(low) OVER (ORDER BY ts ROWS BETWEEN {lookback} PRECEDING AND 1 PRECEDING)"
        )

    if not conds:
        return "0"

    return f"CASE WHEN {' AND '.join(conds)} THEN 1 ELSE 0 END"
