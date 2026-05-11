from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

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
    if expected and actual != expected:
        raise SystemExit(f"{name}: expected {expected}, got {actual}")
    return {
        "actual": actual,
        "expected": str(expected or ""),
        "status": "ok" if not expected or actual == expected else "mismatch",
    }


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
    outcomes: Dict[str, Dict[str, str]] = {}
    for scenario in scenario_dirs:
        outcomes[scenario.name] = _run_scenario(scenario, out_root)

    for name, outcome in outcomes.items():
        expected = outcome["expected"] or "(none)"
        print(
            f"{name}: actual={outcome['actual']} expected={expected} status={outcome['status']}"
        )
    print(f"CostRegBench completed: {len(outcomes)} scenario(s) matched expectations.")


if __name__ == "__main__":
    main()
