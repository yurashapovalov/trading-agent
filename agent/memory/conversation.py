"""
Tiered Conversation Memory.

Smart memory that balances detail and efficiency:
- Recent messages: Full text (last N messages)
- Older messages: LLM-generated summaries
- Key facts: Extracted important info

Usage:
    memory = ConversationMemory()

    # Add messages
    memory.add_message("user", "привет")
    memory.add_message("assistant", "Привет! Чем помочь?")

    # Get context for LLM
    context = memory.get_context()
    # Returns formatted string with key_facts + summary + recent
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from google import genai
from google.genai import types

import config

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Single conversation message."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ConversationMemory:
    """
    Tiered conversation memory.

    Tiers:
    1. Recent (full text) - last `recent_limit` messages
    2. Summaries - compressed older messages
    3. Key facts - important extracted info

    Config:
    - recent_limit: Max recent messages to keep full
    - summary_chunk_size: Messages per summary
    - max_summaries: Max summaries to keep
    """

    recent_limit: int = 10
    summary_chunk_size: int = 5
    max_summaries: int = 3

    recent: list[Message] = field(default_factory=list)
    summaries: list[str] = field(default_factory=list)
    key_facts: list[str] = field(default_factory=list)

    _client: Optional[genai.Client] = field(default=None, repr=False)

    def __post_init__(self):
        if self._client is None:
            self._client = genai.Client(api_key=config.GOOGLE_API_KEY)

    def add_message(self, role: str, content: str):
        """
        Add message to memory.

        Automatically compacts when recent exceeds limit.
        """
        self.recent.append(Message(role=role, content=content))

        # Compact if needed
        if len(self.recent) > self.recent_limit + self.summary_chunk_size:
            self._compact()

    def add_key_fact(self, fact: str):
        """Add important fact to remember."""
        if fact not in self.key_facts:
            self.key_facts.append(fact)
            logger.debug(f"Added key fact: {fact}")

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
            # Take last N summaries
            recent_summaries = self.summaries[-self.max_summaries:]
            summary_text = "\n".join(recent_summaries)
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
        """Clear all memory."""
        self.recent.clear()
        self.summaries.clear()
        self.key_facts.clear()

    def _compact(self):
        """Compress oldest messages into summary."""
        if len(self.recent) <= self.recent_limit:
            return

        # Take oldest chunk for summarization
        chunk = self.recent[:self.summary_chunk_size]
        self.recent = self.recent[self.summary_chunk_size:]

        # Generate summary
        summary = self._summarize_chunk(chunk)
        if summary:
            self.summaries.append(summary)

            # Limit summaries
            if len(self.summaries) > self.max_summaries * 2:
                # Merge old summaries
                old_summaries = self.summaries[:-self.max_summaries]
                self.summaries = self.summaries[-self.max_summaries:]
                merged = self._merge_summaries(old_summaries)
                if merged:
                    self.summaries.insert(0, merged)

        logger.debug(f"Compacted {len(chunk)} messages into summary")

    def _summarize_chunk(self, messages: list[Message]) -> Optional[str]:
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

    def _merge_summaries(self, summaries: list[str]) -> Optional[str]:
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
