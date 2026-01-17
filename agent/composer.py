"""
Composer — converts Parser entities to QuerySpec.

This is CODE, not LLM. Deterministic business logic.

Flow:
    Parser (LLM) → entities dict
    Composer (code) → QuerySpec or clarification/concept/greeting/not_supported
    QueryBuilder (code) → SQL
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from agent.query_builder.types import (
    QuerySpec,
    Source,
    Filters,
    Grouping,
    Condition,
    Metric,
    MetricSpec,
    SpecialOp,
    EventTimeSpec,
    TopNSpec,
    CompareSpec,
)


# =============================================================================
# Composer Output Types (non-query)
# =============================================================================

@dataclass
class QueryWithSummary:
    """Ready to execute query with human-readable summary."""
    type: str  # "query"
    summary: str
    spec: QuerySpec


@dataclass
class ClarificationResult:
    """Need user clarification."""
    type: str  # "clarification"
    summary: str
    field: str
    options: list[str]


@dataclass
class ConceptResult:
    """Explain a concept."""
    type: str  # "concept"
    summary: str
    concept: str


@dataclass
class GreetingResult:
    """Greeting response."""
    type: str  # "greeting"
    summary: str


@dataclass
class NotSupportedResult:
    """Query not supported yet."""
    type: str  # "not_supported"
    summary: str
    reason: str


# Union type for return
ComposerResult = QueryWithSummary | ClarificationResult | ConceptResult | GreetingResult | NotSupportedResult


# =============================================================================
# Composer Logic
# =============================================================================

def compose(parsed: dict, symbol: str = "NQ") -> ComposerResult:
    """
    Convert parsed entities to QuerySpec or clarification.

    Args:
        parsed: Output from Parser
        symbol: Trading instrument

    Returns:
        ComposerResult subclass
    """
    what = parsed.get("what", "")
    summary = parsed.get("summary", "")

    # --- Greeting ---
    if what == "greeting":
        return GreetingResult(type="greeting", summary=summary)

    # --- Concept explanation ---
    if what.startswith("explain"):
        concept = what.replace("explain ", "").replace("explain", "").strip()
        return ConceptResult(type="concept", summary=summary, concept=concept or "trading")

    # --- Check for unclear fields ---
    unclear = parsed.get("unclear", [])
    if unclear:
        return _handle_unclear(parsed, unclear, summary, symbol)

    # --- Data query ---
    return _build_query(parsed, summary, symbol)


def _handle_unclear(
    parsed: dict,
    unclear: list,
    summary: str,
    symbol: str
) -> ClarificationResult:
    """Handle queries with unclear fields."""
    from agent.domain.defaults import get_trading_day_options

    # Year clarification for date without year
    if "year" in unclear:
        period = parsed.get("period") or {}
        raw_date = period.get("raw", "this date")
        options = [
            f"Show all {raw_date}s (all years)",
            "I'll specify the year",
        ]
        return ClarificationResult(
            type="clarification",
            summary=summary,
            field="year",
            options=options,
        )

    # Session clarification for specific date
    if "session" in unclear:
        date_str = _extract_date(parsed)
        options = get_trading_day_options(symbol, date_str)
        return ClarificationResult(
            type="clarification",
            summary=summary,
            field="session",
            options=options,
        )

    # Generic unclear
    return ClarificationResult(
        type="clarification",
        summary=summary,
        field=unclear[0] if unclear else "unknown",
        options=[],
    )


def _build_query(parsed: dict, summary: str, symbol: str) -> ComposerResult:
    """Build QuerySpec from parsed entities."""
    what = parsed.get("what", "")
    period = parsed.get("period") or {}
    filters_raw = parsed.get("filters") or {}
    modifiers = parsed.get("modifiers") or {}

    # --- Check if supported first ---
    not_supported = _check_not_supported(what, filters_raw, modifiers)
    if not_supported:
        return NotSupportedResult(type="not_supported", summary=summary, reason=not_supported)

    # --- Check for special ops (needed for source determination) ---
    special_op, op_specs = _determine_special_op(what, modifiers)

    # --- Determine source ---
    session = filters_raw.get("session")
    specific_dates = period.get("dates")  # e.g., ["2024-05-16"]
    needs_prev_day = _needs_prev_day(what, filters_raw)

    if special_op == SpecialOp.EVENT_TIME:
        # EVENT_TIME requires minute data
        source = Source.MINUTES
    elif session and specific_dates:
        # Specific date + session → aggregate to daily OHLC for that session
        # Example: "What happened May 16 RTH?" → one row with RTH OHLC
        source = Source.DAILY
    elif session and special_op == SpecialOp.TOP_N:
        # TOP_N + session → aggregate by days with session filter
        # Example: "Top 10 volatile RTH days" → daily OHLC for RTH, sorted by range
        source = Source.DAILY
    elif session:
        # Session without specific date → need minute data for filtering
        source = Source.MINUTES
    elif needs_prev_day:
        source = Source.DAILY_WITH_PREV
    else:
        source = Source.DAILY

    # --- Build filters ---
    filters = _build_filters(period, filters_raw, symbol)

    # --- Determine grouping ---
    grouping = _determine_grouping(what, modifiers, period, session)

    # --- Determine metrics ---
    metrics = _determine_metrics(what, modifiers)

    # --- Build QuerySpec ---
    spec = QuerySpec(
        symbol=symbol,
        source=source,
        filters=filters,
        grouping=grouping,
        metrics=metrics,
        special_op=special_op,
        event_time_spec=op_specs.get("event_time"),
        top_n_spec=op_specs.get("top_n"),
        compare_spec=op_specs.get("compare"),
    )

    return QueryWithSummary(
        type="query",
        summary=summary,
        spec=spec,
    )


# =============================================================================
# Helper Functions
# =============================================================================

def _extract_date(parsed: dict) -> str:
    """Extract date from parsed period."""
    period = parsed.get("period") or {}
    if period.get("dates"):
        return period["dates"][0]
    if period.get("start"):
        return period["start"]
    return ""


def _needs_prev_day(what: str, filters_raw: dict) -> bool:
    """Check if query needs previous day data (for gap analysis)."""
    conditions = filters_raw.get("conditions") or []
    conditions_str = " ".join(conditions).lower()

    return (
        "gap" in what.lower() or
        "gap" in conditions_str or
        "prev" in conditions_str
    )


def _build_filters(period: dict, filters_raw: dict, symbol: str) -> Filters:
    """Build Filters object from parsed data."""
    from agent.modules.sql import get_data_range

    # Period
    period_start = period.get("start")
    period_end = period.get("end")

    # If no period, use full data range
    if not period_start or not period_end:
        data_range = get_data_range(symbol)
        if data_range:
            period_start = period_start or data_range["start_date"]
            period_end = period_end or data_range["end_date"]
        else:
            period_start = period_start or "2008-01-01"
            period_end = period_end or datetime.now().strftime("%Y-%m-%d")

    # Convert inclusive end to exclusive (half-open interval)
    # Parser returns inclusive end, QueryBuilder expects exclusive
    if period_end and not period.get("dates"):
        from datetime import datetime, timedelta
        try:
            end_dt = datetime.strptime(period_end, "%Y-%m-%d")
            period_end = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Specific dates
    specific_dates = period.get("dates")

    # Calendar filters
    weekdays = filters_raw.get("weekdays")
    months = filters_raw.get("months")

    # Session
    session = filters_raw.get("session")

    # Conditions (parse from raw text)
    conditions = _parse_conditions(filters_raw.get("conditions") or [])

    return Filters(
        period_start=period_start,
        period_end=period_end,
        specific_dates=specific_dates,
        weekdays=weekdays,
        months=months,
        session=session,
        conditions=conditions,
    )


def _parse_conditions(raw_conditions: list[str]) -> list[Condition]:
    """Parse raw condition strings to Condition objects."""
    conditions = []

    for raw in raw_conditions:
        # Try to parse common patterns
        condition = _parse_single_condition(raw)
        if condition:
            conditions.append(condition)

    return conditions


def _parse_single_condition(raw: str) -> Condition | None:
    """Parse a single condition string."""
    import re

    # Normalize
    s = raw.lower().strip()

    # Pattern: "column op value" e.g. "range > 300", "change < -2%"
    # Also handles: "close - low >= 200"
    patterns = [
        # Simple: column op value
        r"^(\w+)\s*(>=|<=|>|<|=|!=)\s*([-\d.]+)%?$",
        # Expression: expr op value (e.g., "close - low >= 200")
        r"^([\w\s\-\+\*\/]+?)\s*(>=|<=|>|<|=|!=)\s*([-\d.]+)%?$",
    ]

    for pattern in patterns:
        match = re.match(pattern, s)
        if match:
            col = match.group(1).strip()
            op = match.group(2)
            val = float(match.group(3))

            # Map column aliases
            col = _map_column(col)
            if col:
                return Condition(column=col, operator=op, value=val)

    return None


def _map_column(col: str) -> str | None:
    """Map column name to valid column."""
    col = col.lower().strip()

    # Direct mappings
    direct = {
        "range": "range",
        "change": "change_pct",
        "change_pct": "change_pct",
        "gap": "gap_pct",
        "gap_pct": "gap_pct",
        "volume": "volume",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
    }

    if col in direct:
        return direct[col]

    # Expression mappings
    expressions = {
        "close - low": "close_to_low",
        "close-low": "close_to_low",
        "high - close": "close_to_high",
        "high-close": "close_to_high",
    }

    if col in expressions:
        return expressions[col]

    return None


def _determine_grouping(
    what: str,
    modifiers: dict,
    period: dict,
    session: str | None
) -> Grouping:
    """Determine grouping based on query type."""
    # Explicit group_by from modifiers
    group_by = modifiers.get("group_by")
    if group_by:
        mapping = {
            "month": Grouping.MONTH,
            "week": Grouping.WEEK,
            "year": Grouping.YEAR,
            "weekday": Grouping.WEEKDAY,
            "day": Grouping.DAY,
            "hour": Grouping.HOUR,
        }
        return mapping.get(group_by, Grouping.NONE)

    # Compare → no grouping (handled by special_op)
    if modifiers.get("compare"):
        return Grouping.NONE

    # Statistics/aggregates → total
    what_lower = what.lower()
    if any(word in what_lower for word in ["statistic", "average", "mean", "volatility"]):
        return Grouping.TOTAL

    # Single day with session → total (aggregate session)
    if session and period.get("dates"):
        return Grouping.TOTAL

    # List of days → none
    if "days" in what_lower or "day" in what_lower:
        return Grouping.NONE

    # Time-based queries
    if "time" in what_lower or "when" in what_lower:
        return Grouping.HOUR

    return Grouping.NONE


def _determine_metrics(what: str, modifiers: dict) -> list[MetricSpec]:
    """Determine which metrics to include."""
    what_lower = what.lower()

    # Default OHLC metrics
    base_metrics = [
        MetricSpec(Metric.OPEN, alias="open"),
        MetricSpec(Metric.HIGH, alias="high"),
        MetricSpec(Metric.LOW, alias="low"),
        MetricSpec(Metric.CLOSE, alias="close"),
    ]

    # Statistics (works for both English "statistic" and Russian via what field)
    if any(word in what_lower for word in ["statistic", "average", "volatility", "статистик"]):
        return [
            MetricSpec(Metric.AVG, column="range", alias="avg_range"),
            MetricSpec(Metric.AVG, column="change_pct", alias="avg_change"),
            MetricSpec(Metric.STDDEV, column="change_pct", alias="volatility"),
            MetricSpec(Metric.COUNT, alias="count"),
        ]

    # Count
    if "count" in what_lower or "how many" in what_lower:
        return [MetricSpec(Metric.COUNT, alias="count")]

    # Win rate / percentage (not fully supported yet)
    if "win rate" in what_lower or "percent" in what_lower:
        return [
            MetricSpec(Metric.COUNT, alias="total"),
            MetricSpec(Metric.AVG, column="change_pct", alias="avg_change"),
        ]

    # Correlation (not supported yet, but return something)
    if "correlation" in what_lower:
        return [
            MetricSpec(Metric.AVG, column="gap_pct", alias="avg_gap"),
            MetricSpec(Metric.AVG, column="range", alias="avg_range"),
        ]

    # Add range to base
    base_metrics.append(MetricSpec(Metric.RANGE, alias="range"))

    return base_metrics


def _determine_special_op(what: str, modifiers: dict) -> tuple[SpecialOp, dict]:
    """Determine special operation and return typed specs."""
    what_lower = what.lower()
    specs: dict = {}

    # Compare
    if modifiers.get("compare"):
        specs["compare"] = CompareSpec(items=modifiers["compare"])
        return SpecialOp.COMPARE, specs

    # Top N
    if modifiers.get("top_n"):
        order_by = "range"  # default
        direction = "DESC"  # default: biggest first

        if "gap" in what_lower:
            order_by = "gap_pct"
            # gap down = negative, gap up = positive
            if "down" in what_lower:
                direction = "ASC"
        elif "drop" in what_lower or "decline" in what_lower or "worst" in what_lower:
            order_by = "change_pct"
            direction = "ASC"  # drops are negative, so ASC for biggest drops
        elif "change" in what_lower or "gain" in what_lower or "growth" in what_lower:
            order_by = "change_pct"
            direction = "DESC"  # gains are positive

        specs["top_n"] = TopNSpec(
            n=modifiers["top_n"],
            order_by=order_by,
            direction=direction,
        )
        return SpecialOp.TOP_N, specs

    # Event time (when is high/low usually)
    if "time of" in what_lower or "when" in what_lower:
        find = "high"
        if "low" in what_lower:
            find = "low"
        specs["event_time"] = EventTimeSpec(find=find)
        return SpecialOp.EVENT_TIME, specs

    return SpecialOp.NONE, specs


def _check_not_supported(what: str, filters_raw: dict, _modifiers: dict) -> str | None:
    """Check if query is not supported yet."""
    what_lower = what.lower()
    conditions = " ".join(filters_raw.get("conditions") or []).lower()

    # Chain queries (next day after X, day after Y)
    if any(phrase in what_lower for phrase in ["next day", "following day", "day after", "after a"]):
        return "Chain queries ('next day after X') not supported yet"

    # Streak detection (3+ days in a row)
    if "in a row" in conditions or "streak" in conditions or "подряд" in conditions:
        return "Streak detection ('N days in a row') not supported yet"

    # Correlation
    if "correlation" in what_lower:
        return "Correlation analysis not supported yet"

    # Win rate (backtest)
    if "win rate" in what_lower:
        return "Strategy backtesting not supported yet"

    # Option expiration
    if "expiration" in conditions or "экспирац" in conditions:
        return "Option expiration calendar not available"

    return None
