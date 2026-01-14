"""
Common SQL fragments — общие части SQL запросов.

Содержит переиспользуемые фрагменты для избежания дублирования.
"""

# Название таблицы с минутными данными (единая точка изменения)
OHLCV_TABLE = "ohlcv_1min"


def build_daily_aggregation_sql(symbol: str, period_start: str, period_end: str) -> str:
    """
    Строит SQL для агрегации минуток в дневные бары.

    Это базовый CTE который используется в:
    - daily.py (Source.DAILY)
    - daily_with_prev.py (Source.DAILY_WITH_PREV)

    Args:
        symbol: Торговый инструмент
        period_start: Начало периода (YYYY-MM-DD)
        period_end: Конец периода (YYYY-MM-DD)

    Returns:
        SQL для daily_raw CTE (без WITH, без запятой в конце)
    """
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
    WHERE symbol = '{symbol}'
      AND timestamp >= '{period_start}'
      AND timestamp < '{period_end}'
    GROUP BY timestamp::date
)"""
