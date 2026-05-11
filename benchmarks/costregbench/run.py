from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Any, Dict, List

import yaml

from costgate.compare import compare_results_and_gate
from costgate.jsonutil import dumps_json
from costgate.report import write_markdown_report
from costgate.run import run_suite
from costgate.validation import load_and_validate_policy


ROOT = Path(__file__).resolve().parent
SCENARIOS = ROOT / "scenarios"
RATE_CARD = ROOT / "rate_card.yaml"


def _load_yaml(path: Path) -> Dict[str, Any]:
    obj = yaml.safe_load(path.read_text(encoding="utf-8"))
    return obj if isinstance(obj, dict) else {}


SUMMARY_METRICS = [
    "cost_per_valid_success_usd",
    "task_success_rate",
    "mean_input_tokens",
    "mean_output_tokens",
    "retry_rate",
    "p95_latency_ms",
]


def _fmt(value: Any) -> str:
    try:
        numeric = float(value)
    except Exception:
        return ""
    if math.isnan(numeric):
        return "nan"
    if math.isinf(numeric):
        return "inf" if numeric > 0 else "-inf"
    return f"{numeric:.12g}"


def _delta_pct(baseline: Any, candidate: Any) -> str:
    try:
        b = float(baseline)
        c = float(candidate)
    except Exception:
        return ""
    if not math.isfinite(b) or not math.isfinite(c) or b == 0:
        return ""
    return _fmt(((c - b) / b) * 100.0)


def _run_scenario(scenario_dir: Path, out_root: Path) -> Dict[str, str]:
    name = scenario_dir.name
    out_dir = out_root / name
    out_dir.mkdir(parents=True, exist_ok=True)

    baseline = run_suite(
        provider="mock",
        model="mock-cheap",
        suite_path=scenario_dir / "baseline_suite.yaml",
        rate_card_path=RATE_CARD,
        repeats=5,
        provider_config=_load_yaml(scenario_dir / "baseline_provider.yaml"),
    )
    candidate = run_suite(
        provider="mock",
        model="mock-cheap",
        suite_path=scenario_dir / "candidate_suite.yaml",
        rate_card_path=RATE_CARD,
        repeats=5,
        provider_config=_load_yaml(scenario_dir / "candidate_provider.yaml"),
    )
    policy = load_and_validate_policy(scenario_dir / "policy.yaml")
    cmp = compare_results_and_gate(
        baseline=baseline,
        pr=candidate,
        policy=policy,
        allow_family_mismatch=True,
    )
    cmp["report_path"] = str(out_dir / "report.md")

    (out_dir / "baseline.json").write_text(
        dumps_json(baseline, indent=2, sort_keys=True), encoding="utf-8"
    )
    (out_dir / "candidate.json").write_text(
        dumps_json(candidate, indent=2, sort_keys=True), encoding="utf-8"
    )
    (out_dir / "compare.json").write_text(
        dumps_json(cmp, indent=2, sort_keys=True), encoding="utf-8"
    )
    (out_dir / "report.md").write_text(write_markdown_report(cmp), encoding="utf-8")

    expected = _load_yaml(scenario_dir / "expected_outcome.yaml").get("overall")
    actual = cmp["overall_verdict"]
    status = "ok" if not expected or actual == expected else "mismatch"
    outcome = {
        "scenario": name,
        "actual": actual,
        "expected": str(expected or ""),
        "status": status,
        "false_positive": str(bool(expected == "pass" and actual in {"warn", "fail"})).lower(),
        "false_negative": str(bool(expected in {"warn", "fail"} and actual == "pass")).lower(),
    }
    baseline_agg = baseline.get("overall_aggregates", {})
    candidate_agg = candidate.get("overall_aggregates", {})
    for metric in SUMMARY_METRICS:
        b = baseline_agg.get(metric)
        c = candidate_agg.get(metric)
        outcome[f"baseline_{metric}"] = _fmt(b)
        outcome[f"candidate_{metric}"] = _fmt(c)
        outcome[f"delta_pct_{metric}"] = _delta_pct(b, c)
    return outcome


def _write_summary(outcomes: List[Dict[str, str]], out_root: Path) -> None:
    out_root.mkdir(parents=True, exist_ok=True)
    if not outcomes:
        return

    fieldnames: List[str] = [
        "scenario",
        "expected",
        "actual",
        "status",
        "false_positive",
        "false_negative",
    ]
    for metric in SUMMARY_METRICS:
        fieldnames.extend(
            [
                f"baseline_{metric}",
                f"candidate_{metric}",
                f"delta_pct_{metric}",
            ]
        )

    csv_path = out_root / "summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in outcomes:
            writer.writerow({field: row.get(field, "") for field in fieldnames})

    md_path = out_root / "summary.md"
    lines = [
        "# CostRegBench Summary",
        "",
        "| scenario | expected | actual | status | false_positive | false_negative | cost_delta_% | task_success_delta_% |",
        "|---|---|---|---|---|---|---:|---:|",
    ]
    for row in outcomes:
        lines.append(
            "| {scenario} | {expected} | {actual} | {status} | {fp} | {fn} | {cost} | {task} |".format(
                scenario=row["scenario"],
                expected=row["expected"],
                actual=row["actual"],
                status=row["status"],
                fp=row["false_positive"],
                fn=row["false_negative"],
                cost=row.get("delta_pct_cost_per_valid_success_usd", ""),
                task=row.get("delta_pct_task_success_rate", ""),
            )
        )
    lines.append("")
    lines.append(
        "A scenario with `actual=fail` or `actual=warn` is successful when it matches the expected controlled-regression verdict."
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic CostRegBench scenarios.")
    parser.add_argument("--scenario", help="Scenario directory name to run")
    parser.add_argument("--out", default=".costgate/costregbench", help="Output directory")
    args = parser.parse_args()

    scenario_dirs = sorted(p for p in SCENARIOS.iterdir() if p.is_dir())
    if args.scenario:
        scenario_dirs = [SCENARIOS / args.scenario]
    if not scenario_dirs:
        raise SystemExit("No CostRegBench scenarios found.")

    out_root = Path(args.out)
    outcomes: List[Dict[str, str]] = []
    for scenario in scenario_dirs:
        outcomes.append(_run_scenario(scenario, out_root))

    _write_summary(outcomes, out_root)

    mismatches = [row for row in outcomes if row["status"] != "ok"]
    for outcome in outcomes:
        expected = outcome["expected"] or "(none)"
        print(
            f"{outcome['scenario']}: actual={outcome['actual']} expected={expected} status={outcome['status']}"
        )
    ok_count = len(outcomes) - len(mismatches)
    print(f"CostRegBench completed: {ok_count}/{len(outcomes)} scenario(s) matched expectations.")
    print(f"Wrote summary: {out_root / 'summary.csv'}")
    print(f"Wrote summary: {out_root / 'summary.md'}")
    if mismatches:
        names = ", ".join(row["scenario"] for row in mismatches)
        raise SystemExit(f"CostRegBench mismatches: {names}")


if __name__ == "__main__":
    main()
