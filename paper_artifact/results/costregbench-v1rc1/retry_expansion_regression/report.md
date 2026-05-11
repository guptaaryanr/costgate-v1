# Costgate Report

**Overall verdict:** WARN

## Run Metadata
| field | baseline | candidate |
|---|---|---|
| provider | `mock` | `mock` |
| resolved_model | `mock-cheap` | `mock-cheap` |
| suite_hash | `31bcfeb2e40612e4434a5172a2ffc3c97cb51105d4eabb94a6b7a128cd387e06` | `31bcfeb2e40612e4434a5172a2ffc3c97cb51105d4eabb94a6b7a128cd387e06` |
| params_hash | `a6525238610454a7a81d6147bcd8a7c7ec3f47d3543ca232613d5edd458bb56d` | `ebc3b66d64661fca8fdf8fd58ce0b573d8fcf358be84590df71202d752425492` |
| rate_card_hash | `068a7d659bdad0b33828c14425292a3ea8c9deb642571eb383fc499f8fb324d2` | `068a7d659bdad0b33828c14425292a3ea8c9deb642571eb383fc499f8fb324d2` |
| schema_version | `costgate.run.v1` | `costgate.run.v1` |
| run_id | `run_20260511T132947Z_daf99cd201` | `run_20260511T132947Z_9a1cf07adf` |
| timestamp | `2026-05-11T13:29:47Z` | `2026-05-11T13:29:47Z` |

## Metric Comparison
| metric | verdict | severity | direction | baseline | candidate | delta | delta_% | practical | statistical | p_value | threshold |
|---|---|---|---|---:|---:|---:|---:|---|---|---:|---|
| `retry_rate` | WARN | warn | higher_is_worse | 0 | 1 | 1 | inf | yes | yes | - | rel=10.000% |

## Success Metrics
- `task_success_rate`: baseline 1, candidate 1
- `cost_per_valid_success_usd`: baseline 1.4e-05, candidate 1.4e-05

## Policy Violations
- WARN: `retry_rate`

## Driver Hints
- Latency noise/increase: p95_latency_ms 20 -> 24.

## Statistical Notes
- Costgate gates on practical threshold and one-sided statistical evidence.
- Metric direction controls which side is considered worse.
- Bootstrap confidence intervals and Cliff's delta are reported for context.
