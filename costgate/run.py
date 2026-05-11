from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from costgate.baselines import (
    build_baseline_key,
    canonical_hash_yaml,
    canonical_hash_json_obj,
)
from costgate.providers.base import ProviderRequest
from costgate.providers.openai_provider import OpenAIProvider
from costgate.suites import Suite, load_and_validate_suite
from costgate.validation import (
    RateCard,
    ValidationError,
    load_and_validate_rate_card,
    match_rate_rule,
)


class RunError(RuntimeError):
    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def _git_sha() -> Optional[str]:
    # Avoid importing subprocess at module import time in case of restricted envs.
    import subprocess

    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        )
        return out.decode("utf-8").strip()
    except Exception:
        return None


def _provider_from_name(name: str):
    if name == "openai":
        return OpenAIProvider()
    raise RunError(f"Unknown provider: {name}. Supported: openai", exit_code=1)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _percentile(arr: List[float], q: float) -> float:
    if not arr:
        return float("nan")
    return float(np.percentile(np.array(arr, dtype=float), q))


def _rate_or_error(
    card: RateCard,
    resolved_model: str,
    allow_missing_rate: bool,
) -> Tuple[Optional[float], Optional[float], str]:
    match = match_rate_rule(card, resolved_model)
    if match is None:
        if allow_missing_rate:
            return None, None, "NO_MATCH"
        raise RunError(
            f"No rate card rule matches resolved_model='{resolved_model}'. "
            f"Set --allow-missing-rate to continue (cost will be NaN).",
            exit_code=1,
        )
    rule, glob = match
    return rule.input_usd_per_1k, rule.output_usd_per_1k, glob


def _compute_cost_usd(
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    in_per_1k: Optional[float],
    out_per_1k: Optional[float],
) -> float:
    if (
        input_tokens is None
        or output_tokens is None
        or in_per_1k is None
        or out_per_1k is None
    ):
        return float("nan")
    return (input_tokens / 1000.0) * in_per_1k + (output_tokens / 1000.0) * out_per_1k


def run_suite(
    provider: str,
    model: str,
    suite_path: Path,
    rate_card_path: Path,
    repeats: int = 7,
    max_output_tokens: int = 96,
    allow_missing_rate: bool = False,
    timeout_s: float = 60.0,
) -> Dict[str, Any]:
    if repeats <= 0:
        raise RunError("repeats must be > 0", exit_code=1)

    suite = load_and_validate_suite(suite_path)
    card = load_and_validate_rate_card(rate_card_path)

    suite_hash = canonical_hash_yaml(suite_path)
    rate_card_hash = canonical_hash_yaml(rate_card_path)

    params = {
        "temperature": 0.0,
        "top_p": 1.0,
        "max_output_tokens": int(max_output_tokens),
        "timeout_s": float(timeout_s),
    }
    params_hash = canonical_hash_json_obj(params)

    prov = _provider_from_name(provider)

    started_at = _now_iso()
    git_sha = _git_sha()

    per_call_runs: List[Dict[str, Any]] = []
    per_repeat_aggregates: List[Dict[str, Any]] = []

    resolved_model_final: Optional[str] = None
    rate_glob_used: Optional[str] = None
    in_per_1k_final: Optional[float] = None
    out_per_1k_final: Optional[float] = None

    for r in range(repeats):
        latencies: List[float] = []
        in_tokens: List[int] = []
        out_tokens: List[int] = []
        retry_counts: List[int] = []
        costs: List[float] = []
        successes = 0

        for t in suite.tests:
            req = ProviderRequest(
                model=model,
                messages=[
                    {"role": "system", "content": t.system},
                    {"role": "user", "content": t.user},
                ],
                temperature=0.0,
                top_p=1.0,
                max_output_tokens=max_output_tokens,
                timeout_s=timeout_s,
            )

            resp = prov.complete(req)
            resolved_model_final = resp.resolved_model

            # Resolve rate card based on resolved model (paid boundary).
            if in_per_1k_final is None and out_per_1k_final is None:
                in_per_1k_final, out_per_1k_final, rate_glob_used = _rate_or_error(
                    card, resolved_model_final, allow_missing_rate
                )

            cost = _compute_cost_usd(
                resp.input_tokens, resp.output_tokens, in_per_1k_final, out_per_1k_final
            )

            record = {
                "repeat_index": r,
                "test_id": t.id,
                "task_type": t.task_type,
                "latency_ms": resp.latency_ms,
                "retry_count": resp.retry_count,
                "input_tokens": resp.input_tokens,
                "output_tokens": resp.output_tokens,
                "total_tokens": resp.total_tokens,
                "token_source": resp.token_source,
                "cost_usd": cost,
                "success": resp.success,
                "error": resp.error,
            }
            per_call_runs.append(record)

            latencies.append(resp.latency_ms)
            retry_counts.append(resp.retry_count)
            if resp.input_tokens is not None:
                in_tokens.append(int(resp.input_tokens))
            if resp.output_tokens is not None:
                out_tokens.append(int(resp.output_tokens))
            costs.append(cost)
            if resp.success:
                successes += 1

        total_cost = float(np.nansum(np.array(costs, dtype=float)))
        cost_per_success = total_cost / successes if successes > 0 else float("inf")
        retry_rate = (
            float(np.mean(np.array(retry_counts, dtype=float))) if retry_counts else 0.0
        )

        agg = {
            "repeat_index": r,
            "total_cost_usd": total_cost,
            "cost_per_success_usd": cost_per_success,
            "p50_latency_ms": _percentile(latencies, 50),
            "p95_latency_ms": _percentile(latencies, 95),
            "mean_input_tokens": (
                float(np.mean(np.array(in_tokens, dtype=float)))
                if in_tokens
                else float("nan")
            ),
            "mean_output_tokens": (
                float(np.mean(np.array(out_tokens, dtype=float)))
                if out_tokens
                else float("nan")
            ),
            "retry_rate": retry_rate,
            "successes": successes,
            "calls": len(suite.tests),
        }
        per_repeat_aggregates.append(agg)

    ended_at = _now_iso()
    resolved_model_final = resolved_model_final or model

    baseline_key = build_baseline_key(
        suite_hash=suite_hash,
        provider=provider,
        resolved_model=resolved_model_final,
        params_hash=params_hash,
        rate_card_hash=rate_card_hash,
    )

    meta = {
        "provider": provider,
        "requested_model": model,
        "resolved_model": resolved_model_final,
        "params": params,
        "repeats": repeats,
        "suite_path": str(suite_path),
        "rate_card_path": str(rate_card_path),
        "suite_hash": suite_hash,
        "params_hash": params_hash,
        "rate_card_hash": rate_card_hash,
        "rate_rule_glob": rate_glob_used,
        "rate_input_usd_per_1k": in_per_1k_final,
        "rate_output_usd_per_1k": out_per_1k_final,
        "started_at": started_at,
        "ended_at": ended_at,
        "git_sha": git_sha,
        "baseline_key": baseline_key,
    }

    return {
        "meta": meta,
        "per_call_runs": per_call_runs,
        "per_repeat_aggregates": per_repeat_aggregates,
    }
