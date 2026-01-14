"""Understander agent - parses user questions into structured query_spec.

Converts natural language questions into JSON query_spec that QueryBuilder
transforms deterministically into SQL.

Architecture:
    Question → Understander → query_spec → QueryBuilder → SQL

The Understander uses LLM to classify intent and extract query parameters,
but does NOT generate SQL directly. This ensures deterministic behavior.

Example:
    understander = Understander()
    result = understander({"question": "What was NQ high in January 2024?"})
    # result["intent"]["query_spec"] contains structured params for QueryBuilder
"""

import json
from datetime import datetime
from google import genai
from google.genai import types

import config
from agent.state import AgentState, Intent, UsageStats
from agent.pricing import calculate_cost
# Default symbol when not specified
DEFAULT_SYMBOL = "NQ"
from agent.modules.sql import get_data_range
from agent.prompts.understander import get_understander_prompt

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
# Understander Agent
# =============================================================================

class Understander:
    """Parses user questions into structured query_spec for QueryBuilder.

    Uses Gemini LLM to understand user intent and extract query parameters.
    Returns query_spec (JSON) that QueryBuilder converts to SQL deterministically.

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
        # Используем основную модель для лучшего понимания
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
            state: Current agent state with question and chat_history.

        Returns:
            Dict with intent, usage stats, agents_used list, and step_number.
        """
        question = state.get("question", "")
        chat_history = list(state.get("chat_history", []))

        print(f"[Understander] Question: {question[:50]}...")

        # Вызываем LLM
        intent = self._parse_with_llm(question, chat_history)
        print(f"[Understander] Intent type={intent.get('type')}")

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

    def _build_prompt(self, question: str, chat_history: list) -> str:
        """Build complete prompt from template with context."""
        # Форматируем историю чата
        history_str = ""
        if chat_history:
            for msg in chat_history[-config.CHAT_HISTORY_LIMIT:]:
                role = "User" if msg.get("role") == "user" else "Assistant"
                history_str += f"{role}: {msg.get('content', '')}\n"

        return get_understander_prompt(
            capabilities="",  # All kubiks documented in prompt template
            data_info=self._get_data_info(),
            today=datetime.now().strftime("%Y-%m-%d"),
            question=question,
            chat_history=history_str,
        )

    def _parse_with_llm(self, question: str, chat_history: list) -> Intent:
        """Call LLM and parse response into Intent."""
        try:
            prompt = self._build_prompt(question, chat_history)

            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,  # Низкая для детерминированности
                    # thinking_config отключен для скорости
                    # thinking_config=types.ThinkingConfig(include_thoughts=True),
                    response_mime_type="application/json",
                    response_schema=RESPONSE_SCHEMA,
                )
            )

            # Трекаем использование токенов
            if response.usage_metadata:
                input_tokens = response.usage_metadata.prompt_token_count or 0
                output_tokens = response.usage_metadata.candidates_token_count or 0
                thinking_tokens = getattr(
                    response.usage_metadata, 'thoughts_token_count', 0
                ) or 0
                cost = calculate_cost(input_tokens, output_tokens, thinking_tokens)
                self._last_usage = UsageStats(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    thinking_tokens=thinking_tokens,
                    cost_usd=cost
                )

            # Парсим JSON
            data = json.loads(response.text)
            return self._build_intent(data)

        except Exception as e:
            print(f"[Understander] Error: {e}")
            return self._default_intent()

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
            # Извлекаем query_spec
            query_spec = data.get("query_spec", {})

            # Получаем фильтры
            filters = query_spec.get("filters", {})
            period_start = filters.get("period_start")
            period_end = filters.get("period_end")

            # Дефолтный период: "all" или пустое значение → берём из БД
            if not period_start or period_start == "all" or not period_end or period_end == "all":
                period_start, period_end = self._full_data_range()
                if "filters" not in query_spec:
                    query_spec["filters"] = {}
                query_spec["filters"]["period_start"] = period_start
                query_spec["filters"]["period_end"] = period_end

            # Добавляем query_spec в intent
            intent["query_spec"] = query_spec

            # Для совместимости добавляем period_start/end на верхний уровень
            intent["period_start"] = period_start
            intent["period_end"] = period_end

        elif intent_type == "concept":
            intent["concept"] = data.get("concept", "")

        elif intent_type == "clarification":
            intent["response_text"] = data.get(
                "clarification_question",
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

    return QuerySpec(
        symbol="NQ",  # TODO: брать из query_spec когда добавим другие символы
        source=source,
        filters=filters,
        grouping=grouping,
        metrics=metrics,
        special_op=special_op,
        event_time_spec=event_time_spec,
        top_n_spec=top_n_spec,
        find_extremum_spec=find_extremum_spec,
    )
