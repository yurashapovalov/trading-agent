"""Formatting utilities for user-friendly number display.

Used by Presenter to format summary values before sending to LLM.
Rules are based on key naming conventions (suffixes) in summary dicts.

Suffixes:
    _pct    → +0.2%
    _usd    → $22,500
    _pts    → 180 pts
    _volume → 15M
"""


def format_summary(summary: dict) -> dict:
    """Format all values in summary for user-friendly display.

    Rules based on key suffix:
    - '_pct' or 'probability' → '+X.X%' / '-X.X%'
    - '_usd' → '$X,XXX'
    - '_pts' → 'X pts'
    - '_volume' or 'volume' → '15M' / '1.5K'
    - 'correlation' → X.XX (coefficient, no unit)
    - other floats → round to 2 decimals
    - integers → keep as is
    """
    formatted = {}
    for key, val in summary.items():
        formatted[key] = format_value(key, val)
    return formatted


def format_value(key: str, val) -> str | int | float:
    """Format a single value based on its key suffix."""
    if val is None:
        return "N/A"

    if not isinstance(val, (int, float)):
        return val  # strings, etc — keep as is

    # Percentage: _pct or probability
    if key.endswith("_pct") or key == "probability":
        return format_pct(val)

    # USD price: _usd
    if key.endswith("_usd"):
        return format_usd(val)

    # Points: _pts
    if key.endswith("_pts"):
        return format_pts(val)

    # Volume (large numbers): _volume or volume
    if key.endswith("_volume") or key == "volume":
        return format_large_number(val)

    # Correlation (-1 to 1) — keep as coefficient
    if key == "correlation":
        return round(val, 2)

    # Regular numbers
    if isinstance(val, float):
        return round(val, 2)

    return val  # integers


def format_pct(val: float) -> str:
    """Format percentage value: 0.199 → '+0.2%', -1.5 → '-1.5%'."""
    if val is None:
        return "N/A"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.1f}%"


def format_usd(val: float | int) -> str:
    """Format USD price: 22500.5 → '$22,500', -100 → '-$100'."""
    if val is None:
        return "N/A"
    sign = "-" if val < 0 else ""
    abs_val = abs(val)
    # Round to whole dollars for large amounts, keep cents for small
    if abs_val >= 100:
        return f"{sign}${abs_val:,.0f}"
    return f"{sign}${abs_val:,.2f}"


def format_pts(val: float | int) -> str:
    """Format points: 180.5 → '180 pts', -50 → '-50 pts'."""
    if val is None:
        return "N/A"
    if isinstance(val, float) and val != int(val):
        return f"{val:.1f} pts"
    return f"{int(val)} pts"


def format_large_number(val: float | int) -> str:
    """Format large numbers: 15000000 → '15M', 1500 → '1.5K'."""
    if val is None:
        return "N/A"

    abs_val = abs(val)
    sign = "-" if val < 0 else ""

    if abs_val >= 1_000_000_000:
        return f"{sign}{abs_val / 1_000_000_000:.1f}B"
    if abs_val >= 1_000_000:
        return f"{sign}{abs_val / 1_000_000:.1f}M"
    if abs_val >= 1_000:
        return f"{sign}{abs_val / 1_000:.1f}K"

    return str(int(val)) if isinstance(val, int) else f"{val:.1f}"
