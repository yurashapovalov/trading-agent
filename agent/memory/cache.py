"""
Explicit Gemini Context Caching.

Caches static prompts (system instructions) to reduce costs.
Minimum 1024 tokens for Flash, 4096 for Pro.

Usage:
    cache_manager = get_cache_manager()

    # Get or create cache for parser prompt
    cache_name = cache_manager.get_or_create(
        key="parser_v1",
        content=SYSTEM_PROMPT,
        ttl_seconds=3600,
    )

    # Use in request
    response = client.models.generate_content(
        model=MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(cached_content=cache_name),
    )
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from google import genai
from google.genai import types

import config

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages explicit Gemini context caches.

    Features:
    - Creates caches on demand
    - Tracks cache expiration
    - Reuses existing caches
    - Auto-refreshes before expiry
    """

    # Minimum tokens for explicit caching
    MIN_TOKENS_FLASH = 1024
    MIN_TOKENS_PRO = 4096

    def __init__(self, model: str | None = None):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        # Use configured model (caching works with preview models too)
        self.model = model or config.GEMINI_LITE_MODEL
        self._caches: dict[str, dict] = {}  # key -> {name, expires_at}

    def get_or_create(
        self,
        key: str,
        content: str,
        ttl_seconds: int = 3600,
        system_instruction: bool = True,
    ) -> Optional[str]:
        """
        Get existing cache or create new one.

        Args:
            key: Unique identifier for this cache (e.g., "parser_v1")
            content: Content to cache (system prompt)
            ttl_seconds: Time to live in seconds (default 1 hour)
            system_instruction: If True, cache as system_instruction

        Returns:
            Cache name to use in requests, or None if caching failed
        """
        # Check if we have valid cache
        if key in self._caches:
            cache_info = self._caches[key]
            # Refresh if expiring soon (5 min buffer)
            if cache_info["expires_at"] > datetime.now(timezone.utc) + timedelta(minutes=5):
                logger.debug(f"Using existing cache: {key}")
                return cache_info["name"]
            else:
                logger.info(f"Cache expiring soon, refreshing: {key}")
                self._delete_cache(cache_info["name"])

        # Create new cache
        return self._create_cache(key, content, ttl_seconds, system_instruction)

    def _create_cache(
        self,
        key: str,
        content: str,
        ttl_seconds: int,
        system_instruction: bool,
    ) -> Optional[str]:
        """Create new cache."""
        try:
            cache_config = types.CreateCachedContentConfig(
                display_name=key,
                ttl=f"{ttl_seconds}s",
            )

            if system_instruction:
                cache_config.system_instruction = content
            else:
                cache_config.contents = [content]

            cache = self.client.caches.create(
                model=self.model,
                config=cache_config,
            )

            # Store cache info
            self._caches[key] = {
                "name": cache.name,
                "expires_at": datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
            }

            logger.info(f"Created cache: {key} -> {cache.name}")
            return cache.name

        except Exception as e:
            logger.warning(f"Failed to create cache {key}: {e}")
            return None

    def _delete_cache(self, cache_name: str):
        """Delete cache by name."""
        try:
            self.client.caches.delete(name=cache_name)
            logger.debug(f"Deleted cache: {cache_name}")
        except Exception as e:
            logger.warning(f"Failed to delete cache {cache_name}: {e}")

    def clear_all(self):
        """Clear all managed caches."""
        for key, cache_info in self._caches.items():
            self._delete_cache(cache_info["name"])
        self._caches.clear()
        logger.info("Cleared all caches")

    def get_stats(self) -> dict:
        """Get cache statistics."""
        now = datetime.now(timezone.utc)
        return {
            "total_caches": len(self._caches),
            "caches": {
                cache_key: {
                    "name": info["name"],
                    "expires_in_seconds": (info["expires_at"] - now).total_seconds(),
                }
                for cache_key, info in self._caches.items()
            },
        }


# Singleton instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get singleton CacheManager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
