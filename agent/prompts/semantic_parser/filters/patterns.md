# patterns

<description>
Filter by candlestick or price patterns.
</description>

<templates>
- inside_day
- outside_day
- doji
- gap_fill
- higher_high
- lower_low
</templates>

<examples>
"inside days" → filter: "inside_day"
"outside days" → filter: "outside_day"
"doji candles" → filter: "doji"
"when gap filled" → filter: "gap_fill"
"new highs" → filter: "higher_high"
"new lows" → filter: "lower_low"
"inside day after gap up" → filter: "inside_day, gap > 0"
"outside day on high volume" → filter: "outside_day, volume > avg"
</examples>
