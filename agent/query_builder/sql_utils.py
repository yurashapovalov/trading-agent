"""SQL utilities for safe query building.

Provides validation and escaping functions to prevent SQL injection:
- validate_*() functions check input format
- safe_sql_*() functions return escaped SQL literals

SQL Injection Protection:
1. All strings validated before use in SQL
2. Column names checked against whitelist
3. Strings escaped via safe_sql_string()

Example:
    symbol = safe_sql_symbol("NQ")  # "'NQ'"
    date = safe_sql_date("2024-01-15")  # "'2024-01-15'"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


# =============================================================================
# Validation Patterns
# =============================================================================

# ISO date: YYYY-MM-DD
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Time: HH:MM:SS
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}:\d{2}$")

# Symbol: uppercase letters and numbers (NQ, ES, CL, etc.)
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{1,10}$")

# Valid weekday names
VALID_WEEKDAYS = frozenset([
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
    "Saturday", "Sunday"
])

# Valid column names (whitelist)
VALID_COLUMNS = frozenset([
    "date", "timestamp", "open", "high", "low", "close", "volume",
    "range", "change_pct", "gap_pct", "prev_close", "prev_change_pct",
    "time_bucket", "frequency", "percentage", "event_type",
    "high_time", "low_time", "high_value", "low_value",
])


# =============================================================================
# Parameterized Query
# =============================================================================

@dataclass
class ParameterizedQuery:
    """
    SQL запрос с параметрами для безопасного выполнения.

    Attributes:
        sql: SQL template с placeholders ($1, $2, ...)
        params: Список значений для placeholders

    Example:
        query = ParameterizedQuery(
            sql="SELECT * FROM t WHERE symbol = $1 AND date >= $2",
            params=["NQ", "2024-01-01"]
        )
        conn.execute(query.sql, query.params)
    """

    sql: str
    params: list[Any]

    def to_raw_sql(self) -> str:
        """
        Для отладки: возвращает SQL с подставленными значениями.

        WARNING: Не использовать для выполнения! Только для логов.
        """
        result = self.sql
        for i, param in enumerate(self.params, 1):
            placeholder = f"${i}"
            if isinstance(param, str):
                value = f"'{param}'"
            else:
                value = str(param)
            result = result.replace(placeholder, value, 1)
        return result


# =============================================================================
# Validation Functions
# =============================================================================

class ValidationError(ValueError):
    """Ошибка валидации входных данных для SQL."""
    pass


def validate_date(value: str, field_name: str = "date") -> str:
    """
    Валидирует ISO дату (YYYY-MM-DD).

    Args:
        value: Строка с датой
        field_name: Имя поля для сообщения об ошибке

    Returns:
        Валидная дата

    Raises:
        ValidationError: Если формат неверный
    """
    if not DATE_PATTERN.match(value):
        raise ValidationError(
            f"Invalid {field_name}: '{value}'. Expected format: YYYY-MM-DD"
        )
    return value


def validate_time(value: str, field_name: str = "time") -> str:
    """
    Валидирует время (HH:MM:SS).

    Args:
        value: Строка со временем
        field_name: Имя поля для сообщения об ошибке

    Returns:
        Валидное время

    Raises:
        ValidationError: Если формат неверный
    """
    if not TIME_PATTERN.match(value):
        raise ValidationError(
            f"Invalid {field_name}: '{value}'. Expected format: HH:MM:SS"
        )
    return value


def validate_symbol(value: str) -> str:
    """
    Валидирует торговый символ.

    Args:
        value: Строка с символом

    Returns:
        Валидный символ (uppercase)

    Raises:
        ValidationError: Если символ невалидный
    """
    upper_value = value.upper()
    if not SYMBOL_PATTERN.match(upper_value):
        raise ValidationError(
            f"Invalid symbol: '{value}'. "
            "Expected: 1-10 uppercase letters/numbers"
        )
    return upper_value


def validate_weekday(value: str) -> str:
    """
    Валидирует день недели.

    Args:
        value: Название дня (Monday, Tuesday, etc.)

    Returns:
        Валидный день

    Raises:
        ValidationError: Если день неизвестен
    """
    if value not in VALID_WEEKDAYS:
        raise ValidationError(
            f"Invalid weekday: '{value}'. "
            f"Expected one of: {', '.join(sorted(VALID_WEEKDAYS))}"
        )
    return value


def validate_column(value: str) -> str:
    """
    Валидирует имя колонки.

    Args:
        value: Имя колонки

    Returns:
        Валидное имя

    Raises:
        ValidationError: Если колонка неизвестна
    """
    if value not in VALID_COLUMNS:
        raise ValidationError(
            f"Invalid column: '{value}'. "
            f"Expected one of: {', '.join(sorted(VALID_COLUMNS))}"
        )
    return value


def validate_integer(value: Any, field_name: str = "value") -> int:
    """
    Валидирует целое число.

    Args:
        value: Значение для проверки
        field_name: Имя поля для сообщения об ошибке

    Returns:
        Целое число

    Raises:
        ValidationError: Если значение не число
    """
    try:
        return int(value)
    except (TypeError, ValueError) as e:
        raise ValidationError(
            f"Invalid {field_name}: '{value}'. Expected integer."
        ) from e


def validate_month(value: Any) -> int:
    """Валидирует номер месяца (1-12)."""
    month = validate_integer(value, "month")
    if not 1 <= month <= 12:
        raise ValidationError(
            f"Invalid month: {month}. Expected 1-12."
        )
    return month


def validate_year(value: Any) -> int:
    """Валидирует год (1900-2100)."""
    year = validate_integer(value, "year")
    if not 1900 <= year <= 2100:
        raise ValidationError(
            f"Invalid year: {year}. Expected 1900-2100."
        )
    return year


# =============================================================================
# SQL Safe String
# =============================================================================

def safe_sql_string(value: str) -> str:
    """
    Безопасно экранирует строку для SQL.

    Заменяет одинарные кавычки на двойные (SQL standard escaping).

    Args:
        value: Исходная строка

    Returns:
        Экранированная строка (без кавычек вокруг)

    Example:
        >>> safe_sql_string("O'Connor")
        "O''Connor"

        Используется как:
        f"WHERE name = '{safe_sql_string(name)}'"
    """
    return value.replace("'", "''")


def safe_sql_literal(value: str) -> str:
    """
    Возвращает безопасный SQL литерал с кавычками.

    Args:
        value: Строка

    Returns:
        SQL литерал: 'escaped_value'

    Example:
        >>> safe_sql_literal("O'Connor")
        "'O''Connor'"
    """
    return f"'{safe_sql_string(value)}'"


def safe_sql_date(value: str) -> str:
    """
    Валидирует дату и возвращает SQL литерал.

    Args:
        value: Дата в формате YYYY-MM-DD

    Returns:
        SQL литерал: '2024-01-15'

    Raises:
        ValidationError: Если дата невалидна
    """
    validated = validate_date(value)
    return f"'{validated}'"


def safe_sql_time(value: str) -> str:
    """
    Валидирует время и возвращает SQL литерал.

    Args:
        value: Время в формате HH:MM:SS

    Returns:
        SQL литерал: '09:30:00'

    Raises:
        ValidationError: Если время невалидно
    """
    validated = validate_time(value)
    return f"'{validated}'"


def safe_sql_symbol(value: str) -> str:
    """
    Валидирует символ и возвращает SQL литерал.

    Args:
        value: Торговый символ

    Returns:
        SQL литерал: 'NQ'

    Raises:
        ValidationError: Если символ невалидный
    """
    validated = validate_symbol(value)
    return f"'{validated}'"


# =============================================================================
# SQL List Builders
# =============================================================================

def safe_sql_date_list(dates: list[str]) -> str:
    """
    Строит SQL IN список из валидированных дат.

    Args:
        dates: Список дат в формате YYYY-MM-DD

    Returns:
        SQL: '2024-01-01', '2024-01-02', '2024-01-03'

    Raises:
        ValidationError: Если какая-то дата невалидна
    """
    validated = [validate_date(d) for d in dates]
    return ", ".join(f"'{d}'" for d in validated)


def safe_sql_weekday_list(weekdays: list[str]) -> str:
    """
    Строит SQL IN список из валидированных дней недели.

    Args:
        weekdays: Список дней ['Monday', 'Friday']

    Returns:
        SQL: 'Monday', 'Friday'

    Raises:
        ValidationError: Если какой-то день невалиден
    """
    validated = [validate_weekday(d) for d in weekdays]
    return ", ".join(f"'{d}'" for d in validated)


def safe_sql_int_list(values: list[Any], field_name: str = "value") -> str:
    """
    Строит SQL IN список из валидированных целых чисел.

    Args:
        values: Список значений
        field_name: Имя поля для сообщений об ошибках

    Returns:
        SQL: 1, 2, 3

    Raises:
        ValidationError: Если какое-то значение не число
    """
    validated = [validate_integer(v, field_name) for v in values]
    return ", ".join(str(v) for v in validated)
