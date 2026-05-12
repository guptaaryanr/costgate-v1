# CostRegBench Summary

| scenario | expected | actual | status | trigger_metric | primary_metric_delta_% | retry_rate_delta_% | false_positive | false_negative |
|---|---|---|---|---|---:|---:|---|---|
| agent_tool_loop_expansion | fail | fail | ok | cost_per_valid_success_usd | 1021.95 | inf | false | false |
| context_bloat_regression | fail | fail | ok | cost_per_valid_success_usd | 1357.14 | 0 | false | false |
| cost_reduction_changes | pass | pass | ok | - | -83.33 | 0 | false | false |
| model_swap_regression | fail | fail | ok | cost_per_valid_success_usd | 500 | 0 | false | false |
| neutral_noop | pass | pass | ok | - | 0 | 0 | false | false |
| prompt_verbosity_regression | fail | fail | ok | cost_per_valid_success_usd | 400 | 0 | false | false |
| retry_expansion_regression | warn | warn | ok | retry_rate | 0 | inf | false | false |
| schema_expansion_regression | fail | fail | ok | cost_per_valid_success_usd | 413.33 | 0 | false | false |

A scenario with `actual=fail` or `actual=warn` is successful when it matches the expected controlled-regression verdict.