from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))

import costgate  # noqa: E402
from _costregbench_tables import (  # noqa: E402
    FINAL_ARTIFACT_DIR,
    REGRESSION_FAMILY,
    TABLES_DIR,
    delta_pct,
    run_scenario,
    scenario_dirs,
    trigger_metric,
    write_table,
)


def table1() -> None:
    rows: list[dict[str, str]] = []
    for scenario_dir in scenario_dirs():
        result = run_scenario(scenario_dir)
        expected = result["expected"]
        observed = result["observed"]
        rows.append(
            {
                "scenario": result["scenario"],
                "regression_family": REGRESSION_FAMILY.get(result["scenario"], result["scenario"]),
                "expected_verdict": expected,
                "observed_verdict": observed,
                "status": result["status"],
                "false_positive": str(expected == "pass" and observed in {"warn", "fail"}).lower(),
                "false_negative": str(expected in {"warn", "fail"} and observed == "pass").lower(),
                "trigger_metric": trigger_metric(result["comparison"]),
                "notes": result["notes"],
            }
        )
    fields = [
        "scenario",
        "regression_family",
        "expected_verdict",
        "observed_verdict",
        "status",
        "false_positive",
        "false_negative",
        "trigger_metric",
        "notes",
    ]
    write_table(
        rows,
        fields,
        TABLES_DIR / "table1_scenario_verdict_matrix.csv",
        TABLES_DIR / "table1_scenario_verdict_matrix.md",
    )


def table2() -> None:
    rows: list[dict[str, str]] = []
    metric_map = {
        "cost_per_valid_success_delta_%": "cost_per_valid_success_usd",
        "total_cost_delta_%": "total_cost_usd",
        "input_tokens_delta_%": "mean_input_tokens",
        "output_tokens_delta_%": "mean_output_tokens",
        "total_tokens_delta_%": "mean_total_tokens",
        "retry_rate_delta_%": "retry_rate",
        "task_success_delta_%": "task_success_rate",
        "latency_p95_delta_%": "p95_latency_ms",
    }
    for scenario_dir in scenario_dirs():
        result = run_scenario(scenario_dir)
        baseline = result["baseline"]["overall_aggregates"]
        candidate = result["candidate"]["overall_aggregates"]
        row = {"scenario": result["scenario"]}
        for column, metric in metric_map.items():
            row[column] = delta_pct(baseline.get(metric), candidate.get(metric))
        row["primary_trigger_metric"] = trigger_metric(result["comparison"])
        rows.append(row)

    fields = ["scenario", *metric_map.keys(), "primary_trigger_metric"]
    write_table(
        rows,
        fields,
        TABLES_DIR / "table2_metric_deltas.csv",
        TABLES_DIR / "table2_metric_deltas.md",
    )


def table3() -> None:
    release_check = FINAL_ARTIFACT_DIR / "release_check.txt"
    manifest = FINAL_ARTIFACT_DIR / "benchmark_manifest.json"
    secret_scan = FINAL_ARTIFACT_DIR / "secret_scan.txt"
    citation = ROOT / "CITATION.cff"
    zenodo = ROOT / ".zenodo.json"
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    cff = yaml.safe_load(citation.read_text(encoding="utf-8")) if citation.exists() else {}

    release_text = release_check.read_text(encoding="utf-8") if release_check.exists() else ""
    secret_text = secret_scan.read_text(encoding="utf-8") if secret_scan.exists() else ""
    manifest_obj = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}

    rows = [
        {
            "check": "pytest",
            "result": "pass" if "45 passed" in release_text else "not_recorded",
            "evidence_file_or_command": "paper_artifact/results/v1.0.0/release_check.txt",
            "notes": "release_check.sh records the pytest run.",
        },
        {
            "check": "release_check.sh",
            "result": "pass" if "[release-check] complete" in release_text else "not_recorded",
            "evidence_file_or_command": "bash scripts/release_check.sh",
            "notes": "Includes CLI help, mock run/compare, CostRegBench smoke, Ruff, actionlint, and gitleaks when available.",
        },
        {
            "check": "GitHub Actions",
            "result": "manual_pending",
            "evidence_file_or_command": "GitHub Actions run URL for the release commit",
            "notes": "Must be verified in GitHub before tagging or immediately before release publication.",
        },
        {
            "check": "CostRegBench full run",
            "result": (
                "pass"
                if manifest_obj.get("observed_verdicts") == manifest_obj.get("expected_verdicts")
                else "not_recorded"
            ),
            "evidence_file_or_command": "paper_artifact/results/v1.0.0/benchmark_manifest.json",
            "notes": "All deterministic scenarios should match expected controlled-regression verdicts.",
        },
        {
            "check": "secret scan",
            "result": "pass" if "no leaks found" in secret_text.lower() else "not_recorded",
            "evidence_file_or_command": "paper_artifact/results/v1.0.0/secret_scan.txt",
            "notes": "Generated by gitleaks when available.",
        },
        {
            "check": "version match",
            "result": (
                "pass"
                if pyproject["project"]["version"] == costgate.__version__ == cff.get("version")
                else "fail"
            ),
            "evidence_file_or_command": "pyproject.toml, costgate/__init__.py, CITATION.cff",
            "notes": f"Detected package version {costgate.__version__}.",
        },
        {
            "check": "citation metadata present",
            "result": "pass" if citation.exists() and zenodo.exists() else "fail",
            "evidence_file_or_command": "CITATION.cff, .zenodo.json",
            "notes": "DOI is intentionally not pre-filled before Zenodo archival.",
        },
        {
            "check": "frozen artifact present",
            "result": "pass" if manifest.exists() and (FINAL_ARTIFACT_DIR / "summary.csv").exists() else "not_recorded",
            "evidence_file_or_command": "paper_artifact/results/v1.0.0/",
            "notes": "Compact frozen artifact only; raw .costgate dumps are excluded.",
        },
    ]
    fields = ["check", "result", "evidence_file_or_command", "notes"]
    write_table(
        rows,
        fields,
        TABLES_DIR / "table3_reproducibility_checks.csv",
        TABLES_DIR / "table3_reproducibility_checks.md",
    )


def main() -> None:
    table1()
    table2()
    table3()
    print(f"Wrote Tables 1-3 to {TABLES_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
