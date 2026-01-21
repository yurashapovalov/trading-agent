# RAP Implementation Plan

Retrieval-Augmented Prompting для Parser агента.

## Проблема

Текущий Parser prompt — 170 строк статических инструкций. Проблемы:

1. **Все примеры всегда** — даже для простого вопроса грузится всё
2. **Ограниченное количество примеров** — нельзя добавить много, prompt станет огромным
3. **Нет персонализации** — одинаковые примеры для разных типов вопросов
4. **Сложно масштабировать** — новые фичи (backtests, strategies) раздуют prompt
5. **Мультиязычность** — нужно дублировать примеры на разных языках

## Решение: RAP + Language Normalization

**RAG для промптов** + **нормализация языка** — всё внутри на English, общение на языке юзера.

```
┌─────────────────────────────────────────────────────────┐
│                    ENGLISH ZONE                         │
│                                                         │
│   Parser ←→ RAP Chunks ←→ Executor                      │
│            (EN only)                                    │
└─────────────────────────────────────────────────────────┘
        ↑ translate                    ↓ translate
┌─────────────────────────────────────────────────────────┐
│                    USER LANGUAGE                        │
│                                                         │
│   IntentClassifier → Clarifier → Responder              │
│   (detect + translate)  (ask + translate)  (respond)    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Language Flow

```
User: "волатильность вчера"
           ↓
IntentClassifier:
   → intent: "data"
   → lang: "ru"
   → question_en: "volatility yesterday"
           ↓
Parser (EN only):
   → input: "volatility yesterday"
   → RAP chunks: English
   → output: parsed_query
           ↓
[If unclear] Clarifier:
   → asks in RU: "За какой год?"
   → user answers: "за 2024"
   → translates: "for 2024"
   → clarified_query_en: "volatility yesterday for 2024"
           ↓
Parser (EN) → parsed_query
           ↓
Executor → data
           ↓
Responder (lang="ru"):
   → "Вчера волатильность была 250 пунктов"
```

**Преимущества:**
- Chunks только на EN — проще, точнее
- Vector search всегда точный (один язык)
- Работает для ЛЮБОГО языка
- Нет дублирования примеров

## Архитектура

### Структура файлов

```
agent/prompts/parser/
├── base.md                     # Всегда грузится (~50 токенов)
│
├── chunks/                     # Библиотека примеров
│   │
│   ├── period/
│   │   ├── relative.md         # yesterday, last week, YTD
│   │   ├── absolute_year.md    # 2024, 2023
│   │   ├── absolute_month.md   # January 2024, март 2024
│   │   ├── absolute_date.md    # May 15, 2024
│   │   ├── range.md            # from X to Y
│   │   └── quarter.md          # Q1 2024
│   │
│   ├── metric/
│   │   ├── volatility.md       # range, волатильность
│   │   ├── volume.md           # объём торгов
│   │   ├── change.md           # return, доходность
│   │   ├── green_pct.md        # win rate, зелёные дни
│   │   └── gap.md              # gaps
│   │
│   ├── operation/
│   │   ├── stats.md            # статистика, average
│   │   ├── compare.md          # vs, сравни
│   │   ├── top_n.md            # top 10, лучшие
│   │   ├── filter.md           # найди дни где
│   │   ├── seasonality.md      # by hour, by weekday
│   │   └── list.md             # покажи данные
│   │
│   ├── filter/
│   │   ├── weekday.md          # Fridays, понедельники
│   │   ├── session.md          # RTH, ETH, overnight
│   │   └── events.md           # OPEX, FOMC, NFP
│   │
│   ├── time/
│   │   └── intraday.md         # from 9:30 to 12:00
│   │
│   ├── unclear/
│   │   ├── missing_year.md     # месяц без года
│   │   ├── missing_period.md   # метрика без периода
│   │   └── missing_metric.md   # период без метрики
│   │
│   └── future/                 # Будущие фичи
│       ├── backtest.md
│       ├── strategy.md
│       └── indicators.md
│
├── embeddings.json             # Pre-computed embeddings
│
└── rap.py                      # PromptRAP class
```

### Формат chunk файла

Каждый chunk — набор примеров в едином формате:

```markdown
# Period: Relative

Examples of relative time periods.

<examples>
Input: какой был рейндж вчера?
Output: {"period": {"type": "relative", "value": "yesterday"}}

Input: volatility last week
Output: {"period": {"type": "relative", "value": "last_week"}}

Input: статистика за последние 30 дней
Output: {"period": {"type": "relative", "value": "last_n_days", "n": 30}}

Input: YTD performance
Output: {"period": {"type": "relative", "value": "ytd"}}

Input: с начала месяца
Output: {"period": {"type": "relative", "value": "mtd"}}
</examples>
```

### base.md (всегда грузится)

```markdown
<role>
You are an entity extractor for trading data queries.
Extract WHAT user said. Do NOT compute or interpret — just classify.
User may write in any language — extract to English field values.
</role>

<constraints>
1. Extract exactly what user said
2. Do NOT calculate actual dates — just identify the type
3. If information is missing, add to unclear[]
4. session/weekday_filter: only if explicitly mentioned
</constraints>

<output_format>
Return ParsedQuery JSON with extracted entities.
</output_format>
```

## Компоненты

### 1. ChunkLoader

```python
class ChunkLoader:
    """Load and parse chunk files."""

    def __init__(self, chunks_dir: Path):
        self.chunks_dir = chunks_dir
        self.chunks: dict[str, str] = {}
        self._load_all()

    def _load_all(self):
        """Load all .md files from chunks directory."""
        for path in self.chunks_dir.rglob("*.md"):
            chunk_id = path.stem  # e.g., "relative", "volatility"
            self.chunks[chunk_id] = path.read_text()

    def get(self, chunk_id: str) -> str:
        return self.chunks.get(chunk_id, "")
```

### 2. ChunkEmbedder

```python
class ChunkEmbedder:
    """Compute and cache embeddings for chunks."""

    CACHE_FILE = "embeddings.json"

    def __init__(self, chunks: dict[str, str]):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.chunks = chunks
        self.embeddings: dict[str, np.ndarray] = {}
        self._load_or_compute()

    def _load_or_compute(self):
        """Load from cache or compute embeddings."""
        if self._cache_exists():
            self._load_cache()
        else:
            self._compute_all()
            self._save_cache()

    def _embed(self, text: str) -> np.ndarray:
        result = self.client.models.embed_content(
            model="text-embedding-004",
            contents=text
        )
        return np.array(result.embeddings[0].values)

    def embed_query(self, query: str) -> np.ndarray:
        """Embed user query (not cached)."""
        return self._embed(query)
```

### 3. ChunkRetriever

```python
class ChunkRetriever:
    """Find relevant chunks using vector similarity."""

    def __init__(self, embedder: ChunkEmbedder):
        self.embedder = embedder
        self._build_index()

    def _build_index(self):
        """Build numpy matrix for fast search."""
        self.chunk_ids = list(self.embedder.embeddings.keys())
        self.matrix = np.stack([
            self.embedder.embeddings[cid]
            for cid in self.chunk_ids
        ])

    def search(self, query: str, top_k: int = 5) -> list[str]:
        """Find top-k relevant chunks."""
        q_emb = self.embedder.embed_query(query)
        scores = np.dot(self.matrix, q_emb)
        top_indices = np.argsort(scores)[-top_k:][::-1]
        return [self.chunk_ids[i] for i in top_indices]
```

### 4. PromptRAP

```python
class PromptRAP:
    """Build dynamic prompts using RAP."""

    def __init__(self):
        self.loader = ChunkLoader(CHUNKS_DIR)
        self.embedder = ChunkEmbedder(self.loader.chunks)
        self.retriever = ChunkRetriever(self.embedder)
        self.base_prompt = (PROMPTS_DIR / "base.md").read_text()

    def build(self, question: str, top_k: int = 5) -> str:
        """Build prompt with relevant chunks."""
        # Find relevant chunks
        chunk_ids = self.retriever.search(question, top_k=top_k)

        # Combine base + chunks
        chunks_text = "\n\n".join([
            self.loader.get(cid) for cid in chunk_ids
        ])

        return f"{self.base_prompt}\n\n{chunks_text}"
```

### 5. Интеграция с Parser

```python
class Parser:
    def __init__(self):
        self.rap = PromptRAP()
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)

    def parse(self, question: str) -> ParseResult:
        # Build dynamic prompt
        system_prompt = self.rap.build(question, top_k=5)

        # Call LLM
        response = self.client.models.generate_content(
            model=config.GEMINI_LITE_MODEL,
            contents=f"{system_prompt}\n\nQuestion: {question}",
            config=...
        )
        ...
```

## Метрики

### Latency

| Компонент | Время |
|-----------|-------|
| Embed query | ~300ms |
| Vector search | ~1-5ms |
| Parser LLM call | ~2000ms |
| **Total** | ~2300ms |

vs текущий Parser: ~3500ms (с thinking)

### Tokens

| Подход | Input tokens |
|--------|--------------|
| Текущий (static) | ~1800 |
| RAP (base + 5 chunks) | ~500-800 |

### Cost

| Подход | Cost per query |
|--------|----------------|
| Текущий | ~$0.0002 |
| RAP | ~$0.0001 + embed ~$0.00001 |

## План реализации

### Phase 1: Language Detection + Translation

1. [ ] Обновить `IntentClassifier`:
   - Добавить `lang` detection
   - Добавить `question_en` translation
   - Обновить `IntentResult` dataclass
2. [ ] Обновить `State`:
   - Добавить `lang: str`
   - Добавить `question_en: str`
3. [ ] Обновить `Clarifier`:
   - Спрашивать на `lang`
   - Переводить ответ на EN
4. [ ] Обновить `Responder`:
   - Отвечать на `lang`

### Phase 2: RAP Chunks (EN only)

1. [ ] Создать `agent/prompts/parser/` структуру
2. [ ] Написать `base.md` (EN)
3. [ ] Разбить текущий prompt на chunks (EN)
4. [ ] Добавить примеры в каждый chunk (EN)

### Phase 3: RAP Engine

1. [ ] Реализовать `ChunkLoader`
2. [ ] Реализовать `ChunkEmbedder` с кэшированием
3. [ ] Реализовать `ChunkRetriever`
4. [ ] Реализовать `PromptRAP`

### Phase 4: Integration

1. [ ] Обновить Parser для использования RAP
2. [ ] Parser получает `question_en` вместо оригинала
3. [ ] Тесты: сравнить качество static vs RAP
4. [ ] Тесты: latency, tokens, cost

### Phase 5: Расширение

1. [ ] Добавить больше примеров
2. [ ] Добавить комбинации (period + metric + operation)
3. [ ] Логирование: какие chunks используются
4. [ ] Реальные вопросы → новые примеры

## Комбинации примеров

Конечное множество комбинаций:

```
period (6) × metric (5) × operation (6) × filter (3) = 540 комбинаций
```

Но не все комбинации валидны. Реалистично:

- ~50 period examples
- ~30 metric examples
- ~40 operation examples
- ~20 filter examples
- ~30 unclear examples
- ~50 combination examples

**Total: ~220 chunks**

Каждый chunk: 3-5 examples = ~800 примеров total.

При top_k=5 каждый запрос видит 15-25 релевантных примеров.

## Мониторинг

Логировать для каждого запроса:

```python
{
    "question": "...",
    "retrieved_chunks": ["period_relative", "metric_volatility", ...],
    "similarity_scores": [0.72, 0.65, ...],
    "prompt_tokens": 650,
    "parse_result": {...},
    "latency_ms": {
        "embed": 320,
        "search": 2,
        "parse": 1800
    }
}
```

Это позволит:
- Видеть какие chunks популярны
- Находить вопросы где chunks не релевантны
- Добавлять новые примеры на основе реальных вопросов

## Будущее

1. **User feedback loop** — если парсинг неправильный, добавлять как пример
2. **Auto-generate examples** — LLM генерирует примеры для комбинаций
3. **Multi-instrument** — chunks для разных инструментов (ES, CL, NQ)
4. **Backtests & Strategies** — новые категории chunks
