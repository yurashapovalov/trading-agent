# Pattern Integration Plan

> Авторитетное заключение на основе анализа кодовой базы

## Executive Summary

**Вывод:** Паттерны должны быть **data enrichment**, не отдельная операция.

**Дополнительно:** Parser должен динамически получать списки из Config (patterns, events, holidays) — не из статичных RAP chunks.

Текущая архитектура идеально поддерживает интеграцию:
- Scanner уже есть (`agent/patterns/scanner.py`)
- Config уже есть (`agent/config/patterns/candle.py`, `price.py`)
- Presenter уже готов (`_count_flags`, `_build_flags_context`)
- Фильтр `pattern` уже заглушен в executor

**Что нужно:** 5 точечных изменений, ~100 строк кода.

---

## Текущее состояние

### Что есть

| Компонент | Статус | Файл |
|-----------|--------|------|
| Pattern definitions | ✅ Готово | `agent/config/patterns/candle.py` (20+ паттернов) |
| Pattern scanner | ✅ Готово | `agent/patterns/scanner.py` (stateless) |
| Presenter flag handling | ✅ Готово | `agent/agents/presenter.py` |
| Filter parsing | ⚠️ Частично | `agent/rules/filters.py` (только green/red/gap_fill) |
| Executor apply_pattern | ⚠️ Частично | `agent/agents/executor.py` (только green/red/gap_fill) |
| Parser RAP chunk | ❌ Нет | `agent/prompts/semantic_parser/filters/patterns.md` |

### Data Flow (текущий)

```
get_bars() → enrich() → apply_filters() → operation() → presenter()
                ↓
        is_green, gap, range...     ← НЕТ is_doji, is_hammer...
```

### Data Flow (целевой)

```
get_bars() → enrich() → scan_patterns() → apply_filters() → operation() → presenter()
                              ↓
                    is_doji, is_hammer, is_engulfing, is_inside_bar...
```

---

## Архитектурное решение

### Почему НЕ новая операция

| Критерий | Новая операция | Enrichment |
|----------|----------------|------------|
| Код | ~300 строк + rules + pydantic | ~50 строк |
| Тесты | Новый test file | Расширить существующие |
| RAP chunks | Новые примеры | Добавить в filters/patterns.md |
| Дублирование | Да (list + patterns overlap) | Нет |
| Совместимость | Нужно учить парсер | Все операции автоматически |

**Вердикт:** Enrichment — правильный подход.

### Почему enrichment в Executor, не в `enrich()`

1. **Performance:** Не все запросы нуждаются в паттернах (stats, correlation)
2. **Granularity:** Паттерны только для daily data
3. **Separation:** `enrich()` — базовые вычисления, scanner — специализированный

**Решение:** Вызывать `scan_patterns_df()` в executor после `enrich()`, только для операций с raw rows.

---

## План интеграции

### Phase 1: Core Integration (обязательно)

#### 1.1 Executor: добавить scan_patterns

**Файл:** `agent/agents/executor.py`

```python
# После строки 192: df = enrich(df)
from agent.patterns import scan_patterns_df

def _load_data_with_semantics(req, operation, symbol):
    ...
    df = enrich(df)

    # Scan patterns for daily data (needs OHLC)
    if req.timeframe == "1D" and {"open", "high", "low", "close"}.issubset(df.columns):
        df = scan_patterns_df(df)

    ...
```

**Риск:** Минимальный. Добавляет колонки, не меняет существующие.

#### 1.2 Filter parsing: расширить pattern list

**Файл:** `agent/rules/filters.py`

```python
# Текущий код (строка ~80):
PATTERN_FILTERS = {"green", "red", "gap_fill", "gap_filled"}

# Изменить на:
from agent.config.patterns.candle import list_candle_patterns
from agent.config.patterns.price import list_price_patterns

def get_all_patterns() -> set[str]:
    """Get all pattern names from config (single source of truth)."""
    patterns = {"green", "red", "gap_fill", "gap_filled"}  # legacy
    patterns.update(list_candle_patterns())
    patterns.update(list_price_patterns())
    return patterns

PATTERN_FILTERS = get_all_patterns()
```

**Риск:** Нулевой. Расширяет список, не меняет логику.

#### 1.3 Executor: расширить _apply_pattern

**Файл:** `agent/agents/executor.py`

```python
def _apply_pattern(df: pd.DataFrame, f: dict) -> pd.DataFrame:
    """Apply pattern filter."""
    pattern = f.get("pattern")

    # Legacy patterns (computed in enrich)
    if pattern == "green" and "is_green" in df.columns:
        return df[df["is_green"]]
    elif pattern == "red" and "is_green" in df.columns:
        return df[~df["is_green"]]
    elif pattern in ("gap_fill", "gap_filled") and "gap_filled" in df.columns:
        return df[df["gap_filled"]]

    # Scanner patterns (computed in scan_patterns)
    col = f"is_{pattern}"
    if col in df.columns:
        return df[df[col] == 1]

    # Pattern not found — log warning, return unchanged
    logger.warning(f"Pattern column {col} not found in data")
    return df
```

**Риск:** Минимальный. Fallback на unchanged df.

#### 1.4 Parser RAP: добавить patterns chunk

**Файл:** `agent/prompts/semantic_parser/filters/patterns.md` (новый)

```markdown
# Candle & Price Patterns

<description>
Filter by candlestick patterns (doji, hammer, engulfing) or price patterns (inside_bar, higher_high).
Patterns are detected automatically on daily data.
</description>

<templates>
- doji
- hammer
- engulfing_bullish
- engulfing_bearish
- inside_bar
- outside_bar
- higher_high
- lower_low
- morning_star
- evening_star
</templates>

<examples>
User: "найди все doji за 2024"
→ filter: "doji"

User: "дни с hammer pattern"
→ filter: "hammer"

User: "inside days на прошлой неделе"
→ filter: "inside_bar"

User: "после engulfing что было"
→ operation: "around", filter: "engulfing_bullish"

User: "вероятность роста после hammer"
→ operation: "probability", filter: "hammer"
</examples>

<notes>
- Patterns work with all operations (list, count, around, probability, streak)
- Patterns require daily (1D) timeframe — intraday patterns not supported
- Multiple patterns can be combined: filter: "doji, monday"
</notes>
```

**Риск:** Нулевой. Добавляет знания парсеру.

### Phase 2: Retrospective Context (улучшение)

#### 2.1 Presenter: pattern context в ответах

**Файл:** `agent/agents/presenter.py`

Presenter уже готов! `_count_flags()` и `_build_flags_context()` работают.

**Нужно только:** Убедиться что rows содержат `is_*` колонки (Phase 1 это делает).

### Phase 3: Predictive Insights (продвинутое)

#### 3.1 Partial pattern detection

**Новый файл:** `agent/patterns/predictor.py`

```python
def detect_partial_patterns(df: pd.DataFrame) -> list[dict]:
    """
    Analyze last N bars for partial pattern formations.

    Returns:
        [{"pattern": "three_black_crows", "bars_formed": 2, "needs": "red day"}]
    """
    if len(df) < 2:
        return []

    partials = []

    # Example: Two red days → potential Three Black Crows
    last_two = df.tail(2)
    if all(~last_two["is_green"]):
        partials.append({
            "pattern": "three_black_crows",
            "bars_formed": 2,
            "needs": "ещё один красный день",
            "probability": 0.35,  # from historical data
        })

    # More partial patterns...
    return partials
```

#### 3.2 Presenter: predictive context

```python
def _build_predictive_context(df: pd.DataFrame) -> str | None:
    """Build context about potential forming patterns."""
    from agent.patterns.predictor import detect_partial_patterns

    partials = detect_partial_patterns(df)
    if not partials:
        return None

    lines = []
    for p in partials:
        lines.append(
            f"- {p['pattern']}: сформировано {p['bars_formed']} из 3 баров. "
            f"Если {p['needs']} — паттерн завершится."
        )

    return "\n".join(lines)
```

---

## Validation & Rules Audit

### Текущие правила (agent/rules/)

| Файл | Что делает | Изменения |
|------|------------|-----------|
| `filters.py` | Парсинг фильтров | Расширить PATTERN_FILTERS |
| `semantics.py` | filter × operation → semantic | Без изменений (pattern уже есть) |
| `operations.py` | Параметры операций | Без изменений |
| `metrics.py` | Маппинг метрик на колонки | Без изменений |

### Pydantic валидация (agent/types.py)

| Валидатор | Статус | Комментарий |
|-----------|--------|-------------|
| `validate_gap_vs_intraday` | ✅ OK | Паттерны = daily, нет конфликта |
| `validate_filter_combinations` | ✅ OK | pattern type уже в semantics |
| `validate_timeframe` | ⚠️ Добавить | Pattern filter → force 1D timeframe |

**Рекомендация:** Добавить валидатор в `Atom`:

```python
@model_validator(mode="after")
def validate_pattern_timeframe(self):
    """Pattern filters require daily timeframe."""
    if self.filter and any(p in self.filter for p in list_candle_patterns()):
        if self.timeframe != "1D":
            # Auto-correct instead of error
            self.timeframe = "1D"
    return self
```

---

## Тестирование

### Unit tests

```python
# agent/tests/test_patterns.py (уже есть)
# Добавить:

def test_pattern_filter_in_executor():
    """Patterns can be used as filters."""
    df = get_test_data()  # with OHLC
    df = enrich(df)
    df = scan_patterns_df(df)

    filtered = _apply_pattern(df, {"type": "pattern", "pattern": "doji"})
    assert all(filtered["is_doji"] == 1)

def test_pattern_in_list_operation():
    """List operation includes pattern flags."""
    plan = ExecutionPlan(
        mode="single",
        operation="list",
        requests=[DataRequest(period=("2024-01-01", "2024-12-31"), filters=[])],
        metrics=["change"],
        params={"n": 10},
    )
    result = execute_plan(plan)

    # Check pattern columns exist
    if result["rows"]:
        assert any(k.startswith("is_") for k in result["rows"][0].keys())
```

### Integration tests

```python
# agent/tests/test_graph.py
# Добавить вопросы:

PATTERN_QUESTIONS = [
    "найди все doji за 2024",
    "сколько hammer было в январе",
    "после engulfing bullish что происходит",
    "вероятность роста после inside day",
]
```

---

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Scanner тормозит | Низкая | Профилировать; кэшировать если нужно |
| Parser не понимает паттерны | Средняя | RAP chunk + примеры |
| Колонки is_* ломают presenter | Низкая | Presenter уже готов |
| Много колонок в output | Средняя | Фильтровать в _df_to_rows() |

---

## Порядок реализации

```
Phase 1 (Core):
1. executor.py — scan_patterns после enrich     [10 строк]
2. filters.py — расширить PATTERN_FILTERS       [15 строк]
3. executor.py — расширить _apply_pattern       [20 строк]
4. filters/patterns.md — RAP chunk              [50 строк]
5. Тесты                                        [30 строк]

Phase 2 (Retrospective):
6. Проверить presenter работает                 [0 строк, уже готов]

Phase 3 (Predictive):
7. predictor.py — partial patterns              [~100 строк]
8. presenter.py — predictive context            [~30 строк]
```

**Общий объём Phase 1:** ~125 строк кода + тесты

---

## Заключение

Архитектура проекта **готова к интеграции паттернов**:

1. **Single source of truth** — config/patterns/ определяет всё
2. **Stateless scanner** — легко интегрировать
3. **RAP system** — парсер учится из chunks
4. **Semantic filtering** — pattern уже валидный тип
5. **Presenter** — уже умеет в flags

**Рекомендация:** Начать с Phase 1, проверить на реальных вопросах, потом Phase 2-3.

**Не нужно:**
- Новых операций
- Новых pydantic моделей
- Изменений в semantics.py
- Изменений в graph.py

---

## Appendix A: Config → Parser Sync

### Текущая проблема

RAP chunks — статичные markdown файлы. Config — динамический источник правды.

| Источник | Что содержит | Как парсер узнаёт |
|----------|--------------|-------------------|
| `config/patterns/candle.py` | 20+ паттернов | ❌ RAP chunk с 6 примерами |
| `config/patterns/price.py` | 8+ паттернов | ❌ RAP chunk с 6 примерами |
| `config/market/events.py` | 30+ событий | ⚠️ RAP chunk с 3 примерами |
| `config/market/holidays.py` | 14 праздников | ❌ Нет RAP chunk |

**Риск:** Добавляем паттерн/событие в config → парсер не знает → не может обработать вопрос.

### Решение: Динамическая инъекция

RAP уже инжектит инструмент в prompt:

```python
# Текущий код в rap.py
def _build_instrument_context(self, instrument: str) -> str:
    cfg = get_instrument(instrument)
    # ... builds <instrument>...</instrument>
```

**Добавить аналогичные методы:**

```python
def _build_patterns_context(self) -> str:
    """Inject available patterns from config (single source of truth)."""
    from agent.config.patterns.candle import CANDLE_PATTERNS
    from agent.config.patterns.price import PRICE_PATTERNS

    lines = ["<available_patterns>"]
    lines.append("Candle patterns (require OHLC data, daily timeframe):")
    for name, cfg in CANDLE_PATTERNS.items():
        signal = cfg.get("signal", "neutral")
        tf = ", ".join(cfg.get("timeframes", ["1D"]))
        lines.append(f"  - {name} ({signal}, {tf})")

    lines.append("")
    lines.append("Price patterns:")
    for name, cfg in PRICE_PATTERNS.items():
        signal = cfg.get("signal", "neutral")
        lines.append(f"  - {name} ({signal})")

    lines.append("</available_patterns>")
    return "\n".join(lines)


def _build_events_context(self, instrument: str) -> str:
    """Inject available events from config."""
    from agent.config.market.events import get_event_types_for_instrument

    events = get_event_types_for_instrument(instrument)
    if not events:
        return ""

    lines = ["<available_events>"]
    by_impact = {"high": [], "medium": [], "low": []}
    for e in events:
        by_impact[e.impact.value].append(f"{e.id} ({e.name})")

    if by_impact["high"]:
        lines.append(f"High impact: {', '.join(by_impact['high'])}")
    if by_impact["medium"]:
        lines.append(f"Medium impact: {', '.join(by_impact['medium'])}")
    lines.append("</available_events>")
    return "\n".join(lines)


def _build_holidays_context(self) -> str:
    """Inject holiday names for parser."""
    from agent.config.market.holidays import HOLIDAY_NAMES

    lines = ["<holidays>"]
    lines.append("Full close: " + ", ".join([
        k for k in HOLIDAY_NAMES.keys()
        if not k.endswith("_eve") and k != "black_friday"
    ]))
    lines.append("Early close: christmas_eve, black_friday, new_year_eve, independence_day_eve")
    lines.append("</holidays>")
    return "\n".join(lines)


def build(self, question: str, top_k: int = 3, instrument: str = "NQ") -> tuple[str, list[str]]:
    results = self.retriever.search(question, top_k=top_k)
    chunk_ids = [r[0] for r in results]
    chunks_text = "\n\n".join([self.loader.get(cid) for cid in chunk_ids])

    # Dynamic context injection from config
    instrument_context = self._build_instrument_context(instrument)
    patterns_context = self._build_patterns_context()
    events_context = self._build_events_context(instrument)
    holidays_context = self._build_holidays_context()

    prompt = f"""{self.base_prompt}

{instrument_context}

{patterns_context}

{events_context}

{holidays_context}

<relevant_examples>
{chunks_text}
</relevant_examples>"""

    return prompt, chunk_ids
```

### Timeframes для паттернов

Добавить поле в config:

```python
# agent/config/patterns/candle.py
"hammer": {
    "name": "Hammer",
    "timeframes": ["1H", "4H", "1D", "1W"],  # где имеет смысл
    "min_timeframe": "1H",                    # минимальный таймфрейм
    ...
}

"three_black_crows": {
    "name": "Three Black Crows",
    "timeframes": ["1D", "1W"],               # только дневные+
    "min_timeframe": "1D",
    ...
}
```

**Валидация в executor:**

```python
def _should_scan_patterns(timeframe: str, pattern_config: dict) -> bool:
    """Check if pattern is valid for this timeframe."""
    min_tf = pattern_config.get("min_timeframe", "1D")
    tf_order = ["1m", "5m", "15m", "30m", "1H", "4H", "1D", "1W", "1M"]
    return tf_order.index(timeframe) >= tf_order.index(min_tf)
```

---

## Appendix B: Порядок реализации (обновлённый)

### Phase 0: Config Enhancement
1. Добавить `timeframes` / `min_timeframe` в candle patterns  [~30 строк]
2. Добавить `timeframes` в price patterns                    [~10 строк]

### Phase 1: Core Integration
3. `executor.py` — scan_patterns после enrich                [~15 строк]
4. `filters.py` — PATTERN_FILTERS из config                  [~15 строк]
5. `executor.py` — расширить _apply_pattern                  [~20 строк]

### Phase 2: Parser Sync
6. `rap.py` — `_build_patterns_context()`                    [~25 строк]
7. `rap.py` — `_build_events_context()`                      [~20 строк]
8. `rap.py` — `_build_holidays_context()`                    [~15 строк]
9. `rap.py` — inject в `build()`                             [~10 строк]

### Phase 3: Retrospective (уже готово)
10. Presenter работает автоматически                         [0 строк]

### Phase 4: Predictive (опционально)
11. `predictor.py` — partial pattern detection               [~100 строк]
12. `presenter.py` — predictive context                      [~30 строк]

**Общий объём:** ~290 строк кода (без Phase 4)

---

## Appendix C: Тестирование RAP Sync

```python
# agent/tests/test_rap_sync.py

def test_all_patterns_in_prompt():
    """All patterns from config appear in RAP prompt."""
    from agent.prompts.semantic_parser.rap import get_rap
    from agent.config.patterns.candle import list_candle_patterns
    from agent.config.patterns.price import list_price_patterns

    rap = get_rap()
    prompt, _ = rap.build("test question", instrument="NQ")

    for pattern in list_candle_patterns():
        assert pattern in prompt, f"Pattern {pattern} not in prompt"

    for pattern in list_price_patterns():
        assert pattern in prompt, f"Pattern {pattern} not in prompt"


def test_all_events_in_prompt():
    """All events for instrument appear in RAP prompt."""
    from agent.prompts.semantic_parser.rap import get_rap
    from agent.config.market.events import get_event_types_for_instrument

    rap = get_rap()
    prompt, _ = rap.build("test question", instrument="NQ")

    events = get_event_types_for_instrument("NQ")
    for event in events:
        assert event.id in prompt, f"Event {event.id} not in prompt"
```
