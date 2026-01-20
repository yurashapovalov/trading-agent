"""DataFetcher agent - executes SQL and fetches data from DuckDB.

Pure Python agent (no LLM). Executes SQL from QueryBuilder or falls back
to template queries for simple requests.

Architecture:
    QueryBuilder → SQL → DataFetcher → summary (for Analyst) + full_data (for UI)

The agent automatically summarizes large result sets to reduce token usage:
- Analyst receives top-N rows + stats (cheap, accurate)
- UI can access full_data for display/download

Example:
    fetcher = DataFetcher()
    result = fetcher({"sql_query": "SELECT ...", "intent": {...}})
    # result["data"]["rows"] - summary for Analyst (max 50 rows)
    # result["full_data"]["rows"] - all rows for UI
"""

import time
import duckdb
from typing import Any

import config
from agent.state import AgentState
from agent.modules import sql
from agent.patterns import scan_patterns

# Maximum rows to send to Analyst (to reduce token usage)
MAX_ROWS_FOR_ANALYST = 50

# Priority columns for smart sorting (most interesting first)
# Data will be sorted by the first column found in this list (DESC)
SORT_PRIORITY = [
    # Volatility/movement - most interesting for traders
    "range", "change_pct", "gap_pct",
    # Distance to extremes
    "close_to_low", "close_to_high",
    "open_to_high", "open_to_low",
    # Candle structure
    "body", "upper_wick", "lower_wick",
    # Volume
    "volume",
    # Aggregations
    "count", "pct", "frequency",
]


class DataFetcher:
    """Fetches trading data based on Intent from Understander.

    Pure Python agent (no LLM). Routes to appropriate data source:
    - sql_query exists: Execute SQL from QueryBuilder
    - type="concept": No data needed
    - else: Use template queries from sql.py

    Attributes:
        name: Agent name for logging.
        agent_type: Agent type ("data" - fetches data).
    """

    name = "data_fetcher"
    agent_type = "data"

    def __call__(self, state: AgentState) -> dict:
        """Fetch data based on intent.

        Args:
            state: Agent state with sql_query, intent, and sql_validation.

        Returns:
            Dict with data (rows, row_count, granularity), agents_used.
        """
        start_time = time.time()

        intent = state.get("intent")
        if not intent:
            return {
                "data": {},
                "error": "No intent provided",
                "agents_used": [self.name],
            }

        intent_type = intent.get("type", "data")

        # Check for SQL query (from QueryBuilder or SQL Agent)
        sql_validation = state.get("sql_validation") or {}
        sql_query = state.get("sql_query")

        # Route to appropriate handler
        # 1. SQL from QueryBuilder (no validation needed - deterministically valid)
        # 2. SQL from SQL Agent (needs sql_validation.status == "ok")
        # 3. Concept - no data needed
        # 4. Fallback - use templates
        if sql_query and (sql_validation.get("status") == "ok" or not sql_validation):
            # Execute SQL (from QueryBuilder or validated SQL Agent)
            full_data = self._execute_sql(sql_query, intent)
        elif intent_type == "concept":
            full_data = self._handle_concept(intent)
        else:  # "data" or default - use templates
            full_data = self._handle_data(intent)

        # Create summary for Analyst (truncate large result sets)
        data = self._create_summary(full_data)

        duration_ms = int((time.time() - start_time) * 1000)

        return {
            "data": data,           # Summary for Analyst (max N rows)
            "full_data": full_data, # Full data for UI
            "agents_used": [self.name],
            "step_number": state.get("step_number", 0) + 1,
            "total_duration_ms": state.get("total_duration_ms", 0) + duration_ms,
        }

    def _execute_sql(self, sql_query: str, intent: dict = None) -> dict[str, Any]:
        """Execute SQL query in DuckDB.

        Args:
            sql_query: SQL query string from QueryBuilder.
            intent: Optional intent to determine granularity from query_spec.

        Returns:
            Dict with rows, row_count, granularity, columns, sql_query, source.
        """
        try:
            with duckdb.connect(config.DATABASE_PATH, read_only=True) as conn:
                df = conn.execute(sql_query).df()
                rows = df.to_dict(orient='records')

                # Convert numpy types to Python types
                rows = sql._convert_numpy_types(rows)

                # Determine granularity from query_spec or default
                granularity = "daily"
                source = "query_builder"

                if intent:
                    query_spec = intent.get("query_spec", {})
                    if query_spec:
                        source = "query_builder"
                        # Map source to granularity
                        spec_source = query_spec.get("source", "daily")
                        if spec_source == "minutes":
                            granularity = "minute"
                        elif spec_source in ("daily", "daily_with_prev"):
                            granularity = "daily"

                        # Special ops have their own granularity
                        special_op = query_spec.get("special_op", "none")
                        if special_op == "event_time":
                            granularity = "distribution"

                # Scan for patterns if data has OHLC columns (raw bar data)
                columns = set(df.columns) if len(df) > 0 else set()
                has_ohlc = {"open", "high", "low", "close"}.issubset(columns)

                if has_ohlc and rows:
                    rows = scan_patterns(rows)
                    # Update columns list with pattern flags
                    columns = list(rows[0].keys()) if rows else list(df.columns)
                else:
                    columns = list(df.columns) if len(df) > 0 else []

                # Smart sort by priority column
                rows, sort_col = self._smart_sort(rows)

                return {
                    "rows": rows,
                    "row_count": len(rows),
                    "granularity": granularity,
                    "columns": columns,
                    "source": source,
                    "sorted_by": sort_col,
                }
        except Exception as e:
            return {
                "error": str(e),
                "rows": [],
                "row_count": 0,
            }

    def _handle_data(self, intent: dict) -> dict[str, Any]:
        """Handle type=data using template queries from sql.py."""
        symbol = intent.get("symbol", "NQ")
        period_start = intent.get("period_start")
        period_end = intent.get("period_end")
        granularity = intent.get("granularity", "daily")

        if not period_start or not period_end:
            return {"error": "Missing period_start or period_end"}

        result = sql.fetch(
            symbol=symbol,
            period_start=period_start,
            period_end=period_end,
            granularity=granularity,
        )

        # Scan for patterns if data has OHLC columns
        rows = result.get("rows", [])
        if rows:
            columns = set(rows[0].keys())
            has_ohlc = {"open", "high", "low", "close"}.issubset(columns)
            if has_ohlc:
                result["rows"] = scan_patterns(rows)
                result["columns"] = list(result["rows"][0].keys()) if result["rows"] else []

        return result

    def _handle_concept(self, intent: dict) -> dict[str, Any]:
        """Handle type=concept - no data needed for concept explanations."""
        return {
            "type": "concept",
            "concept": intent.get("concept", ""),
            "message": "No data needed for concept explanation",
        }

    def _smart_sort(self, rows: list[dict]) -> tuple[list[dict], str | None]:
        """Sort rows by the most interesting column (for better truncation).

        Finds the first column from SORT_PRIORITY that exists in the data
        and sorts by it descending. Falls back to date DESC if no priority
        column found.

        Args:
            rows: List of row dicts from SQL result.

        Returns:
            Tuple of (sorted_rows, sort_column_name or None).
        """
        if not rows:
            return rows, None

        columns = set(rows[0].keys())

        # Find first priority column that exists
        sort_col = None
        for col in SORT_PRIORITY:
            if col in columns:
                sort_col = col
                break

        # Sort by priority column DESC, or by date DESC as fallback
        if sort_col:
            rows = sorted(rows, key=lambda r: r.get(sort_col, 0) or 0, reverse=True)
            return rows, sort_col
        elif "date" in columns:
            rows = sorted(rows, key=lambda r: r.get("date", ""), reverse=True)
            return rows, "date"

        return rows, None

    def _create_summary(self, full_data: dict[str, Any]) -> dict[str, Any]:
        """Create summary of data for Analyst (to reduce token usage).

        If data has more than MAX_ROWS_FOR_ANALYST rows, truncates to top-N
        and adds summary statistics. Otherwise returns data unchanged.

        Args:
            full_data: Full query result with rows, row_count, etc.

        Returns:
            Summary dict with truncated rows and added stats if needed.
        """
        rows = full_data.get("rows", [])
        row_count = full_data.get("row_count", len(rows))

        # If small enough, return as-is
        if row_count <= MAX_ROWS_FOR_ANALYST:
            return full_data

        # Create summary with truncated rows
        sorted_by = full_data.get("sorted_by")

        # Build descriptive note
        if sorted_by and sorted_by != "date":
            sort_note = f"Top {MAX_ROWS_FOR_ANALYST} by {sorted_by} (descending)"
        elif sorted_by == "date":
            sort_note = f"Most recent {MAX_ROWS_FOR_ANALYST}"
        else:
            sort_note = f"First {MAX_ROWS_FOR_ANALYST}"

        summary = {
            **full_data,
            "rows": rows[:MAX_ROWS_FOR_ANALYST],
            "row_count": row_count,  # Keep original count
            "truncated": True,
            "showing": MAX_ROWS_FOR_ANALYST,
            "summary_note": f"{sort_note} of {row_count} total rows.",
        }

        # Add aggregate stats if data has numeric columns
        if rows:
            summary["summary_stats"] = self._calculate_summary_stats(rows)

        return summary

    def _calculate_summary_stats(self, rows: list[dict]) -> dict[str, Any]:
        """Calculate summary statistics for numeric columns.

        Args:
            rows: List of row dicts.

        Returns:
            Dict with stats like total_count, column sums, etc.
        """
        stats = {"total_rows": len(rows)}

        if not rows:
            return stats

        # Find numeric columns (check first row)
        first_row = rows[0]
        numeric_cols = [
            k for k, v in first_row.items()
            if isinstance(v, (int, float)) and k not in ("day_num",)
        ]

        # Calculate sum/avg for key columns like 'count', 'frequency', 'pct'
        for col in numeric_cols:
            if col in ("count", "frequency", "cnt", "occurrences"):
                total = sum(r.get(col, 0) for r in rows)
                stats[f"total_{col}"] = total
            elif col in ("pct", "percent", "percentage"):
                # For percentage columns, sum shows coverage of top-N
                total_pct = sum(r.get(col, 0) for r in rows[:MAX_ROWS_FOR_ANALYST])
                stats["top_n_coverage_pct"] = round(total_pct, 2)

        return stats
