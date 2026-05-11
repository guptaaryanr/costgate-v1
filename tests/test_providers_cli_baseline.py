from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from costgate.baselines import (
    BaselineFamilyMismatchError,
    assert_same_family,
    build_baseline_key,
)
from costgate.jsonutil import dumps_json
from costgate.run import run_suite
from costgate.validation import load_and_validate_rate_card, match_rate_rule


def _suite(tmp_path: Path) -> Path:
    path = tmp_path / "suite.yaml"
    path.write_text(
        """
tests:
  - id: answer
    task_type: qa
    system: Return only the answer.
    user: What is 40 + 2?
    expected:
      type: exact
      value: "42"
""",
        encoding="utf-8",
    )
    return path


def _rate_card(tmp_path: Path) -> Path:
    path = tmp_path / "rates.yaml"
    path.write_text(
        """
version: 1
currency: USD
rules:
  - model_glob: "mock*"
    input_usd_per_1k: 1.0
    output_usd_per_1k: 2.0
""",
        encoding="utf-8",
    )
    return path


def _policy(tmp_path: Path) -> Path:
    path = tmp_path / "policy.yaml"
    path.write_text(
        """
version: 1
gates:
  cost_per_valid_success_usd:
    direction: higher_is_worse
    max_relative_increase: 0.10
    severity: fail
    statistical_test: none
  task_success_rate:
    direction: lower_is_worse
    min_absolute_value: 1.0
    severity: fail
    statistical_test: none
min_repeats: 2
min_sample_size: 2
variance_aware:
  enabled: false
""",
        encoding="utf-8",
    )
    return path


def _mock_config(tmp_path: Path) -> Path:
    path = tmp_path / "mock.yaml"
    path.write_text(
        """
default:
  output_text: "42"
  input_tokens: 10
  output_tokens: 3
  latency_ms: 20
  retry_count: 0
  token_source: mock
""",
        encoding="utf-8",
    )
    return path


def test_mock_provider_run(tmp_path) -> None:
    results = run_suite(
        provider="mock",
        model="mock-model",
        suite_path=_suite(tmp_path),
        rate_card_path=_rate_card(tmp_path),
        repeats=2,
        provider_config={
            "default": {
                "output_text": "42",
                "input_tokens": 10,
                "output_tokens": 3,
                "latency_ms": 20,
            }
        },
    )

    assert results["schema_version"] == "costgate.run.v1"
    assert results["calls"][0]["api_success"] is True
    assert results["calls"][0]["task_success"] is True
    assert results["overall_aggregates"]["cost_per_valid_success_usd"] == pytest.approx(0.016)


def test_replay_provider_run(tmp_path) -> None:
    fixture = tmp_path / "replay.json"
    fixture.write_text(
        dumps_json(
            {
                "calls": [
                    {
                        "task_id": "answer",
                        "repeat": 0,
                        "api_success": True,
                        "output_text": "42",
                        "input_tokens": 8,
                        "output_tokens": 2,
                        "total_tokens": 10,
                        "latency_ms": 10,
                    },
                    {
                        "task_id": "answer",
                        "repeat": 1,
                        "api_success": True,
                        "output_text": "42",
                        "input_tokens": 8,
                        "output_tokens": 2,
                        "total_tokens": 10,
                        "latency_ms": 11,
                    },
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    results = run_suite(
        provider="replay",
        model="mock-model",
        suite_path=_suite(tmp_path),
        rate_card_path=_rate_card(tmp_path),
        repeats=2,
        provider_config={"fixture_path": str(fixture)},
    )

    assert [c["output_text"] for c in results["calls"]] == ["42", "42"]
    assert results["overall_aggregates"]["task_success_rate"] == 1.0


def test_rate_card_matching(tmp_path) -> None:
    card = load_and_validate_rate_card(_rate_card(tmp_path))
    match = match_rate_rule(card, "mock-model-v1")

    assert match is not None
    rule, glob = match
    assert glob == "mock*"
    assert rule.output_usd_per_1k == 2.0


def test_baseline_family_key_stability() -> None:
    first = build_baseline_key("suite", "mock", "mock-model", "params", "rates", "schema")
    second = build_baseline_key("suite", "mock", "mock-model", "params", "rates", "schema")

    assert first == second


def test_baseline_mismatch_rejection() -> None:
    baseline = {"meta": {"suite_hash": "a", "provider": "mock", "resolved_model": "m", "params_hash": "p", "rate_card_hash": "r"}}
    candidate = {"meta": {"suite_hash": "b", "provider": "mock", "resolved_model": "m", "params_hash": "p", "rate_card_hash": "r"}}

    with pytest.raises(BaselineFamilyMismatchError):
        assert_same_family(baseline, candidate)


def test_cli_validate_run_compare_with_mock(tmp_path) -> None:
    suite = _suite(tmp_path)
    rates = _rate_card(tmp_path)
    policy = _policy(tmp_path)
    mock_cfg = _mock_config(tmp_path)
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    compare_json = tmp_path / "compare.json"
    report = tmp_path / "report.md"

    validate = subprocess.run(
        [
            sys.executable,
            "-m",
            "costgate.cli",
            "validate",
            "--suite",
            str(suite),
            "--rate-card",
            str(rates),
            "--policy",
            str(policy),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert validate.returncode == 0, validate.stderr

    base_run = subprocess.run(
        [
            sys.executable,
            "-m",
            "costgate.cli",
            "run",
            "--provider",
            "mock",
            "--model",
            "mock-model",
            "--suite",
            str(suite),
            "--rate-card",
            str(rates),
            "--repeats",
            "2",
            "--provider-config",
            str(mock_cfg),
            "--out",
            str(baseline),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert base_run.returncode == 0, base_run.stderr

    cand_run = subprocess.run(
        [
            sys.executable,
            "-m",
            "costgate.cli",
            "run",
            "--provider",
            "mock",
            "--model",
            "mock-model",
            "--suite",
            str(suite),
            "--rate-card",
            str(rates),
            "--repeats",
            "2",
            "--provider-config",
            str(mock_cfg),
            "--out",
            str(candidate),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert cand_run.returncode == 0, cand_run.stderr

    cmp_run = subprocess.run(
        [
            sys.executable,
            "-m",
            "costgate.cli",
            "compare",
            "--pr-results",
            str(candidate),
            "--baseline-json",
            str(baseline),
            "--policy",
            str(policy),
            "--compare-out",
            str(compare_json),
            "--report-out",
            str(report),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert cmp_run.returncode == 0, cmp_run.stderr
    compare_obj = json.loads(compare_json.read_text(encoding="utf-8"))
    assert compare_obj["overall_verdict"] == "pass"
    assert "Costgate Report" in report.read_text(encoding="utf-8")
