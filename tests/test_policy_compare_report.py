from __future__ import annotations

from pathlib import Path

from costgate.compare import compare_results_and_gate
from costgate.report import write_markdown_report
from costgate.validation import load_and_validate_policy


def _artifact(metric_values: dict[str, list[float]]) -> dict:
    repeats = len(next(iter(metric_values.values())))
    aggs = []
    for i in range(repeats):
        row = {"repeat_index": i}
        for metric, values in metric_values.items():
            row[metric] = values[i]
        aggs.append(row)
    meta = {
        "repeats": repeats,
        "suite_hash": "suite",
        "provider": "mock",
        "resolved_model": "mock-model",
        "params_hash": "params",
        "rate_card_hash": "rates",
        "schema_version": "costgate.run.v1",
    }
    return {
        "schema_version": "costgate.run.v1",
        "meta": meta,
        "per_repeat_aggregates": aggs,
        "calls": [],
    }


def _write_policy(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "policy.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_policy_loads_direction_and_severity(tmp_path) -> None:
    policy = load_and_validate_policy(
        _write_policy(
            tmp_path,
            """
version: 1
gates:
  task_success_rate:
    direction: lower_is_worse
    min_absolute_value: 0.95
    severity: fail
min_repeats: 5
min_sample_size: 5
variance_aware:
  enabled: false
""",
        )
    )

    assert policy.gates["task_success_rate"].direction == "lower_is_worse"
    assert policy.gates["task_success_rate"].severity == "fail"


def test_old_policy_format_still_loads(tmp_path) -> None:
    policy = load_and_validate_policy(
        _write_policy(
            tmp_path,
            """
version: 1
metrics_to_gate:
  - total_cost_usd
regression_threshold_pct:
  total_cost_usd: 10
min_repeats: 5
min_sample_size: 5
""",
        )
    )

    assert "total_cost_usd" in policy.gates


def test_metric_direction_higher_is_worse_fails(tmp_path) -> None:
    policy = load_and_validate_policy(
        _write_policy(
            tmp_path,
            """
version: 1
gates:
  cost_per_valid_success_usd:
    direction: higher_is_worse
    max_relative_increase: 0.10
    severity: fail
min_repeats: 5
min_sample_size: 5
variance_aware:
  enabled: false
""",
        )
    )
    baseline = _artifact({"cost_per_valid_success_usd": [1, 1, 1, 1, 1, 1]})
    candidate = _artifact({"cost_per_valid_success_usd": [2, 2, 2, 2, 2, 2]})

    cmp = compare_results_and_gate(baseline, candidate, policy)

    assert cmp["overall_verdict"] == "fail"
    assert cmp["per_metric_verdicts"]["cost_per_valid_success_usd"] == "fail"


def test_metric_direction_lower_is_worse_fails(tmp_path) -> None:
    policy = load_and_validate_policy(
        _write_policy(
            tmp_path,
            """
version: 1
gates:
  task_success_rate:
    direction: lower_is_worse
    max_relative_decrease: 0.05
    severity: fail
min_repeats: 5
min_sample_size: 5
variance_aware:
  enabled: false
""",
        )
    )
    baseline = _artifact({"task_success_rate": [1, 1, 1, 1, 1, 1]})
    candidate = _artifact({"task_success_rate": [0.8, 0.8, 0.8, 0.8, 0.8, 0.8]})

    cmp = compare_results_and_gate(baseline, candidate, policy)

    assert cmp["overall_verdict"] == "fail"
    assert cmp["per_metric_verdicts"]["task_success_rate"] == "fail"


def test_warn_severity_sets_overall_warn(tmp_path) -> None:
    policy = load_and_validate_policy(
        _write_policy(
            tmp_path,
            """
version: 1
gates:
  p95_latency_ms:
    direction: higher_is_worse
    max_relative_increase: 0.10
    severity: warn
min_repeats: 5
min_sample_size: 5
variance_aware:
  enabled: false
""",
        )
    )
    baseline = _artifact({"p95_latency_ms": [100, 100, 100, 100, 100, 100]})
    candidate = _artifact({"p95_latency_ms": [200, 200, 200, 200, 200, 200]})

    cmp = compare_results_and_gate(baseline, candidate, policy)

    assert cmp["overall_verdict"] == "warn"
    assert cmp["per_metric_verdicts"]["p95_latency_ms"] == "warn"


def test_markdown_report_generation(tmp_path) -> None:
    policy = load_and_validate_policy(
        _write_policy(
            tmp_path,
            """
version: 1
gates:
  cost_per_valid_success_usd:
    direction: higher_is_worse
    max_relative_increase: 0.10
    severity: fail
min_repeats: 5
min_sample_size: 5
variance_aware:
  enabled: false
""",
        )
    )
    cmp = compare_results_and_gate(
        _artifact({"cost_per_valid_success_usd": [1, 1, 1, 1, 1, 1]}),
        _artifact({"cost_per_valid_success_usd": [1, 1, 1, 1, 1, 1]}),
        policy,
    )

    report = write_markdown_report(cmp)

    assert "Overall verdict" in report
    assert "cost_per_valid_success_usd" in report
