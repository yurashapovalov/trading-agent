# session

<description>
Filter by trading session. Use session names, not time values.
</description>

<templates>
- session = SESSION_NAME
</templates>

<sessions>
- MORNING — morning session
- AFTERNOON — afternoon session
- RTH — regular trading hours
- OVERNIGHT — overnight session
- RTH_OPEN — first hour of RTH
- RTH_CLOSE — last hour of RTH
- ASIAN — Asian session
- EUROPEAN — European session
</sessions>

<examples>
"morning session" → filter: "session = MORNING"
"afternoon" → filter: "session = AFTERNOON"
"regular trading hours" → filter: "session = RTH"
"overnight" → filter: "session = OVERNIGHT"
"at the open" → filter: "session = RTH_OPEN"
"first hour" → filter: "session = RTH_OPEN"
"last hour" → filter: "session = RTH_CLOSE"
</examples>
