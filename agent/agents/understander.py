"""Understander agent - parses user questions into structured query_spec.

Converts natural language questions into JSON query_spec that QueryBuilder
transforms deterministically into SQL.

Architecture (RAP - Retrieval-Augmented Prompting):
    Question → Classifier (lite model) → query_type
            → Handler (main model) → query_spec → QueryBuilder → SQL

Instead of one 800-token monolithic prompt, we use:
1. Classifier (~50 tokens) - determines query type
2. Handler (~50-200 tokens) - specialized prompt for that type

Benefits:
- ~80% token savings on average
- Better model focus (only relevant instructions)
- Easier to maintain and test

Example:
    understander = Understander()
    result = understander({"question": "What was NQ high in January 2024?"})
    # result["intent"]["query_spec"] contains structured params for QueryBuilder
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING
from google import genai
from google.genai import types

import config

if TYPE_CHECKING:
    from agent.query_builder import QuerySpec
from agent.state import AgentState, Intent, UsageStats, get_current_question, get_chat_history
from agent.pricing import calculate_cost

# Default symbol when not specified
DEFAULT_SYMBOL = "NQ"
from agent.modules.sql import get_data_range
from agent.query_builder.holidays import get_holidays_for_year
from agent.domain import apply_defaults

# RAP prompts (new modular approach)
from agent.prompts.understander import (
    get_classifier_prompt,
    get_handler_prompt,
    QueryType,
)

# Schema auto-generation (Single Source of Truth)
from agent.query_builder.schema import (
    get_query_spec_schema,
    get_response_schema,
    get_special_op_map,
)


# =============================================================================
# JSON Schema для query_spec (auto-generated from types.py)
# =============================================================================

# Auto-generated schemas - Single Source of Truth
# Все типы определены в agent/query_builder/types.py
# Schema генерируется автоматически из этих типов
QUERY_SPEC_SCHEMA = get_query_spec_schema()
RESPONSE_SCHEMA = get_response_schema()


# =============================================================================
# Holiday Check Helper
# =============================================================================

def check_dates_for_holidays(
    dates: list[str],
    symbol: str = "NQ",
    time_filter: tuple[str, str] | None = None
) -> dict | None:
    """
    Check if any requested dates fall on market holidays or early close.

    Args:
        dates: List of date strings in YYYY-MM-DD format
        symbol: Trading instrument symbol
        time_filter: Optional (start_time, end_time) to check early close conflicts

    Returns:
        None if no issues, or dict with:
        - holiday_dates: list of dates that are full holidays
        - early_close_dates: list of dates that are early close
        - holiday_names: dict mapping date -> holiday name
        - all_holidays: True if ALL dates are full holidays
        - early_close_conflict: True if time_filter conflicts with early close
    """
    if not dates:
        return None

    # Get unique years from dates
    years = set()
    for d in dates:
        try:
            years.add(int(d[:4]))
        except (ValueError, IndexError):
            continue

    # Collect holidays for these years
    full_close_map = {}  # date -> name
    early_close_map = {}  # date -> name

    for year in years:
        holidays = get_holidays_for_year(symbol, year)
        for d in holidays.get("full_close", []):
            full_close_map[d.isoformat()] = _get_holiday_name(d)
        for d in holidays.get("early_close", []):
            early_close_map[d.isoformat()] = _get_early_close_name(d)

    # Check which requested dates are holidays
    holiday_dates = []
    early_close_dates = []
    holiday_names = {}

    for d in dates:
        if d in full_close_map:
            holiday_dates.append(d)
            holiday_names[d] = full_close_map[d]
        elif d in early_close_map:
            early_close_dates.append(d)
            holiday_names[d] = early_close_map[d] + " (early close)"

    if not holiday_dates and not early_close_dates:
        return None

    # Check if time filter conflicts with early close (market closes at 13:00 on these days)
    early_close_conflict = False
    if time_filter and early_close_dates:
        start_time, end_time = time_filter
        # Early close is typically 13:00 ET
        if end_time and end_time > "13:00:00":
            early_close_conflict = True

    return {
        "holiday_dates": holiday_dates,
        "early_close_dates": early_close_dates,
        "holiday_names": holiday_names,
        "all_holidays": len(holiday_dates) == len(dates) and len(dates) > 0,
        "early_close_conflict": early_close_conflict,
    }


def _get_holiday_name(d) -> str:
    """Get human-readable holiday name for a date."""
    # Common US market holidays
    month_day = (d.month, d.day)

    # Fixed holidays (approximate - actual dates may vary)
    if month_day == (1, 1):
        return "New Year's Day"
    if month_day == (7, 4):
        return "Independence Day"
    if month_day == (12, 25):
        return "Christmas Day"

    # Variable holidays (approximate by month)
    if d.month == 1 and d.weekday() == 0 and 15 <= d.day <= 21:
        return "Martin Luther King Jr. Day"
    if d.month == 2 and d.weekday() == 0 and 15 <= d.day <= 21:
        return "Presidents Day"
    if d.month == 5 and d.weekday() == 0 and d.day >= 25:
        return "Memorial Day"
    if d.month == 6 and d.day == 19:
        return "Juneteenth"
    if d.month == 9 and d.weekday() == 0 and d.day <= 7:
        return "Labor Day"
    if d.month == 11 and d.weekday() == 3 and 22 <= d.day <= 28:
        return "Thanksgiving"

    # Good Friday (variable, usually March/April)
    if d.month in (3, 4) and d.weekday() == 4:
        return "Good Friday"

    return "Market Holiday"


def _get_early_close_name(d) -> str:
    """Get human-readable name for early close days."""
    month_day = (d.month, d.day)

    # Common early close days
    if month_day == (12, 24):
        return "Christmas Eve"
    if month_day == (7, 3):
        return "Day before Independence Day"

    # Day after Thanksgiving (Black Friday)
    if d.month == 11 and d.weekday() == 4 and 23 <= d.day <= 29:
        return "Black Friday"

    return "Early Close Day"


# =============================================================================
# Understander Agent
# =============================================================================

class Understander:
    """Parses user questions into structured query_spec for QueryBuilder.

    Uses RAP (Retrieval-Augmented Prompting) architecture:
    1. Classifier - determines query type (~50 tokens)
    2. Handler - specialized prompt for that type (~50-200 tokens)

    Benefits:
    - ~80% token savings vs monolithic prompt
    - Better model focus (only relevant instructions)
    - Easier to maintain and test

    Attributes:
        name: Agent name for logging.
        agent_type: Agent type ("routing" - decides next step in pipeline).
        model: Gemini model name from config.
    """

    name = "understander"
    agent_type = "routing"

    def __init__(self):
        """Initialize Gemini client and usage tracking."""
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = config.GEMINI_MODEL
        self._last_usage = UsageStats(
            input_tokens=0,
            output_tokens=0,
            thinking_tokens=0,
            cost_usd=0.0
        )

    def __call__(self, state: AgentState) -> dict:
        """Parse question and return structured Intent.

        Args:
            state: Current agent state with messages (MessagesState).

        Returns:
            Dict with intent, usage stats, agents_used list, and step_number.
        """
        question = get_current_question(state)
        chat_history = get_chat_history(state)

        # Debug: log messages state for checkpointer debugging
        messages = state.get("messages", [])
        history_str = self._format_chat_history(chat_history)
        debug_info = {
            "messages_count": len(messages),
            "chat_history_length": len(chat_history),
            "chat_history_preview": history_str[:500] if history_str else "",
            "has_history_context": bool(history_str),
        }
        print(f"[Understander DEBUG] messages={len(messages)}, history={len(chat_history)}, has_context={bool(history_str)}")

        intent = self._parse_with_rap(question, chat_history)

        # Add debug info inside intent (so it passes through LangGraph state)
        intent["_debug"] = debug_info

        return {
            "intent": intent,
            "usage": self._last_usage,
            "agents_used": [self.name],
            "step_number": state.get("step_number", 0) + 1,
        }

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_data_info(self) -> str:
        """Get available data info for prompt context."""
        data_range = get_data_range("NQ")
        if data_range:
            return (
                f"Символ: NQ\n"
                f"Период данных: {data_range['start_date']} — {data_range['end_date']}\n"
                f"Торговых дней: {data_range['trading_days']}"
            )
        return "Данные: NQ"

    def _format_chat_history(self, chat_history: list) -> str:
        """Format chat history for prompts."""
        if not chat_history:
            return ""
        history_str = ""
        for msg in chat_history[-config.CHAT_HISTORY_LIMIT:]:
            role = "User" if msg.get("role") == "user" else "Assistant"
            history_str += f"{role}: {msg.get('content', '')}\n"
        return history_str

    # =========================================================================
    # RAP Methods (New Architecture)
    # =========================================================================

    def _parse_with_rap(self, question: str, chat_history: list) -> Intent:
        """Parse question using RAP architecture (Classifier + Handler).

        Steps:
        1. Classify question type (~50 tokens)
        2. Load appropriate handler for that type
        3. Generate response with handler prompt (~50-200 tokens)

        Total: ~100-250 tokens instead of 800 tokens.
        """
        # Step 1: Classify
        history_str = self._format_chat_history(chat_history)
        query_type = self._classify(question, history_str)
        print(f"[Understander RAP] Classified as: {query_type}")

        # Step 2: Generate with handler
        intent = self._generate_with_handler(question, query_type, history_str)

        # Step 3: Apply instrument-aware defaults
        intent = self._apply_defaults(intent, question)

        # Step 4: Check for holiday dates
        intent = self._check_holiday_intent(intent)

        return intent

    def _classify(self, question: str, chat_history: str) -> str:
        """Classify question type.

        Returns query type string like "data.event_time" or "chitchat".
        """
        prompt = get_classifier_prompt(question, chat_history)

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,  # Deterministic classification
                response_mime_type="application/json",
            )
        )

        # Track classifier usage
        if response.usage_metadata:
            input_tokens = response.usage_metadata.prompt_token_count or 0
            output_tokens = response.usage_metadata.candidates_token_count or 0
            cost = calculate_cost(input_tokens, output_tokens, 0)
            self._classifier_usage = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost,
            }

        data = json.loads(response.text)
        return data.get("type", "data.simple")

    def _generate_with_handler(self, question: str, query_type: str, chat_history: str) -> Intent:
        """Generate response using appropriate handler prompt."""
        # Build handler prompt
        prompt = get_handler_prompt(
            query_type=query_type,
            question=question,
            chat_history=chat_history,
            data_info=self._get_data_info(),
            today=datetime.now().strftime("%Y-%m-%d"),
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
            )
        )

        # Track handler usage + combine with classifier
        if response.usage_metadata:
            input_tokens = response.usage_metadata.prompt_token_count or 0
            output_tokens = response.usage_metadata.candidates_token_count or 0
            thinking_tokens = getattr(response.usage_metadata, 'thoughts_token_count', 0) or 0
            cost = calculate_cost(input_tokens, output_tokens, thinking_tokens)

            # Add classifier usage
            classifier = getattr(self, '_classifier_usage', {})
            self._last_usage = UsageStats(
                input_tokens=input_tokens + classifier.get("input_tokens", 0),
                output_tokens=output_tokens + classifier.get("output_tokens", 0),
                thinking_tokens=thinking_tokens,
                cost_usd=cost + classifier.get("cost_usd", 0.0)
            )

        data = json.loads(response.text)
        return self._build_intent(data)

    def _check_holiday_intent(self, intent: Intent) -> Intent:
        """
        Check if intent requests data for holiday or early close dates.

        Checks both specific_dates and period ranges.
        Adds holiday_info to intent for Analyst to explain.

        Args:
            intent: Original intent from LLM

        Returns:
            Modified intent with holiday_info if detected, original otherwise
        """
        if intent.get("type") != "data":
            return intent

        query_spec = intent.get("query_spec")
        if not query_spec:
            return intent

        filters = query_spec.get("filters", {})
        symbol = query_spec.get("symbol", DEFAULT_SYMBOL)

        # Get time filter for early close check
        time_filter = None
        time_start = filters.get("time_start")
        time_end = filters.get("time_end")
        if time_start and time_end:
            time_filter = (time_start, time_end)

        holiday_check = None

        # Check specific_dates first
        specific_dates = filters.get("specific_dates")
        if specific_dates:
            holiday_check = check_dates_for_holidays(specific_dates, symbol, time_filter)

        # Also check period range for holidays
        period_start = filters.get("period_start")
        period_end = filters.get("period_end")
        if period_start and period_end and period_start != "all" and period_end != "all":
            period_holidays = self._check_period_for_holidays(
                symbol, period_start, period_end
            )
            if period_holidays:
                if holiday_check:
                    # Merge with specific_dates check
                    holiday_check["holiday_dates"].extend(period_holidays.get("holiday_dates", []))
                    holiday_check["early_close_dates"].extend(period_holidays.get("early_close_dates", []))
                    holiday_check["holiday_names"].update(period_holidays.get("holiday_names", {}))
                else:
                    holiday_check = period_holidays

        if not holiday_check:
            return intent

        # Build info strings for logging
        all_dates = holiday_check.get("holiday_dates", []) + holiday_check.get("early_close_dates", [])
        if not all_dates:
            return intent

        holiday_info_str = ", ".join(
            f"{d} ({holiday_check['holiday_names'].get(d, 'holiday')})"
            for d in all_dates[:5]  # Limit to 5 for logging
        )
        if len(all_dates) > 5:
            holiday_info_str += f" (+{len(all_dates) - 5} more)"

        if holiday_check.get("all_holidays"):
            print(f"[Understander] All dates are holidays: {holiday_info_str}")
        elif holiday_check.get("early_close_conflict"):
            print(f"[Understander] Early close conflict: {holiday_info_str}")
        elif all_dates:
            print(f"[Understander] Period contains holidays: {holiday_info_str}")

        # Add holiday_info to intent for Analyst to use
        intent["holiday_info"] = {
            "dates": all_dates,
            "names": holiday_check["holiday_names"],
            "all_holidays": holiday_check.get("all_holidays", False),
            "early_close_dates": holiday_check.get("early_close_dates", []),
            "early_close_conflict": holiday_check.get("early_close_conflict", False),
            "count": len(all_dates),
        }

        return intent

    def _check_period_for_holidays(
        self,
        symbol: str,
        period_start: str,
        period_end: str,
    ) -> dict | None:
        """Check period range for holidays using holiday filter module."""
        from agent.query_builder.filters.holiday import get_holiday_dates_for_period
        from agent.query_builder.holidays import get_day_type
        from datetime import date as dt_date

        # Get all holiday dates in period
        holiday_dates = get_holiday_dates_for_period(
            symbol, period_start, period_end,
            include_holidays=True, include_early_close=True
        )

        if not holiday_dates:
            return None

        # Filter to only dates within actual period
        try:
            start = dt_date.fromisoformat(period_start)
            end = dt_date.fromisoformat(period_end)
            holiday_dates = [d for d in holiday_dates if start <= d < end]
        except (ValueError, TypeError):
            pass

        if not holiday_dates:
            return None

        # Categorize dates
        full_close = []
        early_close = []
        names = {}

        for d in holiday_dates:
            day_type = get_day_type(symbol, d)
            date_str = d.isoformat()
            if day_type == "closed":
                full_close.append(date_str)
                names[date_str] = _get_holiday_name(d)
            elif day_type == "early_close":
                early_close.append(date_str)
                names[date_str] = _get_early_close_name(d) + " (early close)"

        if not full_close and not early_close:
            return None

        return {
            "holiday_dates": full_close,
            "early_close_dates": early_close,
            "holiday_names": names,
            "all_holidays": False,
            "early_close_conflict": False,
        }

    def _apply_defaults(self, intent: Intent, question: str = "") -> Intent:
        """
        Apply instrument-aware defaults for "_default_" markers.

        When LLM returns "_default_" for a field (user implied but didn't specify),
        this method resolves it to actual value based on instrument config.

        Args:
            intent: Intent with potential "_default_" markers
            question: Original user question (for language-aware clarification)

        Returns:
            Intent with resolved values and assumptions list
        """
        if intent.get("type") != "data":
            return intent

        query_spec = intent.get("query_spec", {})
        symbol = query_spec.get("symbol", DEFAULT_SYMBOL)

        # Apply defaults using domain logic
        intent = apply_defaults(intent, symbol)

        # Log assumptions
        assumptions = intent.get("assumptions", [])
        if assumptions:
            assumptions_str = ", ".join(
                f"{a['field']}={a['value']}" for a in assumptions
            )
            print(f"[Understander] Applied defaults: {assumptions_str}")

        # Check if clarification is needed
        needs_clarification = intent.get("needs_clarification")
        if needs_clarification:
            print(f"[Understander] Needs clarification: {needs_clarification}")
            # Convert to clarification intent
            intent = self._convert_to_clarification(intent, needs_clarification, question)

        return intent

    def _convert_to_clarification(
        self, intent: Intent, needs: dict, question: str = ""
    ) -> Intent:
        """
        Convert data intent to clarification when defaults couldn't be resolved.

        Args:
            intent: Original data intent
            needs: Dict of fields needing clarification {field: [options]}
            question: Original user question (for language detection)

        Returns:
            Clarification intent with question and suggestions
        """
        # Detect language from question (simple heuristic: Cyrillic = Russian)
        is_russian = any("\u0400" <= c <= "\u04ff" for c in question)

        # Extract date from intent for contextual message
        query_spec = intent.get("query_spec", {})
        filters = query_spec.get("filters", {})
        specific_dates = filters.get("specific_dates", [])
        # Try specific_dates first, then period_start for single-day queries
        date_str = ""
        if specific_dates:
            date_str = specific_dates[0]
        elif filters.get("period_start"):
            date_str = filters.get("period_start")

        # Build clarification question and suggestions
        # Note: use "response_text" for responder compatibility
        if "trading_day_or_session" in needs:
            options = needs["trading_day_or_session"]

            # Check if market is closed (weekend/holiday) — return direct response, no options
            if options and options[0].startswith("Market closed"):
                return self._build_market_closed_response(date_str, is_russian)

            if is_russian:
                if date_str:
                    response = f"Уточните, что вы имеете в виду под датой {date_str}:"
                else:
                    response = "Уточните, что вы имеете в виду:"
            else:
                if date_str:
                    response = f"Please clarify what you mean by '{date_str}':"
                else:
                    response = "Please clarify what you mean by this date:"

            return {
                "type": "clarification",
                "response_text": response,
                "suggestions": options[:4],
                "original_intent": intent,
            }

        if "session" in needs:
            sessions = needs["session"]
            response = (
                "Какую торговую сессию вы имеете в виду?"
                if is_russian
                else "Which trading session do you mean?"
            )
            return {
                "type": "clarification",
                "response_text": response,
                "suggestions": sessions[:4],
                "original_intent": intent,
            }

        # Generic fallback
        fields = list(needs.keys())
        response = (
            f"Уточните: {', '.join(fields)}"
            if is_russian
            else f"Please clarify: {', '.join(fields)}"
        )
        return {
            "type": "clarification",
            "response_text": response,
            "suggestions": [],
            "original_intent": intent,
        }

    def _build_market_closed_response(self, date_str: str, is_russian: bool) -> Intent:
        """
        Build response for market closed days (weekends/holidays).

        Returns a direct response without suggestions - just explains market
        was closed and suggests adjacent trading days.
        """
        from datetime import datetime, timedelta

        # Find adjacent trading days
        prev_day = ""
        next_day = ""

        if date_str:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                weekday = dt.weekday()
                weekday_names_ru = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
                weekday_names_en = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

                # Find previous trading day (go back until weekday < 5)
                prev_dt = dt - timedelta(days=1)
                while prev_dt.weekday() >= 5:
                    prev_dt -= timedelta(days=1)
                prev_day = prev_dt.strftime("%Y-%m-%d")
                prev_weekday = weekday_names_ru[prev_dt.weekday()] if is_russian else weekday_names_en[prev_dt.weekday()]

                # Find next trading day (go forward until weekday < 5)
                next_dt = dt + timedelta(days=1)
                while next_dt.weekday() >= 5:
                    next_dt += timedelta(days=1)
                next_day = next_dt.strftime("%Y-%m-%d")
                next_weekday = weekday_names_ru[next_dt.weekday()] if is_russian else weekday_names_en[next_dt.weekday()]

                day_name = weekday_names_ru[weekday] if is_russian else weekday_names_en[weekday]

                if is_russian:
                    response = (
                        f"Рынок был закрыт {date_str} ({day_name}). "
                        f"Ближайшие торговые дни: {prev_day} ({prev_weekday}) или {next_day} ({next_weekday})."
                    )
                else:
                    response = (
                        f"Market was closed on {date_str} ({day_name}). "
                        f"Nearest trading days: {prev_day} ({prev_weekday}) or {next_day} ({next_weekday})."
                    )
            except ValueError:
                response = (
                    "Рынок был закрыт в этот день." if is_russian
                    else "Market was closed on this day."
                )
        else:
            response = (
                "Рынок был закрыт в этот день." if is_russian
                else "Market was closed on this day."
            )

        return {
            "type": "clarification",  # Goes through responder, no data fetch
            "response_text": response,
            "suggestions": [],  # No options - just informational response
        }

    def _build_intent(self, data: dict) -> Intent:
        """Build Intent object from parsed LLM response.

        Args:
            data: Parsed JSON from LLM response.

        Returns:
            Intent dict with type, query_spec, and other fields.
        """
        intent_type = data.get("type", "data")

        intent: Intent = {
            "type": intent_type,
            "symbol": DEFAULT_SYMBOL,
            "suggestions": data.get("suggestions", []),
        }

        if intent_type == "data":
            # Извлекаем query_spec (дефолты применяются позже в _apply_defaults)
            query_spec = data.get("query_spec", {})
            intent["query_spec"] = query_spec

            # Для совместимости добавляем period_start/end на верхний уровень
            filters = query_spec.get("filters", {})
            intent["period_start"] = filters.get("period_start")
            intent["period_end"] = filters.get("period_end")

        elif intent_type == "concept":
            intent["concept"] = data.get("concept", "")

        elif intent_type == "clarification":
            # Model may return either clarification_question or response_text
            intent["response_text"] = (
                data.get("clarification_question") or
                data.get("response_text") or
                "Уточните ваш запрос"
            )

        elif intent_type in ("chitchat", "out_of_scope"):
            intent["response_text"] = data.get("response_text", "")

        return intent

    def _default_intent(self) -> Intent:
        """Return default intent on error (fallback)."""
        start, end = self._full_data_range()
        return {
            "type": "data",
            "symbol": DEFAULT_SYMBOL,
            "period_start": start,
            "period_end": end,
            "query_spec": {
                "source": "daily",
                "filters": {
                    "period_start": start,
                    "period_end": end,
                },
                "grouping": "total",
                "metrics": [
                    {"metric": "count", "alias": "trading_days"},
                ],
                "special_op": "none",
            },
        }

    def _full_data_range(self) -> tuple[str, str]:
        """Return full available data range from database."""
        data_range = get_data_range("NQ")
        if data_range:
            return data_range['start_date'], data_range['end_date']
        return "2008-01-01", datetime.now().strftime("%Y-%m-%d")


# =============================================================================
# Conversion Functions
# =============================================================================

def query_spec_to_builder(query_spec: dict) -> "QuerySpec":
    """Convert JSON query_spec to QuerySpec dataclass for QueryBuilder.

    Transforms the JSON dict from Understander into typed QuerySpec object
    that QueryBuilder uses to generate SQL.

    Args:
        query_spec: JSON dict from Understander LLM response.

    Returns:
        QuerySpec dataclass instance ready for QueryBuilder.build().
    """
    from agent.query_builder import (
        QuerySpec,
        Source,
        Filters,
        Condition,
        Grouping,
        Metric,
        MetricSpec,
        SpecialOp,
    )
    from agent.query_builder.types import HolidayFilter

    def _parse_holiday_filter(value: str) -> HolidayFilter:
        """Parse holiday filter string to enum."""
        mapping = {
            "include": HolidayFilter.INCLUDE,
            "exclude": HolidayFilter.EXCLUDE,
            "only": HolidayFilter.ONLY,
        }
        return mapping.get(value, HolidayFilter.INCLUDE)

    # Source (auto-generated from Source enum)
    from agent.query_builder.schema import get_source_map
    source = get_source_map().get(query_spec.get("source", "daily"), Source.DAILY)

    # Filters
    filters_data = query_spec.get("filters", {})
    conditions = []
    for cond in filters_data.get("conditions", []):
        conditions.append(Condition(
            column=cond.get("column", ""),
            operator=cond.get("operator", ">"),
            value=cond.get("value", 0),
        ))

    filters = Filters(
        # Календарные фильтры
        period_start=filters_data.get("period_start", "2020-01-01"),
        period_end=filters_data.get("period_end", "2025-01-01"),
        specific_dates=filters_data.get("specific_dates"),
        years=filters_data.get("years"),
        months=filters_data.get("months"),
        weekdays=filters_data.get("weekdays"),
        # Время суток
        session=filters_data.get("session"),
        time_start=filters_data.get("time_start"),
        time_end=filters_data.get("time_end"),
        # Условия
        conditions=conditions,
        # Праздники (enum: include/exclude/only)
        market_holidays=_parse_holiday_filter(filters_data.get("market_holidays", "include")),
        early_close_days=_parse_holiday_filter(filters_data.get("early_close_days", "include")),
    )

    # Grouping (auto-generated from Grouping enum)
    from agent.query_builder.schema import get_grouping_map, get_metric_map
    grouping = get_grouping_map().get(query_spec.get("grouping", "none"), Grouping.NONE)

    # Metrics (auto-generated from Metric enum)
    metric_map = get_metric_map()
    metrics = []
    for m in query_spec.get("metrics", []):
        metric_type = metric_map.get(m.get("metric", "count"), Metric.COUNT)
        metrics.append(MetricSpec(
            metric=metric_type,
            column=m.get("column"),
            alias=m.get("alias"),
        ))

    # Special Op (auto-generated from SpecialOp enum)
    special_op = get_special_op_map().get(
        query_spec.get("special_op", "none"),
        SpecialOp.NONE
    )

    # Parse spec автоматически на основе special_op
    from agent.query_builder.schema import parse_spec
    parsed_spec = parse_spec(special_op, query_spec)

    # Распределяем parsed_spec по соответствующим полям QuerySpec
    event_time_spec = parsed_spec if special_op == SpecialOp.EVENT_TIME else None
    top_n_spec = parsed_spec if special_op == SpecialOp.TOP_N else None
    find_extremum_spec = parsed_spec if special_op == SpecialOp.FIND_EXTREMUM else None

    # Get symbol from query_spec or use default
    symbol = query_spec.get("symbol", DEFAULT_SYMBOL).upper()

    return QuerySpec(
        symbol=symbol,
        source=source,
        filters=filters,
        grouping=grouping,
        metrics=metrics,
        special_op=special_op,
        event_time_spec=event_time_spec,
        top_n_spec=top_n_spec,
        find_extremum_spec=find_extremum_spec,
    )
