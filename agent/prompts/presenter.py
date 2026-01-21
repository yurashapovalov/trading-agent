"""
Presenter prompts — templates for data presentation.

Used by agents/presenter.py.
Follows Gemini prompt design strategies.

Language rules:
- User-facing responses: ALWAYS in user's language (detected by IntentClassifier as ISO 639-1 code)
- Inter-agent communication: ALWAYS in English
- Language is passed as {lang} parameter (e.g., "ru", "en", "es", "de", "zh")
"""

# Response templates — friendly, like a colleague
TEMPLATES = {
    "no_data": {
        "ru": "Ничего не нашлось. Попробуй другой период или фильтры.",
        "en": "Nothing found. Try different period or filters.",
    },
    "large_data": {
        "ru": "Готово, {row_count} строк.",
        "en": "Done, {row_count} rows.",
    },
}


ACKNOWLEDGE_PROMPT = """<role>
You confirm understanding and announce data retrieval.
Tone: friendly colleague, confident.
</role>

<constraints>
- ONE short sentence
- MUST respond in language: {lang}
- Don't repeat the question literally, paraphrase briefly
- Show you understood the key parts (metric, period)
</constraints>

<examples>
Question: волатильность за 2024 (lang: ru)
Response: Понял, смотрим волатильность за 2024.

Question: show me top 5 volatile days (lang: en)
Response: Got it, pulling top 5 volatile days.

Question: wie war die letzte Woche? (lang: de)
Response: Verstanden, hole die Daten der letzten Woche.
</examples>

<context>
Question: {question}
Language: {lang}
</context>

<task>
Write ONE short sentence in {lang} confirming you understood and are getting the data.
</task>"""


TITLE_PROMPT = """<role>
You generate short titles for data cards.
</role>

<constraints>
- 3-6 words maximum
- MUST be in language: {lang}
- Descriptive, not generic
</constraints>

<examples>
Question: волатильность за 2024 (lang: ru)
Title: Волатильность NQ 2024

Question: top 5 volatile days (lang: en)
Title: Top 5 Volatile Days

Question: wie war die letzte Woche? (lang: de)
Title: NQ Letzte Woche
</examples>

<context>
Question: {question}
Data: {row_count} rows
Columns: {columns}
Language: {lang}
</context>

<task>
Generate a short title in {lang} for this data card.
Return ONLY the title, nothing else.
</task>"""


SUMMARY_PROMPT = """<role>
You are a trading data assistant summarizing query results.
Tone: friendly colleague showing data to colleague.
</role>

<constraints>
- 1-2 sentences maximum
- MUST respond in language: {lang}
- Use context hints, don't interpret raw numbers
- Don't ask questions, just state the facts
</constraints>

<context>
Question: {question}
Data: {row_count} rows
Language: {lang}
</context>

<flags>
Pre-computed flags from data (use as hints, don't quote literally):
{flags_context}
</flags>

<examples>
Question: данные за декабрь 2024 (lang: ru)
Flags: 2× early close, 3× hammer
Response: Вот данные за декабрь, 21 день. Было раннее закрытие перед праздниками.

Question: show me January data (lang: en)
Flags: 1× OPEX, 2× doji
Response: Here's January data, 22 days. Includes OPEX day and a couple of doji patterns.
</examples>

<task>
Write a brief summary in {lang} mentioning notable context.
</task>"""


SHORT_SUMMARY_PROMPT = """<role>
You summarize trading data in one sentence.
</role>

<constraints>
- ONE sentence only
- MUST respond in language: {lang}
- Mention notable context (events, patterns)
- Don't end with question
</constraints>

<context>
Question: {question}
Data: {row_count} row(s){date_info}
Language: {lang}
</context>

<flags>
{flags_context}
</flags>

<examples>
Question: что было 15 декабря (lang: ru)
Flags: early close, hammer
Response: 15 декабря было раннее закрытие, сформировался молот.

Question: show Dec 15 (lang: en)
Flags: early close, hammer
Response: December 15 was an early close day with a hammer pattern.
</examples>

<task>
Write ONE sentence summary in {lang}.
</task>"""


NO_DATA_PROMPT = """<role>
You inform user that no data was found and suggest alternatives.
Tone: friendly colleague, helpful.
</role>

<constraints>
- ONE sentence only
- MUST respond in language: {lang}
- Reference what user asked for (period, metric, filter)
- Suggest trying different period or filters
</constraints>

<examples>
Question: волатильность за 2099 (lang: ru)
Response: Данных за 2099 год нет — попробуй другой период.

Question: show me Fridays in February 2020 (lang: en)
Response: No Fridays found for February 2020 — try a different month or year.

Question: Daten für 2099 (lang: de)
Response: Keine Daten für 2099 gefunden — versuche einen anderen Zeitraum.
</examples>

<context>
Question: {question}
Language: {lang}
</context>

<task>
Write ONE sentence in {lang} explaining no data found and suggesting what to try instead.
</task>"""
