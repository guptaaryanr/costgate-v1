from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from costgate.metrics import REQUIRED_METRICS


class ValidationError(ValueError):
    pass


SUPPORTED_METRICS = REQUIRED_METRICS | {"cost_per_success_usd"}
SUPPORTED_DIRECTIONS = {"higher_is_worse", "lower_is_worse"}
SUPPORTED_SEVERITIES = {"fail", "warn"}
SUPPORTED_STATISTICAL_TESTS = {"mann_whitney", "bootstrap", "none"}


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
    gates: Dict[str, "Gate"]
    metrics_to_gate: List[str]
    regression_threshold_pct: Dict[str, float]
    min_absolute_delta_usd: float
    alpha: float
    min_repeats: int
    min_sample_size: int
    variance_aware: VarianceAwareCfg


@dataclass(frozen=True)
class Gate:
    metric: str
    direction: str
    severity: str
    max_relative_increase: Optional[float] = None
    max_relative_decrease: Optional[float] = None
    min_absolute_value: Optional[float] = None
    max_absolute_value: Optional[float] = None
    min_absolute_delta_usd: Optional[float] = None
    statistical_test: str = "mann_whitney"
    alpha: Optional[float] = None


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

    gates_obj = obj.get("gates")
    metrics = obj.get("metrics_to_gate")

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

    gates: Dict[str, Gate]
    if gates_obj is not None:
        gates = _parse_gates(gates_obj, default_alpha=float(alpha), default_min_abs=float(min_abs))
        parsed_thresholds = {
            metric: float(g.max_relative_increase * 100.0)
            for metric, g in gates.items()
            if g.max_relative_increase is not None
        }
        parsed_metrics = list(gates)
    else:
        if not isinstance(metrics, list) or not metrics:
            raise ValidationError("metrics_to_gate must be a non-empty list when gates is absent.")
        for m in metrics:
            if m not in SUPPORTED_METRICS:
                raise ValidationError(
                    f"Unsupported metric in metrics_to_gate: {m}. Supported: {sorted(SUPPORTED_METRICS)}"
                )
        parsed_metrics = list(metrics)
        gates = {}
        for metric in parsed_metrics:
            threshold_pct = float(parsed_thresholds.get(metric, 10.0))
            gates[metric] = Gate(
                metric=metric,
                direction=_default_direction(metric),
                severity="fail",
                max_relative_increase=(
                    threshold_pct / 100.0 if _default_direction(metric) == "higher_is_worse" else None
                ),
                max_relative_decrease=(
                    threshold_pct / 100.0 if _default_direction(metric) == "lower_is_worse" else None
                ),
                min_absolute_delta_usd=float(min_abs) if _is_cost_metric(metric) else None,
                alpha=float(alpha),
            )

    return Policy(
        version=version,
        gates=gates,
        metrics_to_gate=parsed_metrics,
        regression_threshold_pct=parsed_thresholds,
        min_absolute_delta_usd=float(min_abs),
        alpha=float(alpha),
        min_repeats=min_repeats,
        min_sample_size=min_sample_size,
        variance_aware=VarianceAwareCfg(enabled=enabled, k=float(k)),
    )


def _parse_gates(
    gates_obj: Any, default_alpha: float, default_min_abs: float
) -> Dict[str, Gate]:
    if not isinstance(gates_obj, dict) or not gates_obj:
        raise ValidationError("gates must be a non-empty mapping.")

    gates: Dict[str, Gate] = {}
    for metric, raw in gates_obj.items():
        if metric not in SUPPORTED_METRICS:
            raise ValidationError(
                f"Unsupported metric in gates: {metric}. Supported: {sorted(SUPPORTED_METRICS)}"
            )
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            raise ValidationError(f"gates.{metric} must be a mapping.")

        direction = str(raw.get("direction", _default_direction(metric)))
        if direction not in SUPPORTED_DIRECTIONS:
            raise ValidationError(
                f"gates.{metric}.direction must be one of {sorted(SUPPORTED_DIRECTIONS)}."
            )

        severity = str(raw.get("severity", _default_severity(metric)))
        if severity not in SUPPORTED_SEVERITIES:
            raise ValidationError(
                f"gates.{metric}.severity must be one of {sorted(SUPPORTED_SEVERITIES)}."
            )

        stat = str(raw.get("statistical_test", "mann_whitney"))
        if stat not in SUPPORTED_STATISTICAL_TESTS:
            raise ValidationError(
                f"gates.{metric}.statistical_test must be one of {sorted(SUPPORTED_STATISTICAL_TESTS)}."
            )

        gate_alpha = raw.get("alpha", default_alpha)
        if not isinstance(gate_alpha, (int, float)) or not (0 < gate_alpha < 1):
            raise ValidationError(f"gates.{metric}.alpha must be between 0 and 1.")

        min_abs = raw.get("min_absolute_delta_usd")
        if min_abs is None and _is_cost_metric(metric):
            min_abs = default_min_abs
        if min_abs is not None and (not isinstance(min_abs, (int, float)) or min_abs < 0):
            raise ValidationError(f"gates.{metric}.min_absolute_delta_usd must be >= 0.")

        gates[metric] = Gate(
            metric=metric,
            direction=direction,
            severity=severity,
            max_relative_increase=_optional_nonnegative_float(raw, "max_relative_increase"),
            max_relative_decrease=_optional_nonnegative_float(raw, "max_relative_decrease"),
            min_absolute_value=_optional_float(raw, "min_absolute_value"),
            max_absolute_value=_optional_float(raw, "max_absolute_value"),
            min_absolute_delta_usd=float(min_abs) if min_abs is not None else None,
            statistical_test=stat,
            alpha=float(gate_alpha),
        )

    return gates


def _optional_float(raw: Dict[str, Any], key: str) -> Optional[float]:
    if key not in raw or raw[key] is None:
        return None
    value = raw[key]
    if not isinstance(value, (int, float)):
        raise ValidationError(f"{key} must be a number.")
    return float(value)


def _optional_nonnegative_float(raw: Dict[str, Any], key: str) -> Optional[float]:
    value = _optional_float(raw, key)
    if value is not None and value < 0:
        raise ValidationError(f"{key} must be >= 0.")
    return value


def _default_direction(metric: str) -> str:
    if metric in {"api_success_rate", "task_success_rate"}:
        return "lower_is_worse"
    return "higher_is_worse"


def _default_severity(metric: str) -> str:
    if metric in {"p50_latency_ms", "p95_latency_ms"}:
        return "warn"
    if metric in {"cost_per_valid_success_usd", "total_cost_usd", "task_success_rate"}:
        return "fail"
    return "warn"


def _is_cost_metric(metric: str) -> bool:
    return "cost" in metric
