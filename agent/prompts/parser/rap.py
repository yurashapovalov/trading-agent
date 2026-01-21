"""
RAP (Retrieval-Augmented Prompting) for Parser.

Dynamically builds parser prompt by retrieving relevant chunks
based on user question similarity.

Components:
- ChunkLoader: loads .md files from chunks/
- ChunkEmbedder: computes embeddings via Gemini
- ChunkRetriever: vector similarity search
- PromptRAP: builds dynamic prompts
"""

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np
from google import genai

import config

logger = logging.getLogger(__name__)

# Paths
PARSER_DIR = Path(__file__).parent
CHUNKS_DIR = PARSER_DIR / "chunks"
BASE_PROMPT_PATH = PARSER_DIR / "base.md"
EMBEDDINGS_CACHE = PARSER_DIR / "embeddings.json"


class ChunkLoader:
    """Load and parse chunk files."""

    def __init__(self, chunks_dir: Path = CHUNKS_DIR):
        self.chunks_dir = chunks_dir
        self.chunks: dict[str, str] = {}
        self._load_all()

    def _load_all(self):
        """Load all .md files from chunks directory."""
        for path in self.chunks_dir.rglob("*.md"):
            # Use relative path as chunk_id: "period/relative", "filter/filters"
            rel_path = path.relative_to(self.chunks_dir)
            chunk_id = str(rel_path.with_suffix(""))
            self.chunks[chunk_id] = path.read_text(encoding="utf-8")
            logger.debug(f"Loaded chunk: {chunk_id} ({len(self.chunks[chunk_id])} chars)")

        logger.info(f"Loaded {len(self.chunks)} chunks from {self.chunks_dir}")

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

    def _cache_valid(self) -> bool:
        """Check if cache exists and has all chunks."""
        if not self.cache_path.exists():
            return False

        try:
            with open(self.cache_path, "r") as f:
                cached = json.load(f)
            # Check if all current chunks are in cache
            return set(cached.get("chunk_ids", [])) == set(self.chunks.keys())
        except Exception:
            return False

    def _load_cache(self):
        """Load embeddings from cache."""
        with open(self.cache_path, "r") as f:
            data = json.load(f)
        self.embeddings = data.get("embeddings", {})

    def _save_cache(self):
        """Save embeddings to cache."""
        data = {
            "chunk_ids": list(self.chunks.keys()),
            "embeddings": self.embeddings,
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
            # Use first 500 chars for embedding (title + rules + first examples)
            embed_text = content[:500]
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
        self.matrix = np.array([
            self.embedder.embeddings[cid]
            for cid in self.chunk_ids
        ])
        logger.debug(f"Built index with {len(self.chunk_ids)} chunks")

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        """
        Find top-k relevant chunks.

        Returns list of (chunk_id, score) tuples.
        """
        q_emb = np.array(self.embedder.embed_query(query))

        # Cosine similarity (embeddings are normalized)
        scores = np.dot(self.matrix, q_emb)

        # Get top-k indices
        top_indices = np.argsort(scores)[-top_k:][::-1]

        results = [
            (self.chunk_ids[i], float(scores[i]))
            for i in top_indices
        ]

        logger.debug(f"Query: '{query[:50]}...' → {[r[0] for r in results]}")
        return results


class PromptRAP:
    """Build dynamic prompts using RAP."""

    def __init__(self):
        self.loader = ChunkLoader()
        self.embedder = ChunkEmbedder(self.loader.chunks)
        self.retriever = ChunkRetriever(self.embedder)
        self.base_prompt = BASE_PROMPT_PATH.read_text(encoding="utf-8")

    def build(self, question: str, top_k: int = 5) -> tuple[str, list[str]]:
        """
        Build prompt with relevant chunks.

        Args:
            question: User question (in English)
            top_k: Number of chunks to retrieve

        Returns:
            (prompt, chunk_ids) - built prompt and list of used chunk IDs
        """
        # Find relevant chunks
        results = self.retriever.search(question, top_k=top_k)
        chunk_ids = [r[0] for r in results]

        # Combine base + chunks
        chunks_text = "\n\n".join([
            self.loader.get(cid) for cid in chunk_ids
        ])

        prompt = f"{self.base_prompt}\n\n{chunks_text}"

        logger.info(f"Built prompt with chunks: {chunk_ids}")
        return prompt, chunk_ids

    def get_stats(self) -> dict:
        """Get RAP statistics."""
        return {
            "total_chunks": len(self.loader.chunks),
            "chunk_ids": self.loader.get_all_ids(),
            "embeddings_cached": self.embedder.cache_path.exists(),
        }


# =============================================================================
# Singleton
# =============================================================================

_rap_instance: Optional[PromptRAP] = None


def get_rap() -> PromptRAP:
    """Get singleton PromptRAP instance."""
    global _rap_instance
    if _rap_instance is None:
        _rap_instance = PromptRAP()
    return _rap_instance


# =============================================================================
# Test
# =============================================================================

if __name__ == "__main__":
    import time

    logging.basicConfig(level=logging.INFO)

    rap = PromptRAP()

    test_questions = [
        "volatility for 2024",
        "top 10 days by volume",
        "compare RTH and ETH",
        "what happens after gap up",
        "OPEX stats",
        "predict tomorrow",
        "stats for January",
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
