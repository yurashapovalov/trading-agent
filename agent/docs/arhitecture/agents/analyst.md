# Analyst Agent

**File:** `agent/agents/analyst.py`

**Type:** LLM (Gemini 2.5 Flash)

## Purpose

Анализирует данные и генерирует ответ пользователю со Stats для валидации.

## Principle

- Analyst получает **уже отфильтрованные** данные от DataFetcher
- Для search queries: SQL Agent отфильтровал → Analyst анализирует результат
- Analyst НЕ фильтрует данные - он только анализирует и объясняет

**Важно:** Фильтрация данных - работа SQL Agent + DataFetcher (код).
Analyst получает готовый результат и пишет инсайты.

## Input

### Standard Query

```python
{
    "question": "Как NQ вел себя в январе 2024?",
    "data": {
        "rows": [...],  # 22 дня за январь
        "row_count": 22,
        "granularity": "daily"
    },
    "intent": Intent(type="data", ...)
}
```

### Search Query (данные уже отфильтрованы)

```python
{
    "question": "Найди дни когда NQ упал больше 2%",
    "data": {
        "rows": [...],  # 77 отфильтрованных строк
        "row_count": 77,
        "granularity": "daily"
    },
    "intent": Intent(
        type="data",
        search_condition="days where change_pct < -2%"
    )
}
```

## Output

```python
{
    "response": "Найдено 77 дней с падением более 2%:\n\n| Дата | Изменение |...",
    "stats": Stats(
        matches_count=77,
        max_drop_pct=-7.8,
        ...
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
    matches_count: int      # для поиска - количество совпадений
```

**Важно:** Stats содержит только те числа, которые Analyst упоминает в ответе.

## Response Format

### Standard data query
```
В январе 2024 года индекс NQ показал рост на 2.53%.

| Параметр | Значение |
|----------|----------|
| Открытие | 16,334 |
| Закрытие | 16,747 |
| Максимум | 17,152 |
```

**Инсайты добавляются только если есть неочевидные паттерны:**
```
**Торговые идеи:** (опционально)
- Высокий объём коррелирует с волатильностью, но не с направлением
```

### Search query (данные уже отфильтрованы)
```
Найдено 77 дней с падением более 2%:

| Дата | Изменение | Объём |
|------|-----------|-------|
| 2008-10-15 | -7.80% | 850,000 |
| 2008-10-22 | -5.51% | 720,000 |
...
```

Инсайты добавляются если анализ выявил неочевидные закономерности.

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

        prompt = get_analyst_prompt(
            question=question,
            data=data,
            intent_type=intent.get("type"),
            search_condition=intent.get("search_condition"),  # для контекста
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

## Prompt Guidelines

```xml
<role>
You are a trading data analyst. Analyze data and write clear responses.
</role>

<constraints>
1. ONLY use facts from the provided data
2. The data is ALREADY filtered - just analyze what you receive
3. If analysis reveals non-obvious patterns, add 1-2 brief trading insights
4. Skip insights if the answer is straightforward
5. Use markdown tables for presenting data
</constraints>

<output_format>
Return JSON with:
- "response": plain text markdown (NOT JSON inside)
- "stats": object with numbers you mentioned
</output_format>
```

## Key Difference from Before

**Before (broken):**
- Analyst received ALL 5600 rows
- Had to filter by search_condition
- Missed 47 out of 77 matches

**After (correct):**
- SQL Agent generates filter query
- DataFetcher executes, returns 77 rows
- Analyst analyzes only filtered data
- 100% accuracy

## Usage Tracking

```python
usage = analyst.get_usage()
# UsageStats(input_tokens=5000, output_tokens=1500, cost_usd=0.003)
```

With filtered data, input tokens are much lower (5K vs 650K).
