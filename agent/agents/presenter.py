"""
Presenter — formats query results for user.

Friendly, concise, professional. Like a colleague showing data to a colleague.

Context sources:
1. Pattern flags from SQL (is_hammer, is_doji, etc.) — only for raw data queries
2. Holidays/events from config — checked via dates in data rows
   - config/market/holidays.py: check_dates_for_holidays()
   - config/market/events.py: check_dates_for_events()

LLM uses this context to write natural summaries — doesn't interpret raw OHLC.

Three modes based on row count:
- 0 rows: "Ничего не нашлось"
- 1 row: natural summary (no table)
- 2-5 rows: summary + inline table
- >5 rows: DataCard + offer analysis

No buttons — natural dialog. User responds "да"/"yes" → Analyst.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from google import genai
from google.genai import types

import config
from agent.config.market.events import get_event_type, check_dates_for_events
from agent.config.market.holidays import HOLIDAY_NAMES, check_dates_for_holidays
from agent.config.patterns.candle import get_candle_pattern
from agent.prompts.presenter import (
    TEMPLATES,
    ACKNOWLEDGE_PROMPT,
    TITLE_PROMPT,
    SUMMARY_PROMPT,
    SHORT_SUMMARY_PROMPT,
    NO_DATA_PROMPT,
    SUMMARY_ANSWER_PROMPT,
    TABLE_WITH_SUMMARY_PROMPT,
)
from agent.utils.formatting import format_summary
from agent.config.market.instruments import get_instrument


# =============================================================================
# FLAG DETECTION (code-based, deterministic)
# =============================================================================

# Flag prefixes to look for
FLAG_PREFIXES = ("is_",)

# Event flags (calculable events from config/market/events.py)
EVENT_FLAGS = {"is_opex", "is_nfp", "is_quad_witching", "is_vix_exp"}

# Holiday flags (from config/market/holidays.py)
HOLIDAY_FLAGS = {"is_holiday", "is_early_close"}


def _get_flag_info(flag: str) -> dict:
    """Get name and description for a flag from config.

    Returns dict with 'name' and optional 'description'.
    Uses config/market/events.py, config/market/holidays.py, config/patterns/candle.py.
    """
    flag_id = flag.replace("is_", "")

    # Events — get from events.py (always high importance)
    if flag in EVENT_FLAGS:
        event = get_event_type(flag_id)
        if event:
            return {"name": event.name, "description": None, "importance": "high"}
        return {"name": flag_id.upper(), "description": None, "importance": "high"}

    # Holidays — get from holidays.py (always high importance)
    if flag in HOLIDAY_FLAGS:
        if flag == "is_holiday":
            return {"name": "market holiday", "description": None, "importance": "high"}
        elif flag == "is_early_close":
            return {"name": "early close", "description": None, "importance": "high"}

    # Named holidays (christmas, thanksgiving, etc.) — high importance
    if flag_id in HOLIDAY_NAMES:
        return {"name": HOLIDAY_NAMES[flag_id], "description": None, "importance": "high"}

    # Patterns — get from candle.py
    pattern = get_candle_pattern(flag_id)
    if pattern:
        return {
            "name": pattern["name"],
            "description": pattern.get("description"),
            "signal": pattern.get("signal"),
            "importance": pattern.get("importance", "medium"),
        }

    # Fallback
    return {"name": flag_id.replace("_", " "), "description": None}


def _count_flags(rows: list[dict], columns: list[str]) -> dict[str, int]:
    """Count flag occurrences in rows.

    Returns dict of flag_name -> count where flag=1.
    """
    flag_cols = [c for c in columns if c.startswith(FLAG_PREFIXES)]

    counts = {}
    for col in flag_cols:
        count = sum(1 for row in rows if row.get(col) == 1)
        if count > 0:
            counts[col] = count

    return counts


def _build_flags_context(flag_counts: dict[str, int]) -> str | None:
    """Build context string for LLM from flags.

    Returns structured context that LLM uses to write summary.
    LLM doesn't interpret raw data — flags are pre-computed by code.

    Filters patterns by importance:
    - high: always include
    - medium: include if total patterns <= 5, or if count >= 2
    - low: only include if total patterns <= 3
    """
    if not flag_counts:
        return None

    context_parts = []
    total_flags = len(flag_counts)

    for flag, count in flag_counts.items():
        info = _get_flag_info(flag)
        name = info["name"]
        description = info.get("description")
        signal = info.get("signal")
        importance = info.get("importance", "medium")

        # Filter by importance
        if importance == "low":
            # Low importance: only show if few total patterns
            if total_flags > 3:
                continue
        elif importance == "medium":
            # Medium: show if few patterns OR appears multiple times
            if total_flags > 5 and count < 2:
                continue
        # High importance: always show

        if description:
            context_parts.append(f"- {count}× {name}: {description}")
        elif signal:
            context_parts.append(f"- {count}× {name} ({signal})")
        else:
            context_parts.append(f"- {count}× {name}")

    return "\n".join(context_parts) if context_parts else None


def _extract_dates(rows: list[dict]) -> list[str]:
    """Extract date strings from data rows."""
    dates = []
    for row in rows:
        # Try common date field names
        date_val = row.get("date") or row.get("ts") or row.get("timestamp")
        if date_val:
            # Convert to string if needed, extract date part
            date_str = str(date_val)[:10]  # YYYY-MM-DD
            if len(date_str) == 10 and date_str[4] == "-":
                dates.append(date_str)
    return list(set(dates))  # unique dates


def _build_date_context(dates: list[str], symbol: str = "NQ") -> str | None:
    """Build context from dates using config (holidays, events).

    Checks dates against config/market/holidays.py and events.py.
    Returns structured context for LLM.
    """
    if not dates:
        return None

    context_parts = []

    # Check holidays
    holidays = check_dates_for_holidays(dates, symbol)
    if holidays:
        if holidays.get("early_close_dates"):
            count = len(holidays["early_close_dates"])
            names = [holidays["holiday_names"].get(d, "") for d in holidays["early_close_dates"]]
            unique_names = list(set(n for n in names if n))
            if unique_names:
                context_parts.append(f"- {count}× early close: {', '.join(unique_names)}")
            else:
                context_parts.append(f"- {count}× early close day(s)")

        if holidays.get("holiday_dates"):
            count = len(holidays["holiday_dates"])
            names = [holidays["holiday_names"].get(d, "") for d in holidays["holiday_dates"]]
            unique_names = list(set(n for n in names if n))
            if unique_names:
                context_parts.append(f"- {count}× holiday: {', '.join(unique_names)}")
            else:
                context_parts.append(f"- {count}× market holiday(s)")

    # Check events
    events = check_dates_for_events(dates, symbol)
    if events:
        # Group by event type
        event_counts = {}
        for date_str, event_names in events.get("events", {}).items():
            for name in event_names:
                event_counts[name] = event_counts.get(name, 0) + 1

        for name, count in event_counts.items():
            context_parts.append(f"- {count}× {name}")

    return "\n".join(context_parts) if context_parts else None


def _merge_contexts(*contexts: str | None) -> str | None:
    """Merge multiple context strings into one."""
    parts = [c for c in contexts if c]
    return "\n".join(parts) if parts else None


class DataResponseType(str, Enum):
    """Type of data response."""

    NO_DATA = "no_data"  # 0 rows
    SINGLE = "single"  # 1 row, natural summary
    INLINE = "inline"  # 2-5 rows, summary + table
    LARGE_DATA = "large_data"  # >5 rows


@dataclass
class DataResponse:
    """Response from Presenter.

    Three parts for frontend:
    1. acknowledge - shown before DataCard ("Понял, получаю...")
    2. title - DataCard title
    3. summary - shown after DataCard ("Вот 21 день...")

    Note: If context_compacted=true is passed, the LLM will include a brief
    warning in the summary about possibly not recalling old conversation details.
    """

    acknowledge: str  # "Понял, получаю волатильность за 2024..."
    title: str | None  # DataCard title
    summary: str  # "Вот 21 день. Было раннее закрытие..."
    type: DataResponseType
    row_count: int = 0

    @property
    def text(self) -> str:
        """Combined text for backwards compatibility."""
        if self.title:
            return f"{self.acknowledge}\n\n{self.summary}"
        return self.summary


class Presenter:
    """
    Formats query results for user.

    Friendly, concise, professional — like a colleague.
    Uses domain knowledge to summarize naturally.

    Logic:
    - 0 rows → "Ничего не нашлось"
    - 1 row → natural summary (no table)
    - 2-5 rows → summary + inline table
    - >5 rows → DataCard + "Хочешь анализ?"

    Usage:
        presenter = Presenter(symbol="NQ")
        result = presenter.present(data, question)
    """

    INLINE_THRESHOLD = 5

    def __init__(self, symbol: str = "NQ"):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = config.GEMINI_LITE_MODEL
        self.symbol = symbol
        self.instrument = get_instrument(symbol) or {}
        self.instrument_context = self._build_instrument_context()

    def _build_instrument_context(self) -> str:
        """Build full instrument context for prompts."""
        if not self.instrument:
            return f"Symbol: {self.symbol}"

        # Extract key info for LLM context
        lines = [
            f"Symbol: {self.symbol}",
            f"Name: {self.instrument.get('name', 'Unknown')}",
            f"Exchange: {self.instrument.get('exchange', 'Unknown')}",
            f"Tick size: {self.instrument.get('tick_size')} (${self.instrument.get('tick_value')} per tick)",
            f"Data available: {self.instrument.get('data_start')} to {self.instrument.get('data_end')}",
            f"Default session: {self.instrument.get('default_session', 'RTH')}",
        ]

        # Add sessions
        sessions = self.instrument.get("sessions", {})
        if sessions:
            session_strs = [f"{k}: {v[0]}-{v[1]}" for k, v in list(sessions.items())[:4]]
            lines.append(f"Sessions: {', '.join(session_strs)}")

        return "\n".join(lines)

    def present(
        self,
        data: dict,
        question: str = "",
        lang: str = "en",
        context_compacted: bool = False,
    ) -> DataResponse:
        """
        Format data for user presentation.

        Args:
            data: Query result from executor (rows, row_count, result, etc.)
            question: User's original question
            lang: User's language (ISO 639-1 code from IntentClassifier)
            context_compacted: True if conversation memory was compacted (old messages removed)

        Returns:
            DataResponse with acknowledge, title, summary
        """
        original_question = question

        # Extract rows and summary from executor result
        # Operations return {"rows": [...], "summary": {...}}
        result = data.get("result", {})
        rows = result.get("rows", [])
        summary = result.get("summary")  # Pre-computed answer data

        # Get columns from first row if available
        columns = list(rows[0].keys()) if rows else []
        row_count = data.get("row_count", len(rows))

        # If we have summary — use it for answer generation
        if summary:
            return self._present_with_summary(
                original_question, rows, columns, summary, lang, context_compacted
            )

        # No data
        if row_count == 0:
            summary = self._generate_no_data(original_question, lang)
            return DataResponse(
                acknowledge="",
                title=None,
                summary=summary,
                type=DataResponseType.NO_DATA,
                row_count=0,
            )

        # Single row — natural summary, no table
        if row_count == 1:
            summary = self._summarize_single(rows[0], columns, original_question, lang, context_compacted)
            return DataResponse(
                acknowledge=self._generate_acknowledge(original_question, lang),
                title=None,
                summary=summary,
                type=DataResponseType.SINGLE,
                row_count=1,
            )

        # Small dataset (2-5 rows) — summary + table
        if row_count <= self.INLINE_THRESHOLD:
            summary = self._summarize_small(rows, columns, original_question, lang, context_compacted)
            table = self._format_table(rows, columns)
            summary_with_table = f"{summary}\n\n{table}"
            return DataResponse(
                acknowledge=self._generate_acknowledge(original_question, lang),
                title=None,
                summary=summary_with_table,
                type=DataResponseType.INLINE,
                row_count=row_count,
            )

        # Large dataset (>5 rows) — DataCard + offer analysis
        title = self._generate_title(original_question, columns, row_count, lang)

        # Build context for LLM (flags from SQL + holidays/events from config)
        flag_counts = _count_flags(rows, columns)
        flags_context = _build_flags_context(flag_counts)

        dates = _extract_dates(rows)
        date_context = _build_date_context(dates, self.symbol)

        full_context = _merge_contexts(flags_context, date_context)

        # Generate summary with LLM using context
        if full_context:
            text = self._generate_summary(original_question, row_count, full_context, lang, context_compacted)
        else:
            text = TEMPLATES["large_data"].get(lang, TEMPLATES["large_data"]["en"]).format(row_count=row_count)

        return DataResponse(
            acknowledge=self._generate_acknowledge(original_question, lang),
            title=title,
            summary=text,
            type=DataResponseType.LARGE_DATA,
            row_count=row_count,
        )

    def _present_with_summary(
        self,
        question: str,
        rows: list[dict],
        columns: list[str],
        summary: dict,
        lang: str,
        context_compacted: bool = False,
    ) -> DataResponse:
        """
        Present data using pre-computed summary.

        Logic:
        - rows ≤ 5: acknowledge + table + summary text
        - rows > 5: acknowledge + summary text (table in UI via DataCard)
        """
        row_count = len(rows)

        # Generate acknowledge and summary text
        acknowledge = self._generate_acknowledge(question, lang)
        text = self._generate_summary_answer(question, summary, lang, context_compacted)

        # Small table (≤5 rows) — table first, then summary
        if row_count > 0 and row_count <= self.INLINE_THRESHOLD:
            table = self._format_table(rows, columns)
            table_then_text = f"{table}\n\n{text}"
            return DataResponse(
                acknowledge=acknowledge,
                title=None,
                summary=table_then_text,
                type=DataResponseType.INLINE,
                row_count=row_count,
            )

        # Large table — generate title for DataCard
        if row_count > self.INLINE_THRESHOLD:
            title = self._generate_title(question, columns, row_count, lang)
            return DataResponse(
                acknowledge=acknowledge,
                title=title,
                summary=text,
                type=DataResponseType.LARGE_DATA,
                row_count=row_count,
            )

        # No rows — just text
        return DataResponse(
            acknowledge=acknowledge,
            title=None,
            summary=text,
            type=DataResponseType.SINGLE,
            row_count=row_count,
        )

    def _generate_summary_answer(
        self,
        question: str,
        summary: dict,
        lang: str,
        context_compacted: bool = False,
    ) -> str:
        """Generate text answer from pre-computed summary using LLM."""
        import json
        # Format values for display using centralized rules
        formatted_summary = format_summary(summary)
        summary_str = json.dumps(formatted_summary, ensure_ascii=False)

        prompt = SUMMARY_ANSWER_PROMPT.format(
            question=question,
            summary=summary_str,
            lang=lang,
            instrument=self.instrument_context,
            context_compacted=str(context_compacted).lower(),
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    max_output_tokens=100,
                ),
            )
            return response.text.strip()
        except Exception:
            # Fallback — return raw summary
            if lang == "ru":
                return f"Результат: {summary_str}"
            return f"Result: {summary_str}"

    def _format_table(self, rows: list[dict], columns: list[str]) -> str:
        """Format data as markdown table.

        Hides flag columns (is_*) — they're already summarized in text.
        """
        if not rows or not columns:
            return ""

        # Filter out flag columns — already summarized in text
        data_cols = [c for c in columns if not c.startswith("is_")]

        # Limit to 5 for readability
        display_cols = data_cols[:5]

        lines = []

        # Header
        header = "| " + " | ".join(display_cols) + " |"
        separator = "| " + " | ".join(["---"] * len(display_cols)) + " |"
        lines.append(header)
        lines.append(separator)

        # Rows
        for row in rows:
            values = [str(row.get(col, "")) for col in display_cols]
            line = "| " + " | ".join(values) + " |"
            lines.append(line)

        return "\n".join(lines)

    def _summarize_single(
        self,
        row: dict,
        columns: list[str],
        question: str,
        lang: str,
        context_compacted: bool = False,
    ) -> str:
        """Generate summary for single row using LLM with context."""
        # Count flags from SQL (patterns)
        flag_counts = _count_flags([row], columns)
        flags_context = _build_flags_context(flag_counts)

        # Get date and check holidays/events via config
        date_val = row.get("date") or row.get("ts") or row.get("timestamp")
        dates = _extract_dates([row])
        date_context = _build_date_context(dates, self.symbol)

        full_context = _merge_contexts(flags_context, date_context)

        if full_context:
            # Use LLM to write natural summary
            return self._generate_summary_short(question, 1, full_context, lang, date_val, context_compacted)

        # Fallback — simple template
        if lang == "ru":
            return f"Данные за {date_val}." if date_val else "Вот данные."
        return f"Data for {date_val}." if date_val else "Here's the data."

    def _summarize_small(
        self,
        rows: list[dict],
        columns: list[str],
        question: str,
        lang: str,
        context_compacted: bool = False,
    ) -> str:
        """Generate summary for small dataset (2-5 rows) using LLM with context."""
        row_count = len(rows)

        # Count flags from SQL (patterns)
        flag_counts = _count_flags(rows, columns)
        flags_context = _build_flags_context(flag_counts)

        # Check dates for holidays/events via config
        dates = _extract_dates(rows)
        date_context = _build_date_context(dates, self.symbol)

        full_context = _merge_contexts(flags_context, date_context)

        if full_context:
            # Use LLM to write natural summary
            return self._generate_summary_short(question, row_count, full_context, lang, None, context_compacted)

        # Fallback — simple template
        if lang == "ru":
            return f"Вот {row_count} записей."
        return f"Here are {row_count} records."

    def _generate_summary_short(
        self,
        question: str,
        row_count: int,
        flags_context: str,
        lang: str,
        date_val: str | None = None,
        context_compacted: bool = False,
    ) -> str:
        """Generate short summary (1 sentence) for small datasets."""
        date_info = f", date: {date_val}" if date_val else ""
        prompt = SHORT_SUMMARY_PROMPT.format(
            question=question,
            row_count=row_count,
            date_info=date_info,
            flags_context=flags_context,
            lang=lang,
            context_compacted=str(context_compacted).lower(),
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    max_output_tokens=80,
                ),
            )
            return response.text.strip()
        except Exception:
            if lang == "ru":
                return f"Вот данные, {row_count} строк."
            return f"Here's the data, {row_count} rows."

    def _generate_acknowledge(self, question: str, lang: str) -> str:
        """Generate acknowledge message using LLM.

        Returns short confirmation like "Понял, получаю волатильность за 2024..."
        """
        prompt = ACKNOWLEDGE_PROMPT.format(question=question, lang=lang)

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=50,
                ),
            )
            return response.text.strip()
        except Exception:
            # Fallback
            if lang == "ru":
                return "Понял, получаю данные..."
            return "Got it, fetching data..."

    def _generate_no_data(self, question: str, lang: str) -> str:
        """Generate no-data response using LLM.

        Returns context-aware message like "Данных за 2099 год нет — попробуй другой период."
        """
        prompt = NO_DATA_PROMPT.format(question=question, lang=lang)

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=60,
                ),
            )
            return response.text.strip()
        except Exception:
            # Fallback
            return TEMPLATES["no_data"].get(lang, TEMPLATES["no_data"]["en"])

    def _generate_title(
        self,
        question: str,
        columns: list[str],
        row_count: int,
        lang: str,
    ) -> str:
        """Generate DataCard title using LLM."""
        prompt = TITLE_PROMPT.format(
            question=question,
            columns=", ".join(columns[:5]),
            row_count=row_count,
            lang=lang,
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=30,
                ),
            )
            return response.text.strip().strip('"\'')
        except Exception:
            return f"{self.symbol} Data"

    def _generate_summary(
        self,
        question: str,
        row_count: int,
        flags_context: str,
        lang: str,
        context_compacted: bool = False,
    ) -> str:
        """Generate data summary using LLM with flags as context.

        LLM writes summary in natural language using pre-computed flags
        as hints — doesn't interpret raw data, just formulates nicely.
        """
        prompt = SUMMARY_PROMPT.format(
            question=question,
            row_count=row_count,
            flags_context=flags_context,
            lang=lang,
            context_compacted=str(context_compacted).lower(),
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.5,
                    max_output_tokens=150,
                ),
            )
            return response.text.strip()
        except Exception:
            # Fallback to simple template
            return TEMPLATES["large_data"].get(lang, TEMPLATES["large_data"]["en"]).format(row_count=row_count)


# =============================================================================
# SIMPLE API
# =============================================================================

def present(
    question: str,
    data: dict,
    symbol: str = "NQ",
    lang: str = "en",
    context_compacted: bool = False,
) -> str:
    """
    Format data for user presentation.

    Simple wrapper for Presenter class.

    Args:
        question: User's original question
        data: Executor result dict
        symbol: Trading symbol
        lang: User's language (ISO 639-1 code)
        context_compacted: True if conversation memory was compacted

    Returns:
        Formatted text string
    """
    intent = data.get("intent")

    if intent == "no_data":
        if lang == "ru":
            return "Ничего не нашлось. Попробуй другой период или фильтры."
        return "Nothing found. Try different period or filters."

    if intent == "chitchat":
        if lang == "ru":
            return "Привет! Чем могу помочь с анализом данных?"
        return "Hi! How can I help with data analysis?"

    if intent == "concept":
        topic = data.get("topic", "")
        return f"TODO: explain {topic}"

    if intent == "clarification":
        unclear = data.get("unclear", [])
        if lang == "ru":
            return f"Уточни: {', '.join(unclear)}"
        return f"Please clarify: {', '.join(unclear)}"

    # Data intent — use Presenter
    presenter = Presenter(symbol=symbol)
    response = presenter.present(data, question, lang, context_compacted)
    return response.text
