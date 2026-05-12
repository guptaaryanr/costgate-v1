# Related Work Notes

These are categories to cover during drafting. They are intentionally not
complete citations, and no citation should be invented from this file.

## Prompt / Eval Frameworks

- General-purpose LLM evaluation harnesses.
- Prompt regression tests and prompt-unit-test style tools.
- Dataset-driven answer quality evaluation.
- Human/LLM-as-judge evaluation workflows.
- Positioning note: Costgate should be described as complementary, focused on
  CI cost regression and success-normalized cost, not as a replacement for
  model-quality evaluation.

## Observability / Cost Tracking Tools

- LLM telemetry, traces, token usage dashboards, and spend monitoring.
- Production observability tools that aggregate usage over time.
- Provider dashboards and billing exports.
- Positioning note: Costgate is local/CI-first and artifact-backed; it is not a
  hosted observability dashboard or long-term spend warehouse.

## CI Cost Gates / Static Budget Tools

- CI budget checks in cloud infrastructure, dependency size, build time, test
  runtime, and static resource budgets.
- Policy-as-code gates used in pull requests.
- Positioning note: Costgate adapts the budget-gate pattern to LLM inference
  runs with baseline-relative statistical/practical comparison.

## Agent Regression Testing

- Tools that test agent trajectories, tool calls, traces, and task completion.
- Regression testing for multi-step workflows.
- Positioning note: Costgate can simulate agent/tool-loop expansion in
  CostRegBench, but it is not a universal agent behavior regression framework.

## Cost-Aware LLM Inference / Routing

- Model routing based on cost, latency, and quality.
- Cascades, fallback systems, and budget-aware serving.
- Prompt compression and context management for lower cost.
- Positioning note: Costgate detects regressions; it does not optimize prompts,
  choose routes, or manage serving policies.

## Software Artifact Reproducibility

- Reproducible benchmark artifacts.
- Versioned JSON outputs and release manifests.
- Deterministic mock/replay execution.
- DOI/Zenodo archival practices.
- Positioning note: Costgate's paper artifact should emphasize exact commands,
  release tag, and generated tables rather than broad claims.
