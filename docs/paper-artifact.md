# Paper Artifact / Reproducibility Mode

Costgate's paper-artifact path is deterministic and free by default. It uses
`MockProvider` and `ReplayProvider` so reviewers can reproduce controlled
cost-regression results without API keys or paid provider calls.

## Install

Core/mock/replay usage:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Development checks:

```bash
python -m pip install -e '.[dev]'
```

Optional OpenAI examples:

```bash
python -m pip install -e '.[openai]'
export OPENAI_API_KEY="..."
```

## Run Deterministic CostRegBench

```bash
python -m pytest
python benchmarks/costregbench/run.py --out .costgate/costregbench
```

The runner writes per-scenario artifacts plus:

- `.costgate/costregbench/summary.csv`
- `.costgate/costregbench/summary.md`

Scenarios with `actual=fail` or `actual=warn` are successful when the value
matches `expected_outcome.yaml`; those cases are controlled regressions that
Costgate is expected to catch.

## Smoke Test

```bash
python scripts/run_costregbench_smoke.py
```

## MockProvider Reproduction

MockProvider responses are configured with YAML. Example:

```yaml
default:
  output_text: "42"
  input_tokens: 10
  output_tokens: 2
  latency_ms: 20
  token_source: mock
```

Run:

```bash
python -m costgate.cli run \
  --provider mock \
  --model mock-cheap \
  --suite benchmarks/costregbench/scenarios/neutral_noop/baseline_suite.yaml \
  --rate-card benchmarks/costregbench/rate_card.yaml \
  --provider-config benchmarks/costregbench/scenarios/neutral_noop/baseline_provider.yaml \
  --repeats 5 \
  --out .costgate/paper/mock-results.json
```

## ReplayProvider Reproduction

ReplayProvider can replay a previous run artifact or fixture containing
`calls`, `per_call_runs`, `responses`, or `tasks`.

Example provider config:

```yaml
fixture_path: .costgate/paper/mock-results.json
```

Run:

```bash
python -m costgate.cli run \
  --provider replay \
  --model mock-cheap \
  --suite benchmarks/costregbench/scenarios/neutral_noop/baseline_suite.yaml \
  --rate-card benchmarks/costregbench/rate_card.yaml \
  --provider-config replay-provider.yaml \
  --repeats 5 \
  --out .costgate/paper/replay-results.json
```

## What To Archive

For a release or Zenodo artifact, archive:

- the repository source at the release tag
- `benchmarks/costregbench/`
- `paper_artifact/`
- `docs/paper-artifact.md`
- generated `summary.csv` and `summary.md`
- optional per-scenario `compare.json` and `report.md`

Do not archive local virtual environments, `.env` files, API keys, or private
generated `.costgate/` runs from sensitive suites.
