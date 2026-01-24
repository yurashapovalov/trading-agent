"""
Executor — runs ExecutionPlan against data.

Flow: ExecutionPlan → load data → enrich → filter (by semantics) → operation → result

Uses rules from agent/rules/ for:
- Filter semantics (where/condition/event)
- Metric column mapping
- Operation requirements (requires_full_data)
"""

import logging
from datetime import date, timedelta

import pandas as pd

logger = logging.getLogger(__name__)

from agent.data import get_bars, enrich
from agent.operations import OPERATIONS
from agent.agents.planner import ExecutionPlan, DataRequest
from agent.rules import (
    parse_filters,
    split_filters_by_semantic,
    requires_full_data,
    get_column,
)


# =============================================================================
# Main API
# =============================================================================

def execute_plan(plan: ExecutionPlan, symbol: str = "NQ") -> dict:
    """Execute plan and return result."""
    executors = {
        "single": _execute_single,
        "multi_period": _execute_multi_period,
        "multi_filter": _execute_multi_filter,
        "multi_metric": _execute_multi_metric,
    }

    executor = executors.get(plan.mode)
    if not executor:
        return {"error": f"Unknown mode: {plan.mode}"}

    return executor(plan, symbol)


# =============================================================================
# Mode Executors
# =============================================================================

def _execute_single(plan: ExecutionPlan, symbol: str) -> dict:
    """Single request, single metric."""
    req = plan.requests[0]

    # Load data with semantic-aware filtering
    df, condition_filters, event_filters = _load_data_with_semantics(req, plan.operation, symbol)

    if df.empty:
        return _empty_result(req, "No data")

    op = OPERATIONS.get(plan.operation)
    if not op:
        return {"error": f"Unknown operation: {plan.operation}"}

    # Pass condition/event filters to operation params
    params = {**plan.params}
    if condition_filters:
        params["condition_filters"] = condition_filters
    if event_filters:
        params["event_filters"] = event_filters

    result = op(df, plan.metrics[0], params)
    result["period"] = {"start": req.period[0], "end": req.period[1]}
    result["filters"] = req.filters

    return result


def _execute_multi_period(plan: ExecutionPlan, symbol: str) -> dict:
    """Multiple periods, compare stats for each."""
    metric = plan.metrics[0]
    col = get_column(metric)

    rows = []
    periods = []

    for req in plan.requests:
        df, _, _ = _load_data_with_semantics(req, plan.operation, symbol)
        periods.append({"start": req.period[0], "end": req.period[1]})

        if df.empty:
            rows.append({"group": req.label, "avg": None, "count": 0})
            continue

        if col not in df.columns:
            rows.append({"group": req.label, "avg": None, "count": 0, "error": f"No column {col}"})
            continue

        rows.append({
            "group": req.label,
            "avg": round(df[col].mean(), 3),
            "count": len(df),
            "std": round(df[col].std(), 3) if len(df) > 1 else 0,
        })

    summary = _summarize_comparison(rows)
    return {"rows": rows, "summary": summary, "periods": periods}


def _execute_multi_filter(plan: ExecutionPlan, symbol: str) -> dict:
    """Same period, different filters, compare stats."""
    metric = plan.metrics[0]
    col = get_column(metric)

    rows = []

    for req in plan.requests:
        df, _, _ = _load_data_with_semantics(req, plan.operation, symbol)

        if df.empty:
            rows.append({"group": req.label, "avg": None, "count": 0})
            continue

        if col not in df.columns:
            rows.append({"group": req.label, "avg": None, "count": 0, "error": f"No column {col}"})
            continue

        rows.append({
            "group": req.label,
            "avg": round(df[col].mean(), 3),
            "count": len(df),
            "std": round(df[col].std(), 3) if len(df) > 1 else 0,
        })

    summary = _summarize_comparison(rows)
    req = plan.requests[0]
    return {
        "rows": rows,
        "summary": summary,
        "period": {"start": req.period[0], "end": req.period[1]},
    }


def _execute_multi_metric(plan: ExecutionPlan, symbol: str) -> dict:
    """Single request, multiple metrics (correlation)."""
    req = plan.requests[0]
    df, _, _ = _load_data_with_semantics(req, plan.operation, symbol)

    if df.empty:
        return _empty_result(req, "No data")

    op = OPERATIONS.get(plan.operation)
    if not op:
        return {"error": f"Unknown operation: {plan.operation}"}

    params = {**plan.params, "metrics": plan.metrics}
    result = op(df, plan.metrics[0], params)
    result["period"] = {"start": req.period[0], "end": req.period[1]}

    return result


# =============================================================================
# Data Loading with Semantic Filter Handling
# =============================================================================

def _load_data_with_semantics(
    req: DataRequest,
    operation: str,
    symbol: str
) -> tuple[pd.DataFrame, list[dict], list[dict]]:
    """
    Load data and apply filters based on semantics.

    - WHERE filters: always applied (filter rows)
    - CONDITION filters: for requires_full_data ops, passed to params
    - EVENT filters:
        - consecutive: passed to params (needs special logic to find last day of streak)
        - comparison/pattern: applied as WHERE (same result, avoids code duplication)

    Returns: (df, condition_filters, event_filters)
    """
    period = f"{req.period[0]}:{req.period[1]}"
    df = get_bars(symbol, period, timeframe=req.timeframe)

    if df.empty:
        return df, [], []

    df = enrich(df)

    # Scan for patterns on daily data (adds is_* columns)
    if req.timeframe == "1D" and {"open", "high", "low", "close"}.issubset(df.columns):
        from agent.patterns import scan_patterns_df
        df = scan_patterns_df(df)

    # Parse and split filters by semantics
    all_condition_filters = []
    all_event_filters = []

    for filter_str in req.filters:
        parsed = parse_filters(filter_str)
        where_filters, condition_filters, event_filters = split_filters_by_semantic(parsed, operation)

        # Always apply WHERE filters
        df = _apply_where_filters(df, where_filters, symbol)

        # Condition filters: for requires_full_data ops, pass to params
        if requires_full_data(operation):
            all_condition_filters.extend(condition_filters)
        else:
            df = _apply_where_filters(df, condition_filters, symbol)

        # Event filters: consecutive needs special handling, others apply as WHERE
        for ef in event_filters:
            if ef.get("type") == "consecutive":
                # Consecutive requires special logic in operation (find streaks → last day)
                all_event_filters.append(ef)
            else:
                # comparison, pattern — apply as WHERE (same result, no code duplication)
                df = _apply_where_filters(df, [ef], symbol)

    return df, all_condition_filters, all_event_filters


def _apply_where_filters(df: pd.DataFrame, filters: list[dict], symbol: str) -> pd.DataFrame:
    """Apply WHERE filters to DataFrame."""
    if df.empty or not filters:
        return df

    for f in filters:
        filter_type = f.get("type")

        if filter_type == "categorical":
            df = _apply_categorical(df, f, symbol)

        elif filter_type == "comparison":
            df = _apply_comparison(df, f)

        elif filter_type == "consecutive":
            df = _apply_consecutive(df, f)

        elif filter_type == "time":
            df = _apply_time(df, f)

        elif filter_type == "pattern":
            df = _apply_pattern(df, f)

    return df.reset_index(drop=True)


def _apply_categorical(df: pd.DataFrame, f: dict, symbol: str) -> pd.DataFrame:
    """Apply categorical filter (weekday, session, event)."""
    if f.get("weekday"):
        weekday_map = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4}
        weekday_num = weekday_map.get(f["weekday"])
        if weekday_num is not None and "weekday" in df.columns:
            df = df[df["weekday"] == weekday_num]

    elif f.get("session"):
        df = _apply_session_filter(df, f["session"], symbol)

    elif f.get("event"):
        # Event filtering (fomc, opex, cpi) not yet implemented
        logger.warning(f"Event filter not implemented: {f.get('event')}")

    return df


def _apply_comparison(df: pd.DataFrame, f: dict) -> pd.DataFrame:
    """Apply comparison filter (change > 0, etc.)."""
    col = f.get("metric")
    op = f.get("op")
    value = f.get("value")

    if col not in df.columns:
        return df

    series = df[col]
    ops = {
        ">": series > value,
        "<": series < value,
        ">=": series >= value,
        "<=": series <= value,
        "=": series == value,
    }

    if op in ops:
        df = df[ops[op]]

    return df


def _apply_consecutive(df: pd.DataFrame, f: dict) -> pd.DataFrame:
    """Apply consecutive filter (consecutive red >= 2)."""
    if "is_green" not in df.columns:
        return df

    color = f.get("color")
    op = f.get("op", ">=")
    length = f.get("length", 1)

    mask = df["is_green"] if color == "green" else ~df["is_green"]

    df = df.copy()
    df["_sid"] = (mask != mask.shift()).cumsum()
    lengths = df.groupby("_sid").transform("size")

    if op == ">=":
        df = df[mask & (lengths >= length)]
    elif op == ">":
        df = df[mask & (lengths > length)]
    elif op == "=":
        df = df[mask & (lengths == length)]

    return df.drop(columns=["_sid"])


def _apply_time(df: pd.DataFrame, f: dict) -> pd.DataFrame:
    """Apply time filter (time >= 09:30)."""
    if "time" not in df.columns:
        return df

    op = f.get("op")
    value = f.get("value")

    ops = {
        ">=": df["time"] >= value,
        "<=": df["time"] <= value,
        ">": df["time"] > value,
        "<": df["time"] < value,
    }

    if op in ops:
        df = df[ops[op]]

    return df


def _apply_pattern(df: pd.DataFrame, f: dict) -> pd.DataFrame:
    """Apply pattern filter (inside_day, doji, hammer, etc.)."""
    pattern = f.get("pattern")

    # Legacy patterns (computed in enrich)
    if pattern == "green" and "is_green" in df.columns:
        return df[df["is_green"]]
    if pattern == "red" and "is_green" in df.columns:
        return df[~df["is_green"]]
    if pattern in ("gap_fill", "gap_filled") and "gap_filled" in df.columns:
        return df[df["gap_filled"]]

    # Scanner patterns (is_* columns from scan_patterns)
    col = f"is_{pattern}"
    if col in df.columns:
        return df[df[col] == 1]

    # Pattern not scanned (wrong timeframe or unknown pattern)
    logger.warning(f"Pattern column '{col}' not found — check timeframe is 1D")
    return df


def _apply_session_filter(df: pd.DataFrame, session: str, symbol: str) -> pd.DataFrame:
    """Filter by trading session (MORNING, RTH, etc.)."""
    from agent.config.market.instruments import get_session_times

    times = get_session_times(symbol, session)
    if not times:
        return df

    start_time, end_time = times

    if "time" not in df.columns:
        return df

    df = df[(df["time"] >= start_time) & (df["time"] < end_time)]
    return df


def _empty_result(req: DataRequest, error: str) -> dict:
    """Create empty result with error."""
    return {
        "rows": [],
        "summary": {"error": error},
        "period": {"start": req.period[0], "end": req.period[1]},
    }


def _summarize_comparison(rows: list[dict]) -> dict:
    """Find best/worst from comparison rows."""
    valid = [r for r in rows if r.get("avg") is not None]

    if not valid:
        return {"error": "No valid data"}

    best = max(valid, key=lambda r: r["avg"])
    worst = min(valid, key=lambda r: r["avg"])

    return {
        "best": best["group"],
        "best_avg": best["avg"],
        "worst": worst["group"],
        "worst_avg": worst["avg"],
    }


# =============================================================================
# Legacy API (for backward compatibility)
# =============================================================================

def execute_step(step, symbol: str = "NQ", today: date | None = None) -> dict:
    """Execute Step directly (legacy, use execute_plan instead)."""
    from agent.agents.planner import plan_step
    plan = plan_step(step, today)
    return execute_plan(plan, symbol)


def execute(steps: list, symbol: str = "NQ", today: date | None = None) -> list[dict]:
    """Execute all steps (legacy)."""
    results = []
    for step in steps:
        result = execute_step(step, symbol, today)
        result["step_id"] = step.id
        results.append(result)
    return results
