"""
Common SQL fragments — общие части SQL запросов.

Содержит переиспользуемые фрагменты для избежания дублирования.
Все значения валидируются для защиты от SQL injection.
"""

from agent.query_builder.sql_utils import (
    safe_sql_symbol,
    safe_sql_date,
)

# Название таблицы с минутными данными (единая точка изменения)
OHLCV_TABLE = "ohlcv_1min"


def build_daily_aggregation_sql(symbol: str, period_start: str, period_end: str) -> str:
    """
    Строит SQL для агрегации минуток в дневные бары.

    Это базовый CTE который используется в:
    - daily.py (Source.DAILY)
    - daily_with_prev.py (Source.DAILY_WITH_PREV)

    Все входные данные валидируются для защиты от SQL injection.

    Args:
        symbol: Торговый инструмент
        period_start: Начало периода (YYYY-MM-DD)
        period_end: Конец периода (YYYY-MM-DD)

    Returns:
        SQL для daily_raw CTE (без WITH, без запятой в конце)

    Raises:
        ValidationError: Если входные данные невалидны
    """
    # Валидация и безопасное экранирование
    safe_symbol = safe_sql_symbol(symbol)
    safe_start = safe_sql_date(period_start)
    safe_end = safe_sql_date(period_end)

    return f"""daily_raw AS (
    SELECT
        timestamp::date as date,
        FIRST(open ORDER BY timestamp) as open,
        MAX(high) as high,
        MIN(low) as low,
        LAST(close ORDER BY timestamp) as close,
        SUM(volume) as volume,
        ROUND(MAX(high) - MIN(low), 2) as range,
        ROUND((LAST(close ORDER BY timestamp) - FIRST(open ORDER BY timestamp))
              / NULLIF(FIRST(open ORDER BY timestamp), 0) * 100, 2) as change_pct
    FROM {OHLCV_TABLE}
    WHERE symbol = {safe_symbol}
      AND timestamp >= {safe_start}
      AND timestamp < {safe_end}
    GROUP BY timestamp::date
)"""
