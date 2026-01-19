# Гипотеза: Follow-up через обновление ParsedQuery

**Дата:** 2026-01-19
**Статус:** Гипотеза, требует проверки

---

## Проблема

Пользователь спрашивает "волатильность по часам", получает 24 строки данных.
Затем спрашивает "какой час самый волатильный?" — система не понимает что это follow-up и делает новый запрос с нуля.

**Текущее поведение:**
```
Q1: "волатильность по часам" → Parser: {what: volatility, group_by: hour} → 24 rows
Q2: "какой час самый волатильный?" → Parser: {what: volatility, group_by: hour} → те же 24 rows
```

Parser не знает что Q2 — это уточнение Q1.

---

## Гипотеза

**Parser получает предыдущий ParsedQuery и сам решает:**
- Дополнить/изменить предыдущий запрос
- Или сделать новый с нуля

```
Q1: "волатильность по часам"
    Parser → {what: volatility, group_by: hour}
    Сохраняется в state.parsed_query

Q2: "какой час самый волатильный?"
    Parser видит:
      - previous_parsed: {what: volatility, group_by: hour}
      - current_question: "какой час самый волатильный?"
    Parser решает: это уточнение, добавить top_n
    Parser → {what: volatility, group_by: hour, top_n: 1, order_by: avg_range DESC}
```

**Ключевой принцип:** Код не ошибается, AI — да. Поэтому:
- Parser извлекает intent (AI)
- Composer/QueryBuilder/SQL делают работу (код)
- AI НЕ анализирует цифры — SQL находит максимум через ORDER BY + LIMIT

---

## Что меняется

| Компонент | Изменение |
|-----------|-----------|
| `parse_question()` в graph.py | Передать `state.get("parsed_query")` в Parser |
| Parser prompt | Добавить `<previous_parsed>` секцию |
| Composer | **Без изменений** — получает полный ParsedQuery |
| Responder | **Без изменений** — получает intent как обычно |

---

## Что видит Responder (контекст)

| Данные | ≤5 rows (data_summary) | >5 rows (offer_analysis) |
|--------|------------------------|--------------------------|
| row_count | ✅ | ✅ |
| Сами данные | ✅ data_preview | ❌ только "N rows ready" |

**Вывод:** Для больших датасетов (>5 rows) Responder НЕ видит данные.
Поэтому follow-up вопросы должны обрабатываться через модификацию query, а не AI-анализ.

---

## Сценарии для проверки

### Категория A: Модификация запроса

| # | Q1 | Q2 | Ожидаемый результат |
|---|----|----|---------------------|
| A1 | "волатильность по часам" | "топ 5" | {what: volatility, group_by: hour, **top_n: 5**} |
| A2 | "волатильность по часам" | "какой час самый волатильный?" | {what: volatility, group_by: hour, **top_n: 1**} |
| A3 | "волатильность по часам" | "а по дням?" | {what: volatility, **group_by: day**} |
| A4 | "волатильность по часам" | "только пятницы" | {what: volatility, group_by: hour, **filter: weekday=friday**} |
| A5 | "волатильность по часам" | "за 2023" | {what: volatility, group_by: hour, **period: 2023**} |
| A6 | "статистика за 2024" | "только RTH" | {what: statistics, period: 2024, **session: RTH**} |

### Категория B: Новый запрос (игнорировать previous)

| # | Q1 | Q2 | Ожидаемый результат |
|---|----|----|---------------------|
| B1 | "волатильность по часам" | "статистика за 2024" | {what: statistics, period: 2024} — **новый** |
| B2 | "волатильность по часам" | "когда был хай в январе?" | {what: event_time_high, period: january} — **новый** |
| B3 | "статистика за 2024" | "сравни RTH и ETH" | {what: compare, items: [RTH, ETH]} — **новый** |

### Категория C: Не data-запрос

| # | Q1 | Q2 | Ожидаемый результат |
|---|----|----|---------------------|
| C1 | "волатильность по часам" | "спасибо" | {what: greeting} — **игнорировать previous** |
| C2 | "волатильность по часам" | "что такое RTH?" | {what: concept, concept: RTH} — **игнорировать previous** |
| C3 | "волатильность по часам" | "привет" | {what: greeting} — **игнорировать previous** |

### Категория D: Объяснение данных

| # | Q1 | Q2 | Ожидаемый результат |
|---|----|----|---------------------|
| D1 | "волатильность по часам" | "почему в 10 утра пик?" | ??? — нужно обсудить |
| D2 | "волатильность по часам" | "что означают эти данные?" | ??? — нужно обсудить |

### Категория E: Полная переделка

| # | Q1 | Q2 | Ожидаемый результат |
|---|----|----|---------------------|
| E1 | "волатильность по часам" | "покажи то же самое но для ES" | {what: volatility, group_by: hour, **symbol: ES**} |
| E2 | "волатильность по часам" | "переделай по месяцам за 2020-2024" | {what: volatility, **group_by: month, period: 2020-2024**} |

---

## Открытые вопросы

1. **Категория D (объяснение):** Как обрабатывать "почему в 10 утра пик?"
   - Это требует понимания market structure, не данных
   - Responder/Analyst должен объяснить (RTH open, volume, etc.)
   - Или это вообще другой flow?

2. **Граница между "модификация" и "новый запрос":**
   - "сравни RTH и ETH" после "волатильность по часам" — это модификация (добавить compare) или новый запрос?
   - Решение: Parser сам определяет что оптимальнее

3. **Конфликтующие инструкции:**
   - Q1: "статистика за 2024"
   - Q2: "за 2023"
   - Это замена period или уточнение? (скорее всего замена)

---

## Следующие шаги

1. [ ] Проверить сценарии A1-A6 вручную (с текущим Parser)
2. [ ] Определить как обрабатывать категорию D
3. [ ] Реализовать передачу previous_parsed в Parser
4. [ ] Обновить промпт Parser
5. [ ] Протестировать все сценарии
6. [ ] Обновить Responder если нужно

---

## Техническая реализация (план)

```python
# graph.py - parse_question()
def parse_question(state: AgentState) -> dict:
    question = get_current_question(state)
    chat_history = get_chat_history(state)
    history_str = _format_chat_history(chat_history)

    # НОВОЕ: получить предыдущий ParsedQuery
    previous_parsed = state.get("parsed_query")

    result = parser_agent.parse(
        question,
        chat_history=history_str,
        previous_parsed=previous_parsed,  # ← передать
    )

    return {...}
```

```python
# prompts/parser.py - добавить в промпт
"""
<previous_parsed>
What: {previous.what}
Period: {previous.period}
Filters: {previous.filters}
Modifiers: {previous.modifiers}
</previous_parsed>

<current_question>
{question}
</current_question>

If the current question refines or modifies the previous query,
update the previous result and return complete ParsedQuery.

If the current question is unrelated, ignore previous and return fresh ParsedQuery.
"""
```
