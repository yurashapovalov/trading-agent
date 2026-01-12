# Analyst Agent

**File:** `agent/agents/analyst.py`

**Type:** LLM (Gemini 2.5 Flash)

## Purpose

Интерпретирует данные и генерирует ответ пользователю со Stats для валидации.
Также фильтрует данные по `search_condition` для поисковых запросов.

## Principle

LLM анализирует данные и пишет ответ.
Validator (код) потом проверит что числа в ответе совпадают с данными.

## Input

```python
{
    "question": "Найди дни когда NQ упал больше 2%",
    "data": {
        "rows": [...],  # все дни за период
        "row_count": 4500,
        "granularity": "daily"
    },
    "intent": Intent(
        type="data",
        search_condition="days where change_pct < -2%"
    ),
    "validation": {...}  # если rewrite loop
}
```

## Output

```python
{
    "response": "Найдено 45 дней с падением более 2%:\n\n| Дата | Изменение |...",
    "stats": Stats(
        matches_count=45,
        ...
    )
}
```

## Search Condition Handling

Если `intent.search_condition` задан:

1. Analyst получает ВСЕ дневные данные
2. Фильтрует по условию (например "change_pct < -2% AND previous day > +1%")
3. Возвращает только совпадения в response

Промпт для поиска:
```xml
<search_condition>
days where change_pct < -2% AND previous day change_pct > +1%
</search_condition>

<task>
IMPORTANT: First, filter the data to find rows matching the search_condition.
Then analyze the matching rows and respond.

Steps:
1. Go through each row in the data
2. Check if it matches the search_condition
3. List ALL matching rows in your response
4. Include total count of matches
</task>
```

## Stats Structure

```python
class Stats(TypedDict, total=False):
    change_pct: float       # % изменения
    change_points: float    # абсолютное изменение в пунктах
    trading_days: int       # количество торговых дней
    open_price: float       # цена открытия первого дня
    close_price: float      # цена закрытия последнего дня
    max_price: float        # максимум за период
    min_price: float        # минимум за период
    total_volume: float     # суммарный объем
    matches_count: int      # для поиска - количество совпадений
```

**Важно:** Stats содержит только те числа, которые Analyst упоминает в ответе.

## Rewrite Loop

Если Validator находит ошибки, Analyst получает:

```python
{
    "validation": {
        "status": "rewrite",
        "issues": ["close_price: reported 17500, actual 17449.5"],
        "feedback": "Validation errors:\n- close_price: ..."
    }
}
```

И должен исправить ответ.

## Implementation

```python
class Analyst:
    name = "analyst"
    agent_type = "output"

    def __call__(self, state: AgentState) -> dict:
        question = state["question"]
        data = state["data"]
        intent = state["intent"]
        search_condition = intent.get("search_condition")

        prompt = get_analyst_prompt(
            question=question,
            data=data,
            search_condition=search_condition,
            ...
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json"
            )
        )

        result = json.loads(response.text)
        return {
            "response": result["response"],
            "stats": Stats(**result["stats"])
        }
```

## Response Types

### Regular data query
```
В январе 2024 года (период 01.01-31.01) индекс NQ показал рост...

| Параметр | Значение |
|----------|----------|
| Изменение | +2.53% |
| Торговых дней | 26 |
```

### Search query (with search_condition)
```
Найдено 45 дней с падением более 2%:

| Дата | Изменение | Объём |
|------|-----------|-------|
| 2008-10-15 | -4.56% | 850000 |
| 2008-10-22 | -3.21% | 720000 |
...

**Инсайты:**
- Большинство падений пришлось на 2008 и 2020 годы (кризисы)
- Средний объём в дни падения выше обычного на 40%
```

### Concept explanation
```
## MACD (Moving Average Convergence Divergence)

MACD - это индикатор, который показывает...
```

## Usage Tracking

```python
usage = analyst.get_usage()
# UsageStats(input_tokens=655, output_tokens=327, cost_usd=0.0062)
```
