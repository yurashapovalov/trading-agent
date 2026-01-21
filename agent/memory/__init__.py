"""
Memory module — caching and conversation memory.

- cache.py: Explicit Gemini context caching
- conversation.py: Tiered conversation memory
"""

from agent.memory.cache import CacheManager, get_cache_manager
from agent.memory.conversation import ConversationMemory


class MemoryManager:
    """
    Singleton manager for conversation memories.

    Stores ConversationMemory per session_id.

    Usage:
        manager = get_memory_manager()
        memory = manager.get_or_create("session_123")
        memory.add_message("user", "привет")
    """

    _instance = None
    _memories: dict[str, ConversationMemory]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._memories = {}
        return cls._instance

    def get_or_create(self, session_id: str) -> ConversationMemory:
        """Get existing memory or create new one for session."""
        if session_id not in self._memories:
            self._memories[session_id] = ConversationMemory()
        return self._memories[session_id]

    def get(self, session_id: str) -> ConversationMemory | None:
        """Get memory if exists."""
        return self._memories.get(session_id)

    def clear(self, session_id: str):
        """Clear memory for session."""
        if session_id in self._memories:
            self._memories[session_id].clear()

    def delete(self, session_id: str):
        """Delete memory for session."""
        self._memories.pop(session_id, None)

    def list_sessions(self) -> list[str]:
        """List all active session IDs."""
        return list(self._memories.keys())


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
