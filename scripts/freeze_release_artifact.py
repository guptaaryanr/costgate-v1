from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import costgate  # noqa: E402


def _run_to_file(command: list[str], path: Path, *, check: bool = True) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            stdout=fh,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        fh.write(f"\nexit_code: {proc.returncode}\n")
    if check and proc.returncode != 0:
        raise SystemExit(f"{' '.join(command)} failed; see {path}")
    return proc.returncode


def _write_secret_scan(out_dir: Path) -> None:
    path = out_dir / "secret_scan.txt"
    if shutil.which("gitleaks"):
        _run_to_file(
            ["gitleaks", "detect", "--source", ".", "--no-git", "--redact"],
            path,
            check=True,
        )
        return

    path.write_text(
        (
            "gitleaks unavailable. Run "
            "`gitleaks detect --source . --no-git --redact` manually before final v1.0.0.\n"
            "exit_code: unavailable\n"
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze release validation and CostRegBench artifacts."
    )
    parser.add_argument(
        "--out",
        default=f"paper_artifact/results/v{costgate.__version__}",
        help="Output directory for the frozen release artifact.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove the output directory before regenerating it.",
    )
    parser.add_argument(
        "--skip-release-check",
        action="store_true",
        help="Skip capturing scripts/release_check.sh output.",
    )
    args = parser.parse_args()

    out_dir = (ROOT / args.out).resolve()
    if out_dir.exists() and args.clean:
        shutil.rmtree(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"{out_dir} is not empty; rerun with --clean to regenerate it.")
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.skip_release_check:
        _run_to_file(["bash", "scripts/release_check.sh"], out_dir / "release_check.txt")

    _write_secret_scan(out_dir)

    subprocess.run(
        [
            sys.executable,
            "benchmarks/costregbench/run.py",
            "--out",
            str(out_dir.relative_to(ROOT)),
        ],
        cwd=ROOT,
        check=True,
    )

    print(f"Frozen release artifact written to {out_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
