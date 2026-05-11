from __future__ import annotations

import hashlib
import math
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from costgate import __version__
from costgate.artifacts import RUN_SCHEMA_VERSION
from costgate.baselines import (
    build_baseline_key,
    canonical_hash_yaml,
    canonical_hash_json_obj,
)
from costgate.metrics import compute_aggregates
from costgate.providers import available_providers, get_provider
from costgate.providers.base import ProviderRequest
from costgate.suites import load_and_validate_suite
from costgate.validation import (
    RateCard,
    load_and_validate_rate_card,
    match_rate_rule,
)
from costgate.validators import validate_output

TOKEN_ESTIMATOR = "provider_usage_or_costgate_estimator_v1"


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


def _provider_from_name(name: str, config: Optional[Dict[str, Any]] = None):
    try:
        return get_provider(name, config=config)
    except Exception as e:
        supported = ", ".join(available_providers())
        raise RunError(f"{e}. Supported providers: {supported}", exit_code=1) from e


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def _output_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _merge_provider_config(
    provider: str, suite_config: Optional[Dict[str, Any]], cli_config: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    if suite_config:
        if isinstance(suite_config.get(provider), dict):
            merged.update(suite_config[provider])
        else:
            merged.update(suite_config)
    if cli_config:
        if isinstance(cli_config.get(provider), dict):
            merged.update(cli_config[provider])
        else:
            merged.update(cli_config)
    return merged


def _token_source_summary(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    for record in records:
        source = str(record.get("token_source") or "unknown")
        counts[source] = counts.get(source, 0) + 1
    total = len(records)
    estimated = counts.get("estimated", 0)
    return {
        "counts": counts,
        "estimated": estimated,
        "total": total,
        "estimated_token_fraction": estimated / total if total else float("nan"),
    }


def run_suite(
    provider: str,
    model: str,
    suite_path: Path,
    rate_card_path: Path,
    repeats: int = 7,
    max_output_tokens: int = 96,
    allow_missing_rate: bool = False,
    timeout_s: float = 60.0,
    provider_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if repeats <= 0:
        raise RunError("repeats must be > 0", exit_code=1)

    suite = load_and_validate_suite(suite_path)
    card = load_and_validate_rate_card(rate_card_path)

    suite_hash = canonical_hash_yaml(suite_path)
    rate_card_hash = canonical_hash_yaml(rate_card_path)
    provider_config_final = _merge_provider_config(
        provider, suite.provider_config, provider_config
    )
    provider_config_hash = canonical_hash_json_obj(provider_config_final)

    params = {
        "temperature": 0.0,
        "top_p": 1.0,
        "max_output_tokens": int(max_output_tokens),
        "timeout_s": float(timeout_s),
        "provider_config_hash": provider_config_hash,
    }
    params_hash = canonical_hash_json_obj(params)

    prov = _provider_from_name(provider, config=provider_config_final)

    started_at = _now_iso()
    git_sha = _git_sha()
    run_id = f"run_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}_{uuid.uuid4().hex[:10]}"

    per_call_runs: List[Dict[str, Any]] = []
    per_repeat_aggregates: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    resolved_model_final: Optional[str] = None
    rate_glob_used: Optional[str] = None
    in_per_1k_final: Optional[float] = None
    out_per_1k_final: Optional[float] = None

    for r in range(repeats):
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
                extra={
                    "task_id": t.id,
                    "task_type": t.task_type,
                    "repeat_index": r,
                },
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
            api_success = bool(resp.success)
            validator_result = validate_output(
                output=resp.text or "",
                expected=t.expected,
                api_success=api_success,
            )
            task_success = bool(api_success and validator_result.passed)
            if validator_result.warning:
                warnings.append(
                    {
                        "type": "missing_validator",
                        "task_id": t.id,
                        "repeat": r,
                        "message": validator_result.warning,
                    }
                )

            record = {
                "task_id": t.id,
                "test_id": t.id,
                "task_type": t.task_type,
                "repeat": r,
                "repeat_index": r,
                "api_success": api_success,
                "task_success": task_success,
                "validator_type": validator_result.validator_type,
                "validator_passed": bool(validator_result.passed),
                "validator_details": validator_result.details,
                "latency_ms": resp.latency_ms,
                "retry_count": resp.retry_count,
                "input_tokens": resp.input_tokens,
                "output_tokens": resp.output_tokens,
                "total_tokens": resp.total_tokens,
                "token_source": resp.token_source,
                "cost_usd": cost,
                "cost_status": "ok" if math.isfinite(cost) else "missing_cost",
                "success": api_success,
                "error": resp.error,
                "output_hash": _output_hash(resp.text or ""),
                "output_text": resp.text or "",
            }
            per_call_runs.append(record)

        repeat_records = [record for record in per_call_runs if record["repeat_index"] == r]
        agg = compute_aggregates(repeat_records, repeat_index=r)
        per_repeat_aggregates.append(agg)

    ended_at = _now_iso()
    resolved_model_final = resolved_model_final or model

    baseline_key = build_baseline_key(
        suite_hash=suite_hash,
        provider=provider,
        resolved_model=resolved_model_final,
        params_hash=params_hash,
        rate_card_hash=rate_card_hash,
        artifact_schema=RUN_SCHEMA_VERSION,
    )

    meta = {
        "schema_version": RUN_SCHEMA_VERSION,
        "costgate_version": __version__,
        "run_id": run_id,
        "provider": provider,
        "requested_model": model,
        "resolved_model": resolved_model_final,
        "params": params,
        "provider_config_hash": provider_config_hash,
        "repeats": repeats,
        "suite_path": str(suite_path),
        "rate_card_path": str(rate_card_path),
        "suite_hash": suite_hash,
        "params_hash": params_hash,
        "rate_card_hash": rate_card_hash,
        "rate_rule_glob": rate_glob_used,
        "rate_input_usd_per_1k": in_per_1k_final,
        "rate_output_usd_per_1k": out_per_1k_final,
        "pricing_version": card.version,
        "tokenizer": TOKEN_ESTIMATOR,
        "token_estimator_version": TOKEN_ESTIMATOR,
        "started_at": started_at,
        "ended_at": ended_at,
        "timestamp": started_at,
        "git_sha": git_sha,
        "baseline_key": baseline_key,
    }

    overall_aggregates = compute_aggregates(per_call_runs)
    token_source_summary = _token_source_summary(per_call_runs)

    return {
        "schema_version": RUN_SCHEMA_VERSION,
        "costgate_version": __version__,
        "run_id": run_id,
        "timestamp": started_at,
        "provider": provider,
        "model": resolved_model_final,
        "requested_model": model,
        "suite_hash": suite_hash,
        "params_hash": params_hash,
        "rate_card_hash": rate_card_hash,
        "pricing_version": card.version,
        "tokenizer": TOKEN_ESTIMATOR,
        "token_estimator_version": TOKEN_ESTIMATOR,
        "token_source": token_source_summary,
        "meta": meta,
        "calls": per_call_runs,
        "tasks": per_call_runs,
        "per_call_runs": per_call_runs,
        "per_repeat_aggregates": per_repeat_aggregates,
        "overall_aggregates": overall_aggregates,
        "warnings": warnings,
    }
