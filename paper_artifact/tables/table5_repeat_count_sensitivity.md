# Table5 Repeat Count Sensitivity

| scenario | verdict_N1 | verdict_N3 | verdict_N5 | verdict_N7 | verdict_N10 | stable | notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| agent_tool_loop_expansion | fail | fail | fail | fail | fail | true | Deterministic mock run; policy min_repeats/min_sample_size set to N. |
| context_bloat_regression | fail | fail | fail | fail | fail | true | Deterministic mock run; policy min_repeats/min_sample_size set to N. |
| cost_reduction_changes | pass | pass | pass | pass | pass | true | Deterministic mock run; policy min_repeats/min_sample_size set to N. |
| model_swap_regression | fail | fail | fail | fail | fail | true | Deterministic mock run; policy min_repeats/min_sample_size set to N. |
| neutral_noop | pass | pass | pass | pass | pass | true | Deterministic mock run; policy min_repeats/min_sample_size set to N. |
| prompt_verbosity_regression | fail | fail | fail | fail | fail | true | Deterministic mock run; policy min_repeats/min_sample_size set to N. |
| retry_expansion_regression | warn | warn | warn | warn | warn | true | Deterministic mock run; policy min_repeats/min_sample_size set to N. |
| schema_expansion_regression | fail | fail | fail | fail | fail | true | Deterministic mock run; policy min_repeats/min_sample_size set to N. |
