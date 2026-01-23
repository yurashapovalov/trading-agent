# categorical

<description>
Filter by weekday, session, or event. Values from schema and instrument config.
</description>

<templates>
- weekday: monday, tuesday, wednesday, thursday, friday
- session: from instrument (RTH, ETH, OVERNIGHT, etc.)
- event: from instrument (fomc, nfp, opex, etc.)
</templates>

<examples>
"on mondays" → filter: "monday"
"fridays" → filter: "friday"
"during RTH" → filter: "RTH"
"overnight session" → filter: "OVERNIGHT"
"FOMC days" → filter: "fomc"
"options expiration" → filter: "opex"
"NFP days" → filter: "nfp"
"mondays during RTH" → filter: "monday, RTH"
</examples>
