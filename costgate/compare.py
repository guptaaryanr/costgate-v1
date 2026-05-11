from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any, Dict, List, Tuple

import numpy as np

from costgate.baselines import assert_same_family
from costgate.stats import (
    bootstrap_ci_cliffs_delta,
    bootstrap_ci_mean_diff,
    cliffs_delta,
    mann_whitney_u_greater,
)
from costgate.validation import Policy, SUPPORTED_METRICS


class CompareError(RuntimeError):
    pass


def _metric_samples(results: Dict[str, Any], metric: str) -> List[float]:
    aggs = results.get("per_repeat_aggregates", [])
    if not isinstance(aggs, list) or not aggs:
        return []
    vals = []
    for a in aggs:
        v = a.get(metric)
        try:
            vals.append(float(v))
        except Exception:
            vals.append(float("nan"))
    return vals


def _safe_mean(xs: List[float]) -> float:
    arr = np.array([float(x) for x in xs if not math.isnan(float(x))], dtype=float)
    return float(np.mean(arr)) if len(arr) else float("nan")


def _safe_std(xs: List[float]) -> float:
    arr = np.array([float(x) for x in xs if not math.isnan(float(x))], dtype=float)
    return float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0


def _is_cost_metric(metric: str) -> bool:
    return "cost" in metric


def _effective_threshold_fraction(
    policy: Policy,
    metric: str,
    baseline_samples: List[float],
) -> Tuple[float, Dict[str, Any]]:
    user_pct = float(policy.regression_threshold_pct.get(metric, 10.0))
    user_frac = user_pct / 100.0

    info: Dict[str, Any] = {"user_threshold_pct": user_pct}

    if policy.variance_aware.enabled:
        m = _safe_mean(baseline_samples)
        s = _safe_std(baseline_samples)
        if math.isfinite(m) and m != 0:
            dyn = policy.variance_aware.k * (s / abs(m))
        else:
            dyn = 0.0
        eff = max(user_frac, dyn)
        info.update(
            {
                "variance_aware_enabled": True,
                "k": policy.variance_aware.k,
                "dynamic_frac": dyn,
            }
        )
        return eff, info

    info.update({"variance_aware_enabled": False})
    return user_frac, info


def _practical_regression(
    metric: str,
    baseline_samples: List[float],
    pr_samples: List[float],
    threshold_frac: float,
    min_abs_usd: float,
) -> Dict[str, Any]:
    b_mean = _safe_mean(baseline_samples)
    p_mean = _safe_mean(pr_samples)

    delta = p_mean - b_mean
    delta_pct = (
        (delta / b_mean) * 100.0
        if (math.isfinite(b_mean) and b_mean != 0)
        else float("inf")
    )

    exceeds = False
    reasons = []

    if not (math.isfinite(b_mean) and math.isfinite(p_mean)):
        return {
            "baseline_mean": b_mean,
            "pr_mean": p_mean,
            "delta": delta,
            "delta_pct": delta_pct,
            "threshold_frac": threshold_frac,
            "exceeds_threshold": False,
            "reasons": ["non_finite_means"],
        }

    if p_mean > b_mean * (1.0 + threshold_frac):
        exceeds = True
    else:
        reasons.append("below_relative_threshold")

    if _is_cost_metric(metric):
        if abs(delta) < float(min_abs_usd):
            exceeds = False
            reasons.append("below_min_absolute_delta_usd")

    return {
        "baseline_mean": b_mean,
        "pr_mean": p_mean,
        "delta": delta,
        "delta_pct": delta_pct,
        "threshold_frac": threshold_frac,
        "exceeds_threshold": exceeds,
        "reasons": reasons,
    }


def compare_results_and_gate(
    baseline: Dict[str, Any],
    pr: Dict[str, Any],
    policy: Policy,
    allow_family_mismatch: bool = False,
) -> Dict[str, Any]:
    if not allow_family_mismatch:
        assert_same_family(baseline, pr)

    b_repeats = int(baseline.get("meta", {}).get("repeats", 0) or 0)
    p_repeats = int(pr.get("meta", {}).get("repeats", 0) or 0)
    if b_repeats < policy.min_repeats or p_repeats < policy.min_repeats:
        raise CompareError(
            f"Not enough repeats. baseline_repeats={b_repeats} pr_repeats={p_repeats} "
            f"min_repeats={policy.min_repeats}"
        )

    results: Dict[str, Any] = {
        "meta": {
            "baseline_key": baseline.get("meta", {}).get("baseline_key"),
            "baseline_path_hint": baseline.get("meta", {}).get("baseline_path"),
            "baseline_family": {
                "suite_hash": baseline.get("meta", {}).get("suite_hash"),
                "provider": baseline.get("meta", {}).get("provider"),
                "resolved_model": baseline.get("meta", {}).get("resolved_model"),
                "params_hash": baseline.get("meta", {}).get("params_hash"),
                "rate_card_hash": baseline.get("meta", {}).get("rate_card_hash"),
            },
            "policy_version": policy.version,
        },
        "metrics": {},
        "verdict": {"status": "pass", "regressions": []},
        "drivers": {},
    }

    regressions = []

    for metric in policy.metrics_to_gate:
        if metric not in SUPPORTED_METRICS:
            raise CompareError(f"Unsupported metric: {metric}")

        b_samples = _metric_samples(baseline, metric)
        p_samples = _metric_samples(pr, metric)

        if (
            len(b_samples) < policy.min_sample_size
            or len(p_samples) < policy.min_sample_size
        ):
            raise CompareError(
                f"Not enough samples for {metric}. "
                f"baseline={len(b_samples)} pr={len(p_samples)} min_sample_size={policy.min_sample_size}"
            )

        thr_frac, thr_info = _effective_threshold_fraction(policy, metric, b_samples)
        practical = _practical_regression(
            metric, b_samples, p_samples, thr_frac, policy.min_absolute_delta_usd
        )

        mw = mann_whitney_u_greater(p_samples, b_samples)
        ci = bootstrap_ci_mean_diff(b_samples, p_samples, alpha=policy.alpha)
        cd = bootstrap_ci_cliffs_delta(b_samples, p_samples, alpha=policy.alpha)

        statistically_worse = bool(mw["p_value"] < policy.alpha)

        gate_triggered = bool(practical["exceeds_threshold"] and statistically_worse)

        metric_obj = {
            "samples": {"baseline": b_samples, "pr": p_samples},
            "means": {
                "baseline": practical["baseline_mean"],
                "pr": practical["pr_mean"],
            },
            "delta": {"absolute": practical["delta"], "pct": practical["delta_pct"]},
            "threshold": {
                "effective_pct": thr_frac * 100.0,
                "details": thr_info,
                "min_absolute_delta_usd": (
                    policy.min_absolute_delta_usd if _is_cost_metric(metric) else None
                ),
            },
            "practical": practical,
            "stats": {
                "alpha": policy.alpha,
                "mann_whitney_u": mw,
                "bootstrap_mean_diff_ci": ci,
                "effect_size": cd,  # Cliff's delta + CI
            },
            "gate": {
                "practical_exceeded": practical["exceeds_threshold"],
                "statistically_worse": statistically_worse,
                "triggered": gate_triggered,
            },
        }

        results["metrics"][metric] = metric_obj

        if gate_triggered:
            regressions.append(metric)

    if regressions:
        results["verdict"]["status"] = "regression"
        results["verdict"]["regressions"] = regressions

    results["drivers"] = _driver_hints(baseline, pr, results)

    return results


def _driver_hints(
    baseline: Dict[str, Any], pr: Dict[str, Any], cmp: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Heuristic driver hints for why total cost/latency/retries got worse.
    """
    hints: List[str] = []

    def mean_metric(res: Dict[str, Any], name: str) -> float:
        return _safe_mean(_metric_samples(res, name))

    b_out = mean_metric(baseline, "mean_output_tokens")
    p_out = mean_metric(pr, "mean_output_tokens")
    b_retry = mean_metric(baseline, "retry_rate")
    p_retry = mean_metric(pr, "retry_rate")
    b_p95 = mean_metric(baseline, "p95_latency_ms")
    p_p95 = mean_metric(pr, "p95_latency_ms")
    b_cost = mean_metric(baseline, "total_cost_usd")
    p_cost = mean_metric(pr, "total_cost_usd")

    if math.isfinite(b_cost) and math.isfinite(p_cost) and p_cost > b_cost:
        if math.isfinite(b_out) and math.isfinite(p_out) and p_out > b_out * 1.05:
            hints.append(
                f"Output tokens ↑ (mean_output_tokens {b_out:.1f} → {p_out:.1f})"
            )
        if (
            math.isfinite(b_retry)
            and math.isfinite(p_retry)
            and p_retry > b_retry * 1.25
        ):
            hints.append(f"Retries ↑ (retry_rate {b_retry:.2f} → {p_retry:.2f})")

    if math.isfinite(b_p95) and math.isfinite(p_p95) and p_p95 > b_p95 * 1.10:
        hints.append(f"Latency ↑ (p95 {b_p95:.0f}ms → {p_p95:.0f}ms)")

    # Token-source quality hint
    pr_calls = pr.get("per_call_runs", []) or []
    est = sum(1 for c in pr_calls if c.get("token_source") == "estimated")
    if pr_calls and est > 0:
        hints.append(
            f"Token usage estimated for {est}/{len(pr_calls)} calls (provider did not return usage)"
        )

    return {
        "hints": hints,
        "baseline_means": {
            "mean_output_tokens": b_out,
            "retry_rate": b_retry,
            "p95_latency_ms": b_p95,
            "total_cost_usd": b_cost,
        },
        "pr_means": {
            "mean_output_tokens": p_out,
            "retry_rate": p_retry,
            "p95_latency_ms": p_p95,
            "total_cost_usd": p_cost,
        },
    }
