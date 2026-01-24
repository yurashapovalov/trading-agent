# patterns

<description>
Filter by candlestick or price patterns. When did pattern appear, show patterns, find patterns.
See <available_patterns> for full list. Works with all operations: list, count, around, probability.
</description>

<templates>
- Single pattern: hammer, doji, engulfing_bullish, morning_star, inside_bar...
- Multiple patterns: "hammer, shooting_star" (any of these)
- Combined: "doji, monday" (pattern + other filter)
</templates>

<examples>
# List/Count — WHERE semantics (filter rows)
"покажи все doji" → operation: "list", filter: "doji"
"сколько было hammer" → operation: "count", filter: "hammer"
"inside days за 2024" → operation: "list", filter: "inside_bar"
"когда появлялись inside day" → operation: "list", filter: "inside_bar"
"when did doji appear" → operation: "list", filter: "doji"

# Around — EVENT semantics (what happened after)
"что было после engulfing" → operation: "around", filter: "bullish_engulfing"
"после morning star" → operation: "around", filter: "morning_star"

# Probability — CONDITION semantics
"вероятность роста после doji" → operation: "probability", filter: "doji"
"шансы после hammer" → operation: "probability", filter: "hammer"

# Reversal patterns (bullish)
"признаки разворота вверх" → filter: "hammer, morning_star, bullish_engulfing"

# Reversal patterns (bearish)
"признаки разворота вниз" → filter: "shooting_star, evening_star, bearish_engulfing"

# Combined filters
"doji в понедельник" → filter: "doji, monday"
"hammer после gap down" → filter: "hammer, gap < 0"
</examples>
