"""Validator agent - checks Analyst's Stats against actual data.

Pure Python agent (no LLM). Compares structured Stats from Analyst response
against actual data from DataFetcher. Returns "rewrite" status if numbers
don't match within tolerance.

This ensures factual accuracy of responses by validating all numbers
mentioned by Analyst against the source data.

Tolerances:
    - Percentages: ±0.5%
    - Prices: ±$0.01
    - Counts: Exact match
"""

from agent.state import AgentState, Stats, ValidationResult


# Tolerance for floating point comparisons
TOLERANCE_PCT = 0.5  # 0.5% tolerance for percentages
TOLERANCE_PRICE = 0.01  # $0.01 tolerance for prices


class Validator:
    """Validates Analyst's Stats against actual data.

    Pure Python validation (no LLM). Compares numbers from Stats against
    actual data to ensure factual accuracy.

    Attributes:
        name: Agent name for logging.
        agent_type: Agent type ("validation").
        max_attempts: Max validation attempts before auto-approve.
    """

    name = "validator"
    agent_type = "validation"
    max_attempts = 3

    def __call__(self, state: AgentState) -> dict:
        """Validate stats against data.

        Args:
            state: Agent state with stats, data, and validation_attempts.

        Returns:
            Dict with validation result (status, issues, feedback).
        """
        stats = state.get("stats") or {}
        data = state.get("data") or {}
        intent = state.get("intent") or {}
        intent_type = intent.get("type", "data")
        attempts = state.get("validation_attempts", 0)

        # Max attempts reached - auto approve
        if attempts >= self.max_attempts:
            return {
                "validation": ValidationResult(
                    status="ok",
                    issues=["Max validation attempts reached"],
                    feedback=""
                ),
                "agents_used": [self.name],
            }

        # No stats or concept type - nothing to validate
        if not stats or intent_type == "concept":
            return {
                "validation": ValidationResult(
                    status="ok",
                    issues=[],
                    feedback=""
                ),
                "agents_used": [self.name],
            }

        # Validate based on data type
        if intent_type == "pattern":
            issues = self._validate_pattern(stats, data)
        else:
            issues = self._validate_data(stats, data)

        # Build result
        if issues:
            return {
                "validation": ValidationResult(
                    status="rewrite",
                    issues=issues,
                    feedback=self._format_feedback(issues)
                ),
                "agents_used": [self.name],
            }

        return {
            "validation": ValidationResult(
                status="ok",
                issues=[],
                feedback=""
            ),
            "agents_used": [self.name],
        }

    def _validate_data(self, stats: dict, data: dict) -> list[str]:
        """Validate stats for type=data queries."""
        issues = []

        rows = data.get("rows", [])
        if not rows:
            return issues

        first_row = rows[0]

        # Detect data format:
        # 1. SQL aggregated results (correlation, statistics) - has fields like trading_days, corr_*, avg_*
        # 2. Period format (aggregated by data_fetcher) - has open_price
        # 3. Raw daily/hourly rows - has open, close, high, low

        # Check for SQL aggregated results (statistics queries)
        aggregated_prefixes = ("corr_", "avg_", "stddev_", "total_", "sum_", "min_", "max_")
        is_sql_aggregated = (
            "trading_days" in first_row and
            len(rows) == 1 and
            any(key.startswith(aggregated_prefixes) for key in first_row.keys())
        )

        is_period_format = "open_price" in first_row

        if is_sql_aggregated:
            # SQL already computed aggregates - use values directly
            actual = first_row
        elif is_period_format:
            # Already aggregated from SQL period query
            actual = first_row
        else:
            # Daily/hourly rows - need to aggregate
            actual = self._aggregate_rows(rows)

        issues.extend(self._compare_row(stats, actual))
        return issues

    def _validate_pattern(self, stats: dict, data: dict) -> list[str]:
        """Validate stats for type=pattern queries."""
        issues = []

        # Check matches_count if mentioned
        if "matches_count" in stats:
            actual = data.get("matches_count", 0)
            if stats["matches_count"] != actual:
                issues.append(
                    f"matches_count: reported {stats['matches_count']}, actual {actual}"
                )

        return issues

    def _compare_row(self, stats: dict, actual: dict) -> list[str]:
        """Compare stats against actual data row."""
        issues = []

        # Map of stat fields to data fields with tolerances
        field_map = {
            "change_pct": ("change_pct", TOLERANCE_PCT),
            "trading_days": ("trading_days", 0),
            "open_price": ("open_price", TOLERANCE_PRICE),
            "close_price": ("close_price", TOLERANCE_PRICE),
            "max_price": ("max_price", TOLERANCE_PRICE),
            "min_price": ("min_price", TOLERANCE_PRICE),
            "total_volume": ("total_volume", 0),
            "change_points": ("change_points", TOLERANCE_PRICE),
        }

        for stat_field, (data_field, tolerance) in field_map.items():
            if stat_field not in stats:
                continue

            stat_value = stats[stat_field]
            actual_value = actual.get(data_field)

            if actual_value is None:
                continue

            if not self._values_match(stat_value, actual_value, tolerance):
                issues.append(
                    f"{stat_field}: reported {stat_value}, actual {actual_value}"
                )

        return issues

    def _aggregate_rows(self, rows: list[dict]) -> dict:
        """Aggregate daily/hourly rows into period stats."""
        if not rows:
            return {}

        sorted_rows = sorted(rows, key=lambda r: r.get("date", ""))

        return {
            "trading_days": len(rows),
            "open_price": sorted_rows[0].get("open"),
            "close_price": sorted_rows[-1].get("close"),
            "max_price": max(r.get("high", 0) for r in rows),
            "min_price": min(r.get("low", float("inf")) for r in rows),
            "total_volume": sum(r.get("volume", 0) for r in rows),
            "change_pct": self._calc_change_pct(sorted_rows),
        }

    def _calc_change_pct(self, rows: list[dict]) -> float | None:
        """Calculate percentage change from first to last row."""
        if not rows:
            return None

        first_open = rows[0].get("open")
        last_close = rows[-1].get("close")

        if not first_open or not last_close:
            return None

        return round((last_close - first_open) / first_open * 100, 2)

    def _values_match(self, a, b, tolerance: float) -> bool:
        """Check if two values match within tolerance."""
        if a is None or b is None:
            return True

        try:
            a = float(a)
            b = float(b)
        except (TypeError, ValueError):
            return str(a) == str(b)

        if tolerance == 0:
            return a == b

        return abs(a - b) <= tolerance

    def _format_feedback(self, issues: list[str]) -> str:
        """Format issues into feedback string."""
        return "Validation errors:\n" + "\n".join(f"- {issue}" for issue in issues)
