# Analyst Agent

**File:** `agent/agents/analyst.py`

**Type:** LLM (Gemini, настраиваемая модель)

## Purpose

Интерпретирует данные и генерирует ответ пользователю со Stats для валидации.

## Principle

LLM анализирует данные и пишет ответ.
Validator (код) потом проверит что числа в ответе совпадают с данными.

## Input

```python
{
    "question": "Как NQ вел себя в январе 2024?",
    "data": {
        "rows": [...],
        "row_count": 26,
        "granularity": "daily"
    },
    "intent": Intent(type="data"),
    "validation": {...}  # если rewrite loop
}
```

## Output

```python
{
    "response": "В январе 2024 NQ вырос на 2.53%...",
    "stats": Stats(
        change_pct=2.53,
        trading_days=26,
        open_price=17019.0,
        close_price=17449.5,
        max_price=17793.5,
        min_price=16334.25,
        total_volume=12886739
    )
}
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
    matches_count: int      # для паттернов - количество совпадений
```

**Важно:** Stats содержит только те числа, которые Analyst упоминает в ответе.
Validator сравнит эти числа с реальными данными.

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

## JSON Mode Output

Analyst возвращает JSON:

```json
{
    "response": "В январе 2024 года индекс NQ...",
    "stats": {
        "change_pct": 2.53,
        "trading_days": 26
    }
}
```

## Implementation

```python
class Analyst:
    name = "analyst"
    agent_type = "output"

    def __call__(self, state: AgentState) -> dict:
        question = state["question"]
        data = state["data"]
        intent_type = state["intent"]["type"]

        # Check for rewrite
        validation = state.get("validation", {})
        if validation.get("status") == "rewrite":
            previous_response = state["response"]
            issues = validation["issues"]

        prompt = get_analyst_prompt(...)

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

## Prompt Structure

```xml
<role>
You are a trading data analyst.
</role>

<constraints>
- Only use data provided
- Be precise with numbers
- Respond in user's language
</constraints>

<output_format>
Return JSON with:
- response: markdown text for user
- stats: object with numbers used in response
</output_format>

<data>
{data}
</data>

<task>
{question}
</task>
```

## Streaming

Для стриминга есть отдельный метод:

```python
for chunk in analyst.generate_stream(state):
    yield chunk  # str
# Returns final stats at the end
```

Но JSON mode не работает со стримингом, поэтому stats парсятся из полного текста.

## Usage Tracking

```python
usage = analyst.get_usage()
# UsageStats(input_tokens=655, output_tokens=327, cost_usd=0.0062)
```

## Response Types

### type=data
```
В январе 2024 года (период 01.01-31.01) индекс NQ показал рост...

| Параметр | Значение |
|----------|----------|
| Изменение | +2.53% |
| Торговых дней | 26 |
```

### type=pattern
```
За указанный период найдено 5 дней с ростом более 2%:

1. **15 марта 2024** - +2.5%
2. **22 марта 2024** - +2.8%
...
```

### type=concept
```
## MACD (Moving Average Convergence Divergence)

MACD - это индикатор, который показывает...
```
