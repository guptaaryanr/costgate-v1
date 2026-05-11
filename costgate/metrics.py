from __future__ import annotations

import math
from typing import Any, Dict, List

import numpy as np

from costgate.jsonutil import coerce_float


REQUIRED_METRICS = {
    "total_cost_usd",
    "cost_per_api_success_usd",
    "cost_per_valid_success_usd",
    "api_success_rate",
    "task_success_rate",
    "mean_input_tokens",
    "mean_output_tokens",
    "mean_total_tokens",
    "p50_latency_ms",
    "p95_latency_ms",
    "retry_rate",
    "estimated_token_fraction",
}


def finite_mean(values: List[Any]) -> float:
    arr = np.array(
        [coerce_float(v) for v in values if math.isfinite(coerce_float(v))],
        dtype=float,
    )
    return float(np.mean(arr)) if len(arr) else float("nan")


def percentile(values: List[Any], q: float) -> float:
    arr = np.array(
        [coerce_float(v) for v in values if math.isfinite(coerce_float(v))],
        dtype=float,
    )
    if not len(arr):
        return float("nan")
    return float(np.percentile(arr, q))


def cost_sum(costs: List[Any]) -> float:
    vals = [coerce_float(v) for v in costs]
    if not vals:
        return 0.0
    if any(not math.isfinite(v) for v in vals):
        return float("nan")
    return float(np.sum(np.array(vals, dtype=float)))


def compute_aggregates(records: List[Dict[str, Any]], repeat_index: int | None = None) -> Dict[str, Any]:
    calls = len(records)
    api_successes = sum(1 for r in records if bool(r.get("api_success")))
    task_successes = sum(1 for r in records if bool(r.get("task_success")))

    total_cost = cost_sum([r.get("cost_usd") for r in records])
    if task_successes == 0:
        cost_per_valid = float("inf")
        cost_per_valid_status = "no_valid_successes"
    elif math.isfinite(total_cost):
        cost_per_valid = total_cost / task_successes
        cost_per_valid_status = "ok"
    else:
        cost_per_valid = float("nan")
        cost_per_valid_status = "missing_cost"

    if api_successes == 0:
        cost_per_api = float("inf")
        cost_per_api_status = "no_api_successes"
    elif math.isfinite(total_cost):
        cost_per_api = total_cost / api_successes
        cost_per_api_status = "ok"
    else:
        cost_per_api = float("nan")
        cost_per_api_status = "missing_cost"

    estimated = sum(1 for r in records if r.get("token_source") == "estimated")
    missing_cost = sum(1 for r in records if not math.isfinite(coerce_float(r.get("cost_usd"))))

    agg: Dict[str, Any] = {
        "calls": calls,
        "api_successes": api_successes,
        "task_successes": task_successes,
        "total_cost_usd": total_cost,
        "cost_per_api_success_usd": cost_per_api,
        "cost_per_api_success_status": cost_per_api_status,
        "cost_per_valid_success_usd": cost_per_valid,
        "cost_per_valid_success_status": cost_per_valid_status,
        "api_success_rate": api_successes / calls if calls else float("nan"),
        "task_success_rate": task_successes / calls if calls else float("nan"),
        "mean_input_tokens": finite_mean([r.get("input_tokens") for r in records]),
        "mean_output_tokens": finite_mean([r.get("output_tokens") for r in records]),
        "mean_total_tokens": finite_mean([r.get("total_tokens") for r in records]),
        "p50_latency_ms": percentile([r.get("latency_ms") for r in records], 50),
        "p95_latency_ms": percentile([r.get("latency_ms") for r in records], 95),
        "retry_rate": (
            sum(1 for r in records if int(r.get("retry_count") or 0) > 0) / calls
            if calls
            else float("nan")
        ),
        "estimated_token_fraction": estimated / calls if calls else float("nan"),
        "missing_cost_count": missing_cost,
    }
    if repeat_index is not None:
        agg["repeat_index"] = repeat_index

    # Backward-compatible alias for older policies/artifacts.
    agg["cost_per_success_usd"] = agg["cost_per_api_success_usd"]
    return agg
