"""
Planner — transforms Parser output into execution plan.

Parser returns WHAT user wants.
Planner decides HOW to execute it.
Executor runs the plan.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from agent.types import Step, Atom


@dataclass
class DataRequest:
    """What data to load."""
    period: tuple[str, str]
    timeframe: str
    filters: list[str]
    label: str
    session: str | None = None  # Trading session (RTH, OVERNIGHT, etc.)


@dataclass
class ExecutionPlan:
    """How to execute a step."""
    mode: Literal["single", "multi_period", "multi_filter", "multi_metric"]
    operation: str
    requests: list[DataRequest]
    params: dict = field(default_factory=dict)
    metrics: list[str] = field(default_factory=list)


def plan_step(step: Step, today: date | None = None, symbol: str = "NQ") -> ExecutionPlan:
    """
    Create execution plan for a step.

    Analyzes atoms and decides execution strategy:
    - single: one atom, standard execution
    - multi_period: atoms with different 'when' (compare Q1 vs Q4)
    - multi_filter: atoms with same 'when', different 'filter' (monday vs friday)
    - multi_metric: atoms with same 'when', different 'what' (correlation)
    """
    today = today or date.today()

    if not step.atoms:
        raise ValueError("Step has no atoms")

    # Single atom — simple case
    if len(step.atoms) == 1:
        return _plan_single(step, today, symbol)

    # Multiple atoms — analyze pattern
    atoms = step.atoms
    whens = {a.when for a in atoms}
    whats = {a.what for a in atoms}

    # Different 'when' → compare periods
    if len(whens) > 1:
        return _plan_multi_period(step, today, symbol)

    # Same 'when', different 'what' → correlation
    if len(whats) > 1:
        return _plan_multi_metric(step, today, symbol)

    # Same 'when', same 'what', different filters → compare filters
    return _plan_multi_filter(step, today, symbol)


def _plan_single(step: Step, today: date, symbol: str) -> ExecutionPlan:
    """Plan for single atom."""
    atom = step.atoms[0]
    start, end = _resolve_when(atom.when, today)

    raw_filters = [atom.filter] if atom.filter else []
    session, clean_filters = _extract_session(raw_filters)

    request = DataRequest(
        period=(start, end),
        timeframe=atom.timeframe,
        filters=clean_filters,
        label=atom.when,
        session=session,
    )

    params = _extract_params(step, atom)

    return ExecutionPlan(
        mode="single",
        operation=step.operation,
        requests=[request],
        params=params,
        metrics=[atom.what],
    )


def _plan_multi_period(step: Step, today: date, symbol: str) -> ExecutionPlan:
    """Plan for comparing different periods (Q1 vs Q4)."""
    requests = []

    for atom in step.atoms:
        start, end = _resolve_when(atom.when, today)
        raw_filters = [atom.filter] if atom.filter else []
        session, clean_filters = _extract_session(raw_filters)

        requests.append(DataRequest(
            period=(start, end),
            timeframe=atom.timeframe,
            filters=clean_filters,
            label=atom.when,
            session=session,
        ))

    # All atoms should have same 'what'
    metric = step.atoms[0].what
    params = _extract_params(step, step.atoms[0])

    return ExecutionPlan(
        mode="multi_period",
        operation=step.operation,
        requests=requests,
        params=params,
        metrics=[metric],
    )


def _plan_multi_filter(step: Step, today: date, symbol: str) -> ExecutionPlan:
    """Plan for comparing different filters (monday vs friday)."""
    atom = step.atoms[0]
    start, end = _resolve_when(atom.when, today)

    # One data request, multiple filters applied separately
    requests = []
    for a in step.atoms:
        raw_filters = [a.filter] if a.filter else []
        session, clean_filters = _extract_session(raw_filters)

        requests.append(DataRequest(
            period=(start, end),
            timeframe=a.timeframe,
            filters=clean_filters,
            label=a.filter or "all",
            session=session,
        ))

    params = _extract_params(step, atom)

    return ExecutionPlan(
        mode="multi_filter",
        operation=step.operation,
        requests=requests,
        params=params,
        metrics=[atom.what],
    )


def _plan_multi_metric(step: Step, today: date, symbol: str) -> ExecutionPlan:
    """Plan for multiple metrics (correlation)."""
    atom = step.atoms[0]
    start, end = _resolve_when(atom.when, today)

    raw_filters = [atom.filter] if atom.filter else []
    session, clean_filters = _extract_session(raw_filters)

    request = DataRequest(
        period=(start, end),
        timeframe=atom.timeframe,
        filters=clean_filters,
        label=atom.when,
        session=session,
    )

    metrics = [a.what for a in step.atoms]
    params = _extract_params(step, atom)

    return ExecutionPlan(
        mode="multi_metric",
        operation=step.operation,
        requests=[request],
        params=params,
        metrics=metrics,
    )


def _extract_params(step: Step, atom: Atom) -> dict:
    """Extract operation params from step and atom."""
    params = {}

    if step.params:
        if step.params.n:
            params["n"] = step.params.n
        if step.params.sort:
            params["sort"] = step.params.sort
        if step.params.outcome:
            params["outcome"] = step.params.outcome
        if step.params.offset:
            params["offset"] = step.params.offset

    if atom.group:
        params["group_by"] = _parse_group(atom.group)

    return params


def _parse_group(group: str) -> str:
    """Parse group string to column name."""
    group = group.lower()
    if "month" in group:
        return "month"
    if "week" in group or "day" in group:
        return "weekday"
    if "year" in group:
        return "year"
    if "quarter" in group:
        return "quarter"
    if "hour" in group:
        return "hour"
    return group


def _extract_session(filters: list[str]) -> tuple[str | None, list[str]]:
    """
    Extract session from filters list.

    Returns (session, clean_filters) where session is extracted
    and clean_filters has session removed.

    Example:
        ["session = RTH", "gap > 0"] → ("RTH", ["gap > 0"])
        ["gap > 0, session = OVERNIGHT"] → ("OVERNIGHT", ["gap > 0"])
        ["monday", "change > 0"] → (None, ["monday", "change > 0"])
    """
    import re

    session = None
    clean_filters = []

    for f in filters:
        # Check if this filter contains session
        match = re.search(r"session\s*=\s*(\w+)", f, re.IGNORECASE)
        if match:
            session = match.group(1).upper()
            # Remove session part from filter
            cleaned = re.sub(r",?\s*session\s*=\s*\w+\s*,?", "", f, flags=re.I).strip()
            cleaned = cleaned.strip(",").strip()
            if cleaned:
                clean_filters.append(cleaned)
        else:
            clean_filters.append(f)

    return session, clean_filters


def _resolve_when(when: str, today: date) -> tuple[str, str]:
    """Resolve 'when' to (start_date, end_date)."""
    from agent.date_resolver import resolve_date
    return resolve_date(when, today)
