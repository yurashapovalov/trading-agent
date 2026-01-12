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
        "",
        "### Гранулярность (type='data'):",
    ]

    for name, desc in GRANULARITIES.items():
        lines.append(f"- {name}: {desc}")

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
