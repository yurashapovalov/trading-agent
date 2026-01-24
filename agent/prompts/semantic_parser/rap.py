"""
RAP (Retrieval-Augmented Prompting) for Semantic Parser.

Dynamically builds parser prompt by retrieving relevant chunks
based on user question similarity.

Chunks:
- operations/ — operation descriptions and examples
- atoms/ — atom field descriptions (when, what, filter, group)

Also injects instrument-specific market config (sessions, trading day, etc.)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
from google import genai

import config
from agent.config.market.instruments import get_instrument
from agent.config.market.events import get_event_types_for_instrument

logger = logging.getLogger(__name__)

# Paths
PARSER_DIR = Path(__file__).parent
CHUNK_DIRS = [
    PARSER_DIR / "operations",
    PARSER_DIR / "filters",
]
BASE_PROMPT_PATH = PARSER_DIR / "base.md"
EMBEDDINGS_CACHE = PARSER_DIR / "embeddings.json"


class ChunkLoader:
    """Load and parse chunk files."""

    def __init__(self, chunk_dirs: list[Path] = CHUNK_DIRS):
        self.chunk_dirs = chunk_dirs
        self.chunks: dict[str, str] = {}
        self._load_all()

    def _load_all(self):
        """Load all .md files from chunk directories."""
        for chunks_dir in self.chunk_dirs:
            if not chunks_dir.exists():
                logger.warning(f"Chunks directory not found: {chunks_dir}")
                continue

            for path in chunks_dir.rglob("*.md"):
                # Use filename as chunk_id (without extension)
                chunk_id = path.stem
                self.chunks[chunk_id] = path.read_text(encoding="utf-8")
                logger.debug(f"Loaded chunk: {chunk_id} ({len(self.chunks[chunk_id])} chars)")

        logger.info(f"Loaded {len(self.chunks)} chunks")

    def get(self, chunk_id: str) -> str:
        """Get chunk content by ID."""
        return self.chunks.get(chunk_id, "")

    def get_all_ids(self) -> list[str]:
        """Get all chunk IDs."""
        return list(self.chunks.keys())


class ChunkEmbedder:
    """Compute and cache embeddings for chunks."""

    MODEL = "text-embedding-004"

    def __init__(self, chunks: dict[str, str], cache_path: Path = EMBEDDINGS_CACHE):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.chunks = chunks
        self.cache_path = cache_path
        self.embeddings: dict[str, list[float]] = {}
        self._load_or_compute()

    def _load_or_compute(self):
        """Load from cache or compute embeddings."""
        if self._cache_valid():
            self._load_cache()
            logger.info(f"Loaded {len(self.embeddings)} embeddings from cache")
        else:
            self._compute_all()
            self._save_cache()
            logger.info(f"Computed and cached {len(self.embeddings)} embeddings")

    # Cache TTL in seconds (7 days)
    CACHE_TTL = 7 * 24 * 60 * 60

    def _cache_valid(self) -> bool:
        """Check if cache exists, has all chunks, and is not expired."""
        if not self.cache_path.exists():
            return False

        try:
            with open(self.cache_path, "r") as f:
                cached = json.load(f)

            # Check chunk_ids match
            if set(cached.get("chunk_ids", [])) != set(self.chunks.keys()):
                return False

            # Check TTL (if created_at exists)
            created_at = cached.get("created_at")
            if created_at:
                from datetime import datetime
                created = datetime.fromisoformat(created_at)
                age_seconds = (datetime.now() - created).total_seconds()
                if age_seconds > self.CACHE_TTL:
                    logger.info(f"Cache expired (age: {age_seconds/3600:.1f}h)")
                    return False

            return True
        except Exception:
            return False

    def _load_cache(self):
        """Load embeddings from cache."""
        with open(self.cache_path, "r") as f:
            data = json.load(f)
        self.embeddings = data.get("embeddings", {})

    def _save_cache(self):
        """Save embeddings to cache with timestamp."""
        from datetime import datetime
        data = {
            "chunk_ids": list(self.chunks.keys()),
            "embeddings": self.embeddings,
            "created_at": datetime.now().isoformat(),
        }
        with open(self.cache_path, "w") as f:
            json.dump(data, f)
        logger.debug(f"Saved embeddings cache to {self.cache_path}")

    def _embed(self, text: str) -> list[float]:
        """Embed single text."""
        result = self.client.models.embed_content(
            model=self.MODEL,
            contents=text,
        )
        return result.embeddings[0].values

    def _compute_all(self):
        """Compute embeddings for all chunks."""
        for chunk_id, content in self.chunks.items():
            # Use first 1000 chars for embedding (includes description + key examples)
            embed_text = content[:1000]
            self.embeddings[chunk_id] = self._embed(embed_text)
            logger.debug(f"Embedded chunk: {chunk_id}")

    def embed_query(self, query: str) -> list[float]:
        """Embed user query (not cached)."""
        return self._embed(query)


class ChunkRetriever:
    """Find relevant chunks using vector similarity."""

    def __init__(self, embedder: ChunkEmbedder):
        self.embedder = embedder
        self._build_index()

    def _build_index(self):
        """Build numpy matrix for fast search."""
        self.chunk_ids = list(self.embedder.embeddings.keys())
        if not self.chunk_ids:
            self.matrix = np.array([])
            return
        self.matrix = np.array([
            self.embedder.embeddings[cid]
            for cid in self.chunk_ids
        ])
        logger.debug(f"Built index with {len(self.chunk_ids)} chunks")

    def search(self, query: str, top_k: int = 3) -> list[tuple[str, float]]:
        """Find top-k relevant chunks."""
        if len(self.chunk_ids) == 0:
            return []

        q_emb = np.array(self.embedder.embed_query(query))
        scores = np.dot(self.matrix, q_emb)
        top_indices = np.argsort(scores)[-top_k:][::-1]

        results = [
            (self.chunk_ids[i], float(scores[i]))
            for i in top_indices
        ]

        logger.debug(f"Query: '{query[:50]}...' → {[r[0] for r in results]}")
        return results


class SemanticParserRAP:
    """Build dynamic prompts for semantic parser using RAP."""

    def __init__(self):
        self.loader = ChunkLoader()
        self.embedder = ChunkEmbedder(self.loader.chunks)
        self.retriever = ChunkRetriever(self.embedder)
        self.base_prompt = BASE_PROMPT_PATH.read_text(encoding="utf-8")

    def _build_patterns_context(self) -> str:
        """Build available patterns context from config (single source of truth)."""
        from agent.config.patterns import CANDLE_PATTERNS, PRICE_PATTERNS

        lines = ["<available_patterns>"]

        # Group candle patterns by signal
        by_signal: dict[str, list[str]] = {"bullish": [], "bearish": [], "neutral": []}
        for name, cfg in CANDLE_PATTERNS.items():
            signal = cfg.get("signal", "neutral")
            if signal == "indecision":
                signal = "neutral"
            by_signal.setdefault(signal, []).append(name)

        lines.append("Candle patterns (reversal/continuation signals):")
        if by_signal["bullish"]:
            lines.append(f"  Bullish: {', '.join(by_signal['bullish'])}")
        if by_signal["bearish"]:
            lines.append(f"  Bearish: {', '.join(by_signal['bearish'])}")
        if by_signal["neutral"]:
            lines.append(f"  Neutral: {', '.join(by_signal['neutral'])}")

        lines.append("")
        lines.append("Price patterns (structural):")
        price_names = list(PRICE_PATTERNS.keys())
        lines.append(f"  {', '.join(price_names)}")

        lines.append("")
        lines.append("Legacy: green, red, gap_fill")
        lines.append("</available_patterns>")

        return "\n".join(lines)

    def _build_holidays_context(self) -> str:
        """Build holidays context from config (single source of truth)."""
        from agent.config.market.holidays import HOLIDAY_NAMES

        lines = ["<holidays>"]

        # Full close holidays
        full_close = [k for k in HOLIDAY_NAMES.keys()
                      if not k.endswith("_eve") and k not in ("black_friday",)]
        lines.append("Full close (market closed):")
        lines.append(f"  {', '.join(full_close)}")

        # Early close holidays
        early_close = ["christmas_eve", "new_year_eve", "independence_day_eve", "black_friday"]
        lines.append("Early close (shortened session):")
        lines.append(f"  {', '.join(early_close)}")

        lines.append("")
        lines.append("Use event filter: event = thanksgiving, event = christmas, etc.")
        lines.append("</holidays>")

        return "\n".join(lines)

    def _build_instrument_context(self, instrument: str) -> str:
        """Build instrument-specific context for prompt."""
        cfg = get_instrument(instrument)
        if not cfg:
            return ""

        sessions = list(cfg.get("sessions", {}).keys())
        trading_day = cfg.get("trading_day", {})

        lines = [
            f"<instrument>",
            f"Symbol: {instrument}",
            f"Name: {cfg.get('name', instrument)}",
            f"Trading day: {trading_day.get('start', '18:00')} (prev day) → {trading_day.get('end', '17:00')} (current day)",
            f"Available sessions: {', '.join(sessions)}",
            f"Default session: {cfg.get('default_session', 'RTH')}",
            f"",
            f"Session times (ET):",
        ]

        for session, times in cfg.get("sessions", {}).items():
            lines.append(f"  {session}: {times[0]} - {times[1]}")

        # Add events
        events = get_event_types_for_instrument(instrument)
        if events:
            event_ids = [e.id for e in events]
            lines.append(f"")
            lines.append(f"Available events: {', '.join(event_ids)}")

        lines.append(f"</instrument>")

        return "\n".join(lines)

    def build(self, question: str, top_k: int = 3, instrument: str = "NQ") -> tuple[str, list[str]]:
        """
        Build prompt with relevant chunks and instrument context.

        Args:
            question: User question (in English)
            top_k: Number of chunks to retrieve
            instrument: Trading instrument symbol (default: NQ)

        Returns:
            (prompt, chunk_ids) - built prompt and list of used chunk IDs
        """
        results = self.retriever.search(question, top_k=top_k)
        chunk_ids = [r[0] for r in results]

        chunks_text = "\n\n".join([
            self.loader.get(cid) for cid in chunk_ids
        ])

        instrument_context = self._build_instrument_context(instrument)
        patterns_context = self._build_patterns_context()
        holidays_context = self._build_holidays_context()

        prompt = f"{self.base_prompt}\n\n{instrument_context}\n\n{patterns_context}\n\n{holidays_context}\n\n<relevant_examples>\n{chunks_text}\n</relevant_examples>"

        logger.info(f"Built prompt with chunks: {chunk_ids}, instrument: {instrument}")
        return prompt, chunk_ids

    def get_stats(self) -> dict:
        """Get RAP statistics."""
        return {
            "total_chunks": len(self.loader.chunks),
            "chunk_ids": self.loader.get_all_ids(),
            "embeddings_cached": self.embedder.cache_path.exists(),
        }


# Singleton with thread-safe initialization
import threading

_rap_instance: SemanticParserRAP | None = None
_rap_lock = threading.Lock()


def get_rap() -> SemanticParserRAP:
    """Get singleton SemanticParserRAP instance (thread-safe)."""
    global _rap_instance
    if _rap_instance is None:
        with _rap_lock:
            if _rap_instance is None:
                _rap_instance = SemanticParserRAP()
    return _rap_instance


if __name__ == "__main__":
    import time

    logging.basicConfig(level=logging.INFO)

    rap = SemanticParserRAP()

    test_questions = [
        "top 10 by volume in 2024",
        "what happened after red days",
        "compare mondays and fridays",
        "correlation between volume and change",
        "how many red days in 2024",
    ]

    print(f"\nRAP Stats: {rap.get_stats()}")
    print("\n" + "=" * 60)

    for q in test_questions:
        start = time.time()
        prompt, chunks = rap.build(q, top_k=3)
        elapsed = (time.time() - start) * 1000

        print(f"\nQ: {q}")
        print(f"Chunks: {chunks}")
        print(f"Time: {elapsed:.0f}ms")
        print(f"Prompt length: {len(prompt)} chars")
