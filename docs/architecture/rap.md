# RAP (Retrieval-Augmented Prompting)

Динамически строит промпт парсера, выбирая релевантные chunks по вопросу.

## Зачем

Все операции и фильтры в одном промпте = слишком много токенов.
RAP выбирает только релевантные примеры.

```
User: "топ по объёму"
         ↓
RAP: ищет chunks по embeddings
         ↓
Chunks: list, range_volume
         ↓
Prompt = base + chunks
```

## Структура

```
agent/prompts/semantic_parser/
├── base.md           # Базовый промпт (всегда включён)
├── embeddings.json   # Кэш embeddings (7 дней TTL)
├── operations/       # Chunks операций
│   ├── list.md
│   ├── count.md
│   ├── compare.md
│   ├── correlation.md
│   ├── around.md
│   ├── streak.md
│   ├── distribution.md
│   ├── probability.md
│   └── formation.md
└── filters/          # Chunks фильтров
    ├── categorical.md
    ├── consecutive.md
    ├── patterns.md
    ├── price.md
    ├── range_volume.md
    └── time.md
```

## Как работает

```
┌──────────────┐
│  User Query  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Embed      │  text-embedding-004
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Search     │  cosine similarity
└──────┬───────┘
       │ top_k chunks
       ▼
┌──────────────┐
│   Build      │  base + instrument + patterns + chunks
└──────┬───────┘
       │
       ▼
   Final Prompt
```

### 1. ChunkLoader

Загружает все `.md` файлы из `operations/` и `filters/`.

```python
loader = ChunkLoader()
loader.chunks  # {"list": "...", "around": "...", ...}
```

### 2. ChunkEmbedder

Вычисляет embeddings для первых 1000 символов каждого chunk.

```python
embedder = ChunkEmbedder(loader.chunks)
embedder.embed_query("топ по объёму")  # [0.12, -0.34, ...]
```

**Важно:** 1000 символов достаточно для description + key examples.

### 3. ChunkRetriever

Ищет top-k релевантных chunks по cosine similarity.

```python
retriever = ChunkRetriever(embedder)
retriever.search("топ по объёму", top_k=3)
# [("list", 0.82), ("range_volume", 0.76), ("count", 0.71)]
```

### 4. SemanticParserRAP

Собирает финальный промпт:

```
base.md
+ <instrument>NQ, sessions, trading day</instrument>
+ <available_patterns>candle, price patterns</available_patterns>
+ <holidays>christmas, thanksgiving...</holidays>
+ <relevant_examples>top-k chunks</relevant_examples>
```

## Кэширование

Embeddings кэшируются в `embeddings.json`:

```json
{
  "chunk_ids": ["list", "count", ...],
  "embeddings": {"list": [0.12, ...], ...},
  "created_at": "2026-01-23T12:00:00"
}
```

**TTL:** 7 дней. После истечения — пересчёт.

**Инвалидация:** Удалить `embeddings.json` при изменении chunks.

## Контекст

RAP автоматически добавляет контекст из конфигов:

| Контекст | Источник |
|----------|----------|
| Instrument | `config/market/instruments.py` |
| Patterns | `config/patterns/` |
| Holidays | `config/market/holidays.py` |
| Events | `config/market/events.py` |

## Параметры

| Параметр | Значение | Описание |
|----------|----------|----------|
| `top_k` | 3 | Сколько chunks включать |
| `embed_chars` | 1000 | Символов для embedding |
| `cache_ttl` | 7 days | Время жизни кэша |

## Использование

```python
from agent.prompts.semantic_parser.rap import get_rap

rap = get_rap()  # singleton
prompt, chunk_ids = rap.build("топ по объёму", top_k=3)

# chunk_ids = ["list", "range_volume", "count"]
# prompt = "..." (полный промпт для LLM)
```

## Отладка

```bash
python -m agent.prompts.semantic_parser.rap
```

Выведет для тестовых вопросов:
- Какие chunks выбраны
- Время поиска
- Длина промпта

## Важно

- Chunk должен содержать description в первых строках
- Key examples должны быть в первых 1000 символах
- При изменении chunks — удалить `embeddings.json`
