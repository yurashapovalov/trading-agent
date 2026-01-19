"""
Composer — converts ParsedQuery to QuerySpec.

This is CODE, not LLM. Deterministic business logic.

Flow:
    Parser (LLM) → ParsedQuery (typed)
    Composer (code) → QuerySpec or clarification/concept/greeting/not_supported
    QueryBuilder (code) → SQL
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from agent.query_builder.types import (
    ParsedQuery,
    ParsedPeriod,
    ParsedFilters,
    ParsedModifiers,
    QuerySpec,
    Source,
    Filters,
    PeriodFilter,
    CalendarFilter,
    TimeFilter,
    Grouping,
    Condition,
    Metric,
    MetricSpec,
    SpecialOp,
    EventTimeSpec,
    TopNSpec,
    CompareSpec,
)
from agent.market.events import get_event_dates


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

def compose(parsed: ParsedQuery, symbol: str = "NQ") -> ComposerResult:
    """Convert ParsedQuery to QuerySpec or clarification."""

    # Chitchat: greeting, thanks, acknowledgment, etc.
    chitchat_keywords = {"greeting", "acknowledgment", "thanks", "thank you", "bye", "goodbye"}
    if parsed.what.lower() in chitchat_keywords:
        return GreetingResult(type="greeting", summary=parsed.summary)

    if parsed.what.startswith("explain"):
        concept = parsed.what.replace("explain ", "").replace("explain", "").strip()
        # If concept is generic "session" and filters has specific session, use that
        if concept == "session" and parsed.filters and parsed.filters.session:
            concept = f"{parsed.filters.session} session"
        return ConceptResult(type="concept", summary=parsed.summary, concept=concept or "trading")

    if parsed.unclear:
        return _handle_unclear(parsed, symbol)

    return _build_query(parsed, symbol)


def _handle_unclear(parsed: ParsedQuery, symbol: str) -> ClarificationResult | NotSupportedResult:
    """Handle queries with unclear fields."""
    from agent.market.instruments import get_trading_day_options

    if "year" in parsed.unclear:
        raw_date = parsed.period.raw if parsed.period else "this date"
        return ClarificationResult(
            type="clarification",
            summary=f"Which year for {raw_date}? Or say 'all years' to see all.",
            field="year",
            options=[],
        )

    if "session" in parsed.unclear:
        date_str = _extract_date(parsed)
        options = get_trading_day_options(symbol, date_str)
        return ClarificationResult(
            type="clarification",
            summary=parsed.summary,
            field="session",
            options=options,
        )

    unclear_field = parsed.unclear[0] if parsed.unclear else "your question"
    return NotSupportedResult(
        type="not_supported",
        summary=parsed.summary,
        reason=f"I don't understand what you mean by '{unclear_field}'. Could you please rephrase or be more specific?",
    )


def _build_query(parsed: ParsedQuery, symbol: str) -> ComposerResult:
    """Build QuerySpec from ParsedQuery."""
    period = parsed.period
    filters_raw = parsed.filters
    modifiers = parsed.modifiers

    not_supported = _check_not_supported(parsed.what, filters_raw, modifiers)
    if not_supported:
        return NotSupportedResult(type="not_supported", summary=parsed.summary, reason=not_supported)

    # Handle event_filter: convert to specific_dates
    event_filter = filters_raw.event_filter if filters_raw else None
    if event_filter:
        period, event_error = _resolve_event_filter(event_filter, period, symbol)
        if event_error:
            return NotSupportedResult(type="not_supported", summary=parsed.summary, reason=event_error)

    special_op, op_specs = _determine_special_op(parsed.what, modifiers)

    session = filters_raw.session if filters_raw else None
    specific_dates = period.dates if period else None
    needs_prev_day = _needs_prev_day(parsed.what, filters_raw)

    # Determine grouping FIRST — it affects source selection
    grouping = _determine_grouping(parsed.what, modifiers, period, session)

    source = _determine_source(special_op, session, specific_dates, needs_prev_day, grouping)

    # Check for excessive data volume (MINUTES + NONE grouping + long period)
    volume_issue = _check_data_volume(source, grouping, period, symbol)
    if volume_issue:
        return volume_issue

    filters = _build_filters(period, filters_raw, symbol)
    metrics = _determine_metrics(parsed.what, modifiers)

    # Reconcile metrics with TOP_N order_by
    # If grouping or ordering by aggregate column, ensure aggregate metrics are used
    if special_op == SpecialOp.TOP_N and op_specs.get("top_n"):
        top_n_spec = op_specs["top_n"]
        metrics, new_order_by = _reconcile_metrics_with_order_by(metrics, top_n_spec.order_by, grouping)
        # Update TopNSpec if order_by changed
        if new_order_by != top_n_spec.order_by:
            op_specs["top_n"] = TopNSpec(
                n=top_n_spec.n,
                order_by=new_order_by,
                direction=top_n_spec.direction,
            )

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

    return QueryWithSummary(type="query", summary=parsed.summary, spec=spec)


# =============================================================================
# Helper Functions
# =============================================================================

def _extract_date(parsed: ParsedQuery) -> str:
    """Extract date from parsed period."""
    if not parsed.period:
        return ""
    if parsed.period.dates:
        return parsed.period.dates[0]
    if parsed.period.start:
        return parsed.period.start
    return ""


def _resolve_event_filter(
    event_filter: str,
    period: ParsedPeriod | None,
    symbol: str,
) -> tuple[ParsedPeriod, str | None]:
    """Resolve event_filter to specific_dates.

    Returns (updated_period, error_message).
    If error_message is not None, the event filter couldn't be resolved.
    """
    from datetime import date, timedelta
    from agent.market.instruments import get_instrument

    # Get period bounds
    if period and period.start and period.end:
        start_str = period.start
        end_str = period.end
    else:
        # Use instrument data range as default
        instrument = get_instrument(symbol)
        if instrument:
            start_str = period.start if period and period.start else instrument.get("data_start", "2008-01-01")
            end_str = period.end if period and period.end else instrument.get("data_end", datetime.now().strftime("%Y-%m-%d"))
        else:
            start_str = period.start if period and period.start else "2008-01-01"
            end_str = period.end if period and period.end else datetime.now().strftime("%Y-%m-%d")

    try:
        start_date = date.fromisoformat(start_str)
        end_date = date.fromisoformat(end_str)
    except ValueError:
        return period, f"Invalid date format for event filter: {start_str} - {end_str}"

    # Get event dates
    event_dates = get_event_dates(event_filter, start_date, end_date)

    if not event_dates:
        # Event is not calculable (like FOMC, CPI) - needs historical data
        event_names = {
            "fomc": "FOMC",
            "cpi": "CPI",
            "ppi": "PPI",
            "gdp": "GDP",
            "pce": "PCE",
        }
        event_name = event_names.get(event_filter.lower(), event_filter.upper())
        return period, f"Календарь {event_name} пока не загружен. Доступны: OPEX, NFP, Quad Witching, VIX Expiration."

    # Convert dates to strings
    date_strings = [d.isoformat() for d in event_dates]

    # Return updated period with specific_dates
    updated_period = ParsedPeriod(
        raw=period.raw if period else None,
        start=start_str,
        end=end_str,
        dates=date_strings,
    )

    return updated_period, None


def _needs_prev_day(what: str, filters_raw: ParsedFilters | None) -> bool:
    """Check if query needs previous day data (for gap analysis)."""
    conditions = filters_raw.conditions if filters_raw else []
    conditions_str = " ".join(conditions or []).lower()

    return "gap" in what.lower() or "gap" in conditions_str or "prev" in conditions_str


def _determine_source(
    special_op: SpecialOp,
    session: str | None,
    specific_dates: list[str] | None,
    needs_prev_day: bool,
    grouping: Grouping = Grouping.NONE,
) -> Source:
    """
    Determine data source based on query characteristics.

    Decision Table:
    ┌─────────────────┬───────────────┬─────────┬────────────────┬───────────────┬─────────────────────┐
    │ special_op      │ grouping      │ session │ specific_dates │ needs_prev    │ Source              │
    ├─────────────────┼───────────────┼─────────┼────────────────┼───────────────┼─────────────────────┤
    │ EVENT_TIME      │ any           │ any     │ any            │ any           │ MINUTES             │
    │ FIND_EXTREMUM   │ any           │ any     │ any            │ any           │ (handled separately)│
    │ any             │ time-based    │ any     │ any            │ any           │ MINUTES             │
    │ any             │ other         │ yes     │ yes            │ any           │ DAILY               │
    │ TOP_N           │ other         │ yes     │ no             │ any           │ DAILY               │
    │ any             │ other         │ yes     │ no             │ any           │ MINUTES             │
    │ any             │ other         │ no      │ any            │ yes           │ DAILY_WITH_PREV     │
    │ any             │ other         │ no      │ any            │ no            │ DAILY               │
    └─────────────────┴───────────────┴─────────┴────────────────┴───────────────┴─────────────────────┘

    Why each rule:
    - EVENT_TIME → MINUTES: Need minute-level timestamps for time bucket analysis
    - time-based grouping → MINUTES: HOUR/MINUTE_* grouping needs timestamp column
    - session + specific_dates → DAILY: Single day with session = aggregate in CTE
    - session + TOP_N → DAILY: TOP_N ranks daily bars, session filter in aggregation
    - session (no specific) → MINUTES: Multi-day range with session needs minute filtering
    - needs_prev_day → DAILY_WITH_PREV: Gap analysis requires previous day's close
    - default → DAILY: Standard daily aggregation
    """
    # EVENT_TIME always needs minute data for time bucket analysis
    if special_op == SpecialOp.EVENT_TIME:
        return Source.MINUTES

    # Time-based grouping (HOUR, MINUTE_*) needs minute data with timestamp
    if grouping.is_time_based():
        return Source.MINUTES

    # SESSION grouping needs minute data to classify RTH/ETH by time
    if grouping == Grouping.SESSION:
        return Source.MINUTES

    # With session filter:
    if session:
        # Specific dates (single day query) - aggregate in daily CTE with session
        if specific_dates:
            return Source.DAILY
        # TOP_N with session - rank daily bars with session filter in aggregation
        if special_op == SpecialOp.TOP_N:
            return Source.DAILY
        # TOTAL grouping with session - daily stats filtered by session
        if grouping == Grouping.TOTAL:
            return Source.DAILY
        # Multi-day range with session - need minute-level for time filtering
        return Source.MINUTES

    # No session:
    # Gap analysis needs previous day data
    if needs_prev_day:
        return Source.DAILY_WITH_PREV

    # Default: standard daily aggregation
    return Source.DAILY


def _build_filters(period: ParsedPeriod | None, filters_raw: ParsedFilters | None, symbol: str) -> Filters:
    """Build Filters object from parsed data."""
    from agent.market.instruments import get_instrument

    specific_dates = period.dates if period else None

    # Derive period from specific_dates if not explicitly set
    if specific_dates:
        period_start = period.start if period and period.start else min(specific_dates)
        period_end = period.end if period and period.end else max(specific_dates)
    else:
        period_start = period.start if period else None
        period_end = period.end if period else None

    # Fill missing period from instrument data range
    if not period_start or not period_end:
        instrument = get_instrument(symbol)
        if instrument:
            period_start = period_start or instrument.get("data_start", "2008-01-01")
            period_end = period_end or instrument.get("data_end", datetime.now().strftime("%Y-%m-%d"))
        else:
            period_start = period_start or "2008-01-01"
            period_end = period_end or datetime.now().strftime("%Y-%m-%d")

    # Convert inclusive end to exclusive (Parser returns inclusive, QueryBuilder expects exclusive)
    from datetime import timedelta
    try:
        end_dt = datetime.strptime(period_end, "%Y-%m-%d")
        period_end = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    except ValueError as e:
        # Log but continue — invalid date format shouldn't crash, but should be visible
        print(f"[Composer] Warning: Could not parse period_end '{period_end}': {e}")

    weekdays = filters_raw.weekdays if filters_raw else None
    months = filters_raw.months if filters_raw else None
    session = filters_raw.session if filters_raw else None
    time_start = filters_raw.time_start if filters_raw else None
    time_end = filters_raw.time_end if filters_raw else None
    conditions = _parse_conditions(filters_raw.conditions or [] if filters_raw else [])

    # Build structured filters
    period_filter = PeriodFilter(
        start=period_start,
        end=period_end,
        specific_dates=specific_dates,
    )

    calendar_filter = None
    if weekdays or months:
        calendar_filter = CalendarFilter(weekdays=weekdays, months=months)

    time_filter = None
    # time_start/time_end takes precedence (calendar day mode)
    if time_start and time_end:
        time_filter = TimeFilter(start=time_start, end=time_end)
    elif session and session.upper() in ("RTH", "ETH", "OVERNIGHT"):
        # Only use session if it's a known session type
        time_filter = TimeFilter(session=session)

    return Filters(
        period=period_filter,
        calendar=calendar_filter,
        time=time_filter,
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
    modifiers: ParsedModifiers | None,
    period: ParsedPeriod | None,
    session: str | None
) -> Grouping:
    """Determine grouping based on query type."""
    group_by = modifiers.group_by if modifiers else None
    if group_by:
        mapping = {
            "month": Grouping.MONTH,
            "week": Grouping.WEEK,
            "year": Grouping.YEAR,
            "weekday": Grouping.WEEKDAY,
            "day": Grouping.DAY,
            "hour": Grouping.HOUR,
            "session": Grouping.SESSION,
        }
        return mapping.get(group_by, Grouping.NONE)

    if modifiers and modifiers.compare:
        return Grouping.NONE

    what_lower = what.lower()
    if any(word in what_lower for word in ["statistic", "average", "mean", "volatility"]):
        return Grouping.TOTAL

    if session and period and period.dates:
        return Grouping.TOTAL

    if "days" in what_lower or "day" in what_lower:
        return Grouping.NONE

    if "time" in what_lower or "when" in what_lower:
        return Grouping.HOUR

    return Grouping.NONE


def _reconcile_metrics_with_order_by(
    metrics: list[MetricSpec],
    order_by: str,
    grouping: Grouping = Grouping.NONE,
) -> tuple[list[MetricSpec], str]:
    """Ensure metrics include the order_by column.

    Rules:
    1. If grouping != NONE, we're aggregating rows → need aggregate metrics
    2. If ordering by aggregate column (volatility, avg_range), need aggregate metrics

    Args:
        metrics: Current metrics from _determine_metrics
        order_by: Column to order by (from TopNSpec)
        grouping: Query grouping type

    Returns:
        Tuple of (metrics, updated_order_by)
    """
    aggregate_metrics = [
        MetricSpec(metric=Metric.AVG, column="range", alias="avg_range"),
        MetricSpec(metric=Metric.AVG, column="change_pct", alias="avg_change"),
        MetricSpec(metric=Metric.STDDEV, column="change_pct", alias="volatility"),
        MetricSpec(metric=Metric.SUM, column="volume", alias="total_volume"),
        MetricSpec(metric=Metric.COUNT, alias="count"),
    ]

    # Map raw columns to aggregate aliases
    column_to_aggregate = {
        "range": "avg_range",
        "change_pct": "avg_change",
        "volume": "total_volume",
    }

    # Rule 1: Grouping requires aggregate metrics
    # (each row = aggregation of multiple days/hours/etc)
    if grouping not in (Grouping.NONE,):
        # Always map order_by to aggregate column when grouping
        new_order_by = column_to_aggregate.get(order_by, order_by)

        # Check if current metrics are already aggregates
        metric_aliases = {m.alias for m in metrics if m.alias}
        if "volatility" in metric_aliases or "avg_range" in metric_aliases:
            return metrics, new_order_by  # Already aggregate, but still map order_by

        return aggregate_metrics, new_order_by

    # Rule 2: Aggregate order_by column requires aggregate metrics
    aggregate_columns = {"volatility", "avg_range", "avg_change", "stddev"}
    if order_by in aggregate_columns:
        metric_aliases = {m.alias for m in metrics if m.alias}
        if order_by not in metric_aliases:
            return aggregate_metrics, order_by

    return metrics, order_by


def _determine_metrics(what: str, modifiers: ParsedModifiers | None) -> list[MetricSpec]:
    """Determine which metrics to include."""
    what_lower = what.lower()

    base_metrics = [
        MetricSpec(metric=Metric.OPEN, alias="open"),
        MetricSpec(metric=Metric.HIGH, alias="high"),
        MetricSpec(metric=Metric.LOW, alias="low"),
        MetricSpec(metric=Metric.CLOSE, alias="close"),
    ]

    if any(word in what_lower for word in ["statistic", "average", "volatility", "статистик"]):
        return [
            MetricSpec(metric=Metric.AVG, column="range", alias="avg_range"),
            MetricSpec(metric=Metric.AVG, column="change_pct", alias="avg_change"),
            MetricSpec(metric=Metric.STDDEV, column="change_pct", alias="volatility"),
            MetricSpec(metric=Metric.COUNT, alias="count"),
        ]

    if "count" in what_lower or "how many" in what_lower:
        return [MetricSpec(metric=Metric.COUNT, alias="count")]

    if "win rate" in what_lower or "percent" in what_lower:
        return [
            MetricSpec(metric=Metric.COUNT, alias="total"),
            MetricSpec(metric=Metric.AVG, column="change_pct", alias="avg_change"),
        ]

    if "correlation" in what_lower:
        return [
            MetricSpec(metric=Metric.AVG, column="gap_pct", alias="avg_gap"),
            MetricSpec(metric=Metric.AVG, column="range", alias="avg_range"),
        ]

    base_metrics.append(MetricSpec(metric=Metric.RANGE, alias="range"))

    return base_metrics


def _determine_special_op(what: str, modifiers: ParsedModifiers | None) -> tuple[SpecialOp, dict]:
    """Determine special operation and return typed specs."""
    what_lower = what.lower()
    specs: dict = {}

    # Compare
    if modifiers and modifiers.compare:
        specs["compare"] = CompareSpec(items=modifiers.compare)
        return SpecialOp.COMPARE, specs

    # Get find and top_n from modifiers
    find = modifiers.find if modifiers else None
    top_n = modifiers.top_n if modifiers else None

    # find without explicit top_n implies top_n=1
    if find and not top_n:
        top_n = 1

    # Top N (explicit or implied from find)
    if top_n:
        order_by = "range"  # default
        direction = "DESC"  # default: biggest first

        # find field takes precedence for direction
        if find == "min":
            direction = "ASC"
        elif find == "max":
            direction = "DESC"
        # Fallback to what-based inference if no find
        elif "gap" in what_lower:
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

        # Determine order_by from what
        if "volati" in what_lower:
            order_by = "volatility"
        elif "volume" in what_lower or "объём" in what_lower:
            order_by = "volume"
        elif "change" in what_lower or "изменен" in what_lower:
            order_by = "change_pct"
        elif "range" in what_lower:
            order_by = "range"

        specs["top_n"] = TopNSpec(
            n=top_n,
            order_by=order_by,
            direction=direction,
        )
        return SpecialOp.TOP_N, specs

    # Event time (when is high/low usually)
    if "time of" in what_lower or "when" in what_lower:
        event_find = "high"
        if "low" in what_lower:
            event_find = "low"
        specs["event_time"] = EventTimeSpec(find=event_find)
        return SpecialOp.EVENT_TIME, specs

    return SpecialOp.NONE, specs


def _check_not_supported(what: str, filters_raw: ParsedFilters | None, _modifiers: ParsedModifiers | None) -> str | None:
    """Check if query is not supported yet."""
    what_lower = what.lower()
    raw_conditions = filters_raw.conditions if filters_raw else []
    conditions = " ".join(raw_conditions or []).lower()

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


def _calculate_period_days(period: ParsedPeriod | None, symbol: str) -> int:
    """Calculate number of days in the period."""
    from agent.market.instruments import get_instrument

    if not period:
        # No period = all data, use instrument range
        instrument = get_instrument(symbol)
        if instrument:
            start = instrument.get("data_start", "2008-01-01")
            end = instrument.get("data_end", datetime.now().strftime("%Y-%m-%d"))
        else:
            start = "2008-01-01"
            end = datetime.now().strftime("%Y-%m-%d")
    else:
        start = period.start
        end = period.end

    if not start or not end:
        return 365 * 10  # Assume large period if unknown

    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
        return (end_dt - start_dt).days
    except ValueError:
        return 365 * 10  # Assume large period on error


def _check_data_volume(
    source: Source,
    grouping: Grouping,
    period: ParsedPeriod | None,
    symbol: str,
) -> ClarificationResult | None:
    """Check if query would return too much data.

    Returns ClarificationResult if user should narrow down the query.
    """
    # Only check MINUTES source with no grouping
    if source != Source.MINUTES:
        return None

    if grouping != Grouping.NONE:
        return None  # Grouping aggregates data, OK

    period_days = _calculate_period_days(period, symbol)

    # Threshold: 30 days of minute data is manageable (~40k rows max)
    if period_days > 30:
        return ClarificationResult(
            type="clarification",
            summary="Слишком много минутных данных для отображения.",
            field="grouping",
            options=["по часам", "по дням недели", "сократить период"],
        )

    return None
