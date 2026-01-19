"""
Conversation Test — tests Parser → Composer → QueryBuilder → DataFetcher flow.

Captures full traces:
- Parser: input (question, previous_parsed) → output (parsed_query, tokens)
- Composer: input (parsed_query) → output (type, spec)
- QueryBuilder: spec → SQL
- DataFetcher: SQL → data

Run:
    python -m agent.tests.conversation_test --scenario=follow_up
    python -m agent.tests.conversation_test --scenario=follow_up --filter=A2
    python -m agent.tests.conversation_test --scenario=greetings --filter=Hello
    python -m agent.tests.conversation_test --list
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

os.environ["ANALYST_FAST_MODE"] = "true"

import importlib
import config
importlib.reload(config)

from agent.agents.parser import Parser
from agent.agents.composer_agent import ComposerAgent
from agent.query_builder import QueryBuilder
from agent.agents.data_fetcher import DataFetcher
from agent.agents.responder import Responder

from agent.tests.scenarios import (
    get_scenario,
    list_scenarios,
    is_chain_scenario,
)
from agent.pricing import calculate_cost


# =============================================================================
# Result Dataclasses
# =============================================================================

@dataclass
class TokenUsage:
    input: int = 0
    output: int = 0
    thinking: int = 0
    cached: int = 0
    model: str = ""

    @property
    def cost(self) -> float:
        return calculate_cost(
            input_tokens=self.input,
            output_tokens=self.output,
            thinking_tokens=self.thinking,
            cached_tokens=self.cached,
            model=self.model,
        )


@dataclass
class ValidationCheck:
    key: str
    expected: Any
    actual: Any
    passed: bool


@dataclass
class ValidationResult:
    passed: bool
    checks: list[ValidationCheck] = field(default_factory=list)


@dataclass
class StepResult:
    step: int
    question: str
    time_ms: int = 0
    parser_input: dict = field(default_factory=dict)
    parser_output: dict = field(default_factory=dict)
    parser_tokens: TokenUsage = field(default_factory=TokenUsage)
    composer_type: str = ""
    composer_summary: str = ""
    composer_spec: dict | None = None
    sql: str | None = None
    sql_error: str | None = None
    data_row_count: int | None = None
    data_columns: list[str] | None = None
    data_rows: list[dict] | None = None  # actual data
    responder_text: str | None = None  # response to user
    responder_title: str | None = None  # data card title
    validation: ValidationResult | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        if self.error:
            return False
        if self.validation and not self.validation.passed:
            return False
        return True


@dataclass
class ChainResult:
    name: str
    description: str
    steps: list[StepResult] = field(default_factory=list)
    total_time_ms: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    @property
    def success(self) -> bool:
        return all(step.success for step in self.steps)

    @property
    def total_cost(self) -> float:
        """Sum of costs from steps (already calculated with correct model)."""
        return sum(step.parser_tokens.cost for step in self.steps)


@dataclass
class SingleResult:
    question: str
    step: StepResult
    total_time_ms: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    @property
    def success(self) -> bool:
        return self.step.success

    @property
    def total_cost(self) -> float:
        """Cost from step (already calculated with correct model)."""
        return self.step.parser_tokens.cost


# =============================================================================
# Validator
# =============================================================================

class Validator:
    """Validates test results against expected values."""

    def validate(self, parser_result, composer_result, expected: dict, data_result: dict | None = None) -> ValidationResult:
        """Validate result against expected dict."""
        if not expected:
            return ValidationResult(passed=True)

        checks = []
        parsed = parser_result.parsed_query if parser_result else None
        spec = composer_result.spec if composer_result else None

        for key, expected_value in expected.items():
            actual = self._extract_value(key, parsed, spec, composer_result, data_result)
            passed = self._values_match(actual, expected_value, key)
            checks.append(ValidationCheck(
                key=key,
                expected=expected_value,
                actual=actual,
                passed=passed,
            ))

        return ValidationResult(
            passed=all(c.passed for c in checks),
            checks=checks,
        )

    def _extract_value(self, key: str, parsed, spec, composer_result, data_result: dict | None = None) -> Any:
        """Extract actual value for validation key."""
        # Data result checks
        if data_result:
            if key == "rows":
                return data_result.get("row_count")
            if key == "has_columns":
                return data_result.get("columns", [])

        # Type checks
        if key == "type":
            return composer_result.type if composer_result else None

        # Holiday check
        if key == "holiday":
            # Check if composer returned holiday response
            if composer_result and composer_result.type == "holiday":
                return True
            return False

        # Clarification check
        if key == "clarification":
            if composer_result and composer_result.type == "clarification":
                return composer_result.clarification_type
            return None

        # Parser extractions
        if parsed:
            if key == "what":
                return parsed.what

            # Period
            if key == "period_start" and parsed.period:
                return parsed.period.start
            if key == "period_end" and parsed.period:
                return parsed.period.end

            # Filters
            if parsed.filters:
                if key == "filter_weekdays":
                    return parsed.filters.weekdays
                if key == "filter_session":
                    return parsed.filters.session
                if key == "event_filter":
                    return parsed.filters.event_filter
                if key == "conditions":
                    return parsed.filters.conditions

            # Modifiers
            if parsed.modifiers:
                if key == "grouping":
                    return parsed.modifiers.group_by
                if key == "top_n":
                    # Check parsed first, then spec (Composer may infer from find)
                    if parsed.modifiers.top_n:
                        return parsed.modifiers.top_n
                    # Fallback to spec
                    if spec and spec.top_n_spec:
                        return spec.top_n_spec.n
                    return None
                if key == "compare":
                    return parsed.modifiers.compare
                if key == "find":
                    return parsed.modifiers.find
                if key == "group_by":
                    return parsed.modifiers.group_by

        # Spec extractions (fallback for grouping/special_op)
        if spec:
            if key == "source":
                return spec.source.value
            if key == "grouping" and not (parsed and parsed.modifiers and parsed.modifiers.group_by):
                return spec.grouping.value
            if key == "special_op":
                return spec.special_op.value

        return None

    def _values_match(self, actual: Any, expected: Any, key: str = "") -> bool:
        """Check if actual value matches expected."""
        if actual is None:
            return expected is None

        # has_columns: check all expected columns are present (subset check)
        if key == "has_columns":
            if not isinstance(actual, list) or not isinstance(expected, list):
                return False
            actual_lower = set(str(x).lower() for x in actual)
            return all(str(col).lower() in actual_lower for col in expected)

        # String comparison (case-insensitive)
        if isinstance(actual, str) and isinstance(expected, str):
            return actual.upper() == expected.upper()

        # List comparison (order-independent, exact match)
        if isinstance(expected, list):
            if not isinstance(actual, list):
                return False
            return set(str(x).lower() for x in actual) == set(str(x).lower() for x in expected)

        return actual == expected


# =============================================================================
# TestRunner
# =============================================================================

class TestRunner:
    """Runs test scenarios through Parser → Composer → QueryBuilder → DataFetcher → Responder."""

    def __init__(self):
        self.parser = Parser()
        self.composer = ComposerAgent()
        self.query_builder = QueryBuilder()
        self.data_fetcher = DataFetcher()
        self.responder = Responder()
        self.validator = Validator()

    def run_chain(self, chain_spec: dict) -> ChainResult:
        """Run follow-up chain: Q1 → Q2 → Q3..."""
        name = chain_spec.get("name", "unnamed")
        description = chain_spec.get("description", "")
        chain = chain_spec.get("chain", [])

        start_time = datetime.now()
        steps: list[StepResult] = []
        previous_parsed = None
        total_input = 0
        total_output = 0

        for i, step_spec in enumerate(chain):
            step_result, parsed_query = self._run_step_with_parsed(
                step_num=i + 1,
                question=step_spec["q"],
                expected=step_spec.get("expect"),
                previous_parsed=previous_parsed,
            )
            steps.append(step_result)

            total_input += step_result.parser_tokens.input
            total_output += step_result.parser_tokens.output

            # Update context for next step
            if parsed_query:
                previous_parsed = parsed_query

            if step_result.error:
                break

        return ChainResult(
            name=name,
            description=description,
            steps=steps,
            total_time_ms=int((datetime.now() - start_time).total_seconds() * 1000),
            total_input_tokens=total_input,
            total_output_tokens=total_output,
        )

    def run_single(self, question: str, expected: dict | None = None) -> SingleResult:
        """Run single question through the full flow."""
        start_time = datetime.now()

        step_result, _ = self._run_step_with_parsed(
            step_num=1,
            question=question,
            expected=expected,
            previous_parsed=None,
        )

        return SingleResult(
            question=question,
            step=step_result,
            total_time_ms=int((datetime.now() - start_time).total_seconds() * 1000),
            total_input_tokens=step_result.parser_tokens.input,
            total_output_tokens=step_result.parser_tokens.output,
        )

    def _run_step_with_parsed(
        self,
        step_num: int,
        question: str,
        expected: dict | None,
        previous_parsed,
    ) -> tuple[StepResult, Any]:
        """Run single step through the pipeline. Returns (StepResult, parsed_query)."""
        step_start = datetime.now()
        parsed_query = None

        result = StepResult(
            step=step_num,
            question=question,
        )

        try:
            # === PARSER ===
            parser_result = self.parser.parse(
                question,
                previous_parsed=previous_parsed,
            )
            parsed_query = parser_result.parsed_query

            result.parser_input = {
                "question": question,
                "previous_parsed": self._serialize_parsed(previous_parsed),
            }
            result.parser_output = {
                "parsed_query": self._serialize_parsed(parsed_query),
                "raw": parser_result.raw_output,
            }
            result.parser_tokens = TokenUsage(
                input=parser_result.input_tokens,
                output=parser_result.output_tokens,
                thinking=parser_result.thinking_tokens,
                cached=parser_result.cached_tokens,
                model=self.parser.model,
            )

            # === COMPOSER ===
            composer_result = self.composer.compose(
                parsed_query,
                original_question=question,
            )

            result.composer_type = composer_result.type
            result.composer_summary = composer_result.summary or ""

            # Add spec if query type
            if composer_result.type == "query" and composer_result.spec:
                spec = composer_result.spec
                result.composer_spec = {
                    "source": spec.source.value,
                    "grouping": spec.grouping.value,
                    "special_op": spec.special_op.value,
                }

                # === QUERY BUILDER ===
                try:
                    sql = self.query_builder.build(spec)
                    result.sql = sql

                    # === DATA FETCHER ===
                    fetch_result = self.data_fetcher({
                        "sql_query": sql,
                        "intent": {"query_spec": {}},
                    })
                    data = fetch_result.get("data", {})
                    result.data_row_count = data.get("row_count", 0)
                    result.data_columns = data.get("columns", [])
                    # Save first 10 rows for inspection
                    rows = data.get("rows", [])
                    result.data_rows = rows[:10] if rows else []

                    # === RESPONDER (mirrors graph.py flow) ===
                    try:
                        row_count = data.get("row_count", 0)
                        rows = data.get("rows", [])
                        columns = data.get("columns", [])

                        # Determine response type based on row count (same as graph.py)
                        # 0 rows → no_data, 1-5 rows → data_summary, >5 rows → offer_analysis
                        AUTO_SUMMARIZE_THRESHOLD = 5
                        if row_count == 0:
                            # No data found
                            responder_state = {
                                "messages": [{"role": "user", "content": question}],
                                "intent": {
                                    "type": "no_data",
                                    "parser_output": parser_result.raw_output,
                                    "symbol": "NQ",
                                    "row_count": 0,
                                },
                            }
                        elif row_count <= AUTO_SUMMARIZE_THRESHOLD:
                            # Small dataset: data_summary with table
                            data_preview = ""
                            if rows and columns:
                                header = "| " + " | ".join(columns) + " |"
                                separator = "| " + " | ".join(["---"] * len(columns)) + " |"
                                data_preview = header + "\n" + separator + "\n"
                                for row in rows[:5]:
                                    values = [str(row.get(col, "")) for col in columns]
                                    data_preview += "| " + " | ".join(values) + " |\n"

                            responder_state = {
                                "messages": [{"role": "user", "content": question}],
                                "intent": {
                                    "type": "data_summary",
                                    "parser_output": parser_result.raw_output,
                                    "symbol": "NQ",
                                    "data_preview": data_preview,
                                    "row_count": row_count,
                                },
                            }
                        else:
                            # Large dataset: offer_analysis
                            responder_state = {
                                "messages": [{"role": "user", "content": question}],
                                "intent": {
                                    "type": "offer_analysis",
                                    "parser_output": parser_result.raw_output,
                                    "symbol": "NQ",
                                    "row_count": row_count,
                                },
                            }

                        resp_result = self.responder(responder_state)
                        result.responder_text = resp_result.get("response", "")
                        result.responder_title = resp_result.get("data_title")
                    except Exception as e:
                        result.responder_text = f"Responder error: {e}"

                except Exception as e:
                    result.sql_error = str(e)

            # === RESPONDER for non-query types ===
            if composer_result.type != "query":
                try:
                    responder_state = {
                        "messages": [{"role": "user", "content": question}],
                        "intent": {
                            "type": composer_result.type,
                            "parser_output": parser_result.raw_output,
                            "symbol": "NQ",
                            "concept": getattr(composer_result, 'concept', None),
                            "field": getattr(composer_result, 'field', None),
                            "suggestions": getattr(composer_result, 'options', []),
                        },
                    }
                    resp_result = self.responder(responder_state)
                    result.responder_text = resp_result.get("response", "")
                except Exception as e:
                    result.responder_text = f"Responder error: {e}"

            # === VALIDATION ===
            if expected:
                # Build data_result for validation
                data_result = None
                if result.data_row_count is not None:
                    data_result = {
                        "row_count": result.data_row_count,
                        "columns": result.data_columns or [],
                    }
                result.validation = self.validator.validate(
                    parser_result,
                    composer_result,
                    expected,
                    data_result,
                )

            result.time_ms = int((datetime.now() - step_start).total_seconds() * 1000)

        except Exception as e:
            result.error = str(e)
            result.time_ms = int((datetime.now() - step_start).total_seconds() * 1000)

        return result, parsed_query

    def _serialize_parsed(self, parsed) -> dict | None:
        """Serialize ParsedQuery to dict for JSON."""
        if not parsed:
            return None

        return {
            "what": parsed.what,
            "period": {
                "raw": parsed.period.raw if parsed.period else None,
                "start": parsed.period.start if parsed.period else None,
                "end": parsed.period.end if parsed.period else None,
            } if parsed.period else None,
            "filters": {
                "weekdays": parsed.filters.weekdays if parsed.filters else None,
                "session": parsed.filters.session if parsed.filters else None,
                "event_filter": parsed.filters.event_filter if parsed.filters else None,
                "conditions": getattr(parsed.filters, 'conditions', None) if parsed.filters else None,
            } if parsed.filters else None,
            "modifiers": {
                "group_by": parsed.modifiers.group_by if parsed.modifiers else None,
                "top_n": parsed.modifiers.top_n if parsed.modifiers else None,
                "compare": parsed.modifiers.compare if parsed.modifiers else None,
                "find": parsed.modifiers.find if parsed.modifiers else None,
            } if parsed.modifiers else None,
        }


# =============================================================================
# Scenario Runner
# =============================================================================

def run_scenario(scenario_name: str, filter_pattern: str | None = None) -> dict:
    """Run a specific scenario, optionally filtering items by name/question."""
    scenario = get_scenario(scenario_name)
    is_chain = is_chain_scenario(scenario)

    # Filter items if pattern provided
    if filter_pattern:
        pattern = filter_pattern.lower()
        if is_chain:
            # Filter chains by name
            scenario = [c for c in scenario if pattern in c.get("name", "").lower()]
        else:
            # Filter single items by question
            scenario = [i for i in scenario if pattern in i.get("q", "").lower()]

        if not scenario:
            print(f"No items match filter: {filter_pattern}")
            return {"scenario": scenario_name, "results": [], "total_time_ms": 0}

    print(f"\n{'='*70}")
    print(f"Scenario: {scenario_name}" + (f" (filter: {filter_pattern})" if filter_pattern else ""))
    print(f"Type: {'chain' if is_chain else 'single'}")
    print(f"Items: {len(scenario)}")
    print(f"{'='*70}\n")

    runner = TestRunner()
    results: list[ChainResult | SingleResult] = []
    start_time = datetime.now()

    if is_chain:
        for i, chain_spec in enumerate(scenario, 1):
            name = chain_spec.get("name", f"chain_{i}")
            print(f"[{i}/{len(scenario)}] Chain: {name}")

            result = runner.run_chain(chain_spec)
            results.append(result)

            # Print steps
            for step in result.steps:
                status = "✓" if step.success else "✗"
                q = step.question[:40]
                tokens = f"{step.parser_tokens.input}→{step.parser_tokens.output}"
                print(f"    {status} Step {step.step}: {q}... [{tokens}]")

                # Show validation failures
                if step.validation and not step.validation.passed:
                    for check in step.validation.checks:
                        if not check.passed:
                            print(f"       FAIL: {check.key} expected={check.expected} actual={check.actual}")

            status = "✓" if result.success else "✗"
            print(f"    {status} {result.total_time_ms}ms, {result.total_input_tokens}→{result.total_output_tokens} tokens\n")
    else:
        for i, item in enumerate(scenario, 1):
            question = item["q"]
            expected = item.get("expect")

            print(f"[{i}/{len(scenario)}] Q: {question[:50]}...")

            result = runner.run_single(question, expected)
            results.append(result)

            status = "✓" if result.success else "✗"
            comp_type = result.step.composer_type or "?"
            tokens = f"{result.total_input_tokens}→{result.total_output_tokens}"
            rows = result.step.data_row_count
            rows_str = f", rows={rows}" if rows else ""

            print(f"    {status} {comp_type} | {result.total_time_ms}ms [{tokens}]{rows_str}")

            if result.step.validation and not result.step.validation.passed:
                for check in result.step.validation.checks:
                    if not check.passed:
                        print(f"       FAIL: {check.key} expected={check.expected} actual={check.actual}")

            if result.step.error:
                print(f"    Error: {result.step.error}")

            print()

    total_time = int((datetime.now() - start_time).total_seconds() * 1000)

    save_results(scenario_name, results, total_time, filter_pattern)
    print_summary(scenario_name, results, total_time)

    return {"scenario": scenario_name, "results": results, "total_time_ms": total_time}


# =============================================================================
# Results Saving
# =============================================================================

def _build_conversation(steps: list[StepResult]) -> list[dict]:
    """Build conversation view for quick overview."""
    conversation = []
    for step in steps:
        # User message
        conversation.append({
            "role": "user",
            "content": step.question,
        })
        # Assistant response
        if step.responder_text:
            assistant_msg = {"role": "assistant", "content": step.responder_text}
            if step.responder_title:
                assistant_msg["data_title"] = step.responder_title
            conversation.append(assistant_msg)
    return conversation


def _result_to_dict(result: ChainResult | SingleResult) -> dict:
    """Convert result to dict for JSON serialization."""
    if isinstance(result, ChainResult):
        return {
            "name": result.name,
            "description": result.description,
            "success": result.success,
            "total_time_ms": result.total_time_ms,
            "total_input_tokens": result.total_input_tokens,
            "total_output_tokens": result.total_output_tokens,
            "total_cost_usd": result.total_cost,
            "conversation": _build_conversation(result.steps),
            "steps": [_step_to_dict(s) for s in result.steps],
        }
    else:
        return {
            "question": result.question,
            "success": result.success,
            "total_time_ms": result.total_time_ms,
            "total_input_tokens": result.total_input_tokens,
            "total_output_tokens": result.total_output_tokens,
            "total_cost_usd": result.total_cost,
            "conversation": _build_conversation([result.step]),
            "step": _step_to_dict(result.step),
        }


def _step_to_dict(step: StepResult) -> dict:
    """Convert step to dict for JSON serialization."""
    d = {
        "step": step.step,
        "question": step.question,
        "time_ms": step.time_ms,
        "success": step.success,
        "parser": {
            "input": step.parser_input,
            "output": step.parser_output,
            "tokens": {
                "input": step.parser_tokens.input,
                "output": step.parser_tokens.output,
                "thinking": step.parser_tokens.thinking,
                "cached": step.parser_tokens.cached,
                "cost_usd": step.parser_tokens.cost,
            },
        },
        "composer": {
            "type": step.composer_type,
            "summary": step.composer_summary,
        },
    }

    if step.composer_spec:
        d["composer"]["spec"] = step.composer_spec

    if step.sql:
        d["query_builder"] = {"sql": step.sql}
    elif step.sql_error:
        d["query_builder"] = {"error": step.sql_error}

    if step.data_row_count is not None:
        d["data_fetcher"] = {
            "row_count": step.data_row_count,
            "columns": step.data_columns,
            "rows": step.data_rows,
        }

    if step.responder_text:
        d["responder"] = {
            "text": step.responder_text,
            "title": step.responder_title,
        }

    if step.validation:
        d["validation"] = {
            "passed": step.validation.passed,
            "checks": [
                {
                    "key": c.key,
                    "expected": c.expected,
                    "actual": c.actual,
                    "passed": c.passed,
                }
                for c in step.validation.checks
            ],
        }

    if step.error:
        d["error"] = step.error

    return d


def save_results(scenario_name: str, results: list, total_time_ms: int, filter_pattern: str | None = None):
    """Save results to JSON file."""
    log_dir = Path(__file__).parent.parent.parent / "docs" / "logs" / "tests"
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"{scenario_name}_{filter_pattern}" if filter_pattern else scenario_name
    log_file = log_dir / f"{name}_{timestamp}.json"

    success_count = sum(1 for r in results if r.success)
    total_input = sum(r.total_input_tokens for r in results)
    total_output = sum(r.total_output_tokens for r in results)
    total_cost = sum(r.total_cost for r in results)

    meta = {
        "scenario": scenario_name,
        "timestamp": datetime.now().isoformat(),
        "total_items": len(results),
        "successful": success_count,
        "failed": len(results) - success_count,
        "total_time_ms": total_time_ms,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cost_usd": total_cost,
    }
    if filter_pattern:
        meta["filter"] = filter_pattern

    output = {
        "meta": meta,
        "results": [_result_to_dict(r) for r in results],
    }

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print(f"\nResults saved: {log_file}")


def print_summary(scenario_name: str, results: list, total_time_ms: int):
    """Print test summary."""
    print(f"\n{'='*70}")
    print(f"SUMMARY: {scenario_name}")
    print(f"{'='*70}")

    success = sum(1 for r in results if r.success)
    total = len(results)
    total_input = sum(r.total_input_tokens for r in results)
    total_output = sum(r.total_output_tokens for r in results)
    total_cost = sum(r.total_cost for r in results)

    print(f"\nSuccess: {success}/{total} ({success/total*100:.0f}%)")
    print(f"Time: {total_time_ms}ms")
    print(f"Tokens: {total_input} in → {total_output} out")
    print(f"Cost: ${total_cost:.6f}")

    failures = [r for r in results if not r.success]
    if failures:
        print(f"\nFailures ({len(failures)}):")
        for r in failures:
            if isinstance(r, ChainResult):
                print(f"  - {r.name}")
            else:
                print(f"  - {r.question[:40]}")

    print(f"\n{'='*70}\n")


# =============================================================================
# Main
# =============================================================================

def main():
    import sys

    scenario_name = None
    filter_pattern = None
    show_list = False

    for arg in sys.argv[1:]:
        if arg.startswith("--scenario="):
            scenario_name = arg.split("=")[1]
        elif arg.startswith("--filter="):
            filter_pattern = arg.split("=")[1]
        elif arg == "--list":
            show_list = True

    if show_list:
        print("\nAvailable scenarios:")
        for name in list_scenarios():
            scenario = get_scenario(name)
            is_chain = is_chain_scenario(scenario)
            type_str = "chain" if is_chain else "single"
            print(f"  {name:30} ({type_str}, {len(scenario)} items)")
        return

    if not scenario_name:
        print("Usage: python -m agent.tests.conversation_test --scenario=<name>")
        print("       python -m agent.tests.conversation_test --scenario=<name> --filter=<pattern>")
        print("       python -m agent.tests.conversation_test --list")
        print("\nExamples:")
        print("  --scenario=follow_up              # run all follow_up chains")
        print("  --scenario=follow_up --filter=A2  # run only chains containing 'A2'")
        print("  --scenario=greetings --filter=Hi  # run only items containing 'Hi'")
        return

    run_scenario(scenario_name, filter_pattern)


if __name__ == "__main__":
    main()
