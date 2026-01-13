# Trading Analytics Agent

## Идея

Мультиагентная система для анализа торговых данных на естественном языке. Вместо написания кода — просто говоришь что нужно, система сама понимает запрос, генерирует SQL, выполняет и возвращает результат с инсайтами.

## Примеры использования

```
User: "Посчитай корреляцию между объёмом и изменением цены"

System: [Understander → SQL Agent → Validator → DataFetcher → Analyst → Validator]
        → Корреляция -0.09, связь отсутствует. Но объём коррелирует с волатильностью (0.70).
```

```
User: "Покажи статистику по NQ за январь 2024"

System: → Рост 2.53%, объём выше среднего на 15%, макс волатильность в первую неделю.
```

```
User: "Найди дни когда NQ упал больше 2% после роста накануне"

System: [SQL Agent генерирует запрос с LAG()]
        → Найдено 23 таких дня. Чаще всего в 2008, 2020, 2022.
```

## Архитектура: Multi-Agent System

```
┌─────────────────────────────────────────────────────────────────────┐
│                           USER INPUT                                 │
│              "Найди корреляцию объёма и цены"                       │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         UNDERSTANDER (LLM)                          │
│                                                                     │
│  Понимает запрос → возвращает Intent:                              │
│  {type: "data", symbol: "NQ", search_condition: "correlation..."}  │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
              data/search                  chitchat/concept
                    │                           │
                    ▼                           ▼
┌───────────────────────────────┐    ┌─────────────────────┐
│        SQL AGENT (LLM)        │    │  RESPONDER (Code)   │
│                               │    │                     │
│  Intent → SQL запрос          │    │  Прямой ответ       │
│  (CORR, LAG, window funcs)    │    │                     │
└───────────────────────────────┘    └─────────────────────┘
                    │
                    ▼
┌───────────────────────────────┐
│     SQL VALIDATOR (Code)      │
│                               │
│  Проверяет SQL:               │
│  - Безопасность (только SELECT)│
│  - Синтаксис (выполняет LIMIT 1)│
└───────────────────────────────┘
                    │
                    ▼
┌───────────────────────────────┐
│      DATA FETCHER (Code)      │
│                               │
│  Выполняет SQL в DuckDB       │
│  → возвращает данные          │
└───────────────────────────────┘
                    │
                    ▼
┌───────────────────────────────┐
│        ANALYST (LLM)          │
│                               │
│  Данные → Ответ + Stats       │
│  Интерпретирует результаты    │
│  Добавляет торговые инсайты   │
└───────────────────────────────┘
                    │
                    ▼
┌───────────────────────────────┐
│       VALIDATOR (Code)        │
│                               │
│  Проверяет Stats vs Data      │
│  Защита от галлюцинаций       │
└───────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                            RESPONSE                                  │
│  "Корреляция -0.09 — связь отсутствует. Объём не предсказывает     │
│   направление, но коррелирует с волатильностью (0.70)."            │
└─────────────────────────────────────────────────────────────────────┘
```

## Принцип: LLM decides WHAT, Code validates HOW

| Агент | Тип | Роль |
|-------|-----|------|
| Understander | LLM | Понимает запрос → Intent |
| SQL Agent | LLM | Генерирует SQL |
| SQL Validator | Code | Проверяет SQL перед выполнением |
| DataFetcher | Code | Выполняет SQL |
| Analyst | LLM | Анализирует данные → ответ |
| Validator | Code | Проверяет числа в ответе |

**Паттерн:** Каждый LLM-агент имеет Code-валидатор. Это защита от галлюцинаций.

## Текущий стек

| Слой | Технология |
|------|------------|
| LLM | Gemini 3 Flash (Analyst), Gemini 2.5 Flash Lite (Understander, SQL Agent) |
| Оркестрация | LangGraph (state machine) |
| Backend | FastAPI + SSE streaming |
| Frontend | Next.js 15 + React + shadcn/ui |
| База данных | DuckDB (trading data) + Supabase (auth, logs) |
| Деплой | Hetzner VPS (backend) + Vercel (frontend) |

## Что реализовано

### Анализ данных
- [x] Запросы на естественном языке
- [x] SQL генерация для сложных условий (LAG, LEAD, CORR, window functions)
- [x] Статистика по периодам (daily, hourly, monthly, weekday)
- [x] Поиск паттернов (падение после роста, гэпы, серии дней)
- [x] Валидация ответов против данных

### Инфраструктура
- [x] Streaming ответов (SSE)
- [x] Авторизация (Supabase Auth)
- [x] Логирование запросов и трейсов
- [x] Подсчёт токенов и стоимости

### UX
- [x] Clarification при неясных запросах
- [x] Chat history для контекста
- [x] Агентские шаги видны в UI

## Roadmap

### Ближайшее
- [ ] **AI Actions** — like/dislike/pin сообщения
- [ ] **Pinned Sidebar** — сохранённые ответы
- [ ] Убрать счётчик токенов из UI (данные в БД для аналитики)

### Бэктестинг
- [ ] Определение стратегии через natural language
- [ ] Backtest Agent — тестирование на истории
- [ ] Метрики: winrate, profit factor, max drawdown, Sharpe ratio

### Поиск точек входа
- [ ] Entry Finder Agent — поиск оптимальных входов
- [ ] Фильтры: RR, max stop, min winrate, время
- [ ] Сравнение разных параметров

### Расширение
- [ ] Несколько инструментов (ES, CL, GC)
- [ ] Технические индикаторы (RSI, MACD, EMA)
- [ ] Кастомные паттерны
- [ ] Walk-forward analysis

## База данных

### Trading Data (DuckDB)
```sql
CREATE TABLE ohlcv_1min (
    timestamp TIMESTAMP,
    symbol VARCHAR,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume INTEGER
);
```

### Application Data (Supabase)
```sql
-- Chat logs
CREATE TABLE chat_logs (
    id SERIAL PRIMARY KEY,
    user_id UUID,
    request_id UUID,
    question TEXT,
    response TEXT,
    route TEXT,
    agents_used TEXT[],
    validation_passed BOOLEAN,
    input_tokens INT,
    output_tokens INT,
    cost_usd DECIMAL,
    pinned BOOLEAN DEFAULT FALSE,      -- планируется
    feedback JSONB,                     -- планируется
    created_at TIMESTAMPTZ
);

-- Agent traces
CREATE TABLE request_traces (
    id SERIAL PRIMARY KEY,
    request_id UUID,
    step_number INT,
    agent_name TEXT,
    input_data JSONB,
    output_data JSONB,
    duration_ms INT
);
```

## Метрики успеха

| Метрика | Цель |
|---------|------|
| Точность ответов | >95% (валидация проходит с первой попытки) |
| Время ответа | <10 сек для простых запросов |
| Стоимость запроса | <$0.01 для типичного запроса |
| Покрытие запросов | Статистика, паттерны, корреляции, поиск |

## Отличие от ChatGPT/Claude

1. **Специализация** — заточен под трейдинг, знает схему данных
2. **Валидация** — числа проверяются кодом, не галлюцинации
3. **SQL генерация** — сложные запросы с window functions
4. **Streaming** — ответ появляется по мере генерации
5. **История** — контекст сохраняется между сессиями
