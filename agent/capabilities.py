"""
System capabilities configuration.

Defines what the system can and cannot do.
Understander reads this to know available features.
"""

from agent.modules.patterns import PATTERN_DESCRIPTIONS


# =============================================================================
# Data Granularities
# =============================================================================

GRANULARITIES = {
    "period": "Агрегированная статистика за весь период (одна строка)",
    "daily": "Данные по дням (OHLCV + change% для каждого дня)",
    "hourly": "Данные по часам (средние значения для каждого часа)",
}


# =============================================================================
# Trading Sessions (for time-of-day filtering)
# =============================================================================

TRADING_SESSIONS = {
    "RTH": {
        "name": "Regular Trading Hours",
        "description": "Основная торговая сессия",
        "hours": "09:30-16:00 ET",
        "sql_filter": "timestamp::time BETWEEN '09:30:00' AND '16:00:00'",
    },
    "ETH": {
        "name": "Extended Trading Hours",
        "description": "Электронная сессия (до и после RTH)",
        "hours": "Всё кроме 09:30-16:00",
        "sql_filter": "timestamp::time NOT BETWEEN '09:30:00' AND '16:00:00'",
    },
    "OVERNIGHT": {
        "name": "Overnight Session",
        "description": "Ночная сессия",
        "hours": "18:00-09:30 ET",
        "sql_filter": "timestamp::time >= '18:00:00' OR timestamp::time < '09:30:00'",
    },
}


# =============================================================================
# Patterns (for complex queries)
# =============================================================================

PATTERNS = PATTERN_DESCRIPTIONS  # Imported from patterns module


# =============================================================================
# Future Capabilities (not yet implemented)
# =============================================================================

FUTURE_CAPABILITIES = {
    "backtest": "Бэктестинг торговых стратегий",
    "rsi": "Индикатор RSI",
    "macd": "Индикатор MACD",
    "bollinger": "Полосы Боллинджера",
}


# =============================================================================
# Supported Symbols
# =============================================================================

SUPPORTED_SYMBOLS = ["NQ"]  # Currently only NQ has data

DEFAULT_SYMBOL = "NQ"
DEFAULT_GRANULARITY = "daily"


# =============================================================================
# Helper Functions
# =============================================================================

def get_capabilities_prompt() -> str:
    """
    Generate capabilities description for LLM prompt.

    Used by Understander to know what's available.
    """
    lines = [
        "## Возможности системы",
        "",
        "### Данные",
        f"Символы: {', '.join(SUPPORTED_SYMBOLS)}",
        "Данные: минутные свечи (OHLCV) 24 часа в сутки",
        "",
        "### Гранулярность (type='data'):",
    ]

    for name, desc in GRANULARITIES.items():
        lines.append(f"- {name}: {desc}")

    lines.append("")
    lines.append("### Торговые сессии (можно фильтровать по времени дня):")
    for name, info in TRADING_SESSIONS.items():
        lines.append(f"- {name}: {info['description']} ({info['hours']})")

    lines.append("")
    lines.append("### Паттерны (type='pattern'):")
    for name, info in PATTERNS.items():
        lines.append(f"- {name}: {info['description']}")
        lines.append(f"  Параметры: {info['params']}")
        lines.append(f"  Примеры: {', '.join(info['examples'][:2])}")

    lines.append("")
    lines.append("### В разработке:")
    for name, desc in FUTURE_CAPABILITIES.items():
        lines.append(f"- {name}: {desc}")

    return "\n".join(lines)


def is_valid_granularity(granularity: str) -> bool:
    """Check if granularity is valid."""
    return granularity in GRANULARITIES


def is_valid_pattern(pattern: str) -> bool:
    """Check if pattern is valid."""
    return pattern in PATTERNS


def is_valid_symbol(symbol: str) -> bool:
    """Check if symbol is supported."""
    return symbol in SUPPORTED_SYMBOLS
