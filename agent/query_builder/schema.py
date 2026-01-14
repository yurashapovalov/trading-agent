"""
Auto-generation of JSON Schema from Python types.

Single Source of Truth — все типы определяются в types.py,
schema генерируется автоматически.

Использование:
    from agent.query_builder.schema import (
        get_query_spec_schema,
        get_special_op_map,
        get_special_op_values,
    )

    # JSON schema для LLM
    schema = get_query_spec_schema()

    # Маппинг строка -> enum
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
    EventTimeSpec,
    TopNSpec,
    CompareSpec,
    FindExtremumSpec,
)


# =============================================================================
# Маппинг SpecialOp -> Spec класс
# =============================================================================

# Связь между SpecialOp и соответствующим Spec классом
SPECIAL_OP_SPECS = {
    SpecialOp.EVENT_TIME: EventTimeSpec,
    SpecialOp.TOP_N: TopNSpec,
    SpecialOp.COMPARE: CompareSpec,
    SpecialOp.FIND_EXTREMUM: FindExtremumSpec,
}


# =============================================================================
# Генерация enum значений
# =============================================================================

def get_enum_values(enum_class: type[Enum]) -> list[str]:
    """Получить список строковых значений из Enum."""
    return [e.value for e in enum_class]


def get_source_values() -> list[str]:
    """Получить список значений Source enum."""
    return get_enum_values(Source)


def get_grouping_values() -> list[str]:
    """Получить список значений Grouping enum."""
    return get_enum_values(Grouping)


def get_special_op_values() -> list[str]:
    """Получить список значений SpecialOp enum."""
    return get_enum_values(SpecialOp)


# =============================================================================
# Маппинг string -> Enum
# =============================================================================

def get_special_op_map() -> dict[str, SpecialOp]:
    """
    Автоматически генерирует маппинг строка -> SpecialOp.

    Returns:
        {"none": SpecialOp.NONE, "event_time": SpecialOp.EVENT_TIME, ...}
    """
    return {op.value: op for op in SpecialOp}


def get_source_map() -> dict[str, Source]:
    """Автоматически генерирует маппинг строка -> Source."""
    return {s.value: s for s in Source}


def get_grouping_map() -> dict[str, Grouping]:
    """Автоматически генерирует маппинг строка -> Grouping."""
    return {g.value: g for g in Grouping}


# =============================================================================
# Генерация JSON Schema из dataclass
# =============================================================================

def _python_type_to_json_schema(python_type) -> dict:
    """Конвертирует Python тип в JSON Schema."""
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

    # Базовые типы
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
    Генерирует JSON Schema из dataclass.

    Args:
        spec_class: Dataclass (EventTimeSpec, TopNSpec, и т.д.)

    Returns:
        JSON Schema для этого класса
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
# Полная Query Spec Schema
# =============================================================================

def get_query_spec_schema() -> dict:
    """
    Генерирует полную JSON Schema для query_spec.

    Автоматически включает:
    - source enum из Source
    - grouping enum из Grouping
    - special_op enum из SpecialOp
    - *_spec schemas из соответствующих dataclass'ов
    """
    schema = {
        "type": "object",
        "properties": {
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
                        "description": "Конкретные даты: ['2005-05-16', '2003-04-12']"
                    },
                    "years": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Конкретные годы: [2020, 2022, 2024]"
                    },
                    "months": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Месяцы (1-12): [1, 6] для января и июня"
                    },
                    "weekdays": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Дни недели: ['Monday', 'Friday']"
                    },
                    "session": {
                        "type": "string",
                        "enum": [
                            "RTH", "ETH", "OVERNIGHT", "GLOBEX",
                            "ASIAN", "EUROPEAN", "US",
                            "PREMARKET", "POSTMARKET", "MORNING", "AFTERNOON", "LUNCH",
                            "LONDON_OPEN", "NY_OPEN", "NY_CLOSE"
                        ]
                    },
                    "time_start": {
                        "type": "string",
                        "description": "Начало кастомного времени: '06:00:00'"
                    },
                    "time_end": {
                        "type": "string",
                        "description": "Конец кастомного времени: '16:00:00'"
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

    # Добавляем spec schemas для каждого special_op
    for special_op, spec_class in SPECIAL_OP_SPECS.items():
        spec_name = f"{special_op.value}_spec"
        schema["properties"][spec_name] = generate_spec_schema(spec_class)

    return schema


def get_response_schema() -> dict:
    """
    Генерирует полную JSON Schema для ответа Understander.

    Включает query_spec и другие поля.
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
# Утилиты для парсинга spec
# =============================================================================

def get_spec_class_for_op(special_op: SpecialOp) -> type | None:
    """
    Возвращает класс Spec для данного SpecialOp.

    Args:
        special_op: SpecialOp enum value

    Returns:
        Класс (EventTimeSpec, TopNSpec, и т.д.) или None
    """
    return SPECIAL_OP_SPECS.get(special_op)


def get_spec_field_name(special_op: SpecialOp) -> str | None:
    """
    Возвращает имя поля в JSON для данного SpecialOp.

    Args:
        special_op: SpecialOp enum value

    Returns:
        Имя поля ("event_time_spec", "top_n_spec", и т.д.) или None
    """
    if special_op in SPECIAL_OP_SPECS:
        return f"{special_op.value}_spec"
    return None


# =============================================================================
# Для отладки и тестирования
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
