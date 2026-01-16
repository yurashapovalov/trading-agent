"""
Common SQL fragments — общие части SQL запросов.

Содержит переиспользуемые фрагменты для избежания дублирования.
Все значения валидируются для защиты от SQL injection.

Trading Day vs Calendar Day:
    For futures (NQ, ES), trading day != calendar day.
    Example: Tuesday's trading day = Monday 18:00 ET → Tuesday 17:00 ET
    Bars after 18:00 ET belong to NEXT calendar day's trading session.
"""

from agent.query_builder.sql_utils import (
    safe_sql_symbol,
    safe_sql_date,
)
from agent.query_builder.instruments import get_instrument

# Название таблицы с минутными данными (единая точка изменения)
OHLCV_TABLE = "ohlcv_1min"


def get_trading_date_expression(symbol: str) -> str:
    """
    Get SQL expression for trading date calculation.

    For futures, trading day spans from previous evening to current afternoon.
    Bars after trading_day_start (e.g., 18:00 ET) belong to next day's session.

    Args:
        symbol: Instrument symbol

    Returns:
        SQL expression that evaluates to trading date

    Example for NQ:
        Bars before 17:00 ET → same calendar date
        Bars at/after 18:00 ET → calendar date + 1 day
        (17:00-18:00 is maintenance, no bars)
    """
    instrument = get_instrument(symbol)
    if not instrument:
        # Fallback: calendar date
        return "timestamp::date"

    trading_day_end = instrument.get("trading_day_end")
    if not trading_day_end:
        return "timestamp::date"

    # Normalize to HH:MM:SS
    if len(trading_day_end.split(":")) == 2:
        trading_day_end = f"{trading_day_end}:00"

    # For futures: if time < trading_day_end, it's current date
    # if time >= trading_day_start (after maintenance), it's next date
    return f"""CASE
        WHEN timestamp::time < '{trading_day_end}'::time
        THEN timestamp::date
        ELSE timestamp::date + INTERVAL '1 day'
    END"""


def build_daily_aggregation_sql(symbol: str, period_start: str, period_end: str) -> str:
    """
    Строит SQL для агрегации минуток в дневные бары.

    Uses trading_date (not calendar date) for futures instruments.
    This correctly groups bars that belong to the same trading session.

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

    # Get trading date expression for this instrument
    trading_date_expr = get_trading_date_expression(symbol)

    return f"""daily_raw AS (
    SELECT
        ({trading_date_expr})::date as date,
        FIRST(open ORDER BY timestamp) as open,
        MAX(high) as high,
        MIN(low) as low,
        LAST(close ORDER BY timestamp) as close,
        SUM(volume) as volume,
        -- Basic metrics
        ROUND(MAX(high) - MIN(low), 2) as range,
        ROUND((LAST(close ORDER BY timestamp) - FIRST(open ORDER BY timestamp))
              / NULLIF(FIRST(open ORDER BY timestamp), 0) * 100, 2) as change_pct,
        -- Close to extremes
        ROUND(LAST(close ORDER BY timestamp) - MIN(low), 2) as close_to_low,
        ROUND(MAX(high) - LAST(close ORDER BY timestamp), 2) as close_to_high,
        -- Open to extremes
        ROUND(MAX(high) - FIRST(open ORDER BY timestamp), 2) as open_to_high,
        ROUND(FIRST(open ORDER BY timestamp) - MIN(low), 2) as open_to_low,
        -- Candle structure
        ROUND(ABS(LAST(close ORDER BY timestamp) - FIRST(open ORDER BY timestamp)), 2) as body,
        ROUND(MAX(high) - GREATEST(FIRST(open ORDER BY timestamp), LAST(close ORDER BY timestamp)), 2) as upper_wick,
        ROUND(LEAST(FIRST(open ORDER BY timestamp), LAST(close ORDER BY timestamp)) - MIN(low), 2) as lower_wick
    FROM {OHLCV_TABLE}
    WHERE symbol = {safe_symbol}
      AND timestamp >= {safe_start}
      AND timestamp < {safe_end}
    GROUP BY ({trading_date_expr})::date
)"""
