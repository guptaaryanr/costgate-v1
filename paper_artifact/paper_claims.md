# Costgate Paper Claims

## Core Claim

Costgate is a local/CI-first framework for baseline-relative LLM inference cost
regression testing. It gates candidate runs against a baseline using
success-normalized cost, task validators, practical/statistical policy checks,
and versioned artifacts suitable for CI and reproducible paper evaluation.

## Supported Claims

- Costgate supports baseline-relative CI cost regression testing for LLM
  inference workflows.
- Costgate records `api_success` separately from `task_success`.
- Costgate uses `cost_per_valid_success_usd` as the primary cost-regression
  metric.
- Costgate supports expected-output validators so task success can be defined
  independently of provider API success.
- CostRegBench provides controlled deterministic benchmark scenarios for
  prompt verbosity, context bloat, schema expansion, model swap, retry
  expansion, agent/tool-loop expansion, neutral/no-op changes, and cost
  reduction changes.
- The generated CostRegBench tables report expected-vs-observed verdicts for
  all controlled scenarios.
- The CostRegBench verdict matrix reports no false positives or false negatives
  for the current deterministic scenario set.
- Mock/replay execution makes the required paper tables reproducible without
  paid API calls.
- Release artifacts include compact JSON/Markdown evidence files rather than
  raw local `.costgate` dumps.

## Unsupported Claims

Do not claim that Costgate is:

- the first LLM evaluation framework;
- the first CI gate for LLMs;
- the first LLM cost tracker;
- a proof of real-world production accuracy across deployments;
- a broad model-quality or model-intelligence benchmark;
- a universal agent-regression framework;
- a hosted observability system;
- a prompt optimizer or routing optimizer.

## Required Caveats

- The benchmark results are controlled scenario results, not field deployment
  results.
- CostRegBench tests cost-regression mechanisms, not broad task quality.
- Real provider runs may vary because of model, pricing, API, account, and
  network changes.
- Latency is noisy and should generally be interpreted as report/warn evidence,
  not a default hard-fail claim.
- Cost accuracy depends on provider token usage and the selected rate card.
- Task success is only as meaningful as the validators supplied by the suite
  author.

## Artifact Availability

The paper artifact includes:

- `paper_artifact/results/v1.0.0/` for compact frozen release evidence;
- `paper_artifact/tables/` for paper-ready CSV/Markdown tables;
- `paper_artifact/scripts/` for deterministic table generation;
- `benchmarks/costregbench/` for the benchmark scenarios and policies;
- `CITATION.cff` and `.zenodo.json` for citation and archival metadata.

No DOI is claimed until Zenodo archives the final GitHub release and assigns
one.

## Reproducibility Statement

The required paper tables are reproducible without paid API calls:

```bash
python scripts/freeze_release_artifact.py --clean --out paper_artifact/results/v1.0.0
python paper_artifact/scripts/generate_result_tables.py
python paper_artifact/scripts/run_threshold_sensitivity.py
python paper_artifact/scripts/run_repeat_sensitivity.py
```

These commands use deterministic mock benchmark scenarios. Optional real
provider checks, if run, must be reported separately as non-deterministic and
API-key-dependent.

## Benchmark Scope

CostRegBench is a small controlled benchmark for cost-regression behavior. Its
purpose is to test whether Costgate catches known cost-regression families under
deterministic conditions. It is not intended to rank models, estimate broad
semantic quality, or represent all production LLM workloads.

## Limitations

- Scenario coverage is intentionally focused and synthetic.
- Sensitivity tables use deterministic mock behavior; they do not estimate
  provider stochasticity.
- Policies are examples, not universal thresholds.
- The benchmark does not measure user satisfaction or downstream business
  value.
- The artifact demonstrates release behavior for Costgate v1.0.0; future
  provider pricing or model behavior may require refreshed rate cards and
  artifacts.
