"""
Base classes for Source CTE Builders.

Определяет протокол для всех source builders и registry для их регистрации.
Новый source = создать класс, унаследовать от SourceBuilder, указать source_type.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from agent.query_builder.types import Filters, Source


class SourceBuilder(ABC):
    """
    Базовый класс для всех source CTE builders.

    Для добавления нового источника:
    1. Создать класс, унаследовать от SourceBuilder
    2. Указать source_type = Source.YOUR_TYPE
    3. Реализовать build_cte()

    Example:
        class WeeklySourceBuilder(SourceBuilder):
            source_type = Source.WEEKLY

            def build_cte(self, symbol, filters, extra_sql=""):
                return "WITH weekly AS (...) SELECT"
    """

    # Какой Source enum этот builder обрабатывает
    source_type: ClassVar["Source"]

    @abstractmethod
    def build_cte(
        self,
        symbol: str,
        filters: "Filters",
        extra_filters_sql: str = ""
    ) -> str:
        """
        Строит CTE для данного источника.

        Args:
            symbol: Торговый инструмент (NQ, ES)
            filters: Объект Filters
            extra_filters_sql: Дополнительные SQL фильтры

        Returns:
            WITH ... AS (...) SELECT часть SQL
        """
        pass

    @property
    def cte_name(self) -> str:
        """Имя CTE для FROM clause."""
        return self.source_type.value


# =============================================================================
# Registry — автоматическая регистрация builders
# =============================================================================

class SourceRegistry:
    """
    Registry для source builders.

    Автоматически собирает все подклассы SourceBuilder.
    """

    _builders: dict["Source", type[SourceBuilder]] = {}

    @classmethod
    def register(cls, builder_class: type[SourceBuilder]) -> type[SourceBuilder]:
        """
        Декоратор для регистрации builder'а.

        Usage:
            @SourceRegistry.register
            class MinutesSourceBuilder(SourceBuilder):
                source_type = Source.MINUTES
                ...
        """
        cls._builders[builder_class.source_type] = builder_class
        return builder_class

    @classmethod
    def get(cls, source: "Source") -> SourceBuilder | None:
        """
        Получает builder для указанного source.

        Args:
            source: Source enum

        Returns:
            Инстанс соответствующего builder'а или None если не найден
        """
        if source not in cls._builders:
            return None
        return cls._builders[source]()

    @classmethod
    def get_or_raise(cls, source: "Source") -> SourceBuilder:
        """
        Получает builder или кидает исключение.

        Используется когда отсутствие builder'а — ошибка.
        """
        builder = cls.get(source)
        if builder is None:
            registered = list(cls._builders.keys())
            raise KeyError(
                f"No builder registered for {source}. "
                f"Registered: {registered}"
            )
        return builder

    @classmethod
    def list_registered(cls) -> list["Source"]:
        """Возвращает список зарегистрированных источников."""
        return list(cls._builders.keys())
