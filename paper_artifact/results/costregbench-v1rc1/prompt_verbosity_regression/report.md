# Costgate Report

**Overall verdict:** FAIL

## Run Metadata
| field | baseline | candidate |
|---|---|---|
| provider | `mock` | `mock` |
| resolved_model | `mock-cheap` | `mock-cheap` |
| suite_hash | `31bcfeb2e40612e4434a5172a2ffc3c97cb51105d4eabb94a6b7a128cd387e06` | `0e81051df3431dd4e92cee4ce7cd9e61bb3e33945c4177e5766b15aa8e41e9fe` |
| params_hash | `34b9a03584c06a503521bca2be1ec3cad36cb4d6e0a36e5f7ae451903ee57548` | `408c96472b5e031e699f91dd94e9e5f7a180e957bc9022c1873be0d7162ca291` |
| rate_card_hash | `068a7d659bdad0b33828c14425292a3ea8c9deb642571eb383fc499f8fb324d2` | `068a7d659bdad0b33828c14425292a3ea8c9deb642571eb383fc499f8fb324d2` |
| schema_version | `costgate.run.v1` | `costgate.run.v1` |
| run_id | `run_20260511T132946Z_b85dc836fc` | `run_20260511T132946Z_f8c555d9a5` |
| timestamp | `2026-05-11T13:29:46Z` | `2026-05-11T13:29:46Z` |

## Metric Comparison
| metric | verdict | severity | direction | baseline | candidate | delta | delta_% | practical | statistical | p_value | threshold |
|---|---|---|---|---:|---:|---:|---:|---|---|---:|---|
| `cost_per_valid_success_usd` | FAIL | fail | higher_is_worse | 1.4e-05 | 7e-05 | 5.6e-05 | 400.000 | yes | yes | - | rel=10.000%, min_usd_delta=0 |

## Success Metrics
- `task_success_rate`: baseline 1, candidate 1
- `cost_per_valid_success_usd`: baseline 1.4e-05, candidate 7e-05, verdict FAIL

## Policy Violations
- FAIL: `cost_per_valid_success_usd`

## Driver Hints
- Output token increase: mean_output_tokens 2.0 -> 30.0.
- Latency noise/increase: p95_latency_ms 20 -> 24.

## Statistical Notes
- Costgate gates on practical threshold and one-sided statistical evidence.
- Metric direction controls which side is considered worse.
- Bootstrap confidence intervals and Cliff's delta are reported for context.
