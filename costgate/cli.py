from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from costgate.baselines import (
    BaselineFamilyMismatchError,
    build_baseline_key,
    find_latest_baseline_json,
    load_json,
    save_baseline,
)
from costgate.compare import CompareError, compare_results_and_gate
from costgate.report import write_markdown_report
from costgate.run import RunError, run_suite
from costgate.suites import load_and_validate_suite
from costgate.validation import load_and_validate_policy, load_and_validate_rate_card

app = typer.Typer(
    add_completion=False, help="costgate: CI-native cost regression gate for LLM costs"
)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


@app.command()
def validate(
    suite: Path = typer.Option(
        Path("costgate/suites/demo_suite.yaml"), help="Suite YAML path"
    ),
    rate_card: Path = typer.Option(
        Path("costgate/rate_cards/default.yaml"), help="Rate card YAML path"
    ),
    policy: Path = typer.Option(
        Path("costgate/policies/default.yaml"), help="Policy YAML path"
    ),
) -> None:
    """
    Validate suite, rate card, and policy YAML.
    """
    load_and_validate_suite(suite)
    load_and_validate_rate_card(rate_card)
    load_and_validate_policy(policy)
    typer.echo("OK: suite, rate card, and policy are valid.")


@app.command()
def run(
    provider: str = typer.Option("openai", help="Provider name (currently: openai)"),
    model: str = typer.Option("gpt-4o-mini", help="Requested model"),
    suite: Path = typer.Option(
        Path("costgate/suites/demo_suite.yaml"), help="Suite YAML path"
    ),
    rate_card: Path = typer.Option(
        Path("costgate/rate_cards/default.yaml"), help="Rate card YAML path"
    ),
    repeats: int = typer.Option(7, help="Repeat count N (default 7)"),
    max_output_tokens: int = typer.Option(
        96, help="Fixed max output tokens (deterministic harness)"
    ),
    out: Path = typer.Option(
        Path(".costgate/results.json"), help="Write results.json here"
    ),
    allow_missing_rate: bool = typer.Option(
        False, help="If set, allow missing rate card match (cost=NaN)"
    ),
    timeout_s: float = typer.Option(60.0, help="Per-request timeout seconds"),
) -> None:
    """
    Run the deterministic harness and write results.json (no comparison).
    """
    try:
        load_and_validate_suite(suite)
        load_and_validate_rate_card(rate_card)
    except Exception as e:
        raise typer.Exit(code=1) from e

    try:
        results = run_suite(
            provider=provider,
            model=model,
            suite_path=suite,
            rate_card_path=rate_card,
            repeats=repeats,
            max_output_tokens=max_output_tokens,
            allow_missing_rate=allow_missing_rate,
            timeout_s=timeout_s,
        )
        _ensure_parent(out)
        out.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
        typer.echo(f"Wrote results: {out}")
        typer.echo(f"Baseline family key: {results['meta']['baseline_key']}")
    except RunError as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(code=e.exit_code)
    except Exception as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(code=1) from e


@app.command()
def baseline(
    provider: str = typer.Option("openai", help="Provider name (currently: openai)"),
    model: str = typer.Option("gpt-4o-mini", help="Requested model"),
    suite: Path = typer.Option(
        Path("costgate/suites/demo_suite.yaml"), help="Suite YAML path"
    ),
    rate_card: Path = typer.Option(
        Path("costgate/rate_cards/default.yaml"), help="Rate card YAML path"
    ),
    repeats: int = typer.Option(7, help="Repeat count N (default 7)"),
    max_output_tokens: int = typer.Option(
        96, help="Fixed max output tokens (deterministic harness)"
    ),
    baselines_root: Path = typer.Option(
        Path(".costgate/baselines"), help="Baselines root directory"
    ),
    out: Path = typer.Option(
        Path(".costgate/results.json"), help="Write run results.json here too"
    ),
    allow_missing_rate: bool = typer.Option(
        False, help="If set, allow missing rate card match (cost=NaN)"
    ),
    timeout_s: float = typer.Option(60.0, help="Per-request timeout seconds"),
) -> None:
    """
    Run and save a baseline under .costgate/baselines/<baseline_key>/baseline.json
    """
    try:
        load_and_validate_suite(suite)
        load_and_validate_rate_card(rate_card)
    except Exception as e:
        raise typer.Exit(code=1) from e

    try:
        results = run_suite(
            provider=provider,
            model=model,
            suite_path=suite,
            rate_card_path=rate_card,
            repeats=repeats,
            max_output_tokens=max_output_tokens,
            allow_missing_rate=allow_missing_rate,
            timeout_s=timeout_s,
        )
        _ensure_parent(out)
        out.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
        baseline_path = save_baseline(results, baselines_root=baselines_root)
        latest_key_path = baselines_root.parent / "latest_baseline_key.txt"
        _ensure_parent(latest_key_path)
        latest_key_path.write_text(results["meta"]["baseline_key"], encoding="utf-8")

        typer.echo(f"Wrote results: {out}")
        typer.echo(f"Saved baseline: {baseline_path}")
        typer.echo(f"Baseline key: {results['meta']['baseline_key']}")
        typer.echo(f"Wrote latest key: {latest_key_path}")
    except RunError as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(code=e.exit_code)
    except Exception as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(code=1) from e


@app.command()
def compare(
    pr_results: Path = typer.Option(
        Path(".costgate/results.json"), help="PR results.json path"
    ),
    baseline_json: Optional[Path] = typer.Option(
        None, help="Path to baseline.json (if omitted, use --baseline-auto)"
    ),
    baseline_root: Path = typer.Option(
        Path(".costgate/baselines"), help="Root dir containing baselines"
    ),
    baseline_auto: bool = typer.Option(
        True, help="Auto-pick latest baseline under baseline_root"
    ),
    policy: Path = typer.Option(
        Path("costgate/policies/default.yaml"), help="Policy YAML path"
    ),
    report_out: Path = typer.Option(
        Path(".costgate/report.md"), help="Write Markdown report here"
    ),
    compare_out: Path = typer.Option(
        Path(".costgate/compare.json"), help="Write comparison JSON here"
    ),
    allow_family_mismatch: bool = typer.Option(
        False, help="Allow baseline family mismatch"
    ),
    exit_on_regression: bool = typer.Option(True, help="Exit code 2 on regression"),
) -> None:
    """
    Compare PR results vs baseline and (optionally) fail on regression.
    """
    try:
        policy_obj = load_and_validate_policy(policy)
    except Exception as e:
        raise typer.Exit(code=1) from e

    if baseline_json is None and baseline_auto:
        baseline_json = find_latest_baseline_json(baseline_root)
        if baseline_json is None:
            typer.echo(
                f"ERROR: No baseline found under {baseline_root}. "
                f"Run `costgate baseline ...` first or provide --baseline-json.",
                err=True,
            )
            raise typer.Exit(code=1)

    if baseline_json is None:
        typer.echo(
            "ERROR: Provide --baseline-json or enable --baseline-auto.", err=True
        )
        raise typer.Exit(code=1)

    try:
        pr = load_json(pr_results)
        base = load_json(baseline_json)

        cmp = compare_results_and_gate(
            baseline=base,
            pr=pr,
            policy=policy_obj,
            allow_family_mismatch=allow_family_mismatch,
        )

        _ensure_parent(compare_out)
        compare_out.write_text(
            json.dumps(cmp, indent=2, sort_keys=True), encoding="utf-8"
        )

        md = write_markdown_report(cmp)
        _ensure_parent(report_out)
        report_out.write_text(md, encoding="utf-8")

        verdict = cmp["verdict"]["status"]
        typer.echo(f"Verdict: {verdict}")
        typer.echo(f"Wrote compare JSON: {compare_out}")
        typer.echo(f"Wrote report: {report_out}")

        if verdict == "regression" and exit_on_regression:
            raise typer.Exit(code=2)
    except BaselineFamilyMismatchError as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(code=1)
    except CompareError as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(code=1)
    except FileNotFoundError as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(code=1) from e
