"""
DataResponder — handles query results.

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
    OFFER_ANALYSIS = "offer_analysis"  # >5 rows, ask about analysis


@dataclass
class DataResponse:
    """Response from DataResponder."""

    text: str
    type: DataResponseType
    title: str | None = None  # DataCard title (only for offer_analysis)
    row_count: int = 0


def _detect_language(text: str) -> str:
    """Simple language detection based on character set."""
    cyrillic_count = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
    return "ru" if cyrillic_count > len(text) * 0.3 else "en"


# Templates — friendly, like a colleague
TEMPLATES = {
    "no_data": {
        "ru": "Ничего не нашлось. Попробуй другой период или фильтры.",
        "en": "Nothing found. Try different period or filters.",
    },
    "offer_analysis": {
        "ru": "Готово, {row_count} строк. Там много интересного — хочешь анализ?",
        "en": "Done, {row_count} rows. Lots of interesting stuff — want analysis?",
    },
}


TITLE_PROMPT = """Generate a short title (3-6 words) for this data card.

User question: {question}
Data: {row_count} rows, columns: {columns}

Return ONLY the title in the same language as the question."""


SUMMARY_PROMPT = """Write a brief data summary (1-2 sentences) for a trading colleague.

Question: {question}
Data: {row_count} rows

Context from data (pre-computed flags — use as hints, don't quote literally):
{flags_context}

Rules:
- Write in the same language as the question
- Be concise, friendly, like a colleague
- Use the flag context to mention what's notable (holidays, events, patterns)
- Don't interpret raw numbers — just mention the context
- End with a natural transition like "хочешь анализ?" or "want analysis?"

Example (RU): "Вот данные за декабрь, 21 день. Учти, попало раннее закрытие перед праздником. Было несколько молотов — покупатели отбивали низы. Хочешь детальный анализ?"
Example (EN): "Here's December data, 21 days. Note: includes early close before holiday. Few hammers — buyers defended lows. Want detailed analysis?\""""


class DataResponder:
    """
    Handles query results.

    Friendly, concise, professional — like a colleague.
    Uses domain knowledge to summarize naturally.

    Logic:
    - 0 rows → "Ничего не нашлось"
    - 1 row → natural summary (no table)
    - 2-5 rows → summary + inline table
    - >5 rows → DataCard + "Хочешь анализ?"

    Usage:
        responder = DataResponder(symbol="NQ")
        result = responder.respond(query, data, original_question)
        # 1 row → "10 января был диапазон 150 пунктов, закрылись выше открытия."
        # 5 rows → "Вот 5 пятниц. В среднем диапазон 120 пунктов.\n\n| date | ... |"
    """

    INLINE_THRESHOLD = 5

    def __init__(self, symbol: str = "NQ"):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = config.GEMINI_LITE_MODEL
        self.symbol = symbol

    def respond(
        self,
        data: dict,
        question: str = "",
    ) -> DataResponse:
        """
        Generate response for query data.

        Args:
            data: Query result from executor (rows, row_count, result, etc.)
            question: User's original question

        Returns:
            DataResponse with text, type, optional title
        """
        original_question = question

        # Extract rows from executor result
        # v2 executor puts rows in result["rows"] for list/filter operations
        result = data.get("result", {})
        rows = result.get("rows", [])

        # Get columns from first row if available
        columns = list(rows[0].keys()) if rows else []
        row_count = data.get("row_count", len(rows))

        lang = _detect_language(original_question)

        # No data
        if row_count == 0:
            return DataResponse(
                text=TEMPLATES["no_data"][lang],
                type=DataResponseType.NO_DATA,
                row_count=0,
            )

        # Single row — natural summary, no table
        if row_count == 1:
            text = self._summarize_single(rows[0], columns, original_question)
            return DataResponse(
                text=text,
                type=DataResponseType.SINGLE,
                row_count=1,
            )

        # Small dataset (2-5 rows) — summary + table
        if row_count <= self.INLINE_THRESHOLD:
            summary = self._summarize_small(rows, columns, original_question)
            table = self._format_table(rows, columns)
            text = f"{summary}\n\n{table}"
            return DataResponse(
                text=text,
                type=DataResponseType.INLINE,
                row_count=row_count,
            )

        # Large dataset (>5 rows) — DataCard + offer analysis
        title = self._generate_title(original_question, columns, row_count)

        # Build context for LLM (flags from SQL + holidays/events from config)
        flag_counts = _count_flags(rows, columns)
        flags_context = _build_flags_context(flag_counts)

        dates = _extract_dates(rows)
        date_context = _build_date_context(dates, self.symbol)

        full_context = _merge_contexts(flags_context, date_context)

        # Generate summary with LLM using context
        if full_context:
            text = self._generate_summary(original_question, row_count, full_context)
        else:
            text = TEMPLATES["offer_analysis"][lang].format(row_count=row_count)

        return DataResponse(
            text=text,
            type=DataResponseType.OFFER_ANALYSIS,
            title=title,
            row_count=row_count,
        )

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
    ) -> str:
        """Generate summary for single row using LLM with context."""
        lang = _detect_language(question)

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
            return self._generate_summary_short(question, 1, full_context, date_val)

        # Fallback — simple template
        if lang == "ru":
            return f"Данные за {date_val}." if date_val else "Вот данные."
        return f"Data for {date_val}." if date_val else "Here's the data."

    def _summarize_small(
        self,
        rows: list[dict],
        columns: list[str],
        question: str,
    ) -> str:
        """Generate summary for small dataset (2-5 rows) using LLM with context."""
        lang = _detect_language(question)
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
            return self._generate_summary_short(question, row_count, full_context)

        # Fallback — simple template
        if lang == "ru":
            return f"Вот {row_count} записей."
        return f"Here are {row_count} records."

    def _generate_summary_short(
        self,
        question: str,
        row_count: int,
        flags_context: str,
        date_val: str | None = None,
    ) -> str:
        """Generate short summary (1 sentence) for small datasets."""
        prompt = f"""Write ONE sentence summary for trading data.

Question: {question}
Data: {row_count} row(s){f', date: {date_val}' if date_val else ''}

Context (pre-computed flags — use as hints):
{flags_context}

Rules:
- Same language as question
- ONE sentence, concise
- Mention notable context (events, patterns)
- Don't end with question

Example (RU): "Данные за 15 декабря — было раннее закрытие, сформировался молот."
Example (EN): "December 15 data — early close day, hammer formed.\""""

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
            lang = _detect_language(question)
            if lang == "ru":
                return f"Вот данные, {row_count} строк."
            return f"Here's the data, {row_count} rows."

    def _generate_title(
        self,
        question: str,
        columns: list[str],
        row_count: int,
    ) -> str:
        """Generate DataCard title using LLM."""
        prompt = TITLE_PROMPT.format(
            question=question,
            columns=", ".join(columns[:5]),
            row_count=row_count,
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
    ) -> str:
        """Generate data summary using LLM with flags as context.

        LLM writes summary in natural language using pre-computed flags
        as hints — doesn't interpret raw data, just formulates nicely.
        """
        prompt = SUMMARY_PROMPT.format(
            question=question,
            row_count=row_count,
            flags_context=flags_context,
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
            lang = _detect_language(question)
            return TEMPLATES["offer_analysis"][lang].format(row_count=row_count)


# =============================================================================
# SIMPLE API
# =============================================================================

def respond(question: str, data: dict, symbol: str = "NQ") -> str:
    """
    Generate human-friendly response for executor result.

    Simple wrapper for DataResponder.

    Args:
        question: User's original question
        data: Executor result dict
        symbol: Trading symbol

    Returns:
        Response text string
    """
    intent = data.get("intent")

    # Handle non-data intents
    is_ru = any('\u0400' <= c <= '\u04FF' for c in question)

    if intent == "no_data":
        if is_ru:
            return "Ничего не нашлось. Попробуй другой период или фильтры."
        return "Nothing found. Try different period or filters."

    if intent == "chitchat":
        if is_ru:
            return "Привет! Чем могу помочь с анализом данных?"
        return "Hi! How can I help with data analysis?"

    if intent == "concept":
        topic = data.get("topic", "")
        return f"TODO: explain {topic}"

    if intent == "clarification":
        unclear = data.get("unclear", [])
        if is_ru:
            return f"Уточни: {', '.join(unclear)}"
        return f"Please clarify: {', '.join(unclear)}"

    # Data intent — use DataResponder
    responder = DataResponder(symbol=symbol)
    response = responder.respond(data, question)
    return response.text
