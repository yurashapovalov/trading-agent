# consecutive

<description>
Filter by consecutive days condition. Red = negative change, green = positive change.
</description>

<templates>
- consecutive red {op} {N}
- consecutive green {op} {N}
</templates>

<examples>
"after 2 red days" → filter: "consecutive red >= 2"
"after 3 consecutive green days" → filter: "consecutive green >= 3"
"after losing streak of 4+" → filter: "consecutive red >= 4"
"following a winning streak" → filter: "consecutive green >= 2"
"after exactly 2 down days" → filter: "consecutive red = 2"
</examples>
