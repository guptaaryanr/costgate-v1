from __future__ import annotations

import math

import pytest

from costgate.metrics import compute_aggregates
from costgate.suites import load_and_validate_suite
from costgate.validation import ValidationError
from costgate.validators import validate_output


def test_suite_loading_with_expected_validator(tmp_path) -> None:
    suite = tmp_path / "suite.yaml"
    suite.write_text(
        """
tests:
  - id: arithmetic_1
    task_type: math
    system: Return only the final answer.
    user: Compute 1783 + 946 - 502.
    expected:
      type: exact
      value: "2227"
""",
        encoding="utf-8",
    )

    loaded = load_and_validate_suite(suite)

    assert loaded.tests[0].expected == {"type": "exact", "value": "2227"}


def test_suite_rejects_bad_expected_validator(tmp_path) -> None:
    suite = tmp_path / "suite.yaml"
    suite.write_text(
        """
tests:
  - id: bad
    task_type: qa
    system: s
    user: u
    expected:
      type: made_up
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_and_validate_suite(suite)


def test_exact_validator() -> None:
    result = validate_output(" 2227\n", {"type": "exact", "value": "2227"}, True)
    assert result.passed


def test_contains_validator() -> None:
    result = validate_output("hello Costgate", {"type": "contains", "value": "costgate", "case_sensitive": False}, True)
    assert result.passed


def test_regex_validator() -> None:
    result = validate_output("build-123", {"type": "regex", "pattern": r"build-\d+"}, True)
    assert result.passed


def test_json_schema_validator() -> None:
    result = validate_output(
        '{"total":"123.45"}',
        {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "required": ["total"],
                "properties": {"total": {"type": "string"}},
            },
        },
        True,
    )
    assert result.passed


def test_numeric_tolerance_validator() -> None:
    result = validate_output(
        "answer: 10.04",
        {"type": "numeric_tolerance", "value": 10.0, "tolerance": 0.05},
        True,
    )
    assert result.passed


def test_no_expected_defaults_task_success_to_api_success_with_warning() -> None:
    result = validate_output("anything", None, True)
    assert result.passed
    assert result.validator_type == "none"
    assert result.warning


def test_token_and_cost_aggregation() -> None:
    agg = compute_aggregates(
        [
            {
                "api_success": True,
                "task_success": True,
                "cost_usd": 0.10,
                "input_tokens": 10,
                "output_tokens": 20,
                "total_tokens": 30,
                "latency_ms": 100,
                "retry_count": 0,
                "token_source": "api",
            },
            {
                "api_success": True,
                "task_success": False,
                "cost_usd": 0.20,
                "input_tokens": 30,
                "output_tokens": 40,
                "total_tokens": 70,
                "latency_ms": 300,
                "retry_count": 1,
                "token_source": "estimated",
            },
        ]
    )

    assert agg["total_cost_usd"] == pytest.approx(0.30)
    assert agg["cost_per_api_success_usd"] == pytest.approx(0.15)
    assert agg["cost_per_valid_success_usd"] == pytest.approx(0.30)
    assert agg["api_success_rate"] == 1.0
    assert agg["task_success_rate"] == 0.5
    assert agg["mean_total_tokens"] == 50
    assert agg["retry_rate"] == 0.5
    assert agg["estimated_token_fraction"] == 0.5


def test_zero_valid_successes_are_infinite_not_zero() -> None:
    agg = compute_aggregates(
        [
            {
                "api_success": True,
                "task_success": False,
                "cost_usd": 0.10,
                "latency_ms": 100,
                "retry_count": 0,
                "token_source": "api",
            }
        ]
    )

    assert math.isinf(agg["cost_per_valid_success_usd"])
    assert agg["cost_per_valid_success_status"] == "no_valid_successes"


def test_missing_cost_is_nan_not_zero() -> None:
    agg = compute_aggregates(
        [
            {
                "api_success": True,
                "task_success": True,
                "cost_usd": float("nan"),
                "latency_ms": 100,
                "retry_count": 0,
                "token_source": "api",
            }
        ]
    )

    assert math.isnan(agg["total_cost_usd"])
    assert agg["cost_per_valid_success_status"] == "missing_cost"
