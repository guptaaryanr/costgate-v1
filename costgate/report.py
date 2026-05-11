from __future__ import annotations

import math
from typing import Any, Dict, List


def _fmt(x: Any, digits: int = 6) -> str:
    if x is None:
        return "-"
    try:
        xf = float(x)
    except Exception:
        return str(x)
    if math.isnan(xf):
        return "NaN"
    if math.isinf(xf):
        return "inf" if xf > 0 else "-inf"
    if abs(xf) >= 1000:
        return f"{xf:.0f}"
    if abs(xf) >= 10:
        return f"{xf:.3f}"
    return f"{xf:.{digits}g}"


def write_markdown_report(cmp: Dict[str, Any]) -> str:
    verdict = str(cmp.get("overall_verdict") or cmp.get("verdict", {}).get("status", "pass"))
    baseline = cmp.get("baseline", {})
    candidate = cmp.get("candidate", {})

    lines: List[str] = []
    lines.append("# Costgate Report")
    lines.append("")
    lines.append(f"**Overall verdict:** {verdict.upper()}")
    lines.append("")

    lines.append("## Run Metadata")
    lines.append("| field | baseline | candidate |")
    lines.append("|---|---|---|")
    for field in [
        "provider",
        "resolved_model",
        "suite_hash",
        "params_hash",
        "rate_card_hash",
        "schema_version",
        "run_id",
        "timestamp",
    ]:
        lines.append(
            f"| {field} | `{baseline.get(field)}` | `{candidate.get(field)}` |"
        )

    lines.append("")
    lines.append("## Metric Comparison")
    lines.append(
        "| metric | verdict | severity | direction | baseline | candidate | delta | delta_% | practical | statistical | p_value | threshold |"
    )
    lines.append("|---|---|---|---|---:|---:|---:|---:|---|---|---:|---|")

    for metric, obj in cmp.get("metrics", {}).items():
        stats = obj.get("stats", {})
        mw = stats.get("mann_whitney_u") or {}
        threshold = obj.get("threshold", {})
        threshold_bits = []
        if threshold.get("effective_pct") is not None:
            threshold_bits.append(f"rel={_fmt(threshold.get('effective_pct'), 4)}%")
        if threshold.get("min_absolute_value") is not None:
            threshold_bits.append(f"min={_fmt(threshold.get('min_absolute_value'))}")
        if threshold.get("max_absolute_value") is not None:
            threshold_bits.append(f"max={_fmt(threshold.get('max_absolute_value'))}")
        if threshold.get("min_absolute_delta_usd") is not None:
            threshold_bits.append(f"min_usd_delta={_fmt(threshold.get('min_absolute_delta_usd'))}")

        lines.append(
            "| `{metric}` | {verdict} | {severity} | {direction} | {baseline_mean} | "
            "{candidate_mean} | {delta} | {delta_pct} | {practical} | {statistical} | "
            "{p_value} | {threshold} |".format(
                metric=metric,
                verdict=str(obj.get("verdict", "pass")).upper(),
                severity=obj.get("severity"),
                direction=obj.get("direction"),
                baseline_mean=_fmt(obj.get("means", {}).get("baseline")),
                candidate_mean=_fmt(obj.get("means", {}).get("candidate")),
                delta=_fmt(obj.get("delta", {}).get("absolute")),
                delta_pct=_fmt(obj.get("delta", {}).get("pct"), 4),
                practical="yes" if obj.get("gate", {}).get("practical_exceeded") else "no",
                statistical="yes" if obj.get("gate", {}).get("statistically_worse") else "no",
                p_value=_fmt(mw.get("p_value"), 4),
                threshold=", ".join(threshold_bits) if threshold_bits else "-",
            )
        )

    lines.append("")
    lines.append("## Success Metrics")
    _append_metric_pair(lines, cmp, "api_success_rate")
    _append_metric_pair(lines, cmp, "task_success_rate")
    _append_metric_pair(lines, cmp, "cost_per_valid_success_usd")

    lines.append("")
    lines.append("## Policy Violations")
    verdict_obj = cmp.get("verdict", {})
    failures = verdict_obj.get("failures", []) or []
    warnings = verdict_obj.get("warnings", []) or []
    insufficient = verdict_obj.get("insufficient_data", []) or []
    if not failures and not warnings and not insufficient:
        lines.append("- None.")
    for metric in failures:
        lines.append(f"- FAIL: `{metric}`")
    for metric in warnings:
        lines.append(f"- WARN: `{metric}`")
    for metric in insufficient:
        lines.append(f"- INSUFFICIENT_DATA: `{metric}`")

    lines.append("")
    lines.append("## Driver Hints")
    hints = (cmp.get("drivers", {}) or {}).get("hints", []) or []
    if hints:
        for hint in hints:
            lines.append(f"- {hint}")
    else:
        lines.append("- No strong driver hints.")

    lines.append("")
    lines.append("## Statistical Notes")
    lines.append("- Costgate gates on practical threshold and one-sided statistical evidence.")
    lines.append("- Metric direction controls which side is considered worse.")
    lines.append("- Bootstrap confidence intervals and Cliff's delta are reported for context.")
    lines.append("")

    return "\n".join(lines)


def _append_metric_pair(lines: List[str], cmp: Dict[str, Any], metric: str) -> None:
    obj = cmp.get("metrics", {}).get(metric)
    if not obj:
        means = cmp.get("drivers", {})
        b = (means.get("baseline_means", {}) or {}).get(metric)
        c = (means.get("candidate_means", {}) or {}).get(metric)
        if b is None and c is None:
            return
        lines.append(f"- `{metric}`: baseline {_fmt(b)}, candidate {_fmt(c)}")
        return
    lines.append(
        f"- `{metric}`: baseline {_fmt(obj.get('means', {}).get('baseline'))}, "
        f"candidate {_fmt(obj.get('means', {}).get('candidate'))}, "
        f"verdict {str(obj.get('verdict')).upper()}"
    )
