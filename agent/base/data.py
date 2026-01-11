"""Base class for data agents (code-based validation)."""

from abc import ABC, abstractmethod
from typing import Any
import time

from agent.state import AgentState, SQLResult


class DataValidationResult:
    """Result of code-based validation."""

    def __init__(
        self,
        status: str,  # "ok", "retry", "no_data", "low_sample"
        reason: str = "",
        row_count: int = 0
    ):
        self.status = status
        self.reason = reason
        self.row_count = row_count

    @property
    def is_ok(self) -> bool:
        return self.status == "ok"


class BaseDataAgent(ABC):
    """
    Base class for agents that fetch/compute data.

    These agents execute SQL queries or calculations.
    Validation is code-based (free) - check for errors, empty results, etc.
    """

    name: str = "data_agent"
    agent_type: str = "data"

    # Validation thresholds
    min_sample_size: int = 5  # Warn if fewer rows

    @abstractmethod
    def execute(self, state: AgentState) -> list[SQLResult]:
        """
        Execute data retrieval.

        Args:
            state: Current graph state

        Returns:
            List of SQL results
        """
        pass

    def validate(self, results: list[SQLResult]) -> DataValidationResult:
        """
        Validate data results (code-based, free).

        Override for custom validation logic.
        """
        if not results:
            return DataValidationResult("no_data", "No queries executed")

        # Check for errors
        for result in results:
            if result.get("error"):
                return DataValidationResult(
                    "retry",
                    f"SQL error: {result['error']}"
                )

        # Check for empty results
        total_rows = sum(r.get("row_count", 0) for r in results)
        if total_rows == 0:
            return DataValidationResult("no_data", "No data found")

        # Check for low sample size
        if total_rows < self.min_sample_size:
            return DataValidationResult(
                "low_sample",
                f"Only {total_rows} rows found (minimum: {self.min_sample_size})",
                row_count=total_rows
            )

        return DataValidationResult("ok", row_count=total_rows)

    def aggregate_data(self, results: list[SQLResult]) -> dict:
        """
        Aggregate results into a data dict for the Analyst.

        Override for custom aggregation logic.
        """
        return {
            "queries": results,
            "total_rows": sum(r.get("row_count", 0) for r in results),
            "has_errors": any(r.get("error") for r in results),
        }

    def __call__(self, state: AgentState) -> dict:
        """
        Process state and return updates.

        This is called by LangGraph when the node executes.
        """
        start_time = time.time()

        results = self.execute(state)
        validation = self.validate(results)
        data = self.aggregate_data(results)

        duration_ms = int((time.time() - start_time) * 1000)

        # Add validation info to data
        data["validation"] = {
            "status": validation.status,
            "reason": validation.reason,
            "row_count": validation.row_count,
        }

        return {
            "sql_queries": results,
            "data": data,
            "agents_used": [self.name],
            "step_number": state.get("step_number", 0) + 1,
        }

    def get_trace_data(
        self,
        state: AgentState,
        results: list[SQLResult],
        duration_ms: int
    ) -> dict:
        """Return data for request_traces logging."""
        return {
            "agent_name": self.name,
            "agent_type": self.agent_type,
            "input_data": {"question": state.get("question")},
            "output_data": {"row_count": sum(r.get("row_count", 0) for r in results)},
            "sql_query": results[0].get("query") if results else None,
            "sql_result": results[0].get("rows", [])[:10] if results else None,  # First 10 rows
            "sql_rows_returned": sum(r.get("row_count", 0) for r in results),
            "sql_error": next((r.get("error") for r in results if r.get("error")), None),
            "duration_ms": duration_ms,
        }
