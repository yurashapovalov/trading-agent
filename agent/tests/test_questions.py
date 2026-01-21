"""
Test questions for Parser and RAP testing.

Categorized by complexity and type.
"""

# =============================================================================
# Basic Questions
# =============================================================================

BASIC = [
    "Статистика по пятницам 2020-2025 где close - low >= 200",
    "What happened on May 16, 2024?",
    "When is high usually formed?",
    "Top 10 volatile days in 2024",
    "RTH vs ETH range",
    "Привет",
    "What is gap?",
    "Покажи волатильность по месяцам за 2024",
    "Дни когда упали больше 2%",
]

# =============================================================================
# Strategy / Edge Questions (complex)
# =============================================================================

STRATEGY = [
    "Что происходит на следующий день после gap up больше 1%?",
    "Какой средний range в понедельник после пятницы с range > 400?",
    "Как часто high формируется в первый час RTH?",
    "Статистика дней когда overnight high был пробит в RTH",
    "Сравни дни когда открылись выше prev close vs ниже",
    "В какое время чаще всего формируется low если день закрылся в плюс?",
    "Какой win rate у стратегии: вход на открытии если gap down > 0.5%, выход на close?",
    "Средний размер отката от high до close в трендовые дни (change > 1%)",
    "Дни когда range первого часа был больше 50% дневного range",
    "Корреляция между размером gap и дневным range",
    "Сколько раз за 2024 цена закрылась выше high предыдущего дня?",
    "Какой процент дней low формируется после 14:00?",
    "Статистика по дням после 3+ дней роста подряд",
    "RTH range в дни экспирации опционов vs обычные пятницы",
]

# =============================================================================
# By Category (for RAP chunk testing)
# =============================================================================

# Period - relative
PERIOD_RELATIVE = [
    "volatility yesterday",
    "what was the range last week",
    "stats for last 30 days",
    "YTD performance",
    "show me MTD volume",
    "how was last month",
]

# Period - absolute
PERIOD_ABSOLUTE = [
    "volatility for 2024",
    "how was January 2024",
    "stats for Q1 2024",
    "what happened on May 15, 2024",
    "compare 2023 and 2024",
    "range from January to March 2024",
]

# Metrics
METRICS = [
    "what was the volatility in 2024",
    "average daily range for January 2024",
    "total volume last week",
    "return for 2024",
    "how many green days in 2024",
    "biggest gaps in January 2024",
]

# Operations
OPERATIONS = [
    "average range for 2024",
    "compare January and February 2024",
    "top 10 days by volume in 2024",
    "worst days in January 2024",
    "volatility by weekday for 2024",
    "hourly breakdown of volume",
    "find days with range over 300",
    "longest green streak in 2024",
]

# Filters
FILTERS = [
    "volatility on Fridays in 2024",
    "Monday vs Friday performance",
    "RTH volume for January 2024",
    "compare RTH and overnight",
    "OPEX day stats for 2024",
    "how volatile are FOMC days",
    "days with range over 300 points",
    "first trading hour stats",
]

# Unclear (should trigger clarification)
UNCLEAR = [
    "stats for January",          # missing year
    "show volatility",            # missing period
    "how was December",           # missing year, metric
    "top 5 days",                 # missing period, metric
    "what happened on May 15",    # missing year
    "show me the data",           # missing period, metric
    "compare January and February", # missing year
]

# Chitchat
CHITCHAT = [
    "привет",
    "hello",
    "thanks",
    "спасибо",
    "bye",
]

# Concept
CONCEPT = [
    "what is OPEX",
    "что такое gap",
    "explain RTH",
    "what is volatility",
]

# =============================================================================
# Advanced Test Cases
# =============================================================================

# 1. Multi-step calculations
MULTI_STEP = [
    "Сравни среднюю волатильность понедельников и пятниц в 2024 году. В какой день недели лучше торговать?",
    "Найди топ-5 дней с максимальным объёмом в 2024, и посчитай средний change_pct для этих дней",
]

# 2. Complex patterns
COMPLEX_PATTERNS = [
    "Найди дни когда NQ упал больше 2% после роста больше 1% в предыдущий день",
    "Сколько раз в 2024 году было 3+ красных дня подряд?",
]

# 3. Time comparisons & seasonality
SEASONALITY = [
    "Как NQ вёл себя в декабре за последние 3 года?",
    "В какой месяц года NQ исторически растёт лучше всего?",
    "Есть ли сезонность в волатильности NQ по месяцам?",
    "Какой день недели исторически самый волатильный для NQ?",
    "Понедельники vs пятницы — где больше гэпов?",
    "Коррелирует ли волатильность января с годовой доходностью?",
    "Если Q1 был красным, какой обычно Q2?",
]

# 4. Tricky questions
TRICKY = [
    "Какой был максимальный внутридневной диапазон (high-low) в процентах за 2024?",
    "В какое время суток NQ чаще всего достигает дневного максимума?",  # requires minute data
]

# 5. Context chains (multi-turn)
CONTEXT_CHAINS = [
    # Chain 1
    ["Покажи статистику за март 2024", "А теперь сравни с апрелем", "Какой месяц был лучше для лонгов?"],
    # Chain 2
    ["Отдели время электронной сессии от основной", "Сопоставь волатильность и объёмы"],
]

# 6. Edge cases / Should fail gracefully
EDGE_CASES = [
    "Посчитай корреляцию между объёмом и изменением цены",
    "Сделай прогноз на завтра",  # should refuse
    "А что по ES?",  # different instrument
]

# =============================================================================
# All questions
# =============================================================================

ALL = BASIC + STRATEGY + MULTI_STEP + COMPLEX_PATTERNS + SEASONALITY + TRICKY + EDGE_CASES

# For RAP testing - questions mapped to expected chunks
RAP_TEST_CASES = [
    # (question, expected_chunks)
    ("volatility yesterday", ["relative", "metrics"]),
    ("stats for 2024", ["absolute", "operations", "unclear"]),
    ("top 10 days by volume in 2024", ["absolute", "metrics", "operations"]),
    ("OPEX day stats for 2024", ["absolute", "filters", "operations"]),
    ("compare RTH and ETH", ["filters", "operations"]),
    ("show me the data", ["unclear"]),
    ("volatility by weekday for 2024", ["absolute", "metrics", "operations"]),
]
