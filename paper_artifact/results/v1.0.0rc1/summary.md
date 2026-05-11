# CostRegBench Summary

| scenario | expected | actual | status | false_positive | false_negative | cost_delta_% | task_success_delta_% |
|---|---|---|---|---|---|---:|---:|
| agent_tool_loop_expansion | fail | fail | ok | false | false | 1021.95121951 | 0 |
| context_bloat_regression | fail | fail | ok | false | false | 1357.14285714 | 0 |
| cost_reduction_changes | pass | pass | ok | false | false | -83.3333333333 | 0 |
| model_swap_regression | fail | fail | ok | false | false | 500 | 0 |
| neutral_noop | pass | pass | ok | false | false | 0 | 0 |
| prompt_verbosity_regression | fail | fail | ok | false | false | 400 | 0 |
| retry_expansion_regression | warn | warn | ok | false | false | 0 | 0 |
| schema_expansion_regression | fail | fail | ok | false | false | 413.333333333 | 0 |

A scenario with `actual=fail` or `actual=warn` is successful when it matches the expected controlled-regression verdict.