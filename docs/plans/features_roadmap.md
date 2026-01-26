# Features Roadmap

План развития. Обновлено: 2026-01-26

## Текущий статус

| Возможность | Статус | Комментарий |
|-------------|--------|-------------|
| Базовая аналитика | ✅ | list, count, compare, distribution |
| Группировка | ✅ | hour, weekday, month, year |
| Фильтры | ✅ | session, period, comparison |
| Streak detection | ✅ | op_streak |
| Gap fields | ✅ | gap, gap_filled в enrich |
| Свечные паттерны | ✅ | doji, hammer, engulfing, etc. |
| Formation | ✅ | когда формируется high/low |
| Around | ✅ | что после события |
| Probability | ✅ | P(outcome \| condition) |
| Correlation | ✅ | между метриками |
| Supabase logging | ✅ | chat_logs, request_traces |
| Operations unified output | ✅ | все операции возвращают rows |
| Sessions через полночь | ✅ | OVERNIGHT, ETH, ASIAN — OR logic |

---

## Priority 1: UX улучшения

### 1.1 Presenter: inline top 5 таблица

**Проблема:** Для count/around/probability Presenter отвечает абстрактно: "149 gap ups со средним 0.08" — без конкретных примеров.

**Идея:**
- Операции сортируют rows по основной метрике
- Presenter показывает top 5 как inline таблицу
- Полные данные — в UI через DataCard

**Пример ответа:**
```
В 2024 году было 149 gap up дней.

| Дата       | Gap    | Change |
|------------|--------|--------|
| 2024-03-15 | 1.39%  | -0.5%  |
| 2024-01-08 | 0.95%  | +1.2%  |
| ...        |        |        |

Средний gap: 0.08%, максимальный: 1.39%
```

**Требует:**
- Операции должны сортировать rows осмысленно (по метрике)
- Presenter берёт первые 5 и форматирует таблицу

**Статус:** Отложено, нужно продумать какая сортировка для каждой операции.

---

### 1.2 Event filters (holidays, FOMC)

**Проблема:** Executor не умеет фильтровать по событиям.

**Пример:** "насколько опасны пятницы перед длинными выходными?"
- Parser создал: `event = thanksgiving`
- Executor: `Event filter not implemented`

**Нужно:** Реализовать event filters для: thanksgiving, christmas, fomc, opex, etc.

**Файлы:** `agent/data/filters.py`

---

## Priority 2: Расширение функционала

### 2.1 Formation: extended events

**Сейчас:** formation знает только high/low

**Нужные события:**
- `gap_fill` — "в какой час закрывается гэп"
- `range_50` — "когда достигается 50% дневного диапазона"

**Файл:** `agent/operations/formation.py`

---

### 2.2 Session-specific метрики

**Вопрос:** "correlation between overnight range and RTH range"

**Нужно:**
- `overnight_range` — range за ночную сессию
- `rth_range` — range за RTH
- `morning_range`, `afternoon_range`

**Сложность:** Требует join daily + intraday данных

---

### 2.3 Conditional sequences

**Вопрос:** "Если понедельник красный, какой обычно вторник?"

**Требует:** LAG + conditional aggregation

---

## Priority 3: Future

### 3.1 Cross-symbol correlation
"Корреляция NQ и ES за 2024"

### 3.2 Backtesting
Entry/exit conditions, P&L calculation

### 3.3 More instruments
ES, CL, GC — нужны данные

---

## Выполнено (архив)

<details>
<summary>Завершённые задачи</summary>

- ✅ CORR aggregate для одного символа
- ✅ Сезонность (group by month)
- ✅ Day-of-week analysis
- ✅ Streak detection
- ✅ Gap fields (gap, gap_filled)
- ✅ Свечные паттерны (20+ паттернов)
- ✅ Formation high/low
- ✅ Around operation
- ✅ Probability operation
- ✅ Supabase logging (chat_logs, request_traces)
- ✅ Token caching (73% savings)
- ✅ Understander session logic (не добавляет RTH к meta-questions)
- ✅ Operations unified output (все возвращают rows)
- ✅ Presenter: убран acknowledge (делает Understander)
- ✅ Sessions через полночь (OVERNIGHT, ETH, ASIAN — OR logic)

</details>
