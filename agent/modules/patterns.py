"""
Pattern search module - finds complex patterns in trading data.

LLM decides WHAT pattern to search for (parses into PatternDef).
This module executes HOW to search efficiently in code.

No LLM here. Pure Python + SQL.
"""

import duckdb
import numpy as np
from typing import Any, Callable

import config


def _convert_numpy_types(data: list[dict]) -> list[dict]:
    """Convert numpy types to Python native types for JSON serialization."""
    def convert_value(v):
        if isinstance(v, (np.integer, np.int64, np.int32)):
            return int(v)
        elif isinstance(v, (np.floating, np.float64, np.float32)):
            return float(v)
        elif isinstance(v, np.ndarray):
            return v.tolist()
        elif isinstance(v, np.bool_):
            return bool(v)
        return v

    return [
        {k: convert_value(v) for k, v in row.items()}
        for row in data
    ]


# =============================================================================
# Pattern Functions
# =============================================================================

def find_consecutive_days(
    df,
    direction: str = "down",
    min_days: int = 3,
    min_change_pct: float | None = None,
    **kwargs
) -> list[dict]:
    """
    Find sequences of N consecutive days moving in same direction.

    Params:
        direction: "up" or "down"
        min_days: minimum consecutive days (default 3)
        min_change_pct: optional minimum change per day

    Returns:
        List of sequences with start_date, end_date, total_change_pct, days
    """
    if df.empty:
        return []

    results = []
    streak_start = None
    streak_days = 0
    streak_change = 0

    for i, row in df.iterrows():
        change = row['change_pct']
        is_match = (
            (direction == "down" and change < 0) or
            (direction == "up" and change > 0)
        )

        # Check min_change_pct if specified
        if is_match and min_change_pct is not None:
            is_match = abs(change) >= min_change_pct

        if is_match:
            if streak_start is None:
                streak_start = row['date']
                streak_days = 1
                streak_change = change
            else:
                streak_days += 1
                streak_change += change
        else:
            # End of streak
            if streak_days >= min_days:
                results.append({
                    "start_date": streak_start,
                    "end_date": df.iloc[i-1]['date'] if i > 0 else streak_start,
                    "days": streak_days,
                    "total_change_pct": round(streak_change, 2),
                    "direction": direction,
                })
            streak_start = None
            streak_days = 0
            streak_change = 0

    # Don't forget last streak
    if streak_days >= min_days:
        results.append({
            "start_date": streak_start,
            "end_date": df.iloc[-1]['date'],
            "days": streak_days,
            "total_change_pct": round(streak_change, 2),
            "direction": direction,
        })

    return results


def find_big_moves(
    df,
    threshold_pct: float = 2.0,
    direction: str | None = None,
    **kwargs
) -> list[dict]:
    """
    Find days with large price movements.

    Params:
        threshold_pct: minimum absolute change (default 2%)
        direction: "up", "down", or None for both

    Returns:
        List of days with date, change_pct, open, close, volume
    """
    if df.empty:
        return []

    results = []
    for _, row in df.iterrows():
        change = row['change_pct']
        abs_change = abs(change)

        if abs_change >= threshold_pct:
            if direction is None or \
               (direction == "up" and change > 0) or \
               (direction == "down" and change < 0):
                results.append({
                    "date": row['date'],
                    "change_pct": round(change, 2),
                    "open": row['open'],
                    "close": row['close'],
                    "high": row['high'],
                    "low": row['low'],
                    "volume": row['volume'],
                })

    return results


def find_reversals(
    df,
    trend_days: int = 3,
    reversal_threshold_pct: float = 1.0,
    **kwargs
) -> list[dict]:
    """
    Find reversal days after a trend.

    Params:
        trend_days: number of days in trend before reversal (default 3)
        reversal_threshold_pct: minimum reversal move (default 1%)

    Returns:
        List of reversal days with trend info
    """
    if df.empty or len(df) < trend_days + 1:
        return []

    results = []

    for i in range(trend_days, len(df)):
        # Check if previous N days were trending
        prev_days = df.iloc[i-trend_days:i]
        current = df.iloc[i]

        # Calculate trend direction
        trend_changes = prev_days['change_pct'].tolist()
        all_up = all(c > 0 for c in trend_changes)
        all_down = all(c < 0 for c in trend_changes)

        if not (all_up or all_down):
            continue

        trend_direction = "up" if all_up else "down"
        current_change = current['change_pct']

        # Check for reversal
        is_reversal = (
            (trend_direction == "up" and current_change < -reversal_threshold_pct) or
            (trend_direction == "down" and current_change > reversal_threshold_pct)
        )

        if is_reversal:
            results.append({
                "date": current['date'],
                "reversal_change_pct": round(current_change, 2),
                "prior_trend": trend_direction,
                "prior_trend_days": trend_days,
                "prior_trend_total_pct": round(sum(trend_changes), 2),
                "open": current['open'],
                "close": current['close'],
            })

    return results


def find_gaps(
    df,
    min_gap_pct: float = 0.5,
    direction: str | None = None,
    **kwargs
) -> list[dict]:
    """
    Find gap opens (price jumps between close and next open).

    Params:
        min_gap_pct: minimum gap size (default 0.5%)
        direction: "up", "down", or None for both

    Returns:
        List of gap days
    """
    if df.empty or len(df) < 2:
        return []

    results = []

    for i in range(1, len(df)):
        prev = df.iloc[i-1]
        curr = df.iloc[i]

        gap_pct = (curr['open'] - prev['close']) / prev['close'] * 100

        if abs(gap_pct) >= min_gap_pct:
            gap_dir = "up" if gap_pct > 0 else "down"

            if direction is None or direction == gap_dir:
                results.append({
                    "date": curr['date'],
                    "gap_pct": round(gap_pct, 2),
                    "direction": gap_dir,
                    "prev_close": prev['close'],
                    "open": curr['open'],
                    "close": curr['close'],
                    "filled": curr['low'] <= prev['close'] if gap_dir == "up" else curr['high'] >= prev['close'],
                })

    return results


def find_range_breakouts(
    df,
    lookback_days: int = 20,
    **kwargs
) -> list[dict]:
    """
    Find days that broke out of recent range.

    Params:
        lookback_days: days to look back for range (default 20)

    Returns:
        List of breakout days
    """
    if df.empty or len(df) < lookback_days + 1:
        return []

    results = []

    for i in range(lookback_days, len(df)):
        # Calculate range from lookback period
        lookback = df.iloc[i-lookback_days:i]
        range_high = lookback['high'].max()
        range_low = lookback['low'].min()

        curr = df.iloc[i]

        # Check for breakout
        if curr['high'] > range_high:
            results.append({
                "date": curr['date'],
                "direction": "up",
                "breakout_price": curr['high'],
                "range_high": range_high,
                "range_low": range_low,
                "close": curr['close'],
                "held": curr['close'] > range_high,  # Did it close above?
            })
        elif curr['low'] < range_low:
            results.append({
                "date": curr['date'],
                "direction": "down",
                "breakout_price": curr['low'],
                "range_high": range_high,
                "range_low": range_low,
                "close": curr['close'],
                "held": curr['close'] < range_low,  # Did it close below?
            })

    return results


# =============================================================================
# Pattern Registry
# =============================================================================

PATTERNS: dict[str, Callable] = {
    "consecutive_days": find_consecutive_days,
    "big_move": find_big_moves,
    "reversal": find_reversals,
    "gap": find_gaps,
    "range_breakout": find_range_breakouts,
}

# Pattern descriptions for Understander prompt
PATTERN_DESCRIPTIONS = {
    "consecutive_days": {
        "description": "N дней подряд в одном направлении",
        "params": {
            "direction": "up или down",
            "min_days": "минимум дней подряд (default: 3)",
            "min_change_pct": "минимальное изменение за день (опционально)",
        },
        "examples": [
            "найди когда NQ падал 3 дня подряд",
            "покажи серии из 5+ дней роста",
        ],
    },
    "big_move": {
        "description": "Дни с большим движением цены",
        "params": {
            "threshold_pct": "порог изменения в % (default: 2)",
            "direction": "up, down или любое (опционально)",
        },
        "examples": [
            "найди дни когда NQ двигался больше 3%",
            "покажи все падения больше 2%",
        ],
    },
    "reversal": {
        "description": "Развороты после тренда",
        "params": {
            "trend_days": "дней тренда перед разворотом (default: 3)",
            "reversal_threshold_pct": "минимум разворота в % (default: 1)",
        },
        "examples": [
            "найди развороты после 3 дней падения",
            "когда был разворот после роста",
        ],
    },
    "gap": {
        "description": "Гэпы на открытии",
        "params": {
            "min_gap_pct": "минимальный гэп в % (default: 0.5)",
            "direction": "up, down или любое (опционально)",
        },
        "examples": [
            "найди гэпы вверх больше 1%",
            "покажи все гэпы",
        ],
    },
    "range_breakout": {
        "description": "Пробои диапазона",
        "params": {
            "lookback_days": "период для расчёта диапазона (default: 20)",
        },
        "examples": [
            "найди пробои 20-дневного диапазона",
            "когда был breakout",
        ],
    },
}


# =============================================================================
# Main Search Function
# =============================================================================

def search(
    symbol: str,
    period_start: str,
    period_end: str,
    pattern_name: str,
    params: dict | None = None
) -> dict[str, Any]:
    """
    Search for a pattern in trading data.

    Args:
        symbol: Trading symbol (NQ, ES, etc.)
        period_start: Start date ISO format
        period_end: End date ISO format
        pattern_name: Name of pattern to search for
        params: Pattern-specific parameters

    Returns:
        {
            "pattern": "consecutive_days",
            "params": {...},
            "symbol": "NQ",
            "period_start": "2024-01-01",
            "period_end": "2024-12-31",
            "matches_count": 5,
            "matches": [{...}, {...}, ...]
        }
    """
    params = params or {}

    # Validate pattern
    pattern_fn = PATTERNS.get(pattern_name)
    if not pattern_fn:
        return {
            "error": f"Unknown pattern: {pattern_name}",
            "available_patterns": list(PATTERNS.keys()),
        }

    # First, get daily data (patterns work on daily data)
    sql = """
        SELECT
            timestamp::date as date,
            FIRST(open ORDER BY timestamp) as open,
            MAX(high) as high,
            MIN(low) as low,
            LAST(close ORDER BY timestamp) as close,
            SUM(volume) as volume,
            ROUND((LAST(close ORDER BY timestamp) - FIRST(open ORDER BY timestamp))
                  / FIRST(open ORDER BY timestamp) * 100, 2) as change_pct
        FROM ohlcv_1min
        WHERE symbol = $1
          AND timestamp >= $2
          AND timestamp < $3
        GROUP BY date
        ORDER BY date
    """

    try:
        with duckdb.connect(config.DATABASE_PATH, read_only=True) as conn:
            df = conn.execute(sql, [symbol, period_start, period_end]).df()

            # Convert date to string for JSON serialization
            df['date'] = df['date'].astype(str).str[:10]

            # Run pattern search
            matches = pattern_fn(df, **params)

            # Convert numpy types to Python native types
            matches = _convert_numpy_types(matches)

            return {
                "pattern": pattern_name,
                "params": params,
                "symbol": symbol,
                "period_start": period_start,
                "period_end": period_end,
                "total_days": len(df),
                "matches_count": len(matches),
                "matches": matches,
            }

    except Exception as e:
        return {
            "error": str(e),
            "pattern": pattern_name,
            "symbol": symbol,
        }


def get_available_patterns() -> list[str]:
    """Get list of available pattern names."""
    return list(PATTERNS.keys())


def get_pattern_info(pattern_name: str) -> dict | None:
    """Get description and params for a pattern."""
    return PATTERN_DESCRIPTIONS.get(pattern_name)
