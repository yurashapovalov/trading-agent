# Understander Agent

**File:** `agent/agents/understander.py`

**Type:** LLM (Gemini 2.0 Flash)

## Purpose

Парсит вопрос пользователя в структурированный Intent.

## Principle

LLM решает ЧТО нужно сделать (какие данные, за какой период, какой паттерн искать).
Код потом решает КАК это сделать.

## Input

```python
{
    "question": "Как NQ вел себя в январе 2024?",
    "chat_history": [...]  # optional
}
```

## Output

```python
{
    "intent": Intent(
        type="data",           # data | pattern | concept | strategy
        symbol="NQ",
        period_start="2024-01-01",
        period_end="2024-01-31",
        granularity="daily",   # period | daily | hourly
        pattern=None,          # PatternDef for type="pattern"
        concept=None,          # str for type="concept"
    )
}
```

## Intent Types

| Type | Когда | Пример вопроса |
|------|-------|----------------|
| `data` | Вопросы про цены/объемы | "Как NQ вел себя в январе?" |
| `pattern` | Поиск паттернов | "Покажи дни когда NQ вырос больше 2%" |
| `concept` | Объяснение концепций | "Что такое MACD?" |
| `strategy` | Бэктест стратегий | (будущее) |

## Granularity

LLM выбирает granularity в зависимости от вопроса:

| Granularity | Когда | Ответ |
|-------------|-------|-------|
| `period` | "За месяц" / "В 2024" | 1 агрегированная строка |
| `daily` | "По дням" / детальный анализ | 1 строка на день |
| `hourly` | "Внутри дня" | 1 строка на час |

## Pattern Detection

Если вопрос про паттерны, Understander возвращает:

```python
Intent(
    type="pattern",
    pattern=PatternDef(
        name="big_move",
        params={"threshold_pct": 2.0, "direction": "up"}
    )
)
```

Доступные паттерны:
- `consecutive_days` - N дней подряд вверх/вниз
- `big_move` - дни с большим изменением (>N%)
- `reversal` - внутридневной разворот
- `gap` - гэп вверх/вниз
- `range_breakout` - пробой диапазона

## Implementation Details

```python
class Understander:
    name = "understander"
    agent_type = "routing"

    def __call__(self, state: AgentState) -> dict:
        question = state.get("question", "")
        intent = self._parse_with_llm(question)
        return {"intent": intent}
```

- Использует Gemini с JSON mode для структурированного вывода
- Промпт в `agent/prompts/understander.py`
- При ошибке возвращает default intent (data, period, last month)
- Максимум 3 попытки уточнения если вопрос непонятен

## Prompt Structure

```xml
<role>
You are a trading data analyst...
</role>

<constraints>
- Only use available patterns
- Default to last month if no period
- Respond in user's language
</constraints>

<capabilities>
{DATA_CAPABILITIES}
</capabilities>

<examples>
Q: "Как NQ вел себя в январе?"
→ type=data, granularity=daily

Q: "Покажи дни когда рост больше 2%"
→ type=pattern, pattern=big_move
</examples>

<task>
{question}
</task>
```
