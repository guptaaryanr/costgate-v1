# Costgate Paper Outline

## 1. Introduction

- Motivation: LLM changes can silently increase inference cost in CI/CD.
- Gap: existing eval and observability workflows do not always provide a small
  baseline-relative cost-regression gate for repository workflows.
- Contribution summary: Costgate, artifacts, CostRegBench, reproducible tables.

## 2. Problem Framing

- Define LLM inference cost regression.
- Explain why API success is not enough.
- Define task success and success-normalized cost.
- Discuss CI constraints: fast, local, artifact-backed, deterministic where
  possible.

## 3. Method

- Baseline vs candidate comparison.
- Primary metric: `cost_per_valid_success_usd`.
- Supporting metrics: total cost, token means, retry rate, latency, success
  rates.
- Policy gates: direction, severity, practical thresholds, statistical checks.
- Artifact schema and baseline-family compatibility.

## 4. Implementation

- CLI workflow: validate, run, baseline, compare, report.
- Providers: OpenAI optional, MockProvider, ReplayProvider.
- Validators: exact, contains, regex, JSON schema, numeric tolerance.
- GitHub Action usage.
- Release artifact and reproducibility scripts.

## 5. CostRegBench

- Controlled deterministic scenario design.
- Regression families represented.
- Expected verdict labels and policy files.
- Why mock/replay is used for reproducibility.

## 6. Experiments

- Full CostRegBench verdict matrix.
- Metric delta table.
- Reproducibility checks.
- Threshold sensitivity.
- Repeat-count sensitivity.
- Optional real-provider smoke test, if performed, clearly separated.

## 7. Results

- Expected-vs-observed verdict outcomes.
- False positive/false negative summary for the controlled benchmark.
- Dominant trigger metrics and metric deltas.
- Stability under threshold and repeat-count sweeps.

## 8. Related Work

- Prompt/eval frameworks.
- Observability and cost tracking tools.
- CI cost gates and static budget tools.
- Agent regression testing.
- Cost-aware inference/routing.
- Software artifact reproducibility.

## 9. Limitations

- Controlled benchmark scope.
- No claim of broad model-quality evaluation.
- Provider stochasticity and pricing drift.
- Suite-validator dependence.
- Latency noise.

## 10. Conclusion

- Restate bounded contribution.
- Summarize software artifact and deterministic benchmark evidence.
- Point to future work: broader workloads, real-provider studies, richer
  statistical designs, additional providers.
