# Table4 Threshold Sensitivity

| scenario | verdict_at_5% | verdict_at_10% | verdict_at_20% | verdict_at_50% | stable | notes |
| --- | --- | --- | --- | --- | --- | --- |
| agent_tool_loop_expansion | fail | fail | fail | fail | true | Relative gate threshold varied; min absolute and severity settings preserved. |
| context_bloat_regression | fail | fail | fail | fail | true | Relative gate threshold varied; min absolute and severity settings preserved. |
| cost_reduction_changes | pass | pass | pass | pass | true | Relative gate threshold varied; min absolute and severity settings preserved. |
| model_swap_regression | fail | fail | fail | fail | true | Relative gate threshold varied; min absolute and severity settings preserved. |
| neutral_noop | pass | pass | pass | pass | true | Relative gate threshold varied; min absolute and severity settings preserved. |
| prompt_verbosity_regression | fail | fail | fail | fail | true | Relative gate threshold varied; min absolute and severity settings preserved. |
| retry_expansion_regression | warn | warn | warn | warn | true | Relative gate threshold varied; min absolute and severity settings preserved. |
| schema_expansion_regression | fail | fail | fail | fail | true | Relative gate threshold varied; min absolute and severity settings preserved. |
