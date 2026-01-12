"""
SQL Validator - validates SQL queries before execution.

Returns:
- sql_validation: {status: "ok"} or {status: "rewrite", issues: [...], feedback: "..."}
"""

import duckdb
import config
from agent.state import AgentState


class SQLValidator:
    """
    Validates SQL queries from SQL Agent before DataFetcher executes them.

    Checks:
    1. Safety - only SELECT allowed
    2. Syntax - query parses correctly
    3. Execution - query runs without errors (with LIMIT 1)
    """

    name = "sql_validator"
    agent_type = "validation"

    def __call__(self, state: AgentState) -> dict:
        """Validate SQL query."""
        sql_query = state.get("sql_query")

        # No SQL to validate
        if not sql_query:
            return {
                "sql_validation": {"status": "ok"},
                "step_number": state.get("step_number", 0) + 1,
            }

        issues = []

        # Check 1: Safety
        safety_issues = self._check_safety(sql_query)
        issues.extend(safety_issues)

        # Check 2: Syntax and execution (combined - try to run it)
        if not issues:  # Only check if safety passed
            execution_issues = self._check_execution(sql_query)
            issues.extend(execution_issues)

        # Return result
        if issues:
            feedback = "SQL validation failed:\n" + "\n".join(f"- {issue}" for issue in issues)
            return {
                "sql_validation": {
                    "status": "rewrite",
                    "issues": issues,
                    "feedback": feedback,
                },
                "step_number": state.get("step_number", 0) + 1,
            }

        return {
            "sql_validation": {"status": "ok"},
            "step_number": state.get("step_number", 0) + 1,
        }

    def _check_safety(self, sql: str) -> list[str]:
        """Check that SQL is safe (only SELECT)."""
        issues = []
        sql_upper = sql.upper()

        # Forbidden operations
        forbidden = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE', 'GRANT', 'REVOKE']
        for word in forbidden:
            # Check for word boundary to avoid false positives
            if f" {word} " in f" {sql_upper} " or sql_upper.startswith(f"{word} "):
                issues.append(f"Forbidden operation: {word}")

        # Must use our table
        if 'ohlcv_1min' not in sql.lower():
            issues.append("Query must use ohlcv_1min table")

        return issues

    def _check_execution(self, sql: str) -> list[str]:
        """Check that SQL executes without errors."""
        issues = []

        try:
            with duckdb.connect(config.DATABASE_PATH, read_only=True) as conn:
                # Wrap in subquery with LIMIT to avoid full table scan
                test_sql = f"SELECT * FROM ({sql}) AS test_query LIMIT 1"
                conn.execute(test_sql)

        except duckdb.Error as e:
            error_msg = str(e)
            # Clean up error message
            if "Catalog Error" in error_msg:
                issues.append(f"Column or table not found: {error_msg}")
            elif "Parser Error" in error_msg:
                issues.append(f"SQL syntax error: {error_msg}")
            elif "Binder Error" in error_msg:
                issues.append(f"SQL binding error: {error_msg}")
            else:
                issues.append(f"SQL execution error: {error_msg}")

        except Exception as e:
            issues.append(f"Unexpected error: {str(e)}")

        return issues
