"""
Tiered Conversation Memory with Supabase persistence.

Smart memory that balances detail and efficiency:
- Recent messages: Full text from chat_logs (last N messages)
- Older messages: LLM-generated summaries in chat_sessions.memory
- Key facts: Extracted important info in chat_sessions.memory

Usage:
    memory = ConversationMemory(chat_id="xxx", user_id="yyy")
    await memory.load()  # Load from Supabase

    memory.add_message("user", "привет")
    memory.add_message("assistant", "Привет! Чем помочь?")

    context = memory.get_context()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from google import genai
from google.genai import types

import config

logger = logging.getLogger(__name__)


async def _safe_background(coro, name: str):
    """Run coroutine and log errors instead of losing them."""
    try:
        await coro
    except Exception as e:
        logger.error(f"Background task {name} failed: {e}")


@dataclass
class Message:
    """Single conversation message."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    db_id: int | None = None  # chat_logs.id if from DB


@dataclass
class ConversationMemory:
    """
    Tiered conversation memory with Supabase persistence.

    Tiers:
    1. Recent (full text) - last `recent_limit` messages from chat_logs
    2. Summaries - compressed older messages in chat_sessions.memory
    3. Key facts - important extracted info in chat_sessions.memory

    Config:
    - recent_limit: Max recent messages to keep (pairs * 2)
    - summary_chunk_size: Messages per summary
    - max_summaries: Max summaries to keep
    """

    # DB identifiers
    chat_id: str | None = None
    user_id: str | None = None

    # Config (from config.py)
    recent_limit: int = config.MEMORY_RECENT_LIMIT
    summary_chunk_size: int = config.MEMORY_SUMMARY_CHUNK_SIZE
    max_summaries: int = config.MEMORY_MAX_SUMMARIES

    # Memory tiers
    recent: list[Message] = field(default_factory=list)
    summaries: list[dict] = field(default_factory=list)  # [{content, up_to_id}]
    key_facts: list[str] = field(default_factory=list)

    # Internal
    _client: genai.Client | None = field(default=None, repr=False)
    _supabase: object | None = field(default=None, repr=False)
    _loaded: bool = field(default=False, repr=False)
    _last_db_id: int | None = field(default=None, repr=False)  # Last chat_logs.id we've seen

    def __post_init__(self):
        if self._client is None:
            self._client = genai.Client(api_key=config.GOOGLE_API_KEY)

    def _get_supabase(self):
        """Lazy load Supabase client."""
        if self._supabase is None and config.SUPABASE_URL:
            from supabase import create_client
            self._supabase = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
        return self._supabase

    # =========================================================================
    # LOAD FROM DB
    # =========================================================================

    async def load(self) -> bool:
        """
        Load memory from Supabase.

        - Recent messages from chat_logs
        - Summaries and key_facts from chat_sessions.memory

        Returns True if loaded successfully.
        """
        if not self.chat_id or self._loaded:
            return False

        supabase = self._get_supabase()
        if not supabase:
            return False

        try:
            # 1. Load summaries and key_facts from chat_sessions
            session_result = supabase.table("chat_sessions") \
                .select("memory") \
                .eq("id", self.chat_id) \
                .execute()

            if session_result.data:
                memory_data = session_result.data[0].get("memory") or {}
                self.summaries = memory_data.get("summaries", [])
                self.key_facts = memory_data.get("key_facts", [])

                # Get last summarized id
                if self.summaries:
                    self._last_db_id = self.summaries[-1].get("up_to_id")

            # 2. Load recent messages from chat_logs
            query = supabase.table("chat_logs") \
                .select("id, question, response, created_at") \
                .eq("chat_id", self.chat_id) \
                .order("created_at", desc=True) \
                .limit(self.recent_limit // 2)  # Pairs, not messages

            # Only get messages after last summary
            if self._last_db_id:
                query = query.gt("id", self._last_db_id)

            logs_result = query.execute()

            if logs_result.data:
                # Reverse to get chronological order
                for row in reversed(logs_result.data):
                    # Add user message
                    self.recent.append(Message(
                        role="user",
                        content=row["question"],
                        timestamp=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
                        db_id=row["id"],
                    ))
                    # Add assistant message (if exists)
                    if row.get("response"):
                        self.recent.append(Message(
                            role="assistant",
                            content=row["response"],
                            timestamp=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
                            db_id=row["id"],
                        ))

            self._loaded = True
            logger.debug(f"Loaded memory for chat {self.chat_id}: {len(self.recent)} recent, {len(self.summaries)} summaries")
            return True

        except Exception as e:
            logger.error(f"Failed to load memory: {e}")
            return False

    def load_sync(self) -> bool:
        """Synchronous version of load()."""
        import asyncio
        try:
            # Check if we're in a running async context
            asyncio.get_running_loop()
            # We are - use sync implementation
            return self._load_sync_impl()
        except RuntimeError:
            # No running loop - run async version
            return asyncio.run(self.load())

    def _load_sync_impl(self) -> bool:
        """Direct sync implementation."""
        if not self.chat_id or self._loaded:
            return False

        supabase = self._get_supabase()
        if not supabase:
            return False

        try:
            # Same logic as async but synchronous
            session_result = supabase.table("chat_sessions") \
                .select("memory") \
                .eq("id", self.chat_id) \
                .execute()

            if session_result.data:
                memory_data = session_result.data[0].get("memory") or {}
                self.summaries = memory_data.get("summaries", [])
                self.key_facts = memory_data.get("key_facts", [])
                if self.summaries:
                    self._last_db_id = self.summaries[-1].get("up_to_id")

            query = supabase.table("chat_logs") \
                .select("id, question, response, created_at") \
                .eq("chat_id", self.chat_id) \
                .order("created_at", desc=True) \
                .limit(self.recent_limit // 2)

            if self._last_db_id:
                query = query.gt("id", self._last_db_id)

            logs_result = query.execute()

            if logs_result.data:
                for row in reversed(logs_result.data):
                    self.recent.append(Message(
                        role="user",
                        content=row["question"],
                        timestamp=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
                        db_id=row["id"],
                    ))
                    if row.get("response"):
                        self.recent.append(Message(
                            role="assistant",
                            content=row["response"],
                            timestamp=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
                            db_id=row["id"],
                        ))

            self._loaded = True
            return True
        except Exception as e:
            logger.error(f"Failed to load memory (sync): {e}")
            return False

    # =========================================================================
    # SAVE TO DB
    # =========================================================================

    async def save_memory_state(self):
        """Save summaries and key_facts to chat_sessions.memory."""
        if not self.chat_id:
            return

        supabase = self._get_supabase()
        if not supabase:
            return

        try:
            memory_data = {
                "summaries": self.summaries,
                "key_facts": self.key_facts,
            }
            supabase.table("chat_sessions") \
                .update({"memory": memory_data}) \
                .eq("id", self.chat_id) \
                .execute()
            logger.debug(f"Saved memory state for chat {self.chat_id}")
        except Exception as e:
            logger.error(f"Failed to save memory state: {e}")

    def save_memory_state_sync(self):
        """Synchronous version."""
        import asyncio
        try:
            # Check if we're in a running async context
            asyncio.get_running_loop()
            # We are - schedule with error handling
            asyncio.create_task(_safe_background(
                self.save_memory_state(),
                f"save_memory_state:{self.chat_id}"
            ))
        except RuntimeError:
            # No running loop - run synchronously
            asyncio.run(self.save_memory_state())

    # =========================================================================
    # MESSAGE MANAGEMENT
    # =========================================================================

    def add_message(self, role: str, content: str, db_id: int | None = None):
        """
        Add message to memory.

        Note: Messages are persisted to chat_logs by the API layer,
        not here. This just updates in-memory state.

        Automatically compacts when recent exceeds limit.
        """
        self.recent.append(Message(role=role, content=content, db_id=db_id))

        # Track last db_id for summarization boundary
        if db_id and (self._last_db_id is None or db_id > self._last_db_id):
            self._last_db_id = db_id

        # Compact if needed
        if len(self.recent) > self.recent_limit + self.summary_chunk_size:
            self._compact()

    def add_key_fact(self, fact: str):
        """Add important fact to remember."""
        if fact not in self.key_facts:
            self.key_facts.append(fact)
            logger.debug(f"Added key fact: {fact}")
            # Save to DB
            self.save_memory_state_sync()

    # =========================================================================
    # CONTEXT GENERATION
    # =========================================================================

    def get_context(self, max_tokens: int = 2000) -> str:
        """
        Get formatted context for LLM prompt.

        Returns string with key facts, summaries, and recent messages.
        """
        parts = []

        # Key facts (most important, always include)
        if self.key_facts:
            facts = "\n".join(f"- {fact}" for fact in self.key_facts[-5:])
            parts.append(f"<key_facts>\n{facts}\n</key_facts>")

        # Summaries (compressed history)
        if self.summaries:
            recent_summaries = self.summaries[-self.max_summaries:]
            summary_text = "\n".join(s["content"] for s in recent_summaries)
            parts.append(f"<history_summary>\n{summary_text}\n</history_summary>")

        # Recent messages (full detail)
        if self.recent:
            messages = self._format_messages(self.recent[-self.recent_limit:])
            parts.append(f"<recent_messages>\n{messages}\n</recent_messages>")

        return "\n\n".join(parts)

    def get_recent_as_list(self) -> list[dict]:
        """Get recent messages as list of dicts."""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.recent[-self.recent_limit:]
        ]

    def clear(self):
        """Clear all memory (in-memory only, doesn't affect DB)."""
        self.recent.clear()
        self.summaries.clear()
        self.key_facts.clear()
        self._last_db_id = None

    # =========================================================================
    # COMPACTION (Summarization)
    # =========================================================================

    def _compact(self):
        """Compress oldest messages into summary."""
        if len(self.recent) <= self.recent_limit:
            return

        # Take oldest chunk for summarization
        chunk = self.recent[:self.summary_chunk_size]
        self.recent = self.recent[self.summary_chunk_size:]

        # Get the last db_id in chunk for tracking
        chunk_last_id = None
        for msg in reversed(chunk):
            if msg.db_id:
                chunk_last_id = msg.db_id
                break

        # Generate summary
        summary_text = self._summarize_chunk(chunk)
        if summary_text:
            self.summaries.append({
                "content": summary_text,
                "up_to_id": chunk_last_id,
            })

            # Limit summaries
            if len(self.summaries) > self.max_summaries * 2:
                # Merge old summaries
                old_summaries = self.summaries[:-self.max_summaries]
                self.summaries = self.summaries[-self.max_summaries:]
                merged = self._merge_summaries([s["content"] for s in old_summaries])
                if merged:
                    # Keep the oldest up_to_id for the merged summary
                    self.summaries.insert(0, {
                        "content": merged,
                        "up_to_id": old_summaries[-1].get("up_to_id"),
                    })

            # Save to DB
            self.save_memory_state_sync()

        logger.debug(f"Compacted {len(chunk)} messages into summary")

    def _summarize_chunk(self, messages: list[Message]) -> str | None:
        """Generate summary for message chunk."""
        if not messages:
            return None

        formatted = self._format_messages(messages)

        prompt = f"""Summarize this conversation chunk in 1-2 sentences.
Focus on: what was discussed, any decisions made, key data requested.
Keep the same language as the conversation.

Conversation:
{formatted}

Summary:"""

        try:
            response = self._client.models.generate_content(
                model=config.GEMINI_LITE_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=100,
                ),
            )
            return response.text.strip()
        except Exception as e:
            logger.warning(f"Failed to summarize: {e}")
            # Fallback: just note the topics
            return f"Discussed: {messages[0].content[:50]}..."

    def _merge_summaries(self, summaries: list[str]) -> str | None:
        """Merge multiple summaries into one."""
        if not summaries:
            return None

        combined = "\n".join(summaries)

        prompt = f"""Combine these conversation summaries into one brief paragraph.
Keep important details, remove redundancy.

Summaries:
{combined}

Combined summary:"""

        try:
            response = self._client.models.generate_content(
                model=config.GEMINI_LITE_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=150,
                ),
            )
            return response.text.strip()
        except Exception as e:
            logger.warning(f"Failed to merge summaries: {e}")
            return summaries[-1]  # Just keep last

    def _format_messages(self, messages: list[Message]) -> str:
        """Format messages for prompt."""
        lines = []
        for msg in messages:
            role = "User" if msg.role == "user" else "Assistant"
            lines.append(f"{role}: {msg.content}")
        return "\n".join(lines)

    def __len__(self) -> int:
        """Total messages (recent + summarized estimate)."""
        summarized_estimate = len(self.summaries) * self.summary_chunk_size
        return len(self.recent) + summarized_estimate
