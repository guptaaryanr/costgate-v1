from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any, Dict, List, Tuple

import numpy as np

from costgate import __version__
from costgate.artifacts import COMPARISON_SCHEMA_VERSION
from costgate.baselines import assert_same_family, canonical_hash_json_obj
from costgate.jsonutil import coerce_float
from costgate.stats import (
    bootstrap_ci_cliffs_delta,
    bootstrap_ci_mean_diff,
    mann_whitney_u_greater,
)
from costgate.validation import Gate, Policy, SUPPORTED_METRICS


class CompareError(RuntimeError):
    pass


def _metric_samples(results: Dict[str, Any], metric: str) -> List[float]:
    aggs = results.get("per_repeat_aggregates", [])
    if not isinstance(aggs, list) or not aggs:
        return []
    return [coerce_float(a.get(metric)) for a in aggs if isinstance(a, dict)]


def _finite_samples(xs: List[float]) -> List[float]:
    return [float(x) for x in xs if math.isfinite(float(x))]


def _safe_mean(xs: List[float]) -> float:
    vals = [float(x) for x in xs]
    if not vals:
        return float("nan")
    if any(math.isnan(x) for x in vals):
        return float("nan")
    if any(math.isinf(x) for x in vals):
        if any(x == float("inf") for x in vals):
            return float("inf")
        return float("-inf")
    return float(np.mean(np.array(vals, dtype=float)))


def _safe_std(xs: List[float]) -> float:
    arr = np.array(_finite_samples(xs), dtype=float)
    return float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0


def _is_cost_metric(metric: str) -> bool:
    return "cost" in metric


def _oriented(samples: List[float], direction: str) -> List[float]:
    finite = _finite_samples(samples)
    if direction == "lower_is_worse":
        return [-x for x in finite]
    return finite


def _effective_relative_threshold(
    policy: Policy,
    gate: Gate,
    baseline_samples: List[float],
) -> Tuple[float | None, Dict[str, Any]]:
    configured = (
        gate.max_relative_increase
        if gate.direction == "higher_is_worse"
        else gate.max_relative_decrease
    )
    info: Dict[str, Any] = {"configured_fraction": configured}
    if configured is None:
        return None, info

    if policy.variance_aware.enabled:
        m = _safe_mean(_finite_samples(baseline_samples))
        s = _safe_std(baseline_samples)
        dyn = policy.variance_aware.k * (s / abs(m)) if math.isfinite(m) and m != 0 else 0.0
        eff = max(float(configured), dyn)
        info.update(
            {
                "variance_aware_enabled": True,
                "k": policy.variance_aware.k,
                "dynamic_fraction": dyn,
            }
        )
        return eff, info

    info["variance_aware_enabled"] = False
    return float(configured), info


def _relative_worse(
    baseline_mean: float,
    candidate_mean: float,
    threshold_frac: float,
    direction: str,
) -> bool:
    if direction == "higher_is_worse":
        if baseline_mean == 0:
            return candidate_mean > 0
        return candidate_mean > baseline_mean * (1.0 + threshold_frac)
    if baseline_mean == 0:
        return candidate_mean < 0
    return candidate_mean < baseline_mean * (1.0 - threshold_frac)


def _practical_check(
    gate: Gate,
    policy: Policy,
    baseline_samples: List[float],
    candidate_samples: List[float],
) -> Dict[str, Any]:
    b_mean = _safe_mean(baseline_samples)
    c_mean = _safe_mean(candidate_samples)
    raw_delta = c_mean - b_mean
    worse_delta = raw_delta if gate.direction == "higher_is_worse" else -raw_delta
    delta_pct = (
        (raw_delta / b_mean) * 100.0
        if (math.isfinite(b_mean) and b_mean != 0 and math.isfinite(raw_delta))
        else float("inf")
    )

    threshold_frac, threshold_info = _effective_relative_threshold(policy, gate, baseline_samples)
    reasons: List[str] = []
    checks: Dict[str, bool] = {}

    if any(math.isnan(x) for x in baseline_samples + candidate_samples):
        return {
            "baseline_mean": b_mean,
            "candidate_mean": c_mean,
            "delta": raw_delta,
            "worse_delta": worse_delta,
            "delta_pct": delta_pct,
            "relative_threshold_frac": threshold_frac,
            "relative_threshold_details": threshold_info,
            "exceeds_threshold": False,
            "insufficient_data": True,
            "reasons": ["non_finite_missing_metric"],
            "checks": checks,
        }

    if threshold_frac is not None:
        checks["relative"] = _relative_worse(
            b_mean, c_mean, threshold_frac, gate.direction
        )
        if not checks["relative"]:
            reasons.append("below_relative_threshold")

    if gate.min_absolute_value is not None:
        checks["min_absolute_value"] = c_mean < gate.min_absolute_value
        if not checks["min_absolute_value"]:
            reasons.append("above_min_absolute_value")

    if gate.max_absolute_value is not None:
        checks["max_absolute_value"] = c_mean > gate.max_absolute_value
        if not checks["max_absolute_value"]:
            reasons.append("below_max_absolute_value")

    exceeded = any(checks.values()) if checks else False

    min_abs_usd = gate.min_absolute_delta_usd
    if exceeded and _is_cost_metric(gate.metric) and min_abs_usd is not None:
        if math.isfinite(worse_delta) and worse_delta < min_abs_usd:
            exceeded = False
            reasons.append("below_min_absolute_delta_usd")

    if math.isinf(c_mean) and gate.direction == "higher_is_worse":
        exceeded = True
        checks["non_finite_worse"] = True
    if math.isinf(c_mean) and gate.direction == "lower_is_worse" and c_mean < 0:
        exceeded = True
        checks["non_finite_worse"] = True

    return {
        "baseline_mean": b_mean,
        "candidate_mean": c_mean,
        "delta": raw_delta,
        "worse_delta": worse_delta,
        "delta_pct": delta_pct,
        "relative_threshold_frac": threshold_frac,
        "relative_threshold_details": threshold_info,
        "exceeds_threshold": exceeded,
        "insufficient_data": False,
        "reasons": reasons,
        "checks": checks,
    }


def _statistical_check(
    gate: Gate,
    baseline_samples: List[float],
    candidate_samples: List[float],
    min_sample_size: int,
) -> Dict[str, Any]:
    alpha = gate.alpha if gate.alpha is not None else 0.05
    b_oriented = _oriented(baseline_samples, gate.direction)
    c_oriented = _oriented(candidate_samples, gate.direction)

    raw_ci = bootstrap_ci_mean_diff(baseline_samples, candidate_samples, alpha=alpha)
    oriented_ci = bootstrap_ci_mean_diff(b_oriented, c_oriented, alpha=alpha)
    effect = bootstrap_ci_cliffs_delta(b_oriented, c_oriented, alpha=alpha)

    if gate.statistical_test == "none":
        return {
            "alpha": alpha,
            "test": "none",
            "mann_whitney_u": None,
            "bootstrap_mean_diff_ci": raw_ci,
            "bootstrap_oriented_mean_diff_ci": oriented_ci,
            "effect_size": effect,
            "statistically_worse": True,
            "insufficient_data": False,
        }

    if len(b_oriented) < min_sample_size or len(c_oriented) < min_sample_size:
        return {
            "alpha": alpha,
            "test": gate.statistical_test,
            "mann_whitney_u": None,
            "bootstrap_mean_diff_ci": raw_ci,
            "bootstrap_oriented_mean_diff_ci": oriented_ci,
            "effect_size": effect,
            "statistically_worse": False,
            "insufficient_data": True,
        }

    if gate.statistical_test == "bootstrap":
        ci_low = coerce_float(oriented_ci.get("ci_low"))
        return {
            "alpha": alpha,
            "test": "bootstrap",
            "mann_whitney_u": None,
            "bootstrap_mean_diff_ci": raw_ci,
            "bootstrap_oriented_mean_diff_ci": oriented_ci,
            "effect_size": effect,
            "statistically_worse": bool(math.isfinite(ci_low) and ci_low > 0.0),
            "insufficient_data": False,
        }

    mw = mann_whitney_u_greater(c_oriented, b_oriented)
    p_value = coerce_float(mw.get("p_value"))
    return {
        "alpha": alpha,
        "test": gate.statistical_test,
        "mann_whitney_u": mw,
        "bootstrap_mean_diff_ci": raw_ci,
        "bootstrap_oriented_mean_diff_ci": oriented_ci,
        "effect_size": effect,
        "statistically_worse": bool(math.isfinite(p_value) and p_value < alpha),
        "insufficient_data": False,
    }


def compare_results_and_gate(
    baseline: Dict[str, Any],
    pr: Dict[str, Any],
    policy: Policy,
    allow_family_mismatch: bool = False,
) -> Dict[str, Any]:
    if not allow_family_mismatch:
        assert_same_family(baseline, pr)

    policy_dict = asdict(policy)
    results: Dict[str, Any] = {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "costgate_version": __version__,
        "baseline": _run_metadata(baseline),
        "candidate": _run_metadata(pr),
        "policy_used": policy_dict,
        "policy_hash": canonical_hash_json_obj(policy_dict),
        "compared_metrics": list(policy.gates),
        "metrics": {},
        "statistical_results": {},
        "per_metric_verdicts": {},
        "overall_verdict": "pass",
        "verdict": {"status": "pass", "failures": [], "warnings": [], "insufficient_data": []},
        "drivers": {},
    }

    fail_metrics: List[str] = []
    warn_metrics: List[str] = []
    insufficient_metrics: List[str] = []

    for metric, gate in policy.gates.items():
        if metric not in SUPPORTED_METRICS:
            raise CompareError(f"Unsupported metric: {metric}")

        b_samples = _metric_samples(baseline, metric)
        c_samples = _metric_samples(pr, metric)

        metric_insufficient = (
            len(b_samples) < policy.min_repeats
            or len(c_samples) < policy.min_repeats
            or len(b_samples) < policy.min_sample_size
            or len(c_samples) < policy.min_sample_size
        )

        practical = _practical_check(gate, policy, b_samples, c_samples)
        stats = _statistical_check(gate, b_samples, c_samples, policy.min_sample_size)

        non_finite_worse = bool(practical["checks"].get("non_finite_worse"))
        statistically_worse = bool(stats["statistically_worse"] or non_finite_worse)
        insufficient = bool(
            metric_insufficient
            or practical.get("insufficient_data")
            or (stats.get("insufficient_data") and not non_finite_worse)
        )

        triggered = (
            bool(practical["exceeds_threshold"])
            and statistically_worse
            and not insufficient
        )

        verdict = "pass"
        if insufficient:
            verdict = "insufficient_data"
            insufficient_metrics.append(metric)
        elif triggered:
            verdict = gate.severity
            if gate.severity == "fail":
                fail_metrics.append(metric)
            else:
                warn_metrics.append(metric)

        metric_obj = {
            "metric": metric,
            "direction": gate.direction,
            "severity": gate.severity,
            "samples": {"baseline": b_samples, "candidate": c_samples, "pr": c_samples},
            "means": {
                "baseline": practical["baseline_mean"],
                "candidate": practical["candidate_mean"],
                "pr": practical["candidate_mean"],
            },
            "delta": {
                "absolute": practical["delta"],
                "worse_delta": practical["worse_delta"],
                "pct": practical["delta_pct"],
            },
            "threshold": {
                "effective_pct": (
                    practical["relative_threshold_frac"] * 100.0
                    if practical["relative_threshold_frac"] is not None
                    else None
                ),
                "details": practical["relative_threshold_details"],
                "min_absolute_delta_usd": gate.min_absolute_delta_usd,
                "min_absolute_value": gate.min_absolute_value,
                "max_absolute_value": gate.max_absolute_value,
            },
            "practical": practical,
            "stats": stats,
            "gate": {
                "practical_exceeded": practical["exceeds_threshold"],
                "statistically_worse": statistically_worse,
                "triggered": triggered,
            },
            "verdict": verdict,
        }

        results["metrics"][metric] = metric_obj
        results["statistical_results"][metric] = stats
        results["per_metric_verdicts"][metric] = verdict

    if fail_metrics:
        overall = "fail"
    elif warn_metrics or insufficient_metrics:
        overall = "warn"
    else:
        overall = "pass"

    results["overall_verdict"] = overall
    results["verdict"] = {
        "status": overall,
        "failures": fail_metrics,
        "warnings": warn_metrics,
        "insufficient_data": insufficient_metrics,
        "regressions": fail_metrics,
    }
    results["drivers"] = _driver_hints(baseline, pr)

    return results


def _run_metadata(results: Dict[str, Any]) -> Dict[str, Any]:
    meta = results.get("meta", {})
    return {
        "schema_version": results.get("schema_version") or meta.get("schema_version"),
        "run_id": results.get("run_id") or meta.get("run_id"),
        "provider": meta.get("provider") or results.get("provider"),
        "requested_model": meta.get("requested_model") or results.get("requested_model"),
        "resolved_model": meta.get("resolved_model") or results.get("model"),
        "suite_hash": meta.get("suite_hash") or results.get("suite_hash"),
        "params_hash": meta.get("params_hash") or results.get("params_hash"),
        "rate_card_hash": meta.get("rate_card_hash") or results.get("rate_card_hash"),
        "pricing_version": meta.get("pricing_version") or results.get("pricing_version"),
        "tokenizer": meta.get("tokenizer"),
        "baseline_key": meta.get("baseline_key"),
        "timestamp": results.get("timestamp") or meta.get("timestamp") or meta.get("started_at"),
        "repeats": meta.get("repeats"),
    }


def _driver_hints(baseline: Dict[str, Any], pr: Dict[str, Any]) -> Dict[str, Any]:
    hints: List[str] = []

    def mean_metric(res: Dict[str, Any], name: str) -> float:
        return _safe_mean(_metric_samples(res, name))

    b_in = mean_metric(baseline, "mean_input_tokens")
    c_in = mean_metric(pr, "mean_input_tokens")
    b_out = mean_metric(baseline, "mean_output_tokens")
    c_out = mean_metric(pr, "mean_output_tokens")
    b_retry = mean_metric(baseline, "retry_rate")
    c_retry = mean_metric(pr, "retry_rate")
    b_p95 = mean_metric(baseline, "p95_latency_ms")
    c_p95 = mean_metric(pr, "p95_latency_ms")
    b_cost = mean_metric(baseline, "cost_per_valid_success_usd")
    c_cost = mean_metric(pr, "cost_per_valid_success_usd")
    b_task = mean_metric(baseline, "task_success_rate")
    c_task = mean_metric(pr, "task_success_rate")
    b_est = mean_metric(baseline, "estimated_token_fraction")
    c_est = mean_metric(pr, "estimated_token_fraction")

    if math.isfinite(b_cost) and (math.isinf(c_cost) or c_cost > b_cost):
        if math.isfinite(b_out) and math.isfinite(c_out) and c_out > b_out * 1.05:
            hints.append(f"Output token increase: mean_output_tokens {b_out:.1f} -> {c_out:.1f}.")
        if math.isfinite(b_in) and math.isfinite(c_in) and c_in > b_in * 1.05:
            hints.append(f"Input/context token increase: mean_input_tokens {b_in:.1f} -> {c_in:.1f}.")
        if math.isfinite(b_retry) and math.isfinite(c_retry) and c_retry > b_retry:
            hints.append(f"Retry increase: retry_rate {b_retry:.2f} -> {c_retry:.2f}.")

    if math.isfinite(b_task) and math.isfinite(c_task) and c_task < b_task:
        hints.append(f"Task success decrease: task_success_rate {b_task:.3f} -> {c_task:.3f}.")

    if math.isfinite(b_est) and math.isfinite(c_est) and c_est > b_est:
        hints.append(
            f"Estimated token fraction increase: estimated_token_fraction {b_est:.2f} -> {c_est:.2f}."
        )

    candidate_calls = pr.get("calls") or pr.get("per_call_runs") or []
    estimated_calls = [c for c in candidate_calls if c.get("token_source") == "estimated"]
    if estimated_calls:
        hints.append(
            f"Token-source warning: {len(estimated_calls)}/{len(candidate_calls)} candidate calls use estimated token counts."
        )

    if math.isfinite(b_p95) and math.isfinite(c_p95) and c_p95 > b_p95 * 1.10:
        hints.append(f"Latency noise/increase: p95_latency_ms {b_p95:.0f} -> {c_p95:.0f}.")

    b_meta = baseline.get("meta", {})
    c_meta = pr.get("meta", {})
    if b_meta.get("resolved_model") != c_meta.get("resolved_model"):
        hints.append("Model mismatch: baseline and candidate resolved models differ.")
    if b_meta.get("rate_card_hash") != c_meta.get("rate_card_hash"):
        hints.append("Rate card mismatch: baseline and candidate rate card hashes differ.")

    no_validator = [
        c.get("task_id") or c.get("test_id")
        for c in candidate_calls
        if c.get("validator_type") == "none"
    ]
    if no_validator:
        unique = sorted({str(x) for x in no_validator if x})
        hints.append(
            f"Validator warning: {len(unique)} task(s) have no expected validator; task_success defaults to api_success."
        )

    return {
        "hints": hints,
        "baseline_means": {
            "mean_input_tokens": b_in,
            "mean_output_tokens": b_out,
            "retry_rate": b_retry,
            "p95_latency_ms": b_p95,
            "cost_per_valid_success_usd": b_cost,
            "task_success_rate": b_task,
            "estimated_token_fraction": b_est,
        },
        "candidate_means": {
            "mean_input_tokens": c_in,
            "mean_output_tokens": c_out,
            "retry_rate": c_retry,
            "p95_latency_ms": c_p95,
            "cost_per_valid_success_usd": c_cost,
            "task_success_rate": c_task,
            "estimated_token_fraction": c_est,
        },
    }
