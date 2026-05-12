from __future__ import annotations

import csv
import math
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from costgate.compare import compare_results_and_gate  # noqa: E402
from costgate.run import run_suite  # noqa: E402
from costgate.validation import Policy, load_and_validate_policy  # noqa: E402


BENCH_ROOT = ROOT / "benchmarks" / "costregbench"
SCENARIOS = BENCH_ROOT / "scenarios"
RATE_CARD = BENCH_ROOT / "rate_card.yaml"
TABLES_DIR = ROOT / "paper_artifact" / "tables"
FINAL_ARTIFACT_DIR = ROOT / "paper_artifact" / "results" / "v1.0.0"

REGRESSION_FAMILY = {
    "agent_tool_loop_expansion": "agent/tool-loop expansion",
    "context_bloat_regression": "context bloat",
    "cost_reduction_changes": "cost reduction",
    "model_swap_regression": "model swap",
    "neutral_noop": "neutral/no-op",
    "prompt_verbosity_regression": "prompt verbosity",
    "retry_expansion_regression": "retry expansion",
    "schema_expansion_regression": "schema expansion",
}


def load_yaml(path: Path) -> dict[str, Any]:
    obj = yaml.safe_load(path.read_text(encoding="utf-8"))
    return obj if isinstance(obj, dict) else {}


def scenario_dirs() -> list[Path]:
    return sorted(path for path in SCENARIOS.iterdir() if path.is_dir())


def scenario_note(scenario_dir: Path) -> str:
    readme = scenario_dir / "README.md"
    if not readme.exists():
        return ""
    lines = [
        line.strip()
        for line in readme.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    return " ".join(lines)


def run_scenario(
    scenario_dir: Path,
    *,
    repeats: int = 5,
    policy_transform: Callable[[Policy], Policy] | None = None,
) -> dict[str, Any]:
    baseline = run_suite(
        provider="mock",
        model="mock-cheap",
        suite_path=scenario_dir / "baseline_suite.yaml",
        rate_card_path=RATE_CARD,
        repeats=repeats,
        provider_config=load_yaml(scenario_dir / "baseline_provider.yaml"),
    )
    candidate = run_suite(
        provider="mock",
        model="mock-cheap",
        suite_path=scenario_dir / "candidate_suite.yaml",
        rate_card_path=RATE_CARD,
        repeats=repeats,
        provider_config=load_yaml(scenario_dir / "candidate_provider.yaml"),
    )
    policy = load_and_validate_policy(scenario_dir / "policy.yaml")
    if policy_transform is not None:
        policy = policy_transform(policy)
    comparison = compare_results_and_gate(
        baseline=baseline,
        pr=candidate,
        policy=policy,
        allow_family_mismatch=True,
    )
    expected = str(load_yaml(scenario_dir / "expected_outcome.yaml").get("overall") or "")
    return {
        "scenario": scenario_dir.name,
        "baseline": baseline,
        "candidate": candidate,
        "comparison": comparison,
        "expected": expected,
        "observed": comparison["overall_verdict"],
        "status": "ok" if expected == comparison["overall_verdict"] else "mismatch",
        "notes": scenario_note(scenario_dir),
    }


def trigger_metric(comparison: dict[str, Any]) -> str:
    for metric, obj in (comparison.get("metrics") or {}).items():
        if (obj.get("gate") or {}).get("triggered"):
            return str(metric)
    for metric, verdict in (comparison.get("per_metric_verdicts") or {}).items():
        if verdict != "pass":
            return str(metric)
    return ""


def delta_pct(baseline: Any, candidate: Any) -> str:
    try:
        b = float(baseline)
        c = float(candidate)
    except Exception:
        return ""
    if not math.isfinite(b) or not math.isfinite(c):
        return ""
    if b == 0:
        if c == 0:
            return "0"
        return "inf" if c > 0 else "-inf"
    return fmt_pct(((c - b) / b) * 100.0)


def fmt_pct(value: Any) -> str:
    try:
        numeric = float(value)
    except Exception:
        return ""
    if math.isnan(numeric):
        return "nan"
    if math.isinf(numeric):
        return "inf" if numeric > 0 else "-inf"
    text = f"{numeric:.2f}"
    return text.rstrip("0").rstrip(".")


def write_table(rows: list[dict[str, str]], fieldnames: list[str], csv_path: Path, md_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})

    lines = [
        f"# {md_path.stem.replace('_', ' ').title()}",
        "",
        "| " + " | ".join(fieldnames) + " |",
        "| " + " | ".join("---" for _ in fieldnames) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_md_cell(row.get(field, "")) for field in fieldnames) + " |")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def policy_with_relative_threshold(threshold_fraction: float) -> Callable[[Policy], Policy]:
    def transform(policy: Policy) -> Policy:
        gates = {}
        for metric, gate in policy.gates.items():
            changes: dict[str, float] = {}
            if gate.max_relative_increase is not None:
                changes["max_relative_increase"] = threshold_fraction
            if gate.max_relative_decrease is not None:
                changes["max_relative_decrease"] = threshold_fraction
            gates[metric] = replace(gate, **changes)
        return replace(
            policy,
            gates=gates,
            regression_threshold_pct={
                metric: threshold_fraction * 100.0 for metric in gates
            },
        )

    return transform


def policy_for_repeat_count(repeats: int) -> Callable[[Policy], Policy]:
    def transform(policy: Policy) -> Policy:
        return replace(policy, min_repeats=repeats, min_sample_size=repeats)

    return transform
