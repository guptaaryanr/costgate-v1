from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


class ValidationError(ValueError):
    pass


SUPPORTED_METRICS = {
    "total_cost_usd",
    "cost_per_success_usd",
    "p50_latency_ms",
    "p95_latency_ms",
    "mean_input_tokens",
    "mean_output_tokens",
    "retry_rate",
}


@dataclass(frozen=True)
class RateRule:
    model_glob: str
    input_usd_per_1k: float
    output_usd_per_1k: float


@dataclass(frozen=True)
class RateCard:
    version: int
    currency: str
    rules: List[RateRule]


@dataclass(frozen=True)
class VarianceAwareCfg:
    enabled: bool
    k: float


@dataclass(frozen=True)
class Policy:
    version: int
    metrics_to_gate: List[str]
    regression_threshold_pct: Dict[str, float]
    min_absolute_delta_usd: float
    alpha: float
    min_repeats: int
    min_sample_size: int
    variance_aware: VarianceAwareCfg


def load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except Exception as e:
        raise ValidationError(f"Failed to parse YAML: {path}: {e}") from e


def load_and_validate_rate_card(path: Path) -> RateCard:
    obj = load_yaml(path)
    if not isinstance(obj, dict):
        raise ValidationError("Rate card must be a YAML mapping.")
    version = obj.get("version")
    currency = obj.get("currency")
    rules = obj.get("rules")

    if version != 1:
        raise ValidationError("Rate card version must be 1.")
    if currency != "USD":
        raise ValidationError("Rate card currency must be USD for v1.")
    if not isinstance(rules, list) or not rules:
        raise ValidationError("Rate card must contain a non-empty rules list.")

    parsed: List[RateRule] = []
    for i, r in enumerate(rules):
        if not isinstance(r, dict):
            raise ValidationError(f"Rate rule #{i} must be a mapping.")
        mg = r.get("model_glob")
        ip = r.get("input_usd_per_1k")
        op = r.get("output_usd_per_1k")
        if not isinstance(mg, str) or not mg:
            raise ValidationError(f"Rate rule #{i} missing model_glob.")
        if not isinstance(ip, (int, float)) or ip < 0:
            raise ValidationError(f"Rate rule #{i} input_usd_per_1k must be >= 0.")
        if not isinstance(op, (int, float)) or op < 0:
            raise ValidationError(f"Rate rule #{i} output_usd_per_1k must be >= 0.")
        parsed.append(
            RateRule(
                model_glob=mg, input_usd_per_1k=float(ip), output_usd_per_1k=float(op)
            )
        )

    return RateCard(version=version, currency=currency, rules=parsed)


def match_rate_rule(card: RateCard, resolved_model: str) -> Tuple[RateRule, str] | None:
    for rule in card.rules:
        if fnmatch.fnmatch(resolved_model, rule.model_glob):
            return rule, rule.model_glob
    return None


def load_and_validate_policy(path: Path) -> Policy:
    obj = load_yaml(path)
    if not isinstance(obj, dict):
        raise ValidationError("Policy must be a YAML mapping.")
    version = obj.get("version")
    if version != 1:
        raise ValidationError("Policy version must be 1.")

    metrics = obj.get("metrics_to_gate")
    if not isinstance(metrics, list) or not metrics:
        raise ValidationError("metrics_to_gate must be a non-empty list.")
    for m in metrics:
        if m not in SUPPORTED_METRICS:
            raise ValidationError(
                f"Unsupported metric in metrics_to_gate: {m}. Supported: {sorted(SUPPORTED_METRICS)}"
            )

    thresholds = obj.get("regression_threshold_pct", {})
    if not isinstance(thresholds, dict):
        raise ValidationError("regression_threshold_pct must be a mapping.")
    parsed_thresholds: Dict[str, float] = {}
    for k, v in thresholds.items():
        if k not in SUPPORTED_METRICS:
            raise ValidationError(
                f"Unsupported metric in regression_threshold_pct: {k}"
            )
        if not isinstance(v, (int, float)) or v < 0:
            raise ValidationError(
                f"regression_threshold_pct[{k}] must be a non-negative number."
            )
        parsed_thresholds[k] = float(v)

    min_abs = obj.get("min_absolute_delta_usd", 1.0e-05)
    if not isinstance(min_abs, (int, float)) or min_abs < 0:
        raise ValidationError("min_absolute_delta_usd must be >= 0.")
    alpha = obj.get("alpha", 0.05)
    if not isinstance(alpha, (int, float)) or not (0 < alpha < 1):
        raise ValidationError("alpha must be between 0 and 1.")
    min_repeats = obj.get("min_repeats", 5)
    min_sample_size = obj.get("min_sample_size", 5)
    if not isinstance(min_repeats, int) or min_repeats <= 0:
        raise ValidationError("min_repeats must be a positive int.")
    if not isinstance(min_sample_size, int) or min_sample_size <= 0:
        raise ValidationError("min_sample_size must be a positive int.")

    var = obj.get("variance_aware", {}) or {}
    if not isinstance(var, dict):
        raise ValidationError("variance_aware must be a mapping.")
    enabled = bool(var.get("enabled", False))
    k = var.get("k", 3)
    if not isinstance(k, (int, float)) or k <= 0:
        raise ValidationError("variance_aware.k must be > 0.")

    return Policy(
        version=version,
        metrics_to_gate=list(metrics),
        regression_threshold_pct=parsed_thresholds,
        min_absolute_delta_usd=float(min_abs),
        alpha=float(alpha),
        min_repeats=min_repeats,
        min_sample_size=min_sample_size,
        variance_aware=VarianceAwareCfg(enabled=enabled, k=float(k)),
    )
