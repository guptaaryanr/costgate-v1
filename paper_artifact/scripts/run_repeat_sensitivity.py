from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))

from _costregbench_tables import (  # noqa: E402
    TABLES_DIR,
    policy_for_repeat_count,
    run_scenario,
    scenario_dirs,
    write_table,
)


REPEAT_COUNTS = [1, 3, 5, 7, 10]


def main() -> None:
    rows: list[dict[str, str]] = []
    for scenario_dir in scenario_dirs():
        verdicts: dict[int, str] = {}
        for repeats in REPEAT_COUNTS:
            result = run_scenario(
                scenario_dir,
                repeats=repeats,
                policy_transform=policy_for_repeat_count(repeats),
            )
            verdicts[repeats] = result["observed"]
        stable = len(set(verdicts.values())) == 1
        rows.append(
            {
                "scenario": scenario_dir.name,
                "verdict_N1": verdicts[1],
                "verdict_N3": verdicts[3],
                "verdict_N5": verdicts[5],
                "verdict_N7": verdicts[7],
                "verdict_N10": verdicts[10],
                "stable": str(stable).lower(),
                "notes": "Deterministic mock run; policy min_repeats/min_sample_size set to N.",
            }
        )

    fields = [
        "scenario",
        "verdict_N1",
        "verdict_N3",
        "verdict_N5",
        "verdict_N7",
        "verdict_N10",
        "stable",
        "notes",
    ]
    write_table(
        rows,
        fields,
        TABLES_DIR / "table5_repeat_count_sensitivity.csv",
        TABLES_DIR / "table5_repeat_count_sensitivity.md",
    )
    print(f"Wrote Table 5 to {TABLES_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
