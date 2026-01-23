"""
Metrics — what user can measure.

Each metric has:
- column: DataFrame column name
- unit: display unit (%, points, contracts)
- description: what it measures
- requires: special requirements (daily data, intraday data, etc.)
- aliases: alternative names that map to this metric
"""

from typing import TypedDict


class MetricDef(TypedDict, total=False):
    column: str
    unit: str
    description: str
    requires: str | None  # "daily", "intraday", None
    aliases: list[str]
    computed: bool  # True if computed in enrich, not raw OHLCV


METRICS: dict[str, MetricDef] = {

    # =========================================================================
    # Raw OHLCV
    # =========================================================================

    "open": {
        "column": "open",
        "unit": "points",
        "description": "Opening price",
        "computed": False,
    },

    "high": {
        "column": "high",
        "unit": "points",
        "description": "Highest price",
        "computed": False,
    },

    "low": {
        "column": "low",
        "unit": "points",
        "description": "Lowest price",
        "computed": False,
    },

    "close": {
        "column": "close",
        "unit": "points",
        "description": "Closing price",
        "computed": False,
    },

    "volume": {
        "column": "volume",
        "unit": "contracts",
        "description": "Trading volume",
        "computed": False,
    },

    # =========================================================================
    # Computed (from enrich)
    # =========================================================================

    "change": {
        "column": "change",
        "unit": "%",
        "description": "Intraday return: (close - open) / open * 100",
        "computed": True,
    },

    "gap": {
        "column": "gap",
        "unit": "%",
        "description": "Overnight gap: (open - prev_close) / prev_close * 100",
        "requires": "daily",  # gap only makes sense for daily data
        "computed": True,
    },

    "range": {
        "column": "range",
        "unit": "points",
        "description": "Intraday range: high - low",
        "aliases": ["volatility"],
        "computed": True,
    },

    "volatility": {
        "column": "range",  # alias for range
        "unit": "points",
        "description": "Same as range (high - low)",
        "aliases": ["range"],
        "computed": True,
    },

    "gap_filled": {
        "column": "gap_filled",
        "unit": "bool",
        "description": "True if gap closed during the day (price returned to prev_close)",
        "requires": "daily",
        "computed": True,
    },

}


# =============================================================================
# Helpers
# =============================================================================

def get_metric(name: str) -> MetricDef | None:
    """Get metric definition by name."""
    # Direct match
    if name in METRICS:
        return METRICS[name]

    # Check aliases
    name_lower = name.lower()
    for metric_name, metric_def in METRICS.items():
        aliases = metric_def.get("aliases", [])
        if name_lower in [a.lower() for a in aliases]:
            return metric_def

    return None


def get_column(metric_name: str) -> str:
    """Get DataFrame column for metric."""
    metric = get_metric(metric_name)
    if metric:
        return metric.get("column", metric_name)
    return metric_name


def get_all_metrics() -> list[str]:
    """Get list of all metric names (excluding aliases)."""
    return list(METRICS.keys())


def get_computed_metrics() -> list[str]:
    """Get metrics that are computed in enrich()."""
    return [name for name, m in METRICS.items() if m.get("computed", False)]


def get_raw_metrics() -> list[str]:
    """Get raw OHLCV metrics."""
    return [name for name, m in METRICS.items() if not m.get("computed", False)]


def requires_daily(metric_name: str) -> bool:
    """Check if metric requires daily data."""
    metric = get_metric(metric_name)
    return metric.get("requires") == "daily" if metric else False


def requires_intraday(metric_name: str) -> bool:
    """Check if metric requires intraday data."""
    metric = get_metric(metric_name)
    return metric.get("requires") == "intraday" if metric else False
