# Costgate Report

**Overall verdict:** FAIL

## Run Metadata
| field | baseline | candidate |
|---|---|---|
| provider | `mock` | `mock` |
| resolved_model | `mock-cheap` | `mock-cheap` |
| suite_hash | `31bcfeb2e40612e4434a5172a2ffc3c97cb51105d4eabb94a6b7a128cd387e06` | `437c15e8d255b113e8018f4a5dc8be71da12edf8a186408781274afe4983369c` |
| params_hash | `34b9a03584c06a503521bca2be1ec3cad36cb4d6e0a36e5f7ae451903ee57548` | `3c9ad27887bffd9e8de156576e425b75bfcbe85a5012bb9b3c0d0b2254c62303` |
| rate_card_hash | `068a7d659bdad0b33828c14425292a3ea8c9deb642571eb383fc499f8fb324d2` | `068a7d659bdad0b33828c14425292a3ea8c9deb642571eb383fc499f8fb324d2` |
| schema_version | `costgate.run.v1` | `costgate.run.v1` |
| run_id | `run_20260512T222941Z_5edc60025a` | `run_20260512T222941Z_3eff045710` |
| timestamp | `2026-05-12T22:29:41Z` | `2026-05-12T22:29:41Z` |

## Metric Comparison
| metric | verdict | severity | direction | baseline | candidate | delta | delta_% | practical | statistical | p_value | threshold |
|---|---|---|---|---:|---:|---:|---:|---|---|---:|---|
| `cost_per_valid_success_usd` | FAIL | fail | higher_is_worse | 1.4e-05 | 0.000204 | 0.00019 | 1357 | yes | yes | - | rel=10.000%, min_usd_delta=0 |

## Success Metrics
- `task_success_rate`: baseline 1, candidate 1
- `cost_per_valid_success_usd`: baseline 1.4e-05, candidate 0.000204, verdict FAIL

## Policy Violations
- FAIL: `cost_per_valid_success_usd`

## Driver Hints
- Input/context token increase: mean_input_tokens 10.0 -> 200.0.
- Latency noise/increase: p95_latency_ms 20 -> 26.

## Statistical Notes
- Costgate gates on practical threshold and one-sided statistical evidence.
- Metric direction controls which side is considered worse.
- Bootstrap confidence intervals and Cliff's delta are reported for context.
