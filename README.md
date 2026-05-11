# Costgate

Costgate is a local/CI-first regression gate for LLM inference cost. It compares a baseline run against a candidate run, checks practical and statistical thresholds, writes versioned artifacts, and exits non-zero when a policy says the candidate regressed.

Costgate is not an observability dashboard, SaaS product, prompt optimizer, generic eval platform, or long-term metrics store. It is meant to be a small open-source tool that can run in a repository, a GitHub Action, or a paper artifact workflow.

## Why Cost Regressions Matter

LLM changes can silently increase cost through longer prompts, larger contexts, verbose outputs, retries, model swaps, schema expansion, or tool-loop growth. Unit tests may still pass, and provider API calls may still succeed. Costgate therefore separates:

- `api_success`: the provider returned without error.
- `task_success`: the model output passed the suite's expected-output validator.

The primary v1 metric is `cost_per_valid_success_usd`, meaning cost per task-valid successful answer.

## Quickstart With MockProvider

No API key or network call is required:

```bash
python -m pip install -e .

cat > /tmp/costgate-mock.yaml <<'YAML'
default:
  output_text: "2227"
  input_tokens: 20
  output_tokens: 4
  latency_ms: 25
  token_source: mock
tasks:
  extract_invoice_total:
    output_text: '{"total":"123.45"}'
    input_tokens: 24
    output_tokens: 8
  classification_1:
    output_text: "neutral"
  numeric_1:
    output_text: "2.5"
YAML

python -m costgate.cli run \
  --provider mock \
  --model mock-cheap \
  --suite costgate/suites/demo_validated_suite.yaml \
  --rate-card benchmarks/costregbench/rate_card.yaml \
  --provider-config /tmp/costgate-mock.yaml \
  --repeats 5 \
  --out .costgate/mock-baseline.json
```

## Quickstart With OpenAI

```bash
python -m pip install -e '.[openai]'
export OPENAI_API_KEY="..."

python -m costgate.cli baseline \
  --provider openai \
  --model gpt-4o-mini \
  --suite costgate/suites/demo_validated_suite.yaml \
  --rate-card costgate/rate_cards/default.yaml \
  --policy costgate/policies/default.yaml \
  --repeats 7
```

OpenAI dependencies are loaded lazily, so importing the CLI or running mock/replay tests does not require an API key.

For development:

```bash
python -m pip install -e '.[dev]'
```

For development plus optional OpenAI provider checks:

```bash
python -m pip install -e '.[dev,openai]'
```

## Quickstart With ReplayProvider

ReplayProvider reuses a prior run artifact or fixture:

```bash
python -m costgate.cli run \
  --provider replay \
  --model mock-cheap \
  --suite costgate/suites/demo_validated_suite.yaml \
  --rate-card benchmarks/costregbench/rate_card.yaml \
  --provider-config replay-provider.yaml \
  --repeats 5 \
  --out .costgate/replay-results.json
```

where `replay-provider.yaml` contains:

```yaml
fixture_path: .costgate/mock-baseline.json
```

## Baseline And Candidate Workflow

Create a baseline:

```bash
python -m costgate.cli baseline \
  --provider mock \
  --model mock-cheap \
  --suite costgate/suites/demo_validated_suite.yaml \
  --rate-card benchmarks/costregbench/rate_card.yaml \
  --provider-config /tmp/costgate-mock.yaml \
  --repeats 5
```

Run a candidate:

```bash
python -m costgate.cli run \
  --provider mock \
  --model mock-cheap \
  --suite costgate/suites/demo_validated_suite.yaml \
  --rate-card benchmarks/costregbench/rate_card.yaml \
  --provider-config /tmp/costgate-mock.yaml \
  --repeats 5 \
  --out .costgate/candidate.json
```

Compare:

```bash
python -m costgate.cli compare \
  --pr-results .costgate/candidate.json \
  --baseline-root .costgate/baselines \
  --baseline-auto \
  --policy costgate/policies/default.yaml \
  --report-out .costgate/report.md \
  --compare-out .costgate/compare.json
```

Costgate refuses baseline-family mismatches by default. The family includes suite hash, provider, resolved model, deterministic params, rate-card hash, tokenizer when available, and artifact schema compatibility.

## Suite Validators

Tests support expected validators:

- `exact`
- `contains`
- `regex`
- `json_schema`
- `numeric_tolerance`

If no `expected` validator is supplied, `task_success` defaults to `api_success` and reports include a warning because success-normalized metrics are weaker.

## Policy Format

Policies use explicit gates:

```yaml
version: 1
gates:
  cost_per_valid_success_usd:
    direction: higher_is_worse
    max_relative_increase: 0.10
    min_absolute_delta_usd: 0.00005
    statistical_test: mann_whitney
    alpha: 0.05
    severity: fail

  task_success_rate:
    direction: lower_is_worse
    min_absolute_value: 0.95
    max_relative_decrease: 0.05
    severity: fail

  p95_latency_ms:
    direction: higher_is_worse
    max_relative_increase: 0.50
    severity: warn
```

Overall verdict is `fail` if any fail-severity gate triggers, `warn` if no fail gate triggers but a warning or insufficient-data condition exists, and `pass` otherwise.

## Artifacts

Run artifacts are versioned with `schema_version: costgate.run.v1` and include:

- run/provider/model metadata
- suite, params, and rate-card hashes
- token-source summary
- call records with API success, task success, validator details, tokens, cost, latency, retries, errors, and output hashes
- per-repeat aggregates
- overall aggregates

Comparison artifacts use `schema_version: costgate.compare.v1` and include policy, statistical results, per-metric verdicts, overall verdict, and report path.

## GitHub Action Usage

This repository includes `action.yml`. A minimal usage pattern:

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
  with:
    python-version: "3.11"
- uses: ./
  with:
    provider: mock
    model: mock-cheap
    suite-path: costgate/suites/demo_validated_suite.yaml
    rate-card-path: benchmarks/costregbench/rate_card.yaml
    provider-config: path/to/mock-provider.yaml
    baseline-path: path/to/baseline.json
    output-dir: .costgate
    fail-on-regression: "true"
```

The action generates `candidate.json`, `compare.json`, and `report.md`; failing CI on regression is enough for v1.

## CostRegBench

CostRegBench lives under `benchmarks/costregbench/` and covers controlled deterministic scenarios:

- prompt verbosity regression
- context bloat regression
- schema expansion regression
- model swap regression
- retry expansion regression
- agent/tool-loop expansion
- neutral/no-op changes
- cost reduction changes

Run:

```bash
python benchmarks/costregbench/run.py
python benchmarks/costregbench/run.py --scenario neutral_noop
```

Some scenarios should report `actual=fail` or `actual=warn`; that means Costgate correctly detected the controlled regression. The benchmark runner fails only when `actual` does not match the scenario's expected outcome.

The runner writes `summary.csv` and `summary.md` to the output directory with expected vs observed verdicts, false-positive/false-negative markers, and major metric deltas.

## Paper Artifact / Reproducibility Mode

For reproducible paper artifacts, use `MockProvider` or `ReplayProvider` and commit only benchmark configs/fixtures, not generated `.costgate/` outputs. `ReplayProvider` accepts a previous fixture or run artifact containing `calls`, `per_call_runs`, `responses`, or `tasks` with output text, token counts, latency, retry count, and error state.

See `docs/paper-artifact.md` for deterministic reproduction instructions.

Recommended paper artifact command:

```bash
python -m pytest
python benchmarks/costregbench/run.py --out .costgate/costregbench
```

## Known Limitations

- Costgate is not a hosted observability platform.
- Costgate is not a semantic quality benchmark by itself; validators define task success for each suite.
- Real provider runs may still be stochastic despite deterministic request parameters.
- Latency is noisy and should usually be reported or warned, not hard-gated.
- Provider-reported token usage is preferred over local estimates; estimated token usage is marked in artifacts and reports.
- CostRegBench scenarios are controlled cost-regression tests, not broad LLM intelligence evaluations.
- Statistical tests are intentionally simple and CI-oriented.
- Cost is only as accurate as the selected rate card and provider token usage.
- OpenAI pricing in the default rate card is illustrative and should be reviewed before production use.
- Reports are Markdown artifacts, not dashboards.
- Replay artifacts may contain output text; avoid sensitive suites unless you control artifact retention.
