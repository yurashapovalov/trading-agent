# range_volume

<description>
Filter by range (points) or volume. Absolute values or relative to average.
</description>

<templates>
- range {op} {N}
- volume {op} {N}
- range {op} avg
- volume {op} avg
</templates>

<examples>
"high volatility days" → filter: "range > avg"
"low volume days" → filter: "volume < avg"
"range over 100 points" → filter: "range > 100"
"narrow range" → filter: "range < 50"
"high volume" → filter: "volume > avg"
"extremely high volume" → filter: "volume > 2000000"
"quiet days" → filter: "range < avg, volume < avg"
</examples>
