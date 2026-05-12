# Costgate Report

**Overall verdict:** PASS

## Run Metadata
| field | baseline | candidate |
|---|---|---|
| provider | `mock` | `mock` |
| resolved_model | `mock-cheap` | `mock-cheap` |
| suite_hash | `31bcfeb2e40612e4434a5172a2ffc3c97cb51105d4eabb94a6b7a128cd387e06` | `31bcfeb2e40612e4434a5172a2ffc3c97cb51105d4eabb94a6b7a128cd387e06` |
| params_hash | `c30099e08bfb030f3df7912e7697be7daaf74491278609e3cfdf49e783709719` | `899a7a863d5d9d1fe68ed3bcbee0c0a07cb443a935c7c4954c0f4e4240e74427` |
| rate_card_hash | `068a7d659bdad0b33828c14425292a3ea8c9deb642571eb383fc499f8fb324d2` | `068a7d659bdad0b33828c14425292a3ea8c9deb642571eb383fc499f8fb324d2` |
| schema_version | `costgate.run.v1` | `costgate.run.v1` |
| run_id | `run_20260512T125510Z_f4b2125fee` | `run_20260512T125510Z_53abcc5d3a` |
| timestamp | `2026-05-12T12:55:10Z` | `2026-05-12T12:55:10Z` |

## Metric Comparison
| metric | verdict | severity | direction | baseline | candidate | delta | delta_% | practical | statistical | p_value | threshold |
|---|---|---|---|---:|---:|---:|---:|---|---|---:|---|
| `cost_per_valid_success_usd` | PASS | fail | higher_is_worse | 0.00018 | 3e-05 | -0.00015 | -83.333 | no | yes | - | rel=10.000%, min_usd_delta=0 |

## Success Metrics
- `task_success_rate`: baseline 1, candidate 1
- `cost_per_valid_success_usd`: baseline 0.00018, candidate 3e-05, verdict PASS

## Policy Violations
- None.

## Driver Hints
- No strong driver hints.

## Statistical Notes
- Costgate gates on practical threshold and one-sided statistical evidence.
- Metric direction controls which side is considered worse.
- Bootstrap confidence intervals and Cliff's delta are reported for context.
