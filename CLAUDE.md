# Stock Trading Assistant

AI-ассистент для анализа торговых данных NQ futures.

## Быстрый старт

```bash
source .venv/bin/activate

# Unit tests
pytest agent/tests/ -v

# Integration tests
python -m agent.tests.test_graph -s    # single questions
python -m agent.tests.test_graph -i    # interactive
```

## Архитектура

**Принцип:** Code for Facts, LLM for Text

```
User → Parser → Executor → Presenter → Response
         ↓         ↓           ↓
     понимает   SQL/data    текст
```

Подробнее: [docs/architecture/](docs/architecture/)
- [overview.md](docs/architecture/overview.md) — общая картина
- [agents.md](docs/architecture/agents.md) — Parser, Clarifier, Responder, Presenter
- [graph.md](docs/architecture/graph.md) — LangGraph, роутинг, state
- [memory.md](docs/architecture/memory.md) — token caching, conversation memory
- [data-layer.md](docs/architecture/data-layer.md) — Executor, operations
- [config.md](docs/architecture/config.md) — паттерны, события, праздники

## Структура

```
agent/
├── agents/        # Parser, Clarifier, Responder, Presenter
├── prompts/       # LLM промпты
├── memory/        # Token cache + conversation
├── operations/    # stats, top_n, compare...
├── config/        # patterns, events, holidays
├── graph.py       # LangGraph
├── executor.py    # Query execution
└── tests/         # pytest + integration

docs/
├── architecture/  # Описание системы
├── plans/         # Roadmap, идеи
└── gemini/        # Gemini API guides
```

## Стек

- Python 3.11+, DuckDB, Google Gemini, Pydantic, LangGraph

## Code Style

<details>
<summary>Senior+ стандарты (click to expand)</summary>

### Типизация
```python
# ДА
def calculate_stats(rows: list[dict], metric: str) -> StatsResult: ...

# НЕТ
def calculate_stats(rows, metric): ...
```

### Функции
```python
# ДА — маленькие, одна задача
def extract_dates(rows: list[dict]) -> list[str]: ...
def check_holidays(dates: list[str]) -> dict: ...

# НЕТ — большая функция делает всё
def process_data(rows): ...  # 100 строк
```

### Ранний выход
```python
# ДА
if not name: return None
if name not in PATTERNS: return None
return PATTERNS[name]

# НЕТ
if name:
    if name in PATTERNS:
        return PATTERNS[name]
return None
```

### Принципы
- **Explicit > Implicit** — никакой магии
- **Flat > Nested** — max 2 уровня
- **Pure > Stateful** — чистые функции
- **Data > Objects** — dataclass вместо классов

</details>

## TODO

### Done
- [x] Cleanup артефактов
- [x] Token caching (73% savings)
- [x] Unit tests (60 tests)
- [x] Supabase persistence (conversation memory)

### Next
- [ ] Anomaly Finder (docs/plans/anomaly_finder.md)
- [ ] More instruments (ES, CL, GC)
- [ ] Auto-detect user language → key_facts
