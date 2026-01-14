"""
Base classes for Special Operation Builders.

Определяет протокол для всех special_op builders и registry.
Новый special_op = создать класс, унаследовать, указать op_type.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from agent.query_builder.types import QuerySpec, SpecialOp


class SpecialOpBuilder(ABC):
    """
    Базовый класс для всех special operation builders.

    Для добавления новой операции:
    1. Создать класс, унаследовать от SpecialOpBuilder
    2. Указать op_type = SpecialOp.YOUR_TYPE
    3. Реализовать build_query()

    Example:
        class CompareOpBuilder(SpecialOpBuilder):
            op_type = SpecialOp.COMPARE

            def build_query(self, spec, extra_filters_sql):
                return "SELECT ... COMPARE ..."
    """

    # Какой SpecialOp этот builder обрабатывает
    op_type: ClassVar["SpecialOp"]

    @abstractmethod
    def build_query(
        self,
        spec: "QuerySpec",
        extra_filters_sql: str = ""
    ) -> str:
        """
        Строит полный SQL запрос для данной операции.

        Args:
            spec: Спецификация запроса
            extra_filters_sql: Дополнительные SQL фильтры

        Returns:
            Полный SQL запрос
        """
        pass


# =============================================================================
# Registry
# =============================================================================

class SpecialOpRegistry:
    """Registry для special operation builders."""

    _builders: dict["SpecialOp", type[SpecialOpBuilder]] = {}

    @classmethod
    def register(cls, builder_class: type[SpecialOpBuilder]) -> type[SpecialOpBuilder]:
        """Декоратор для регистрации builder'а."""
        cls._builders[builder_class.op_type] = builder_class
        return builder_class

    @classmethod
    def get(cls, op: "SpecialOp") -> SpecialOpBuilder | None:
        """
        Получает builder для операции или None если не найден.

        Returns None для SpecialOp.NONE — это не ошибка,
        просто означает использовать стандартный query builder.
        """
        if op not in cls._builders:
            return None
        return cls._builders[op]()

    @classmethod
    def get_or_raise(cls, op: "SpecialOp") -> SpecialOpBuilder:
        """
        Получает builder или кидает исключение.

        Используется когда отсутствие builder'а — ошибка.
        """
        builder = cls.get(op)
        if builder is None:
            registered = list(cls._builders.keys())
            raise KeyError(
                f"No builder registered for {op}. "
                f"Registered: {registered}"
            )
        return builder

    @classmethod
    def has(cls, op: "SpecialOp") -> bool:
        """Проверяет, зарегистрирован ли builder для операции."""
        return op in cls._builders

    @classmethod
    def list_registered(cls) -> list["SpecialOp"]:
        """Возвращает список зарегистрированных операций."""
        return list(cls._builders.keys())
