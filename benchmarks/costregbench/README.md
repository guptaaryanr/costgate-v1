# CostRegBench

CostRegBench is Costgate's deterministic benchmark suite for controlled LLM inference cost-regression scenarios. It uses the `mock` provider by default, so it runs without API keys or paid calls.

Each scenario directory contains:

- `baseline_suite.yaml`
- `candidate_suite.yaml`
- `baseline_provider.yaml`
- `candidate_provider.yaml`
- `policy.yaml`
- `expected_outcome.yaml`
- `README.md`

Run all scenarios:

```bash
python benchmarks/costregbench/run.py
```

Run one smoke scenario:

```bash
python benchmarks/costregbench/run.py --scenario neutral_noop
```

Outputs are written to `.costgate/costregbench/` by default. The runner uses `allow_family_mismatch=True` because several scenarios intentionally alter suite, model, rate card, or provider behavior to simulate controlled regressions.

Important: `actual=fail` or `actual=warn` is not itself a runner failure. Those are the expected Costgate verdicts for controlled regression scenarios. The runner exits non-zero only when a scenario's actual verdict does not match `expected_outcome.yaml`.
