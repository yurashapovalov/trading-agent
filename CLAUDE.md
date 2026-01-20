# Stock Trading Assistant

AI-ассистент для анализа торговых данных. Сейчас работает с NQ futures, будет расширяться на другие инструменты.

## Ключевой принцип

**Code for Facts, LLM for Text**

- Код вычисляет факты детерминированно (паттерны, события, статистика)
- LLM только форматирует готовый контекст в человеческий текст
- LLM не видит сырые данные — не может галлюцинировать цифры

## Архитектура

```
User Question → Parser → Executor → DataResponder → Response
                  ↓          ↓            ↓
              ParsedQuery   SQL/DB    Context → LLM
```

### Pipeline

1. **Parser** (`agent/prompts/parser.py`) — разбирает вопрос в структурированный ParsedQuery (intent, what, period, filters)
2. **Executor** (`agent/executor.py`) — строит и выполняет SQL запрос
3. **DataResponder** (`agent/agents/responders/data.py`) — собирает контекст из данных и генерирует ответ

### Контекст для LLM

DataResponder собирает контекст из:
- **Флаги паттернов** — is_hammer, is_doji и т.д. (из SQL)
- **События** — OPEX, NFP, VIX expiration (проверка дат по конфигу)
- **Праздники** — market holidays, early close (из конфига)

LLM получает готовый контекст типа `3× red, 1× Quad Witching` и пишет человеческий текст.

## Структура

```
agent/
├── prompts/           # Промпты для LLM (parser, responder, analyst)
├── agents/
│   └── responders/    # DataResponder и другие
├── executor.py        # SQL генерация и выполнение
├── patterns/
│   └── scanner.py     # Numpy-детекция паттернов
├── config/
│   ├── patterns/      # Свечные и ценовые паттерны
│   │   ├── candle.py  # hammer, doji, engulfing...
│   │   └── price.py   # gap, trend...
│   ├── market/
│   │   ├── events.py  # OPEX, NFP, Quad Witching
│   │   └── holidays.py
│   └── instruments/   # (будет) настройки инструментов
└── tests/             # Тесты

docs/
├── architecture/      # Описание архитектуры
├── plans/             # Roadmap, идеи фич
├── gemini/            # Гайды по Gemini API
├── claude/            # Prompt engineering гайды
└── code-guides/       # Стиль кода, комментирование
```

## Конфиги паттернов

Каждый паттерн в `agent/config/patterns/candle.py`:

```python
"hammer": {
    "name": "Hammer",
    "category": "reversal",      # reversal, continuation, neutral
    "signal": "bullish",         # bullish, bearish, neutral
    "importance": "medium",      # high, medium, low — для фильтрации
    "description": "...",        # для LLM контекста
    "detection": {...},          # параметры детекции
    "related": [...],            # связанные паттерны
}
```

`importance` определяет что показывать:
- **high** — всегда упоминаем (engulfing, morning/evening star)
- **medium** — упоминаем если немного паттернов или встречается часто
- **low** — только если совсем мало паттернов

## Тестирование

```bash
source .venv/bin/activate

python -m agent.tests.test_graph_v2 -s    # single questions
python -m agent.tests.test_graph_v2 -c    # conversations
python -m agent.tests.test_graph_v2 -i    # interactive
```

## Стек

- Python 3.11+
- DuckDB — аналитическая БД
- Google Gemini — LLM
- Pydantic — типизация
- Supabase — (скоро) персистенция переписок и трейсов

## TODO

- [ ] Чистка старых артефактов
- [ ] Подключение к фронту
- [ ] Supabase для переписок и трейсов
- [ ] Больше инструментов (ES, CL, GC)
- [ ] Бэктесты
- [ ] Индикаторы
