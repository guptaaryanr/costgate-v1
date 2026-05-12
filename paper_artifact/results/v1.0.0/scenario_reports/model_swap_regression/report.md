# Costgate Report

**Overall verdict:** FAIL

## Run Metadata
| field | baseline | candidate |
|---|---|---|
| provider | `mock` | `mock` |
| resolved_model | `mock-cheap` | `mock-expensive` |
| suite_hash | `31bcfeb2e40612e4434a5172a2ffc3c97cb51105d4eabb94a6b7a128cd387e06` | `31bcfeb2e40612e4434a5172a2ffc3c97cb51105d4eabb94a6b7a128cd387e06` |
| params_hash | `70943f95d3113fe2712caea6e756f157ec5a9a32cd5a105c1b809d6ba0da3e24` | `2e04877a13b06432d7b95d71e068c0e373ded66eaab1ff2abf54a85f4b0e76ce` |
| rate_card_hash | `068a7d659bdad0b33828c14425292a3ea8c9deb642571eb383fc499f8fb324d2` | `068a7d659bdad0b33828c14425292a3ea8c9deb642571eb383fc499f8fb324d2` |
| schema_version | `costgate.run.v1` | `costgate.run.v1` |
| run_id | `run_20260512T222942Z_479f3138fe` | `run_20260512T222942Z_579d3a43ec` |
| timestamp | `2026-05-12T22:29:42Z` | `2026-05-12T22:29:42Z` |

## Metric Comparison
| metric | verdict | severity | direction | baseline | candidate | delta | delta_% | practical | statistical | p_value | threshold |
|---|---|---|---|---:|---:|---:|---:|---|---|---:|---|
| `cost_per_valid_success_usd` | FAIL | fail | higher_is_worse | 3e-05 | 0.00018 | 0.00015 | 500.000 | yes | yes | - | rel=10.000%, min_usd_delta=0 |

## Success Metrics
- `task_success_rate`: baseline 1, candidate 1
- `cost_per_valid_success_usd`: baseline 3e-05, candidate 0.00018, verdict FAIL

## Policy Violations
- FAIL: `cost_per_valid_success_usd`

## Driver Hints
- Model mismatch: baseline and candidate resolved models differ.

## Statistical Notes
- Costgate gates on practical threshold and one-sided statistical evidence.
- Metric direction controls which side is considered worse.
- Bootstrap confidence intervals and Cliff's delta are reported for context.
