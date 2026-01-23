"""
Pattern scanner — detects candle patterns on OHLC data.

Uses vectorized numpy operations for speed.
Pattern definitions from config/patterns/candle.py — single source of truth.

Usage:
    rows = scan_patterns(rows)  # list[dict] → list[dict] with is_* flags
    df = scan_patterns_df(df)   # DataFrame → DataFrame with is_* columns
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from agent.config.patterns.candle import CANDLE_PATTERNS, list_candle_patterns
from agent.config.patterns.price import PRICE_PATTERNS, list_price_patterns


# =============================================================================
# STATELESS PATTERN DETECTION
# =============================================================================

def _prepare_arrays(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """Prepare numpy arrays for pattern detection.

    Args:
        df: DataFrame with open, high, low, close columns

    Returns:
        Dict with all computed arrays needed for pattern detection
    """
    n = len(df)
    if n == 0:
        return {"n": 0}

    # Current bar OHLC
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)

    # Computed values for current bar
    range_ = h - l
    body = np.abs(c - o)
    upper_shadow = h - np.maximum(c, o)
    lower_shadow = np.minimum(c, o) - l
    is_green = c > o
    is_red = c < o

    # Ratios (avoid division by zero)
    safe_range = np.where(range_ > 0, range_, 1)
    body_ratio = body / safe_range
    upper_shadow_ratio = upper_shadow / safe_range
    lower_shadow_ratio = lower_shadow / safe_range

    # Previous bar (lag 1)
    prev_o = np.roll(o, 1)
    prev_h = np.roll(h, 1)
    prev_l = np.roll(l, 1)
    prev_c = np.roll(c, 1)
    prev_o[0] = o[0]
    prev_h[0] = h[0]
    prev_l[0] = l[0]
    prev_c[0] = c[0]

    prev_body = np.abs(prev_c - prev_o)
    prev_is_green = prev_c > prev_o
    prev_is_red = prev_c < prev_o
    prev_range = prev_h - prev_l
    safe_prev_range = np.where(prev_range > 0, prev_range, 1)
    prev_body_ratio = prev_body / safe_prev_range

    # Bar 2 ago (for 3-candle patterns)
    prev2_o = np.roll(o, 2)
    prev2_h = np.roll(h, 2)
    prev2_l = np.roll(l, 2)
    prev2_c = np.roll(c, 2)
    prev2_o[:2] = o[:2]
    prev2_h[:2] = h[:2]
    prev2_l[:2] = l[:2]
    prev2_c[:2] = c[:2]

    prev2_body = np.abs(prev2_c - prev2_o)
    prev2_is_green = prev2_c > prev2_o
    prev2_is_red = prev2_c < prev2_o
    prev2_range = prev2_h - prev2_l
    safe_prev2_range = np.where(prev2_range > 0, prev2_range, 1)
    prev2_body_ratio = prev2_body / safe_prev2_range

    return {
        "n": n,
        # Current bar
        "o": o, "h": h, "l": l, "c": c,
        "range": range_, "body": body,
        "upper_shadow": upper_shadow, "lower_shadow": lower_shadow,
        "is_green": is_green, "is_red": is_red,
        "body_ratio": body_ratio,
        "upper_shadow_ratio": upper_shadow_ratio,
        "lower_shadow_ratio": lower_shadow_ratio,
        # Previous bar
        "prev_o": prev_o, "prev_h": prev_h, "prev_l": prev_l, "prev_c": prev_c,
        "prev_body": prev_body, "prev_is_green": prev_is_green, "prev_is_red": prev_is_red,
        "prev_range": prev_range, "prev_body_ratio": prev_body_ratio,
        # Bar 2 ago
        "prev2_o": prev2_o, "prev2_h": prev2_h, "prev2_l": prev2_l, "prev2_c": prev2_c,
        "prev2_body": prev2_body, "prev2_is_green": prev2_is_green, "prev2_is_red": prev2_is_red,
        "prev2_range": prev2_range, "prev2_body_ratio": prev2_body_ratio,
    }


def _detect(arrays: dict[str, np.ndarray], detection: dict, candles: int = 1) -> np.ndarray:
    """Detect pattern based on config rules.

    Args:
        arrays: Dict of numpy arrays from _prepare_arrays()
        detection: Dict of detection rules from config
        candles: Number of candles in pattern (1, 2, or 3)

    Returns:
        Boolean numpy array (True where pattern detected)
    """
    n = arrays["n"]
    if n == 0:
        return np.array([], dtype=bool)

    # Start with all True, then AND conditions
    mask = np.ones(n, dtype=bool)

    # Range must be positive for meaningful patterns
    mask &= arrays["range"] > 0

    # === SINGLE CANDLE CONDITIONS ===

    if "body_ratio_max" in detection:
        mask &= arrays["body_ratio"] < detection["body_ratio_max"]

    if "body_ratio_min" in detection:
        mask &= arrays["body_ratio"] > detection["body_ratio_min"]

    if "lower_shadow_ratio_min" in detection:
        mask &= arrays["lower_shadow_ratio"] > detection["lower_shadow_ratio_min"]

    if "lower_shadow_ratio_max" in detection:
        mask &= arrays["lower_shadow_ratio"] < detection["lower_shadow_ratio_max"]

    if "upper_shadow_ratio_min" in detection:
        mask &= arrays["upper_shadow_ratio"] > detection["upper_shadow_ratio_min"]

    if "upper_shadow_ratio_max" in detection:
        mask &= arrays["upper_shadow_ratio"] < detection["upper_shadow_ratio_max"]

    if detection.get("is_green"):
        mask &= arrays["is_green"]

    if detection.get("is_red"):
        mask &= arrays["is_red"]

    # === TWO CANDLE CONDITIONS ===

    if detection.get("prev_red"):
        mask &= arrays["prev_is_red"]

    if detection.get("prev_green"):
        mask &= arrays["prev_is_green"]

    if detection.get("curr_red"):
        mask &= arrays["is_red"]

    if detection.get("curr_green"):
        mask &= arrays["is_green"]

    if detection.get("curr_body_engulfs_prev"):
        o, c = arrays["o"], arrays["c"]
        prev_o, prev_c = arrays["prev_o"], arrays["prev_c"]
        mask &= (o <= prev_c) & (c >= prev_o) | (o >= prev_c) & (c <= prev_o)

    if detection.get("curr_opens_below_prev_low"):
        mask &= arrays["o"] < arrays["prev_l"]

    if detection.get("curr_opens_above_prev_high"):
        mask &= arrays["o"] > arrays["prev_h"]

    if detection.get("curr_closes_above_prev_midpoint"):
        prev_mid = (arrays["prev_o"] + arrays["prev_c"]) / 2
        mask &= arrays["c"] > prev_mid

    if detection.get("curr_closes_below_prev_midpoint"):
        prev_mid = (arrays["prev_o"] + arrays["prev_c"]) / 2
        mask &= arrays["c"] < prev_mid

    if detection.get("highs_match"):
        tolerance = detection.get("tolerance", 0.001)
        h = arrays["h"]
        mask &= np.abs(h - arrays["prev_h"]) / np.where(h > 0, h, 1) < tolerance

    if detection.get("lows_match"):
        tolerance = detection.get("tolerance", 0.001)
        l = arrays["l"]
        mask &= np.abs(l - arrays["prev_l"]) / np.where(l > 0, l, 1) < tolerance

    # === THREE CANDLE CONDITIONS ===

    if detection.get("first_red"):
        mask &= arrays["prev2_is_red"]

    if detection.get("first_green"):
        mask &= arrays["prev2_is_green"]

    if "first_body_ratio_min" in detection:
        mask &= arrays["prev2_body_ratio"] > detection["first_body_ratio_min"]

    if "second_body_ratio_max" in detection:
        mask &= arrays["prev_body_ratio"] < detection["second_body_ratio_max"]

    if detection.get("third_red"):
        mask &= arrays["is_red"]

    if detection.get("third_green"):
        mask &= arrays["is_green"]

    if detection.get("third_closes_above_first_midpoint"):
        first_mid = (arrays["prev2_o"] + arrays["prev2_c"]) / 2
        mask &= arrays["c"] > first_mid

    if detection.get("third_closes_below_first_midpoint"):
        first_mid = (arrays["prev2_o"] + arrays["prev2_c"]) / 2
        mask &= arrays["c"] < first_mid

    if detection.get("all_green"):
        mask &= arrays["is_green"] & arrays["prev_is_green"] & arrays["prev2_is_green"]

    if detection.get("all_red"):
        mask &= arrays["is_red"] & arrays["prev_is_red"] & arrays["prev2_is_red"]

    if detection.get("each_closes_higher"):
        mask &= (arrays["c"] > arrays["prev_c"]) & (arrays["prev_c"] > arrays["prev2_c"])

    if detection.get("each_closes_lower"):
        mask &= (arrays["c"] < arrays["prev_c"]) & (arrays["prev_c"] < arrays["prev2_c"])

    # === PRICE PATTERN CONDITIONS ===

    if detection.get("high_below_prev_high") and detection.get("low_above_prev_low"):
        mask &= (arrays["h"] < arrays["prev_h"]) & (arrays["l"] > arrays["prev_l"])

    if detection.get("high_above_prev_high") and detection.get("low_below_prev_low"):
        mask &= (arrays["h"] > arrays["prev_h"]) & (arrays["l"] < arrays["prev_l"])

    # First row(s) can't have valid multi-candle patterns
    if candles >= 2 and n > 0:
        mask[0] = False
    if candles >= 3 and n > 1:
        mask[1] = False

    return mask


# =============================================================================
# MAIN SCANNER
# =============================================================================

def scan_patterns_df(df: pd.DataFrame) -> pd.DataFrame:
    """Scan DataFrame for patterns, add is_* columns.

    Reads pattern definitions from config — single source of truth.

    Args:
        df: DataFrame with open, high, low, close columns

    Returns:
        DataFrame with added pattern flag columns
    """
    if df.empty:
        return df

    # Check required columns exist
    required = {"open", "high", "low", "close"}
    if not required.issubset(df.columns):
        return df

    # Make copy to avoid modifying original
    result = df.copy()

    # Prepare arrays once (stateless)
    arrays = _prepare_arrays(df)

    # Scan candle patterns from config
    for name in list_candle_patterns():
        config = CANDLE_PATTERNS[name]
        detection = config.get("detection", {})
        candles = config.get("candles", 1)

        mask = _detect(arrays, detection, candles)
        result[f"is_{name}"] = mask.astype(int)

    # Scan price patterns from config
    for name in list_price_patterns():
        config = PRICE_PATTERNS[name]
        detection = config.get("detection", {})

        mask = _detect(arrays, detection, candles=2)
        result[f"is_{name}"] = mask.astype(int)

    return result


def scan_patterns(rows: list[dict]) -> list[dict]:
    """Scan rows for patterns, add is_* fields.

    Reads pattern definitions from config — single source of truth.

    Args:
        rows: List of dicts with open, high, low, close keys

    Returns:
        List of dicts with added pattern flag fields
    """
    if not rows:
        return rows

    # Convert to DataFrame, scan, convert back
    df = pd.DataFrame(rows)

    # Check required columns exist
    required = {"open", "high", "low", "close"}
    if not required.issubset(df.columns):
        return rows

    result_df = scan_patterns_df(df)

    return result_df.to_dict("records")


def get_pattern_counts(rows: list[dict]) -> dict[str, int]:
    """Count patterns in rows.

    Args:
        rows: List of dicts with is_* pattern flags

    Returns:
        Dict of pattern_name -> count (only non-zero)
    """
    if not rows:
        return {}

    counts = {}
    pattern_cols = [k for k in rows[0].keys() if k.startswith("is_")]

    for col in pattern_cols:
        count = sum(1 for row in rows if row.get(col) == 1)
        if count > 0:
            counts[col] = count

    return counts


def list_supported_patterns() -> list[str]:
    """List all pattern names supported by scanner (from config)."""
    candle = [f"is_{name}" for name in list_candle_patterns()]
    price = [f"is_{name}" for name in list_price_patterns()]
    return candle + price


# Legacy alias for backward compatibility
PatternDetector = None  # Class removed - use stateless functions
