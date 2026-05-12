from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))

from _costregbench_tables import (  # noqa: E402
    TABLES_DIR,
    policy_with_relative_threshold,
    run_scenario,
    scenario_dirs,
    write_table,
)


THRESHOLDS = [5, 10, 20, 50]


def main() -> None:
    rows: list[dict[str, str]] = []
    for scenario_dir in scenario_dirs():
        verdicts: dict[int, str] = {}
        for pct in THRESHOLDS:
            result = run_scenario(
                scenario_dir,
                policy_transform=policy_with_relative_threshold(pct / 100.0),
            )
            verdicts[pct] = result["observed"]
        stable = len(set(verdicts.values())) == 1
        rows.append(
            {
                "scenario": scenario_dir.name,
                "verdict_at_5%": verdicts[5],
                "verdict_at_10%": verdicts[10],
                "verdict_at_20%": verdicts[20],
                "verdict_at_50%": verdicts[50],
                "stable": str(stable).lower(),
                "notes": (
                    "Relative gate threshold varied; min absolute and severity settings preserved."
                ),
            }
        )

    fields = [
        "scenario",
        "verdict_at_5%",
        "verdict_at_10%",
        "verdict_at_20%",
        "verdict_at_50%",
        "stable",
        "notes",
    ]
    write_table(
        rows,
        fields,
        TABLES_DIR / "table4_threshold_sensitivity.csv",
        TABLES_DIR / "table4_threshold_sensitivity.md",
    )
    print(f"Wrote Table 4 to {TABLES_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
