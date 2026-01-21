"""
Memory module — caching and conversation memory.

- cache.py: Explicit Gemini context caching
- conversation.py: Tiered conversation memory with Supabase persistence
"""

from agent.memory.cache import CacheManager, get_cache_manager
from agent.memory.conversation import ConversationMemory


class MemoryManager:
    """
    Singleton manager for conversation memories.

    Stores ConversationMemory per chat_id.
    Automatically loads from Supabase when creating new memory.

    Usage:
        manager = get_memory_manager()
        memory = manager.get_or_create(chat_id="xxx", user_id="yyy")
        # Memory is automatically loaded from DB
    """

    _instance = None
    _memories: dict[str, ConversationMemory]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._memories = {}
        return cls._instance

    def get_or_create(
        self,
        chat_id: str,
        user_id: str | None = None,
        load_from_db: bool = True,
    ) -> ConversationMemory:
        """
        Get existing memory or create new one for chat.

        Args:
            chat_id: Chat session ID (UUID)
            user_id: User ID for DB queries
            load_from_db: Whether to load history from Supabase

        Returns:
            ConversationMemory instance (loaded from DB if exists)
        """
        if chat_id not in self._memories:
            memory = ConversationMemory(chat_id=chat_id, user_id=user_id)

            # Load from DB
            if load_from_db and chat_id:
                memory.load_sync()

            self._memories[chat_id] = memory

        return self._memories[chat_id]

    def get(self, chat_id: str) -> ConversationMemory | None:
        """Get memory if exists in cache (doesn't load from DB)."""
        return self._memories.get(chat_id)

    def clear(self, chat_id: str):
        """Clear memory for chat (in-memory only)."""
        if chat_id in self._memories:
            self._memories[chat_id].clear()

    def delete(self, chat_id: str):
        """Delete memory from cache."""
        self._memories.pop(chat_id, None)

    def list_sessions(self) -> list[str]:
        """List all cached chat IDs."""
        return list(self._memories.keys())

    def save_all(self):
        """Save all dirty memories to DB."""
        for memory in self._memories.values():
            if memory.chat_id:
                memory.save_memory_state_sync()


# Singleton accessor
_memory_manager: MemoryManager | None = None


def get_memory_manager() -> MemoryManager:
    """Get singleton memory manager."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager


__all__ = [
    "CacheManager",
    "get_cache_manager",
    "ConversationMemory",
    "MemoryManager",
    "get_memory_manager",
]
