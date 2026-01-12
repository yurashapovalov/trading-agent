# Understander Agent

**File:** `agent/agents/understander.py`

**Type:** LLM (Gemini 2.5 Flash Lite)

## Purpose

Парсит вопрос пользователя в структурированный Intent.

## Principle

LLM решает ЧТО нужно сделать (какие данные, за какой период, есть ли условие поиска).
Следующие агенты решают КАК это сделать:
- SQL Agent генерирует SQL запрос
- DataFetcher выполняет запрос
- Analyst анализирует результат

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
        type="data",           # data | concept | chitchat | out_of_scope
        symbol="NQ",
        period_start="2024-01-01",
        period_end="2024-01-31",
        granularity="daily",   # period | daily | hourly | weekday | monthly
        search_condition=None, # or "days where change_pct < -2%"
    )
}
```

## Intent Types

| Type | Когда | Пример вопроса |
|------|-------|----------------|
| `data` | Вопросы про данные или поиск | "Как NQ в январе?", "Найди падения >2%" |
| `concept` | Объяснение концепций | "Что такое MACD?" |
| `chitchat` | Приветствия, благодарности | "Привет!", "Спасибо!" |
| `out_of_scope` | Не про трейдинг | "Какая погода?" |

## Granularity

LLM выбирает granularity в зависимости от вопроса:

| Granularity | Когда | Ответ |
|-------------|-------|-------|
| `period` | "За месяц" / общая статистика | 1 агрегированная строка |
| `daily` | "По дням" / поиск паттернов | 1 строка на день |
| `hourly` | "По часам" / внутридневной профиль | 1 строка на час |
| `weekday` | "По дням недели" | 1 строка на день недели |
| `monthly` | "По месяцам" | 1 строка на месяц |

## Search Queries

Для поисковых запросов ("найди", "когда", "покажи дни где..."):

```python
Intent(
    type="data",
    granularity="daily",  # всегда daily для поиска
    search_condition="days where change_pct < -2% AND previous day change_pct > +1%"
)
```

- `search_condition` - описание условия на natural language
- SQL Agent конвертирует это в SQL запрос
- DataFetcher выполняет SQL и возвращает отфильтрованные данные
- Analyst анализирует результат

**Важно:** Understander только описывает ЧТО искать. SQL Agent решает КАК это выразить в SQL.

## Period Defaults

- Если период указан → используем его
- Если период НЕ указан:
  - Для поиска (search_condition есть) → ВСЕ доступные данные
  - Для обычных запросов → последний месяц

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
- При ошибке возвращает default intent (data, daily, last month)

## Prompt Structure

```xml
<role>
You are a trading question parser...
</role>

<constraints>
- Always return valid JSON
- Use granularity="daily" for search queries
- Set search_condition for "find/search" questions
</constraints>

<examples>
Q: "Как NQ вел себя в январе?"
→ type=data, granularity=daily

Q: "Найди дни когда падение >2%"
→ type=data, granularity=daily, search_condition="days where change_pct < -2%"

Q: "Найди падения после роста"
→ type=data, granularity=daily, search_condition="days where change_pct < -2% AND previous day change_pct > +1%"
</examples>

<task>
{question}
</task>
```

## Usage Tracking

```python
usage = understander.get_usage()
# UsageStats(input_tokens=2190, output_tokens=51, cost_usd=0.00024)
```
