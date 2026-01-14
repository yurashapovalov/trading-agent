"""
Grouping Builders — генерация GROUP BY и связанных колонок.

Отвечает за:
- SELECT колонки для группировки (год, месяц, день недели, etc.)
- GROUP BY выражения
- ORDER BY для сгруппированных результатов
"""

from .builders import (
    get_grouping_column,
    get_grouping_expression,
)

__all__ = [
    "get_grouping_column",
    "get_grouping_expression",
]
