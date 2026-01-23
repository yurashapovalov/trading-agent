# price

<description>
Filter by price change or gap. Values in percent.
</description>

<templates>
- change {op} {N}%
- gap {op} {N}%
</templates>

<examples>
"green days" → filter: "change > 0"
"red days" → filter: "change < 0"
"big drop" → filter: "change < -2%"
"small gain" → filter: "change > 0, change < 1%"
"gap up" → filter: "gap > 0"
"gap down over 1%" → filter: "gap < -1%"
"gap up but closed red" → filter: "gap > 0, change < 0"
"gap down but closed green" → filter: "gap < 0, change > 0"
</examples>
