from __future__ import annotations

import subprocess
import sys


def main() -> int:
    return subprocess.call(
        [
            sys.executable,
            "benchmarks/costregbench/run.py",
            "--scenario",
            "neutral_noop",
            "--out",
            ".costgate/costregbench-smoke",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
