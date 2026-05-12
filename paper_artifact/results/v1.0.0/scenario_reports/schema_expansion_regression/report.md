# Costgate Report

**Overall verdict:** FAIL

## Run Metadata
| field | baseline | candidate |
|---|---|---|
| provider | `mock` | `mock` |
| resolved_model | `mock-cheap` | `mock-cheap` |
| suite_hash | `f6cbb083b28026a09111bfefd628674e2ed895c688c0763552309ee28683e7bd` | `bd89656c2fb78286ef8a09e46eed6476e78c2e3e79b5a2e17227833c1c0f6bff` |
| params_hash | `747662e712761314dc84568c16a7e1579157a26bd76809d29f918c4c94b366ad` | `2807c56926c7db95b5155343848e72e84a2820c4e98e143d335799e1cc1439c0` |
| rate_card_hash | `068a7d659bdad0b33828c14425292a3ea8c9deb642571eb383fc499f8fb324d2` | `068a7d659bdad0b33828c14425292a3ea8c9deb642571eb383fc499f8fb324d2` |
| schema_version | `costgate.run.v1` | `costgate.run.v1` |
| run_id | `run_20260512T222946Z_f2f11541c0` | `run_20260512T222946Z_6e2d8eab9d` |
| timestamp | `2026-05-12T22:29:46Z` | `2026-05-12T22:29:46Z` |

## Metric Comparison
| metric | verdict | severity | direction | baseline | candidate | delta | delta_% | practical | statistical | p_value | threshold |
|---|---|---|---|---:|---:|---:|---:|---|---|---:|---|
| `cost_per_valid_success_usd` | FAIL | fail | higher_is_worse | 3e-05 | 0.000154 | 0.000124 | 413.333 | yes | yes | - | rel=10.000%, min_usd_delta=0 |

## Success Metrics
- `task_success_rate`: baseline 1, candidate 1
- `cost_per_valid_success_usd`: baseline 3e-05, candidate 0.000154, verdict FAIL

## Policy Violations
- FAIL: `cost_per_valid_success_usd`

## Driver Hints
- Output token increase: mean_output_tokens 8.0 -> 70.0.
- Latency noise/increase: p95_latency_ms 20 -> 28.

## Statistical Notes
- Costgate gates on practical threshold and one-sided statistical evidence.
- Metric direction controls which side is considered worse.
- Bootstrap confidence intervals and Cliff's delta are reported for context.
