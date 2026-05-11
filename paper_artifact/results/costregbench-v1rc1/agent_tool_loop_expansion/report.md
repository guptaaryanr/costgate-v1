# Costgate Report

**Overall verdict:** FAIL

## Run Metadata
| field | baseline | candidate |
|---|---|---|
| provider | `mock` | `mock` |
| resolved_model | `mock-cheap` | `mock-cheap` |
| suite_hash | `b7f6e6504c4732ae4f946e6ee8dffc86879fbdac0b8bb02cb6ad8567b79fa68e` | `6d1f2ab36aad08c8a45f00e453857c03c7008b1d1a6bef5b82899b7a953f7b68` |
| params_hash | `10960d7ad5705e3fc8a4b6f07180213064e56f70516b7aff136b30e2aaf95d74` | `282c8ae5b86fb21a518c78b88737ec666b430fb63e40ddbff526fd20da15fefb` |
| rate_card_hash | `068a7d659bdad0b33828c14425292a3ea8c9deb642571eb383fc499f8fb324d2` | `068a7d659bdad0b33828c14425292a3ea8c9deb642571eb383fc499f8fb324d2` |
| schema_version | `costgate.run.v1` | `costgate.run.v1` |
| run_id | `run_20260511T132944Z_5ce6fb8421` | `run_20260511T132944Z_cb18ba5b37` |
| timestamp | `2026-05-11T13:29:44Z` | `2026-05-11T13:29:44Z` |

## Metric Comparison
| metric | verdict | severity | direction | baseline | candidate | delta | delta_% | practical | statistical | p_value | threshold |
|---|---|---|---|---:|---:|---:|---:|---|---|---:|---|
| `cost_per_valid_success_usd` | FAIL | fail | higher_is_worse | 4.1e-05 | 0.00046 | 0.000419 | 1022 | yes | yes | - | rel=10.000%, min_usd_delta=0 |
| `retry_rate` | WARN | warn | higher_is_worse | 0 | 1 | 1 | inf | yes | yes | - | rel=10.000% |

## Success Metrics
- `task_success_rate`: baseline 1, candidate 1
- `cost_per_valid_success_usd`: baseline 4.1e-05, candidate 0.00046, verdict FAIL

## Policy Violations
- FAIL: `cost_per_valid_success_usd`
- WARN: `retry_rate`

## Driver Hints
- Output token increase: mean_output_tokens 8.0 -> 120.0.
- Input/context token increase: mean_input_tokens 25.0 -> 220.0.
- Retry increase: retry_rate 0.00 -> 1.00.
- Latency noise/increase: p95_latency_ms 30 -> 85.

## Statistical Notes
- Costgate gates on practical threshold and one-sided statistical evidence.
- Metric direction controls which side is considered worse.
- Bootstrap confidence intervals and Cliff's delta are reported for context.
