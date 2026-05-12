# Costgate Paper Results Interpretation

The CostRegBench tables are controlled, deterministic evidence that Costgate can
detect configured LLM inference cost regressions in a CI-style baseline versus
candidate workflow. The scenarios isolate common regression families such as
prompt verbosity, context growth, schema expansion, model swaps, retries, and
agent/tool-loop expansion.

## What The Benchmark Supports

- Costgate computes and gates the primary metric
  `cost_per_valid_success_usd`.
- API success and task success are tracked separately through expected-output
  validators.
- Practical gates can flag large cost, token, and retry regressions relative to
  a baseline.
- Warning severity and fail severity are reflected separately in overall
  verdicts.
- Deterministic mock/replay-style execution can reproduce the same benchmark
  verdict matrix without paid provider calls.

## What The Benchmark Does Not Prove

- It is not a broad LLM capability or intelligence benchmark.
- It does not prove performance on every real provider, model, or prompt
  distribution.
- It does not remove stochasticity from paid provider runs.
- It does not validate application-specific semantic quality beyond the
  validators supplied in each suite.

## Why Mock/Replay Is Used

The paper tables need to be reproducible by reviewers without API keys, account
state, pricing drift, rate limits, model updates, or network variability.
MockProvider and ReplayProvider keep the paid-boundary accounting behavior
explicit while making the benchmark deterministic and free to rerun.

## Why Latency Is Warn/Report By Default

Latency is often noisy in CI because network, provider load, cold starts, and
runner placement can dominate the measurement. Costgate reports latency and can
warn on large shifts, but the default hard-fail path focuses on cost and task
success where deterministic benchmark evidence is cleaner.

## Why `cost_per_valid_success_usd` Is Primary

Raw spend can be misleading when task success changes. A cheaper candidate that
fails validation is not a useful cost improvement. `cost_per_valid_success_usd`
normalizes spend by task-valid outputs, tying regression detection to useful
work rather than provider API success alone.

## Limitations Of Controlled Scenarios

CostRegBench is intentionally narrow. It demonstrates that the software
correctly catches known cost-regression mechanisms under controlled conditions.
Real deployments should still define domain-specific suites, validators,
rate cards, repeat counts, and policies before using Costgate as a CI gate.
