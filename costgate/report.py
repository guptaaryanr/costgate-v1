from __future__ import annotations

import math
from typing import Any, Dict, List


def _fmt(x: float, digits: int = 6) -> str:
    if x is None:
        return "—"
    try:
        xf = float(x)
    except Exception:
        return "—"
    if not math.isfinite(xf):
        if xf == float("inf"):
            return "∞"
        return "NaN"
    if abs(xf) >= 1000:
        return f"{xf:.0f}"
    if abs(xf) >= 10:
        return f"{xf:.3f}"
    return f"{xf:.{digits}g}"


def write_markdown_report(cmp: Dict[str, Any]) -> str:
    verdict = cmp["verdict"]["status"]
    regressions = cmp["verdict"].get("regressions", [])
    meta = cmp.get("meta", {})
    fam = meta.get("baseline_family", {})

    lines: List[str] = []
    if verdict == "regression":
        lines.append("## ❌ costgate: Regression detected")
        lines.append(f"**Regressed metrics:** {', '.join(regressions)}")
    else:
        lines.append("## ✅ costgate: Pass")
        lines.append("No gated regressions detected.")

    lines.append("")
    lines.append("### Baseline family")
    lines.append(f"- provider: `{fam.get('provider')}`")
    lines.append(f"- resolved_model: `{fam.get('resolved_model')}`")
    lines.append(f"- suite_hash: `{fam.get('suite_hash')}`")
    lines.append(f"- params_hash: `{fam.get('params_hash')}`")
    lines.append(f"- rate_card_hash: `{fam.get('rate_card_hash')}`")
    lines.append(f"- baseline_key: `{meta.get('baseline_key')}`")
    lines.append("")

    lines.append("### Metrics")
    lines.append(
        "| metric | baseline_mean | pr_mean | delta | delta_% | threshold_% | p_value (MWU) | mean_diff_CI | Cliff's δ CI | gate |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---|---|---|")

    for metric, obj in cmp.get("metrics", {}).items():
        b = obj["means"]["baseline"]
        p = obj["means"]["pr"]
        d = obj["delta"]["absolute"]
        dp = obj["delta"]["pct"]
        thr = obj["threshold"]["effective_pct"]
        pval = obj["stats"]["mann_whitney_u"]["p_value"]
        ci = obj["stats"]["bootstrap_mean_diff_ci"]
        cd = obj["stats"]["effect_size"]
        gate = obj["gate"]["triggered"]

        mean_ci = f"[{_fmt(ci['ci_low'])}, {_fmt(ci['ci_high'])}]"
        delta_ci = f"{_fmt(cd['delta'], 4)} [{_fmt(cd['ci_low'], 4)}, {_fmt(cd['ci_high'], 4)}]"

        lines.append(
            f"| `{metric}` | {_fmt(b)} | {_fmt(p)} | {_fmt(d)} | {_fmt(dp, 4)} | {_fmt(thr, 4)} | {_fmt(pval, 4)} | {mean_ci} | {delta_ci} | {'❌' if gate else '✅'} |"
        )

    lines.append("")
    lines.append("### Top driver hints")
    hints = (cmp.get("drivers", {}) or {}).get("hints", []) or []
    if hints:
        for h in hints:
            lines.append(f"- {h}")
    else:
        lines.append("- (no strong hints)")

    lines.append("")
    lines.append("### Gate logic (v1)")
    lines.append("- Gate triggers only if BOTH:")
    lines.append("  - practical threshold exceeded AND")
    lines.append("  - Mann–Whitney U one-sided test indicates PR is worse (p < alpha).")
    lines.append(
        "- Also reported: bootstrap CI for mean difference, Cliff’s delta effect size with CI."
    )
    lines.append("")

    return "\n".join(lines)
