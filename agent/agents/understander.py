"""
Understander — парсит вопрос в query_spec.

Возвращает структурированный JSON (query_spec) для QueryBuilder.
QueryBuilder детерминировано превращает query_spec в SQL.

Архитектура:
    Вопрос → Understander → query_spec → QueryBuilder → SQL
"""

import json
from datetime import datetime
from google import genai
from google.genai import types

import config
from agent.state import AgentState, Intent, UsageStats
from agent.pricing import calculate_cost, GEMINI_2_5_FLASH_LITE
from agent.capabilities import (
    get_capabilities_prompt,
    DEFAULT_SYMBOL,
)
from agent.modules.sql import get_data_range
from agent.prompts.understander import get_understander_prompt


# =============================================================================
# JSON Schema для query_spec
# =============================================================================

QUERY_SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "source": {
            "type": "string",
            "enum": ["minutes", "daily", "daily_with_prev"]
        },
        "filters": {
            "type": "object",
            "properties": {
                "period_start": {"type": "string"},
                "period_end": {"type": "string"},
                "session": {
                    "type": "string",
                    "enum": [
                        "RTH", "ETH", "OVERNIGHT", "GLOBEX",
                        "ASIAN", "EUROPEAN", "US",
                        "PREMARKET", "POSTMARKET", "MORNING", "AFTERNOON", "LUNCH",
                        "LONDON_OPEN", "NY_OPEN", "NY_CLOSE"
                    ]
                },
                "conditions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "column": {"type": "string"},
                            "operator": {"type": "string"},
                            "value": {"type": "number"}
                        }
                    }
                }
            }
        },
        "grouping": {
            "type": "string",
            "enum": [
                "none", "total",
                "5min", "10min", "15min", "30min", "hour",
                "day", "week", "month", "quarter", "year",
                "weekday", "session"
            ]
        },
        "metrics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string"},
                    "column": {"type": "string"},
                    "alias": {"type": "string"}
                }
            }
        },
        "special_op": {
            "type": "string",
            "enum": ["none", "event_time", "top_n", "compare"]
        },
        "event_time_spec": {
            "type": "object",
            "properties": {
                "find": {"type": "string", "enum": ["high", "low"]}
            }
        },
        "top_n_spec": {
            "type": "object",
            "properties": {
                "n": {"type": "integer"},
                "order_by": {"type": "string"},
                "direction": {"type": "string", "enum": ["ASC", "DESC"]}
            }
        }
    }
}

# Полная схема ответа Understander
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "enum": ["data", "concept", "chitchat", "out_of_scope", "clarification"]
        },
        "query_spec": QUERY_SPEC_SCHEMA,
        "concept": {"type": "string"},
        "response_text": {"type": "string"},
        "clarification_question": {"type": "string"},
        "suggestions": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["type"]
}


# =============================================================================
# Understander Agent
# =============================================================================

class Understander:
    """
    Senior trading data analyst that understands user intent.

    Возвращает query_spec — структурированную спецификацию запроса,
    которую QueryBuilder превращает в SQL.

    Attributes:
        name: Имя агента для логов
        agent_type: Тип агента (routing)
    """

    name = "understander"
    agent_type = "routing"

    def __init__(self):
        """Инициализация клиента Gemini."""
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        # Используем lite модель для скорости (парсинг не требует тяжёлой модели)
        self.model = "gemini-2.5-flash-lite"
        self._last_usage = UsageStats(
            input_tokens=0,
            output_tokens=0,
            thinking_tokens=0,
            cost_usd=0.0
        )

    def __call__(self, state: AgentState) -> dict:
        """
        Главный метод — парсит вопрос и возвращает Intent.

        Args:
            state: Текущее состояние агента с вопросом и историей

        Returns:
            dict с intent, usage, agents_used, step_number
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
    # Вспомогательные методы
    # =========================================================================

    def _get_data_info(self) -> str:
        """Получает информацию о доступных данных."""
        data_range = get_data_range("NQ")
        if data_range:
            return (
                f"Символ: NQ\n"
                f"Период данных: {data_range['start_date']} — {data_range['end_date']}\n"
                f"Торговых дней: {data_range['trading_days']}"
            )
        return "Данные: NQ"

    def _build_prompt(self, question: str, chat_history: list) -> str:
        """Строит полный промпт из шаблона."""
        # Форматируем историю чата
        history_str = ""
        if chat_history:
            for msg in chat_history[-config.CHAT_HISTORY_LIMIT:]:
                role = "User" if msg.get("role") == "user" else "Assistant"
                history_str += f"{role}: {msg.get('content', '')}\n"

        return get_understander_prompt(
            capabilities=get_capabilities_prompt(),
            data_info=self._get_data_info(),
            today=datetime.now().strftime("%Y-%m-%d"),
            question=question,
            chat_history=history_str,
        )

    def _parse_with_llm(self, question: str, chat_history: list) -> Intent:
        """Вызывает LLM и парсит ответ в Intent."""
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
                cost = calculate_cost(input_tokens, output_tokens, thinking_tokens, GEMINI_2_5_FLASH_LITE)
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
        """
        Строит Intent из распарсенных данных.

        Args:
            data: JSON от LLM

        Returns:
            Intent с нужными полями
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
        """Возвращает дефолтный intent при ошибке."""
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
        """Возвращает полный диапазон доступных данных."""
        data_range = get_data_range("NQ")
        if data_range:
            return data_range['start_date'], data_range['end_date']
        return "2008-01-01", datetime.now().strftime("%Y-%m-%d")


# =============================================================================
# Функции для конвертации query_spec в объекты QueryBuilder
# =============================================================================

def query_spec_to_builder(query_spec: dict) -> "QuerySpec":
    """
    Конвертирует JSON query_spec в объект QuerySpec.

    Args:
        query_spec: JSON dict от Understander

    Returns:
        QuerySpec объект для QueryBuilder
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
        EventTimeSpec,
        TopNSpec,
    )

    # Source
    source_map = {
        "minutes": Source.MINUTES,
        "daily": Source.DAILY,
        "daily_with_prev": Source.DAILY_WITH_PREV,
    }
    source = source_map.get(query_spec.get("source", "daily"), Source.DAILY)

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
        period_start=filters_data.get("period_start", "2020-01-01"),
        period_end=filters_data.get("period_end", "2025-01-01"),
        session=filters_data.get("session"),
        conditions=conditions,
    )

    # Grouping
    grouping_map = {
        "none": Grouping.NONE,
        "total": Grouping.TOTAL,
        "5min": Grouping.MINUTE_5,
        "10min": Grouping.MINUTE_10,
        "15min": Grouping.MINUTE_15,
        "30min": Grouping.MINUTE_30,
        "hour": Grouping.HOUR,
        "day": Grouping.DAY,
        "week": Grouping.WEEK,
        "month": Grouping.MONTH,
        "quarter": Grouping.QUARTER,
        "year": Grouping.YEAR,
        "weekday": Grouping.WEEKDAY,
        "session": Grouping.SESSION,
    }
    grouping = grouping_map.get(query_spec.get("grouping", "none"), Grouping.NONE)

    # Metrics
    metric_map = {
        "open": Metric.OPEN,
        "high": Metric.HIGH,
        "low": Metric.LOW,
        "close": Metric.CLOSE,
        "volume": Metric.VOLUME,
        "range": Metric.RANGE,
        "change_pct": Metric.CHANGE_PCT,
        "gap_pct": Metric.GAP_PCT,
        "count": Metric.COUNT,
        "avg": Metric.AVG,
        "sum": Metric.SUM,
        "min": Metric.MIN,
        "max": Metric.MAX,
        "stddev": Metric.STDDEV,
        "median": Metric.MEDIAN,
    }
    metrics = []
    for m in query_spec.get("metrics", []):
        metric_type = metric_map.get(m.get("metric", "count"), Metric.COUNT)
        metrics.append(MetricSpec(
            metric=metric_type,
            column=m.get("column"),
            alias=m.get("alias"),
        ))

    # Special Op
    special_op_map = {
        "none": SpecialOp.NONE,
        "event_time": SpecialOp.EVENT_TIME,
        "top_n": SpecialOp.TOP_N,
        "compare": SpecialOp.COMPARE,
    }
    special_op = special_op_map.get(
        query_spec.get("special_op", "none"),
        SpecialOp.NONE
    )

    # Event Time Spec
    event_time_spec = None
    if special_op == SpecialOp.EVENT_TIME:
        ets = query_spec.get("event_time_spec", {})
        event_time_spec = EventTimeSpec(find=ets.get("find", "high"))

    # Top N Spec
    top_n_spec = None
    if special_op == SpecialOp.TOP_N:
        tns = query_spec.get("top_n_spec", {})
        top_n_spec = TopNSpec(
            n=tns.get("n", 10),
            order_by=tns.get("order_by", "range"),
            direction=tns.get("direction", "DESC"),
        )

    return QuerySpec(
        symbol="NQ",  # TODO: брать из query_spec когда добавим другие символы
        source=source,
        filters=filters,
        grouping=grouping,
        metrics=metrics,
        special_op=special_op,
        event_time_spec=event_time_spec,
        top_n_spec=top_n_spec,
    )
