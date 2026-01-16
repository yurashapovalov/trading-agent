# Understander RAP Architecture

Retrieval-Augmented Prompting для Understander агента.

## Проблема

Текущий промпт Understander — 800 строк. Содержит инструкции для всех типов запросов:
- chitchat (привет, пока)
- concept (что такое гэп?)
- clarification (уточняющие вопросы)
- data/event_time (когда формируется high?)
- data/top_n (топ 10 дней)
- data/filters (статистика по пятницам)
- и т.д.

Проблемы:
1. **Токены** — всегда 800 токенов, даже для "Привет!"
2. **Фокус** — модель теряется в большом промпте
3. **Maintainability** — сложно поддерживать монолит
4. **Тестирование** — сложно тестировать отдельные части

## Решение: RAP

Разделить на:
1. **Classifier** — определяет тип запроса (быстро, дёшево)
2. **Handlers** — специализированные инструкции для каждого типа

```
┌─────────────────────────────────────────────────────────┐
│                      User Question                       │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                 CLASSIFIER (gemini-flash)                │
│                                                          │
│  Prompt: ~50 токенов                                     │
│  Task: Определить тип запроса                            │
│                                                          │
│  Output: { "type": "data", "subtype": "event_time" }     │
└─────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
         ┌────────┐   ┌──────────┐   ┌─────────┐
         │chitchat│   │  data    │   │ concept │
         │ 20 tok │   │ 200 tok  │   │ 50 tok  │
         └────────┘   └──────────┘   └─────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                 HANDLER (gemini-pro)                     │
│                                                          │
│  Prompt: base.md + relevant_handler.md                   │
│  Task: Сгенерировать ответ / query_spec                  │
└─────────────────────────────────────────────────────────┘
```

## Типы запросов (Classifier output)

```python
class QueryType(Enum):
    # Простые — не требуют query_spec
    CHITCHAT = "chitchat"           # Привет, пока, как дела
    CONCEPT = "concept"             # Что такое гэп? Что такое RTH?
    OUT_OF_SCOPE = "out_of_scope"   # RSI, MACD, бэктест

    # Требуют уточнения
    CLARIFICATION = "clarification" # Неясный запрос

    # Data запросы — требуют query_spec
    DATA_SIMPLE = "data.simple"         # Статистика за период
    DATA_FILTER = "data.filter"         # Найди дни когда упало > 2%
    DATA_EVENT_TIME = "data.event_time" # Когда формируется high/low
    DATA_TOP_N = "data.top_n"           # Топ N дней
    DATA_COMPARE = "data.compare"       # Сравни RTH vs ETH
```

## Файловая структура

```
agent/prompts/understander/
│
├── classifier.py          # Промпт для классификатора
│
├── base.py                # Общие части (schema, роль)
│
└── handlers/
    ├── chitchat.md        # Как отвечать на болтовню
    ├── concept.md         # Как объяснять термины
    ├── out_of_scope.md    # Как отказывать
    ├── clarification.md   # Когда и как спрашивать
    │
    └── data/
        ├── base.md        # Общее про query_spec, source, filters
        ├── simple.md      # Простая статистика
        ├── filter.md      # Фильтрация по условиям
        ├── event_time.md  # Распределение времени high/low
        ├── top_n.md       # Топ N записей
        └── compare.md     # Сравнение (RTH vs ETH, по годам)
```

## Classifier Prompt (~50 токенов)

```python
CLASSIFIER_PROMPT = """Classify the user question into one of these types:

- chitchat: greetings, small talk
- concept: asking what something means (gap, RTH, range)
- out_of_scope: technical indicators (RSI, MACD), backtesting
- clarification: unclear what user wants
- data.simple: basic statistics for a period
- data.filter: find days matching condition (dropped > 2%)
- data.event_time: when does high/low form (distribution)
- data.top_n: top N days by some metric
- data.compare: compare sessions, periods, weekdays

Return JSON: {"type": "...", "subtype": "..." or null}

Question: {question}
"""
```

## Handler: data/event_time.md (~150 токенов)

```markdown
# Event Time Handler

User wants to know WHEN high/low typically forms (distribution over many days).

## Key decisions

1. **find**: what to find
   - "high" — only if asks about HIGH
   - "low" — only if asks about LOW
   - "both" — if mentions both or unclear

2. **session**: filter by trading session
   - Use if user mentions: RTH, ETH, основная сессия, премаркет
   - Leave null if not specified

3. **grouping**: time bucket size
   - Default: "1min" (most precise)
   - User might ask for "15min", "hour"

## Example

Question: "Когда обычно формируется high на RTH?"

```json
{
  "type": "data",
  "query_spec": {
    "source": "minutes",
    "filters": {
      "period_start": "all",
      "period_end": "all",
      "session": "RTH"
    },
    "grouping": "1min",
    "special_op": "event_time",
    "event_time_spec": {"find": "high"}
  }
}
```
```

## Сравнение токенов

| Тип запроса | Сейчас | RAP | Экономия |
|-------------|--------|-----|----------|
| "Привет!" | 800 | 50 + 20 = 70 | 91% |
| "Что такое гэп?" | 800 | 50 + 50 = 100 | 87% |
| "Когда high на RTH?" | 800 | 50 + 200 = 250 | 69% |
| "Топ 10 дней" | 800 | 50 + 150 = 200 | 75% |
| "Статистика за январь" | 800 | 50 + 100 = 150 | 81% |

**Средняя экономия: ~80% токенов**

## Стоимость

Цены из `agent/pricing.py` (за 1M токенов):

| Модель | Input | Output |
|--------|-------|--------|
| gemini-3-flash-preview | $0.50 | $3.00 |
| gemini-2.5-flash-lite-preview | $0.10 | $0.40 |

### Расчёт на примере "Когда формируется high?"

**Сейчас (монолитный промпт):**
- Input: 800 токенов × $0.50/1M = $0.0004
- Output: ~100 токенов × $3.00/1M = $0.0003
- **Итого: $0.0007**

**RAP:**
- Classifier (lite): 50 input × $0.10/1M + 10 output × $0.40/1M = $0.000009
- Handler (main): 250 input × $0.50/1M + 100 output × $3.00/1M = $0.000425
- **Итого: $0.000434**

**Экономия: ~38% на запрос**

### Для простых запросов ("Привет!")

**Сейчас:** $0.0007
**RAP:** $0.000009 (classifier) + $0.000035 (70 токенов) = $0.000044
**Экономия: ~94%**

## Реализация

### Шаг 1: Classifier

```python
class Classifier:
    """Fast classifier using lite model."""

    def __init__(self):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = config.GEMINI_LITE_MODEL  # gemini-2.5-flash-lite-preview

    def classify(self, question: str) -> dict:
        response = self.client.models.generate_content(
            model=self.model,
            contents=CLASSIFIER_PROMPT.format(question=question),
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
            )
        )
        return json.loads(response.text)
```

### Шаг 2: Handler Loader

```python
class HandlerLoader:
    """Load relevant handler based on classification."""

    HANDLERS_DIR = Path(__file__).parent / "handlers"

    def load(self, query_type: str) -> str:
        """Load handler markdown file."""
        if query_type.startswith("data."):
            subtype = query_type.split(".")[1]
            path = self.HANDLERS_DIR / "data" / f"{subtype}.md"
            base = self.HANDLERS_DIR / "data" / "base.md"
            return base.read_text() + "\n\n" + path.read_text()
        else:
            path = self.HANDLERS_DIR / f"{query_type}.md"
            return path.read_text()
```

### Шаг 3: Updated Understander

```python
class Understander:
    """RAP-based Understander."""

    def __init__(self):
        self.classifier = Classifier()
        self.loader = HandlerLoader()
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = config.GEMINI_MODEL

    def __call__(self, state: AgentState) -> dict:
        question = get_current_question(state)

        # Step 1: Classify
        classification = self.classifier.classify(question)
        query_type = classification["type"]

        # Step 2: Load relevant handler
        handler_prompt = self.loader.load(query_type)

        # Step 3: Build full prompt
        full_prompt = BASE_PROMPT + handler_prompt

        # Step 4: Generate response
        response = self.client.models.generate_content(
            model=self.model,
            contents=full_prompt + f"\n\nQuestion: {question}",
            ...
        )

        return self._parse_response(response, query_type)
```

## Преимущества

1. **Экономия токенов** — ~80% в среднем
2. **Фокус модели** — только релевантные инструкции
3. **Maintainability** — каждый handler в отдельном файле
4. **Тестирование** — можно тестировать handlers независимо
5. **Расширяемость** — добавить новый тип = добавить файл

## Недостатки

1. **Два вызова** — latency +100-200ms на classifier
2. **Сложность** — больше движущихся частей
3. **Classifier errors** — если неправильно классифицировал, handler не поможет

## Митигация рисков

1. **Fallback** — если classifier не уверен (low confidence), использовать полный промпт
2. **Logging** — логировать classification для анализа ошибок
3. **A/B testing** — сравнить качество RAP vs monolithic

## Миграция

1. Создать classifier.py и протестировать на 100 вопросах
2. Разбить текущий промпт на handler файлы
3. Запустить A/B тест: 50% RAP, 50% old
4. Если качество не падает — переключить на RAP

## Альтернатива: Hybrid

Если classifier добавляет слишком много latency:

```python
# Hybrid: classifier встроен в основной вызов
HYBRID_PROMPT = """
First, classify the question type.
Then, based on type, follow the relevant instructions below.

## If chitchat:
...short instructions...

## If data.event_time:
...event_time instructions...

## If data.top_n:
...top_n instructions...
"""
```

Это не даёт экономию токенов, но улучшает фокус модели через явную структуру.
