"""Auto-generation of JSON Schema from Python types.

Single Source of Truth - all types are defined in types.py,
JSON schema is generated automatically for LLM.

Functions:
    get_query_spec_schema() - JSON schema for LLM response validation
    get_special_op_map() - Maps string -> SpecialOp enum
    get_source_map() - Maps string -> Source enum
    parse_spec() - Parse spec dict into dataclass based on special_op

Example:
    schema = get_query_spec_schema()
    op_map = get_special_op_map()
    special_op = op_map.get("find_extremum")  # -> SpecialOp.FIND_EXTREMUM
"""

from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Literal, get_args, get_origin, get_type_hints

from .types import (
    Source,
    Grouping,
    SpecialOp,
    Metric,
    EventTimeSpec,
    TopNSpec,
    CompareSpec,
    FindExtremumSpec,
)


# =============================================================================
# SpecialOp -> Spec class mapping
# =============================================================================

# Mapping between SpecialOp and corresponding Spec class
SPECIAL_OP_SPECS = {
    SpecialOp.EVENT_TIME: EventTimeSpec,
    SpecialOp.TOP_N: TopNSpec,
    SpecialOp.COMPARE: CompareSpec,
    SpecialOp.FIND_EXTREMUM: FindExtremumSpec,
}


# =============================================================================
# Enum value generation
# =============================================================================

def get_enum_values(enum_class: type[Enum]) -> list[str]:
    """Get list of string values from Enum."""
    return [e.value for e in enum_class]


def get_source_values() -> list[str]:
    """Get list of Source enum values."""
    return get_enum_values(Source)


def get_grouping_values() -> list[str]:
    """Get list of Grouping enum values."""
    return get_enum_values(Grouping)


def get_special_op_values() -> list[str]:
    """Get list of SpecialOp enum values."""
    return get_enum_values(SpecialOp)


def get_metric_values() -> list[str]:
    """Get list of Metric enum values."""
    return get_enum_values(Metric)


def get_symbol_values() -> list[str]:
    """
    Get list of available symbols from DB.

    Single Source of Truth - actual data.
    """
    from agent.modules.sql import get_available_symbols

    symbols = get_available_symbols()
    return symbols if symbols else ["NQ"]  # Fallback to NQ


def get_session_values() -> list[str]:
    """
    Get list of available sessions from instruments.py.

    Collects unique sessions from all instruments.
    Includes "_default_" marker for cases when user implies but doesn't specify.
    Single Source of Truth - instruments.py.
    """
    from .instruments import INSTRUMENTS

    sessions = set()
    for instrument in INSTRUMENTS.values():
        sessions.update(instrument.get("sessions", {}).keys())

    # Sort for consistent ordering, add _default_ marker
    result = sorted(sessions)
    result.append("_default_")  # Marker: user implied but didn't specify which session
    return result


# =============================================================================
# String -> Enum mapping
# =============================================================================

def get_special_op_map() -> dict[str, SpecialOp]:
    """
    Auto-generate string -> SpecialOp mapping.

    Returns:
        {"none": SpecialOp.NONE, "event_time": SpecialOp.EVENT_TIME, ...}
    """
    return {op.value: op for op in SpecialOp}


def get_source_map() -> dict[str, Source]:
    """Auto-generate string -> Source mapping."""
    return {s.value: s for s in Source}


def get_grouping_map() -> dict[str, Grouping]:
    """Auto-generate string -> Grouping mapping."""
    return {g.value: g for g in Grouping}


def get_metric_map() -> dict[str, Metric]:
    """
    Auto-generate string -> Metric mapping.

    Returns:
        {"open": Metric.OPEN, "high": Metric.HIGH, "count": Metric.COUNT, ...}
    """
    return {m.value: m for m in Metric}


# =============================================================================
# JSON Schema generation from dataclass
# =============================================================================

def _python_type_to_json_schema(python_type) -> dict:
    """Convert Python type to JSON Schema."""
    origin = get_origin(python_type)

    # Literal["high", "low", "both"] -> {"type": "string", "enum": [...]}
    if origin is Literal:
        args = get_args(python_type)
        if all(isinstance(a, str) for a in args):
            return {"type": "string", "enum": list(args)}
        elif all(isinstance(a, int) for a in args):
            return {"type": "integer", "enum": list(args)}
        else:
            return {"type": "string", "enum": [str(a) for a in args]}

    # list[str] -> {"type": "array", "items": {"type": "string"}}
    if origin is list:
        item_type = get_args(python_type)[0] if get_args(python_type) else str
        return {
            "type": "array",
            "items": _python_type_to_json_schema(item_type)
        }

    # Basic types
    if python_type is str:
        return {"type": "string"}
    elif python_type is int:
        return {"type": "integer"}
    elif python_type is float:
        return {"type": "number"}
    elif python_type is bool:
        return {"type": "boolean"}

    # Fallback
    return {"type": "string"}


def generate_spec_schema(spec_class: type) -> dict:
    """
    Generate JSON Schema from dataclass.

    Args:
        spec_class: Dataclass (EventTimeSpec, TopNSpec, etc.)

    Returns:
        JSON Schema for this class
    """
    if not is_dataclass(spec_class):
        raise ValueError(f"{spec_class} is not a dataclass")

    properties = {}
    type_hints = get_type_hints(spec_class)

    for field in fields(spec_class):
        field_type = type_hints.get(field.name, str)
        properties[field.name] = _python_type_to_json_schema(field_type)

    return {
        "type": "object",
        "properties": properties
    }


# =============================================================================
# Full Query Spec Schema
# =============================================================================

def get_query_spec_schema() -> dict:
    """
    Generate full JSON Schema for query_spec.

    Automatically includes:
    - symbol: trading instrument
    - source enum from Source
    - grouping enum from Grouping
    - special_op enum from SpecialOp
    - *_spec schemas from corresponding dataclasses
    """
    schema = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "enum": get_symbol_values(),
                "description": "Trading instrument symbol"
            },
            "source": {
                "type": "string",
                "enum": get_source_values()
            },
            "filters": {
                "type": "object",
                "properties": {
                    "period_start": {"type": "string"},
                    "period_end": {"type": "string"},
                    "specific_dates": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific dates: ['2005-05-16', '2003-04-12']"
                    },
                    "years": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Specific years: [2020, 2022, 2024]"
                    },
                    "months": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Months (1-12): [1, 6] for January and June"
                    },
                    "weekdays": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Weekdays: ['Monday', 'Friday']"
                    },
                    "session": {
                        "type": "string",
                        "enum": get_session_values(),
                        "description": "Trading session filter (from instruments.py)"
                    },
                    "time_start": {
                        "type": "string",
                        "description": "Custom time start: '06:00:00'"
                    },
                    "time_end": {
                        "type": "string",
                        "description": "Custom time end: '16:00:00'"
                    },
                    "conditions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {"type": "string"},
                                "operator": {"type": "string"},
                                "value": {"type": "number"}
                            }
                        }
                    }
                }
            },
            "grouping": {
                "type": "string",
                "enum": get_grouping_values()
            },
            "metrics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "metric": {"type": "string"},
                        "column": {"type": "string"},
                        "alias": {"type": "string"}
                    }
                }
            },
            "special_op": {
                "type": "string",
                "enum": get_special_op_values()
            },
        }
    }

    # Add spec schemas for each special_op
    for special_op, spec_class in SPECIAL_OP_SPECS.items():
        spec_name = f"{special_op.value}_spec"
        schema["properties"][spec_name] = generate_spec_schema(spec_class)

    return schema


def get_response_schema() -> dict:
    """
    Generate full JSON Schema for Understander response.

    Includes query_spec and other fields.
    """
    return {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": ["data", "concept", "chitchat", "out_of_scope", "clarification"]
            },
            "query_spec": get_query_spec_schema(),
            "concept": {"type": "string"},
            "response_text": {"type": "string"},
            "clarification_question": {"type": "string"},
            "suggestions": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["type"]
    }


# =============================================================================
# Spec parsing utilities
# =============================================================================

def get_spec_class_for_op(special_op: SpecialOp) -> type | None:
    """
    Return Spec class for given SpecialOp.

    Args:
        special_op: SpecialOp enum value

    Returns:
        Class (EventTimeSpec, TopNSpec, etc.) or None
    """
    return SPECIAL_OP_SPECS.get(special_op)


def get_spec_field_name(special_op: SpecialOp) -> str | None:
    """
    Return JSON field name for given SpecialOp.

    Args:
        special_op: SpecialOp enum value

    Returns:
        Field name ("event_time_spec", "top_n_spec", etc.) or None
    """
    if special_op in SPECIAL_OP_SPECS:
        return f"{special_op.value}_spec"
    return None


def parse_spec(special_op: SpecialOp, query_spec: dict) -> object | None:
    """
    Auto-parse spec from JSON for given SpecialOp.

    Uses dataclass introspection to extract fields and defaults.

    Args:
        special_op: SpecialOp enum value
        query_spec: JSON dict with query_spec from LLM

    Returns:
        Spec object (EventTimeSpec, TopNSpec, etc.) or None

    Example:
        >>> parse_spec(SpecialOp.EVENT_TIME, {"event_time_spec": {"find": "low"}})
        EventTimeSpec(find='low')
    """
    spec_class = SPECIAL_OP_SPECS.get(special_op)
    if spec_class is None:
        return None

    spec_field_name = f"{special_op.value}_spec"
    spec_data = query_spec.get(spec_field_name, {})

    # Get defaults from dataclass
    type_hints = get_type_hints(spec_class)
    kwargs = {}

    for field in fields(spec_class):
        field_name = field.name
        field_type = type_hints.get(field_name, str)

        # Get value from JSON or use default
        if field_name in spec_data:
            kwargs[field_name] = spec_data[field_name]
        elif field.default is not field.default_factory:
            # Has explicit default
            if field.default is not dataclass_field_missing:
                kwargs[field_name] = field.default
            elif field.default_factory is not dataclass_field_missing:
                kwargs[field_name] = field.default_factory()
        else:
            # No default - use reasonable value
            kwargs[field_name] = _get_default_for_type(field_type)

    return spec_class(**kwargs)


def _get_default_for_type(field_type) -> object:
    """Return default value for type."""
    origin = get_origin(field_type)

    if origin is Literal:
        args = get_args(field_type)
        return args[0] if args else ""

    if origin is list:
        return []

    if field_type is str:
        return ""
    elif field_type is int:
        return 0
    elif field_type is float:
        return 0.0
    elif field_type is bool:
        return False

    return None


# For checking missing default
from dataclasses import MISSING as dataclass_field_missing


# =============================================================================
# Debug and testing
# =============================================================================

if __name__ == "__main__":
    import json

    print("=== Source values ===")
    print(get_source_values())

    print("\n=== Grouping values ===")
    print(get_grouping_values())

    print("\n=== SpecialOp values ===")
    print(get_special_op_values())

    print("\n=== SpecialOp map ===")
    for k, v in get_special_op_map().items():
        print(f"  {k!r} -> {v}")

    print("\n=== EventTimeSpec schema ===")
    print(json.dumps(generate_spec_schema(EventTimeSpec), indent=2))

    print("\n=== Full query_spec schema ===")
    print(json.dumps(get_query_spec_schema(), indent=2))
