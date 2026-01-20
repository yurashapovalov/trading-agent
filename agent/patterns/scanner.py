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
# GENERIC PATTERN DETECTOR (reads rules from config)
# =============================================================================

class PatternDetector:
    """Detects patterns based on config rules using numpy."""

    def __init__(self, df: pd.DataFrame):
        """Initialize with OHLC DataFrame."""
        self.n = len(df)
        if self.n == 0:
            return

        # Current bar OHLC
        self.o = df["open"].values.astype(float)
        self.h = df["high"].values.astype(float)
        self.l = df["low"].values.astype(float)
        self.c = df["close"].values.astype(float)

        # Computed values for current bar
        self.range = self.h - self.l
        self.body = np.abs(self.c - self.o)
        self.upper_shadow = self.h - np.maximum(self.c, self.o)
        self.lower_shadow = np.minimum(self.c, self.o) - self.l
        self.is_green = self.c > self.o
        self.is_red = self.c < self.o

        # Ratios (avoid division by zero)
        safe_range = np.where(self.range > 0, self.range, 1)
        self.body_ratio = self.body / safe_range
        self.upper_shadow_ratio = self.upper_shadow / safe_range
        self.lower_shadow_ratio = self.lower_shadow / safe_range

        # Previous bar (lag 1)
        self.prev_o = np.roll(self.o, 1)
        self.prev_h = np.roll(self.h, 1)
        self.prev_l = np.roll(self.l, 1)
        self.prev_c = np.roll(self.c, 1)
        self.prev_o[0] = self.o[0]
        self.prev_h[0] = self.h[0]
        self.prev_l[0] = self.l[0]
        self.prev_c[0] = self.c[0]

        self.prev_body = np.abs(self.prev_c - self.prev_o)
        self.prev_is_green = self.prev_c > self.prev_o
        self.prev_is_red = self.prev_c < self.prev_o
        self.prev_range = self.prev_h - self.prev_l
        safe_prev_range = np.where(self.prev_range > 0, self.prev_range, 1)
        self.prev_body_ratio = self.prev_body / safe_prev_range

        # Bar 2 ago (for 3-candle patterns)
        self.prev2_o = np.roll(self.o, 2)
        self.prev2_h = np.roll(self.h, 2)
        self.prev2_l = np.roll(self.l, 2)
        self.prev2_c = np.roll(self.c, 2)
        self.prev2_o[:2] = self.o[:2]
        self.prev2_h[:2] = self.h[:2]
        self.prev2_l[:2] = self.l[:2]
        self.prev2_c[:2] = self.c[:2]

        self.prev2_body = np.abs(self.prev2_c - self.prev2_o)
        self.prev2_is_green = self.prev2_c > self.prev2_o
        self.prev2_is_red = self.prev2_c < self.prev2_o
        self.prev2_range = self.prev2_h - self.prev2_l
        safe_prev2_range = np.where(self.prev2_range > 0, self.prev2_range, 1)
        self.prev2_body_ratio = self.prev2_body / safe_prev2_range

    def detect(self, detection: dict, candles: int = 1) -> np.ndarray:
        """Detect pattern based on config rules.

        Args:
            detection: Dict of detection rules from config
            candles: Number of candles in pattern (1, 2, or 3)

        Returns:
            Boolean numpy array (True where pattern detected)
        """
        if self.n == 0:
            return np.array([], dtype=bool)

        # Start with all True, then AND conditions
        mask = np.ones(self.n, dtype=bool)

        # Range must be positive for meaningful patterns
        mask &= self.range > 0

        # === SINGLE CANDLE CONDITIONS ===

        if "body_ratio_max" in detection:
            mask &= self.body_ratio < detection["body_ratio_max"]

        if "body_ratio_min" in detection:
            mask &= self.body_ratio > detection["body_ratio_min"]

        if "lower_shadow_ratio_min" in detection:
            mask &= self.lower_shadow_ratio > detection["lower_shadow_ratio_min"]

        if "lower_shadow_ratio_max" in detection:
            mask &= self.lower_shadow_ratio < detection["lower_shadow_ratio_max"]

        if "upper_shadow_ratio_min" in detection:
            mask &= self.upper_shadow_ratio > detection["upper_shadow_ratio_min"]

        if "upper_shadow_ratio_max" in detection:
            mask &= self.upper_shadow_ratio < detection["upper_shadow_ratio_max"]

        if detection.get("is_green"):
            mask &= self.is_green

        if detection.get("is_red"):
            mask &= self.is_red

        # === TWO CANDLE CONDITIONS ===

        if detection.get("prev_red"):
            mask &= self.prev_is_red

        if detection.get("prev_green"):
            mask &= self.prev_is_green

        if detection.get("curr_red"):
            mask &= self.is_red

        if detection.get("curr_green"):
            mask &= self.is_green

        if detection.get("curr_body_engulfs_prev"):
            # Current body engulfs previous body
            mask &= (self.o <= self.prev_c) & (self.c >= self.prev_o) | \
                    (self.o >= self.prev_c) & (self.c <= self.prev_o)

        if detection.get("curr_opens_below_prev_low"):
            mask &= self.o < self.prev_l

        if detection.get("curr_opens_above_prev_high"):
            mask &= self.o > self.prev_h

        if detection.get("curr_closes_above_prev_midpoint"):
            prev_mid = (self.prev_o + self.prev_c) / 2
            mask &= self.c > prev_mid

        if detection.get("curr_closes_below_prev_midpoint"):
            prev_mid = (self.prev_o + self.prev_c) / 2
            mask &= self.c < prev_mid

        if detection.get("highs_match"):
            tolerance = detection.get("tolerance", 0.001)
            mask &= np.abs(self.h - self.prev_h) / np.where(self.h > 0, self.h, 1) < tolerance

        if detection.get("lows_match"):
            tolerance = detection.get("tolerance", 0.001)
            mask &= np.abs(self.l - self.prev_l) / np.where(self.l > 0, self.l, 1) < tolerance

        # === THREE CANDLE CONDITIONS ===

        if detection.get("first_red"):
            mask &= self.prev2_is_red

        if detection.get("first_green"):
            mask &= self.prev2_is_green

        if "first_body_ratio_min" in detection:
            mask &= self.prev2_body_ratio > detection["first_body_ratio_min"]

        if "second_body_ratio_max" in detection:
            mask &= self.prev_body_ratio < detection["second_body_ratio_max"]

        if detection.get("third_red"):
            mask &= self.is_red

        if detection.get("third_green"):
            mask &= self.is_green

        if detection.get("third_closes_above_first_midpoint"):
            first_mid = (self.prev2_o + self.prev2_c) / 2
            mask &= self.c > first_mid

        if detection.get("third_closes_below_first_midpoint"):
            first_mid = (self.prev2_o + self.prev2_c) / 2
            mask &= self.c < first_mid

        if detection.get("all_green"):
            mask &= self.is_green & self.prev_is_green & self.prev2_is_green

        if detection.get("all_red"):
            mask &= self.is_red & self.prev_is_red & self.prev2_is_red

        if detection.get("each_closes_higher"):
            mask &= (self.c > self.prev_c) & (self.prev_c > self.prev2_c)

        if detection.get("each_closes_lower"):
            mask &= (self.c < self.prev_c) & (self.prev_c < self.prev2_c)

        # === PRICE PATTERN CONDITIONS ===

        if detection.get("high_below_prev_high") and detection.get("low_above_prev_low"):
            # Inside bar
            mask &= (self.h < self.prev_h) & (self.l > self.prev_l)

        if detection.get("high_above_prev_high") and detection.get("low_below_prev_low"):
            # Outside bar
            mask &= (self.h > self.prev_h) & (self.l < self.prev_l)

        # First row(s) can't have valid multi-candle patterns
        if candles >= 2:
            mask[0] = False
        if candles >= 3:
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

    # Initialize detector
    detector = PatternDetector(df)

    # Scan candle patterns from config
    for name in list_candle_patterns():
        config = CANDLE_PATTERNS[name]
        detection = config.get("detection", {})
        candles = config.get("candles", 1)

        mask = detector.detect(detection, candles)
        result[f"is_{name}"] = mask.astype(int)

    # Scan price patterns from config
    for name in list_price_patterns():
        config = PRICE_PATTERNS[name]
        detection = config.get("detection", {})

        mask = detector.detect(detection, candles=2)  # Price patterns need prev bar
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
