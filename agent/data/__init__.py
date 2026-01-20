"""Data layer — получение и обогащение торговых данных.

Единственная точка доступа к DuckDB.
Логика trading day, сессий, праздников берётся из config/market/instruments.py.

Основные функции:
    get_bars(symbol, period, timeframe) — OHLCV бары любого таймфрейма
    enrich(df) — добавляет вычисляемые поля

Example:
    from agent.data import get_bars, enrich

    df = get_bars("SYMBOL", "2024", timeframe="1D")
    df = enrich(df)

Timeframes:
    "1m"  — минутки (сырые данные)
    "1H"  — часовые
    "1D"  — дневные (с учётом trading day)
    "1W"  — недельные
    "1M"  — месячные
    "RTH" — по сессии (из конфига инструмента)
"""

from agent.data.bars import get_bars
from agent.data.enrich import enrich

__all__ = ["get_bars", "enrich"]
