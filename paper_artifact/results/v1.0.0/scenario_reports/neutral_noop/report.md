# Costgate Report

**Overall verdict:** PASS

## Run Metadata
| field | baseline | candidate |
|---|---|---|
| provider | `mock` | `mock` |
| resolved_model | `mock-cheap` | `mock-cheap` |
| suite_hash | `31bcfeb2e40612e4434a5172a2ffc3c97cb51105d4eabb94a6b7a128cd387e06` | `31bcfeb2e40612e4434a5172a2ffc3c97cb51105d4eabb94a6b7a128cd387e06` |
| params_hash | `34b9a03584c06a503521bca2be1ec3cad36cb4d6e0a36e5f7ae451903ee57548` | `34b9a03584c06a503521bca2be1ec3cad36cb4d6e0a36e5f7ae451903ee57548` |
| rate_card_hash | `068a7d659bdad0b33828c14425292a3ea8c9deb642571eb383fc499f8fb324d2` | `068a7d659bdad0b33828c14425292a3ea8c9deb642571eb383fc499f8fb324d2` |
| schema_version | `costgate.run.v1` | `costgate.run.v1` |
| run_id | `run_20260512T222943Z_e0494ca8dd` | `run_20260512T222943Z_974fee47a1` |
| timestamp | `2026-05-12T22:29:43Z` | `2026-05-12T22:29:43Z` |

## Metric Comparison
| metric | verdict | severity | direction | baseline | candidate | delta | delta_% | practical | statistical | p_value | threshold |
|---|---|---|---|---:|---:|---:|---:|---|---|---:|---|
| `cost_per_valid_success_usd` | PASS | fail | higher_is_worse | 1.4e-05 | 1.4e-05 | 0 | 0 | no | yes | - | rel=10.000%, min_usd_delta=0 |
| `task_success_rate` | PASS | fail | lower_is_worse | 1 | 1 | 0 | 0 | no | yes | - | min=1 |

## Success Metrics
- `task_success_rate`: baseline 1, candidate 1, verdict PASS
- `cost_per_valid_success_usd`: baseline 1.4e-05, candidate 1.4e-05, verdict PASS

## Policy Violations
- None.

## Driver Hints
- No strong driver hints.

## Statistical Notes
- Costgate gates on practical threshold and one-sided statistical evidence.
- Metric direction controls which side is considered worse.
- Bootstrap confidence intervals and Cliff's delta are reported for context.
