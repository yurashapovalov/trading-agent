# Query Blocks v2 — Идеи расширения

> Документ: идеи для расширения системы кубиков
> Статус: brainstorm, не реализовано

## Текущие кубики (v1)

```
Source:     minutes | daily | daily_with_prev
Filters:    period, session (15 сессий), conditions
Grouping:   none | total | 5min..hour | day..year | weekday | session
Metrics:    OHLCV, range, change_pct, gap_pct, count, avg, sum, min, max, stddev, median
SpecialOp:  none | event_time | top_n | compare
```

---

## Проблема масштабирования

**Больше кубиков = сложнее Understander**

Текущий промпт: ~5000 токенов. Если добавить все идеи ниже — будет 15-20K токенов.

### Решения:

1. **Иерархический Understander**
   ```
   Understander L1 → определяет категорию запроса
   Understander L2 → детализирует в рамках категории
   ```

2. **Модульные промпты**
   ```
   base_prompt + category_prompt[detected_category]
   ```

3. **Few-shot по категориям**
   ```
   Если запрос про гэпы → загрузить примеры про гэпы
   Если запрос про время → загрузить примеры про event_time
   ```

4. **RAG для кубиков**
   ```
   Вопрос → embedding → найти релевантные кубики → подставить в промпт
   ```

---

## Новые Sources

| Кубик | Описание | Сложность |
|-------|----------|-----------|
| `weekly` | Недельные OHLCV | Low |
| `monthly` | Месячные OHLCV | Low |
| `streaks` | Таблица серий (win/loss streaks) | Medium |
| `patterns` | Candlestick patterns (doji, hammer, engulfing) | Medium |
| `levels` | Support/resistance levels | High |
| `pivots` | Pivot points (daily, weekly, monthly) | Medium |

### Пример: streaks source

```sql
WITH daily AS (...),
streaks AS (
    SELECT
        date,
        change_pct,
        CASE WHEN change_pct > 0 THEN 1 ELSE -1 END as direction,
        -- streak calculation with window functions
        SUM(CASE WHEN change_pct > 0 THEN 1 ELSE 0 END)
            OVER (ORDER BY date ROWS UNBOUNDED PRECEDING) as cumulative
    FROM daily
)
```

---

## Новые Filters

### По рыночному контексту

| Кубик | Значения | Как вычислить |
|-------|----------|---------------|
| `volatility_regime` | high / normal / low | ATR percentile или VIX level |
| `trend_regime` | uptrend / downtrend / sideways | MA slope или price vs MA |
| `gap_type` | gap_up / gap_down / flat | gap_pct threshold (±0.25%) |
| `prev_day` | green / red / doji | prev change_pct |
| `range_percentile` | top_10 / bottom_10 | range vs rolling percentile |
| `volume_percentile` | high / low / normal | volume vs rolling percentile |

### По событиям (требует доп. данных)

| Кубик | Описание | Источник данных |
|-------|----------|-----------------|
| `fomc_day` | День заседания FOMC | economic calendar |
| `opex` | Options expiration | fixed schedule |
| `nfp_day` | Non-Farm Payrolls | economic calendar |
| `cpi_day` | CPI release | economic calendar |
| `vix_level` | VIX > 20, VIX > 30 | VIX data |

---

## Новые Groupings

| Кубик | Описание | SQL пример |
|-------|----------|------------|
| `by_gap_direction` | gap_up vs gap_down vs flat | `CASE WHEN gap_pct > 0.25 THEN 'up'...` |
| `by_prev_close` | after green vs after red | `CASE WHEN prev_change > 0 THEN 'after_green'...` |
| `by_range_size` | small / medium / large | `NTILE(3) OVER (ORDER BY range)` |
| `by_streak_length` | 1 / 2 / 3+ days | streak calculation |
| `by_weekday_type` | Mon-Wed vs Thu-Fri | `DAYOFWEEK(date)` |

---

## Новые Metrics

### Структура свечи

| Кубик | Формула |
|-------|---------|
| `body_size` | `ABS(close - open)` |
| `body_pct` | `ABS(close - open) / open * 100` |
| `upper_wick` | `high - GREATEST(open, close)` |
| `lower_wick` | `LEAST(open, close) - low` |
| `body_to_range` | `body_size / range` |

### Гэпы

| Кубик | Описание |
|-------|----------|
| `gap_fill_pct` | Какой % гэпа был закрыт внутри дня |
| `gap_fill_time` | Время закрытия гэпа (или NULL) |
| `gap_continuation` | Ушла ли цена дальше в сторону гэпа |

### Время событий

| Кубик | Описание |
|-------|----------|
| `high_time` | Timestamp максимума дня |
| `low_time` | Timestamp минимума дня |
| `high_first` | true если high раньше low |

### Относительные метрики

| Кубик | Описание |
|-------|----------|
| `range_in_atr` | `range / ATR(14)` |
| `move_z_score` | `(change - avg) / stddev` |
| `range_percentile` | Персентиль range за период |

---

## Новые SpecialOps

### streak_analysis

Анализ серий побед/поражений.

```yaml
special_op: streak_analysis
streak_spec:
  type: winning  # или losing
  min_length: 3
  analyze: next_day  # что происходит после серии
```

**Вопросы которые решает:**
- "После 3 красных дней подряд какова вероятность зелёного?"
- "Какая максимальная серия побед за год?"
- "Средняя длина winning streak?"

### sequence

Условные вероятности P(A|B).

```yaml
special_op: sequence
sequence_spec:
  condition: "gap_up AND prev_day = red"
  measure: "close > open"
```

**Вопросы:**
- "Если гэп вверх после красного дня, какова вероятность закрыться в плюс?"
- "После дожи, куда чаще идёт цена?"

### seasonality

Сезонный анализ.

```yaml
special_op: seasonality
seasonality_spec:
  by: month  # или week_of_month, day_of_week
  metric: avg_change_pct
```

**Вопросы:**
- "Какой месяц исторически лучший?"
- "Понедельники лучше пятниц?"

### pattern_match

Поиск похожих паттернов в истории.

```yaml
special_op: pattern_match
pattern_spec:
  lookback: 5  # дней паттерна
  similarity: cosine  # или euclidean
  top_n: 10
```

**Вопросы:**
- "Найди похожие недели в истории"
- "Когда было такое же поведение?"

### backtest (simple)

Простой бэктест без позиций.

```yaml
special_op: backtest
backtest_spec:
  entry: "gap_up > 0.5%"
  exit: "close"  # на закрытии
  metric: "close - open"
```

**Вопросы:**
- "Если покупать на гэпе вверх и продавать на закрытии, какой результат?"

---

## Мета-кубики

### compare_periods

```yaml
meta_op: compare_periods
compare_spec:
  period_a: "2020-01-01 to 2020-12-31"
  period_b: "2023-01-01 to 2023-12-31"
  metrics: [avg_range, win_rate, avg_volume]
```

### drill_down

```yaml
meta_op: drill_down
drill_spec:
  hierarchy: [year, quarter, month]
  metric: total_range
  filter: "top 3 per level"
```

---

## Контекстные модификаторы

Не отдельные кубики, а модификаторы к существующим:

| Модификатор | Эффект |
|-------------|--------|
| `normalize_by: atr` | Все метрики в единицах ATR |
| `relative_to: open` | Цены как % от open |
| `percentile: true` | Показывать персентили вместо абсолютных значений |
| `compare_to: spy` | Добавить сравнение с SPY |

---

## Приоритизация реализации

### P0 — Быстрые победы (1-2 дня каждый)

1. `weekly` / `monthly` sources — простое расширение daily
2. `gap_type` filter — уже есть gap_pct, нужен только CASE
3. `prev_day` filter — аналогично
4. `body_size`, `upper_wick`, `lower_wick` metrics

### P1 — Средняя сложность (3-5 дней)

1. `streak_analysis` special_op
2. `seasonality` special_op
3. `by_gap_direction` grouping
4. `gap_fill_pct` metric

### P2 — Сложные (1-2 недели)

1. `sequence` special_op — требует careful SQL
2. `pattern_match` — требует similarity logic
3. Иерархический Understander

### P3 — Требуют доп. данных

1. Event filters (FOMC, NFP, etc.) — нужен economic calendar
2. `vix_level` filter — нужны данные VIX
3. `compare_to: spy` — нужны данные SPY

---

## Архитектурные заметки

### Как не раздуть Understander

1. **Категоризация первым шагом**
   ```
   User question → Category classifier → Category-specific understander
   ```

   Категории:
   - `timing` — когда что-то происходит (event_time)
   - `statistics` — средние, распределения
   - `comparison` — сравнение периодов/условий
   - `patterns` — поиск паттернов
   - `conditional` — P(A|B) запросы

2. **Ленивая загрузка кубиков**
   ```python
   base_blocks = [source, period, basic_metrics]

   if category == "timing":
       blocks += [session, event_time_spec, time_groupings]
   elif category == "conditional":
       blocks += [conditions, sequence_spec]
   ```

3. **Примеры вместо описаний**
   ```
   Вместо: "streak_analysis позволяет анализировать серии..."
   Лучше:
   Q: "после 3 красных дней что обычно?"
   A: {special_op: "streak_analysis", streak_spec: {type: "losing", min_length: 3}}
   ```

---

## Заключение

Кубики масштабируются, но требуют:

1. **Модульности промптов** — не всё в одном промпте
2. **Иерархии** — сначала категория, потом детали
3. **Приоритизации** — начать с P0, измерять accuracy

Главный принцип сохраняется: **LLM классифицирует, не генерирует**.
