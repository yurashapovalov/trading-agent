"""
Special Operations Builders — сложные SQL запросы.

Использование Registry:
    from agent.query_builder.special_ops import SpecialOpRegistry

    builder = SpecialOpRegistry.get(SpecialOp.EVENT_TIME)
    if builder:
        sql = builder.build_query(spec, extra_filters)

Добавление новой операции:
    1. Создать файл в special_ops/
    2. Унаследовать от SpecialOpBuilder
    3. Добавить декоратор @SpecialOpRegistry.register
    4. Указать op_type = SpecialOp.YOUR_TYPE
"""

from .base import SpecialOpBuilder, SpecialOpRegistry

# Импортируем builders чтобы они зарегистрировались
from .event_time import EventTimeOpBuilder, build_event_time_query
from .top_n import TopNOpBuilder, apply_top_n_to_spec
from .find_extremum import FindExtremumOpBuilder
from .compare import CompareOpBuilder

__all__ = [
    # Base
    "SpecialOpBuilder",
    "SpecialOpRegistry",
    # Builders
    "EventTimeOpBuilder",
    "TopNOpBuilder",
    "FindExtremumOpBuilder",
    "CompareOpBuilder",
    # Functions
    "build_event_time_query",
    "apply_top_n_to_spec",
]
