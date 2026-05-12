from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import math
import platform
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

import costgate
from costgate.compare import compare_results_and_gate
from costgate.jsonutil import dumps_json
from costgate.report import write_markdown_report
from costgate.run import run_suite
from costgate.validation import load_and_validate_policy


ROOT = Path(__file__).resolve().parent
SCENARIOS = ROOT / "scenarios"
RATE_CARD = ROOT / "rate_card.yaml"
BENCHMARK_NAME = "CostRegBench"
BENCHMARK_VERSION = "costregbench.v1"
SUMMARY_SCHEMA_VERSION = "costregbench.summary.v1"


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
    return f"{numeric:.6g}"


def _fmt_pct(value: Any) -> str:
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


def _delta_pct(baseline: Any, candidate: Any) -> str:
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
    return _fmt_pct(((c - b) / b) * 100.0)


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT.parent.parent,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def _installed_package_mode() -> str:
    try:
        dist = importlib.metadata.distribution("costgate")
        direct_url = dist.read_text("direct_url.json")
    except Exception:
        return "unknown"
    if not direct_url:
        return "installed"
    try:
        obj = json.loads(direct_url)
    except Exception:
        return "installed"
    editable = bool((obj.get("dir_info") or {}).get("editable"))
    url = obj.get("url", "")
    return f"{'editable' if editable else 'installed'} ({url})"


def _command_used() -> str:
    return "python " + " ".join(shlex.quote(arg) for arg in sys.argv)


def _run_scenario(scenario_dir: Path, out_root: Path) -> Dict[str, str]:
    name = scenario_dir.name
    report_dir = out_root / "scenario_reports" / name
    report_dir.mkdir(parents=True, exist_ok=True)

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
    cmp["report_path"] = str(report_dir / "report.md")

    (report_dir / "compare.json").write_text(
        dumps_json(cmp, indent=2, sort_keys=True), encoding="utf-8"
    )
    (report_dir / "report.md").write_text(write_markdown_report(cmp), encoding="utf-8")

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
        "trigger_metric": _trigger_metric(cmp),
    }
    baseline_agg = baseline.get("overall_aggregates", {})
    candidate_agg = candidate.get("overall_aggregates", {})
    for metric in SUMMARY_METRICS:
        b = baseline_agg.get(metric)
        c = candidate_agg.get(metric)
        outcome[f"baseline_{metric}"] = _fmt(b)
        outcome[f"candidate_{metric}"] = _fmt(c)
        outcome[f"delta_pct_{metric}"] = _delta_pct(b, c)
    outcome["primary_metric_delta_%"] = outcome.get(
        "delta_pct_cost_per_valid_success_usd", ""
    )
    outcome["retry_rate_delta_%"] = outcome.get("delta_pct_retry_rate", "")
    return outcome


def _trigger_metric(cmp: Dict[str, Any]) -> str:
    triggered = [
        metric
        for metric, obj in (cmp.get("metrics") or {}).items()
        if (obj.get("gate") or {}).get("triggered")
    ]
    if triggered:
        return triggered[0]
    verdicts = cmp.get("per_metric_verdicts") or {}
    for metric, verdict in verdicts.items():
        if verdict != "pass":
            return str(metric)
    return ""


def _write_summary(outcomes: List[Dict[str, str]], out_root: Path) -> None:
    out_root.mkdir(parents=True, exist_ok=True)
    if not outcomes:
        return

    fieldnames: List[str] = [
        "scenario",
        "expected",
        "actual",
        "status",
        "trigger_metric",
        "primary_metric_delta_%",
        "retry_rate_delta_%",
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
        "| scenario | expected | actual | status | trigger_metric | primary_metric_delta_% | retry_rate_delta_% | false_positive | false_negative |",
        "|---|---|---|---|---|---:|---:|---|---|",
    ]
    for row in outcomes:
        lines.append(
            "| {scenario} | {expected} | {actual} | {status} | {trigger} | {primary} | {retry} | {fp} | {fn} |".format(
                scenario=row["scenario"],
                expected=row["expected"],
                actual=row["actual"],
                status=row["status"],
                trigger=row["trigger_metric"] or "-",
                primary=row.get("primary_metric_delta_%", ""),
                retry=row.get("retry_rate_delta_%", ""),
                fp=row["false_positive"],
                fn=row["false_negative"],
            )
        )
    lines.append("")
    lines.append(
        "A scenario with `actual=fail` or `actual=warn` is successful when it matches the expected controlled-regression verdict."
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")


def _write_manifest(outcomes: List[Dict[str, str]], out_root: Path) -> None:
    release_tag = f"v{costgate.__version__}"
    git_commit = _git_commit()
    manifest = {
        "release_tag": release_tag,
        "git_commit": git_commit,
        "costgate_version": costgate.__version__,
        "benchmark_name": BENCHMARK_NAME,
        "benchmark_version": BENCHMARK_VERSION,
        "summary_schema_version": SUMMARY_SCHEMA_VERSION,
        "scenarios": [row["scenario"] for row in outcomes],
        "expected_verdicts": {row["scenario"]: row["expected"] for row in outcomes},
        "observed_verdicts": {row["scenario"]: row["actual"] for row in outcomes},
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "command_used": _command_used(),
        "python_version": sys.version.replace("\n", " "),
    }
    (out_root / "benchmark_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_root / "git_commit.txt").write_text(git_commit + "\n", encoding="utf-8")
    (out_root / "release_tag.txt").write_text(release_tag + "\n", encoding="utf-8")
    (out_root / "costgate_version.txt").write_text(
        costgate.__version__ + "\n", encoding="utf-8"
    )


def _write_environment(out_root: Path) -> None:
    lines = [
        f"python_version: {sys.version.replace(chr(10), ' ')}",
        f"platform: {platform.platform()}",
        f"package_version: {costgate.__version__}",
        f"installed_package_mode: {_installed_package_mode()}",
    ]
    (out_root / "environment.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_placeholders(out_root: Path) -> None:
    secret_scan = out_root / "secret_scan.txt"
    if not secret_scan.exists():
        secret_scan.write_text(
            "gitleaks was not run by the CostRegBench runner. Run `gitleaks detect --source . --no-git --redact` manually before final v1.0.0.\n",
            encoding="utf-8",
        )
    ci_status = out_root / "ci_status.txt"
    if not ci_status.exists():
        ci_status.write_text(
            "github_actions_run_url: TODO\nstatus: TODO\n",
            encoding="utf-8",
        )


def _write_readme(out_root: Path) -> None:
    release_tag = f"v{costgate.__version__}"
    lines = [
        f"# Costgate {release_tag} Frozen CostRegBench Artifact",
        "",
        "This directory contains the frozen deterministic CostRegBench outputs for the Costgate v1.0.0rc1 release candidate.",
        "",
        "## Generated By",
        "",
        "```bash",
        _command_used(),
        "```",
        "",
        "## Contents",
        "",
        "- `summary.csv` and `summary.md`: compact benchmark tables for paper use.",
        "- `benchmark_manifest.json`: release, commit, environment, command, and scenario metadata.",
        "- `scenario_reports/<scenario>/compare.json`: per-scenario comparison artifact.",
        "- `scenario_reports/<scenario>/report.md`: per-scenario Markdown report.",
        "- `release_check.txt`: captured local release validation output when available.",
        "- `secret_scan.txt`: secret-scan result or manual follow-up note.",
        "- `ci_status.txt`: GitHub Actions run URL/status placeholder to fill before final release.",
        "",
        "## Intentionally Excluded",
        "",
        "Raw baseline and candidate run artifacts are not included in this frozen directory to keep the artifact compact and avoid retaining unnecessary generated outputs. They can be regenerated deterministically with MockProvider from `benchmarks/costregbench/`.",
        "",
        "No `.costgate/` directory, virtual environment, cache directory, API key, or private provider artifact should be committed with this folder.",
    ]
    (out_root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


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
    _write_manifest(outcomes, out_root)
    _write_environment(out_root)
    _write_placeholders(out_root)
    _write_readme(out_root)

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
    print(f"Wrote manifest: {out_root / 'benchmark_manifest.json'}")
    if mismatches:
        names = ", ".join(row["scenario"] for row in mismatches)
        raise SystemExit(f"CostRegBench mismatches: {names}")


if __name__ == "__main__":
    main()
