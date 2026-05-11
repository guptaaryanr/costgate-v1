from __future__ import annotations

import math
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

import costgate
from costgate.artifacts import COMPARISON_SCHEMA_VERSION, RUN_SCHEMA_VERSION
from costgate.baselines import BaselineFamilyMismatchError, assert_same_family
from costgate.compare import compare_results_and_gate
from costgate.jsonutil import dumps_json
from costgate.report import write_markdown_report
from costgate.run import run_suite
from costgate.stats import bootstrap_ci_mean_diff
from costgate.validation import load_and_validate_policy
from costgate.validators import validate_output


def _artifact(metric_values: dict[str, list[float]], calls: list[dict] | None = None) -> dict:
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
        "schema_version": RUN_SCHEMA_VERSION,
        "tokenizer": "provider_usage_or_costgate_estimator_v1",
    }
    return {
        "schema_version": RUN_SCHEMA_VERSION,
        "meta": meta,
        "per_repeat_aggregates": aggs,
        "calls": calls or [],
    }


def _policy(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "policy.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def _suite(tmp_path: Path, expected: bool = True) -> Path:
    expected_block = """
    expected:
      type: exact
      value: "42"
""" if expected else ""
    path = tmp_path / "suite.yaml"
    path.write_text(
        f"""
tests:
  - id: answer
    task_type: qa
    system: Return only the answer.
    user: What is 40 + 2?
{expected_block}
""",
        encoding="utf-8",
    )
    return path


def _rate_card(tmp_path: Path, model_glob: str = "mock*") -> Path:
    path = tmp_path / "rates.yaml"
    path.write_text(
        f"""
version: 1
currency: USD
rules:
  - model_glob: "{model_glob}"
    input_usd_per_1k: 1.0
    output_usd_per_1k: 2.0
""",
        encoding="utf-8",
    )
    return path


def test_version_matches_pyproject() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert costgate.__version__ == pyproject["project"]["version"]


def test_openai_dependencies_are_optional() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    deps = pyproject["project"]["dependencies"]
    extras = pyproject["project"]["optional-dependencies"]

    assert not any(dep.lower().startswith("openai") for dep in deps)
    assert not any(dep.lower().startswith("tiktoken") for dep in deps)
    assert any(dep.lower().startswith("openai") for dep in extras["openai"])
    assert any(dep.lower().startswith("tiktoken") for dep in extras["openai"])


def test_cli_import_does_not_import_openai_provider(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    sys.modules.pop("openai", None)
    sys.modules.pop("costgate.providers.openai_provider", None)

    import costgate.cli  # noqa: F401

    assert "costgate.providers.openai_provider" not in sys.modules
    assert "openai" not in sys.modules


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("43", {"type": "exact", "value": "42"}),
        ("hello", {"type": "contains", "value": "costgate"}),
        ("build", {"type": "regex", "pattern": r"build-\d+"}),
        ('{"total": 123.45}', {"type": "json_schema", "schema": {"type": "object", "properties": {"total": {"type": "string"}}}}),
        ("10.2", {"type": "numeric_tolerance", "value": 10.0, "tolerance": 0.05}),
    ],
)
def test_validators_fail_when_expected(output, expected) -> None:
    assert validate_output(output, expected, True).passed is False


def test_run_artifact_schema_and_missing_validator_warning(tmp_path) -> None:
    results = run_suite(
        provider="mock",
        model="mock-model",
        suite_path=_suite(tmp_path, expected=False),
        rate_card_path=_rate_card(tmp_path),
        repeats=1,
        provider_config={"default": {"output_text": "42", "input_tokens": 10, "output_tokens": 2}},
    )

    assert results["schema_version"] == RUN_SCHEMA_VERSION
    for key in [
        "costgate_version",
        "run_id",
        "timestamp",
        "provider",
        "model",
        "suite_hash",
        "params_hash",
        "rate_card_hash",
        "pricing_version",
        "tokenizer",
        "token_source",
        "calls",
        "per_repeat_aggregates",
        "overall_aggregates",
    ]:
        assert key in results

    call = results["calls"][0]
    for key in [
        "task_id",
        "task_type",
        "repeat",
        "api_success",
        "task_success",
        "validator_type",
        "validator_passed",
        "validator_details",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cost_usd",
        "latency_ms",
        "retry_count",
        "token_source",
        "error",
        "output_hash",
    ]:
        assert key in call
    assert call["api_success"] is True
    assert call["task_success"] is True
    assert results["warnings"][0]["type"] == "missing_validator"


def test_missing_rate_card_price_is_explicit_nan(tmp_path) -> None:
    results = run_suite(
        provider="mock",
        model="no-price-model",
        suite_path=_suite(tmp_path),
        rate_card_path=_rate_card(tmp_path, model_glob="other*"),
        repeats=1,
        allow_missing_rate=True,
        provider_config={"default": {"output_text": "42", "input_tokens": 10, "output_tokens": 2}},
    )

    assert results["calls"][0]["cost_status"] == "missing_cost"
    assert math.isnan(results["calls"][0]["cost_usd"])
    assert math.isnan(results["overall_aggregates"]["total_cost_usd"])


def test_comparison_artifact_schema_and_policy_hash(tmp_path) -> None:
    policy = load_and_validate_policy(
        _policy(
            tmp_path,
            """
version: 1
gates:
  cost_per_valid_success_usd:
    direction: higher_is_worse
    max_relative_increase: 0.10
    severity: fail
    statistical_test: none
min_repeats: 1
min_sample_size: 1
variance_aware:
  enabled: false
""",
        )
    )

    cmp = compare_results_and_gate(
        _artifact({"cost_per_valid_success_usd": [1.0]}),
        _artifact({"cost_per_valid_success_usd": [2.0]}),
        policy,
    )

    assert cmp["schema_version"] == COMPARISON_SCHEMA_VERSION
    assert cmp["policy_hash"]
    assert cmp["compared_metrics"] == ["cost_per_valid_success_usd"]
    assert cmp["metrics"]["cost_per_valid_success_usd"]["practical"]["exceeds_threshold"]
    assert cmp["per_metric_verdicts"]["cost_per_valid_success_usd"] == "fail"


def test_baseline_mismatch_requires_explicit_override(tmp_path) -> None:
    policy = load_and_validate_policy(
        _policy(
            tmp_path,
            """
version: 1
gates:
  cost_per_valid_success_usd:
    direction: higher_is_worse
    max_relative_increase: 0.10
    severity: fail
    statistical_test: none
min_repeats: 1
min_sample_size: 1
variance_aware:
  enabled: false
""",
        )
    )
    baseline = _artifact({"cost_per_valid_success_usd": [1.0]})
    candidate = _artifact({"cost_per_valid_success_usd": [2.0]})
    candidate["meta"]["suite_hash"] = "different"

    with pytest.raises(BaselineFamilyMismatchError):
        assert_same_family(baseline, candidate)
    with pytest.raises(BaselineFamilyMismatchError):
        compare_results_and_gate(baseline, candidate, policy)

    cmp = compare_results_and_gate(baseline, candidate, policy, allow_family_mismatch=True)
    assert cmp["overall_verdict"] == "fail"


def test_practical_only_policy_with_disabled_stats(tmp_path) -> None:
    policy = load_and_validate_policy(
        _policy(
            tmp_path,
            """
version: 1
gates:
  cost_per_valid_success_usd:
    direction: higher_is_worse
    max_relative_increase: 0.10
    severity: fail
    statistical_test: none
min_repeats: 1
min_sample_size: 1
variance_aware:
  enabled: false
""",
        )
    )
    cmp = compare_results_and_gate(
        _artifact({"cost_per_valid_success_usd": [1.0]}),
        _artifact({"cost_per_valid_success_usd": [1.3]}),
        policy,
    )

    assert cmp["metrics"]["cost_per_valid_success_usd"]["stats"]["test"] == "none"
    assert cmp["overall_verdict"] == "fail"


def test_bootstrap_gate_and_small_sample_degrade_gracefully(tmp_path) -> None:
    ci = bootstrap_ci_mean_diff([1.0], [2.0], n_boot=100)
    assert ci["mean_diff"] == pytest.approx(1.0)

    policy = load_and_validate_policy(
        _policy(
            tmp_path,
            """
version: 1
gates:
  cost_per_valid_success_usd:
    direction: higher_is_worse
    max_relative_increase: 0.10
    severity: fail
    statistical_test: bootstrap
min_repeats: 3
min_sample_size: 3
variance_aware:
  enabled: false
""",
        )
    )
    cmp = compare_results_and_gate(
        _artifact({"cost_per_valid_success_usd": [1.0]}),
        _artifact({"cost_per_valid_success_usd": [2.0]}),
        policy,
    )

    assert cmp["per_metric_verdicts"]["cost_per_valid_success_usd"] == "insufficient_data"
    assert cmp["overall_verdict"] == "warn"


def test_mann_whitney_one_sided_lower_is_worse(tmp_path) -> None:
    policy = load_and_validate_policy(
        _policy(
            tmp_path,
            """
version: 1
gates:
  task_success_rate:
    direction: lower_is_worse
    max_relative_decrease: 0.05
    severity: fail
    statistical_test: mann_whitney
min_repeats: 6
min_sample_size: 6
variance_aware:
  enabled: false
""",
        )
    )
    cmp = compare_results_and_gate(
        _artifact({"task_success_rate": [1, 1, 1, 1, 1, 1]}),
        _artifact({"task_success_rate": [0.7, 0.7, 0.7, 0.7, 0.7, 0.7]}),
        policy,
    )

    assert cmp["overall_verdict"] == "fail"
    assert cmp["metrics"]["task_success_rate"]["gate"]["statistically_worse"] is True


def test_default_latency_gate_is_warn() -> None:
    policy = load_and_validate_policy(Path("costgate/policies/default.yaml"))

    assert policy.gates["p95_latency_ms"].severity == "warn"


def test_markdown_report_contains_required_sections_and_warnings(tmp_path) -> None:
    policy = load_and_validate_policy(
        _policy(
            tmp_path,
            """
version: 1
gates:
  cost_per_valid_success_usd:
    direction: higher_is_worse
    max_relative_increase: 0.10
    severity: fail
    statistical_test: none
  api_success_rate:
    direction: lower_is_worse
    min_absolute_value: 1.0
    severity: warn
    statistical_test: none
  task_success_rate:
    direction: lower_is_worse
    min_absolute_value: 1.0
    severity: fail
    statistical_test: none
min_repeats: 1
min_sample_size: 1
variance_aware:
  enabled: false
""",
        )
    )
    candidate_calls = [
        {
            "task_id": "no_expected",
            "validator_type": "none",
            "token_source": "estimated",
        }
    ]
    cmp = compare_results_and_gate(
        _artifact(
            {
                "cost_per_valid_success_usd": [1.0],
                "api_success_rate": [1.0],
                "task_success_rate": [1.0],
                "estimated_token_fraction": [0.0],
            }
        ),
        _artifact(
            {
                "cost_per_valid_success_usd": [2.0],
                "api_success_rate": [1.0],
                "task_success_rate": [1.0],
                "estimated_token_fraction": [1.0],
            },
            calls=candidate_calls,
        ),
        policy,
    )
    report = write_markdown_report(cmp)

    for text in [
        "Overall verdict",
        "Run Metadata",
        "cost_per_valid_success_usd",
        "api_success_rate",
        "task_success_rate",
        "Policy Violations",
        "FAIL",
        "Token-source warning",
        "Validator warning",
        "Driver Hints",
    ]:
        assert text in report


def test_cli_fail_and_warn_exit_codes(tmp_path) -> None:
    fail_policy = _policy(
        tmp_path,
        """
version: 1
gates:
  cost_per_valid_success_usd:
    direction: higher_is_worse
    max_relative_increase: 0.10
    severity: fail
    statistical_test: none
min_repeats: 1
min_sample_size: 1
variance_aware:
  enabled: false
""",
    )
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(
        dumps_json(_artifact({"cost_per_valid_success_usd": [1.0]}), indent=2),
        encoding="utf-8",
    )
    candidate.write_text(
        dumps_json(_artifact({"cost_per_valid_success_usd": [2.0]}), indent=2),
        encoding="utf-8",
    )

    failed = subprocess.run(
        [
            sys.executable,
            "-m",
            "costgate.cli",
            "compare",
            "--baseline-json",
            str(baseline),
            "--pr-results",
            str(candidate),
            "--policy",
            str(fail_policy),
            "--compare-out",
            str(tmp_path / "fail-compare.json"),
            "--report-out",
            str(tmp_path / "fail-report.md"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert failed.returncode == 2

    warn_policy = _policy(
        tmp_path,
        """
version: 1
gates:
  p95_latency_ms:
    direction: higher_is_worse
    max_relative_increase: 0.10
    severity: warn
    statistical_test: none
min_repeats: 1
min_sample_size: 1
variance_aware:
  enabled: false
""",
    )
    baseline.write_text(
        dumps_json(_artifact({"p95_latency_ms": [100.0]}), indent=2),
        encoding="utf-8",
    )
    candidate.write_text(
        dumps_json(_artifact({"p95_latency_ms": [200.0]}), indent=2),
        encoding="utf-8",
    )
    warned = subprocess.run(
        [
            sys.executable,
            "-m",
            "costgate.cli",
            "compare",
            "--baseline-json",
            str(baseline),
            "--pr-results",
            str(candidate),
            "--policy",
            str(warn_policy),
            "--compare-out",
            str(tmp_path / "warn-compare.json"),
            "--report-out",
            str(tmp_path / "warn-report.md"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert warned.returncode == 0
    assert "Verdict: warn" in warned.stdout


def test_cli_version_command() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "costgate.cli", "version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == costgate.__version__
