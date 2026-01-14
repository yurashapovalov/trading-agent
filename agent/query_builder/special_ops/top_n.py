"""
Top N Operation Builder — получение топ N записей.

Отвечает на вопросы:
- "10 самых волатильных дней"
- "Топ 5 дней по объёму"
- "Крупнейшие падения за год"

Note:
    TOP_N реализован через модификацию QuerySpec,
    а не как отдельный SQL шаблон. Это позволяет
    переиспользовать стандартный query builder.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.query_builder.types import QuerySpec

from agent.query_builder.types import SpecialOp
from .base import SpecialOpBuilder, SpecialOpRegistry


@SpecialOpRegistry.register
class TopNOpBuilder(SpecialOpBuilder):
    """
    Builder для SpecialOp.TOP_N.

    Особенность: не генерирует свой SQL шаблон,
    а модифицирует QuerySpec и возвращает маркер
    для использования стандартного builder'а.
    """

    op_type = SpecialOp.TOP_N

    def build_query(
        self,
        spec: "QuerySpec",
        extra_filters_sql: str = ""
    ) -> str:
        """
        TOP_N не генерирует SQL напрямую.

        Возвращает специальный маркер — вызывающий код
        должен вызвать apply_top_n_to_spec() и использовать
        стандартный builder.

        Raises:
            NotImplementedError: TOP_N требует особой обработки
        """
        raise NotImplementedError(
            "TOP_N requires special handling. "
            "Use apply_top_n_to_spec() and standard builder."
        )

    @staticmethod
    def transform_spec(spec: "QuerySpec") -> "QuerySpec":
        """Трансформирует spec для стандартного builder'а."""
        return apply_top_n_to_spec(spec)


def apply_top_n_to_spec(spec: "QuerySpec") -> "QuerySpec":
    """
    Применяет TOP_N параметры к спецификации.

    Создаёт новый QuerySpec с order_by, order_direction и limit
    из top_n_spec. special_op устанавливается в NONE чтобы
    использовать стандартный builder.

    Args:
        spec: Оригинальная спецификация с top_n_spec

    Returns:
        Новая спецификация для стандартного билдера
    """
    from agent.query_builder.types import QuerySpec, SpecialOp

    top_n = spec.top_n_spec

    return QuerySpec(
        symbol=spec.symbol,
        source=spec.source,
        filters=spec.filters,
        grouping=spec.grouping,
        metrics=spec.metrics,
        special_op=SpecialOp.NONE,
        order_by=top_n.order_by,
        order_direction=top_n.direction,
        limit=top_n.n,
    )
