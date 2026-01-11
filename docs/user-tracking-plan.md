# User Tracking & Chat Logging

## Цель
Идентифицировать пользователей тестовой группы (20 трейдеров) и сохранять все переписки для анализа.

## Требования
- Без регистрации
- Каждая сессия с чистого листа (контекст не сохраняется)
- Возможность анализировать: кто, что спрашивал, какие тулы, сколько стоило
- Просмотр через DBeaver

## Архитектура

### Frontend
1. При первом визите — модалка "Как тебя зовут?"
2. Сохранять `user_name` в localStorage
3. Отправлять с каждым запросом в `/chat/stream`

### Backend
1. Принимать `user_name` в ChatRequest
2. После каждого ответа — логировать в `chat_logs`
3. Сбрасывать контекст агента после каждого запроса (или держать в рамках сессии?)

### Database (DuckDB)

```sql
CREATE TABLE chat_logs (
    id INTEGER PRIMARY KEY,
    user_name VARCHAR NOT NULL,
    session_id VARCHAR,           -- UUID сессии браузера (опционально)
    question TEXT NOT NULL,
    response TEXT NOT NULL,
    tools_used JSON,              -- [{name, input, result, duration_ms}]
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost DECIMAL(10, 6),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chat_logs_user ON chat_logs(user_name);
CREATE INDEX idx_chat_logs_created ON chat_logs(created_at);
```

## Изменения в коде

### 1. Frontend (`chat.tsx`)
- [ ] Добавить state для `userName`
- [ ] Компонент модалки для ввода имени
- [ ] Проверять localStorage при загрузке
- [ ] Отправлять `user_name` в body запроса

### 2. Backend (`api.py`)
- [ ] Добавить `user_name` в `ChatRequest`
- [ ] Функция `log_chat()` для записи в БД
- [ ] Вызывать после получения ответа от агента

### 3. Database (`data/database.py`)
- [ ] Добавить `init_chat_logs_table()`
- [ ] Добавить `save_chat_log(user_name, question, response, ...)`

## Примеры SQL запросов для анализа

```sql
-- Активность по пользователям
SELECT user_name, COUNT(*) as questions, SUM(cost) as total_cost
FROM chat_logs
GROUP BY user_name
ORDER BY questions DESC;

-- Популярные тулы
SELECT
    json_extract(tool, '$.name') as tool_name,
    COUNT(*) as usage_count
FROM chat_logs,
     LATERAL unnest(tools_used::json[]) as tool
GROUP BY tool_name
ORDER BY usage_count DESC;

-- Последние вопросы
SELECT user_name, question, created_at
FROM chat_logs
ORDER BY created_at DESC
LIMIT 20;

-- Расходы по дням
SELECT DATE(created_at) as day, SUM(cost) as daily_cost
FROM chat_logs
GROUP BY day
ORDER BY day;
```

## Вопросы для обсуждения

1. **Контекст в рамках сессии**: держать пока страница открыта, или каждый вопрос независимый?
2. **Session ID**: нужен ли UUID для группировки сообщений в рамках одного визита?
3. **Что ещё логировать?**: user agent, IP (для гео)?
