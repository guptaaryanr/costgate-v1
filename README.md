# costgate

A CI-native cost regression gate for LLM inference and related runtime costs.

Costgate runs a deterministic synthetic harness (no proprietary data), repeats runs to form distributions (default N=7), computes cost/unit metrics using a YAML rate card, compares PR vs baseline using **practical thresholds + statistical significance**, and fails CI on regressions.

## Quickstart (local)

### 1) Install
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

### 2) Set OPENAI_API_KEY
```bash
export OPENAI_API_KEY="YOUR_KEY"
```

### 3) Run a baseline (saved under .costgate/baselines/<baseline_key>/baseline.json)
```bash
costgate baseline \
  --provider openai \
  --model gpt-4o-mini \
  --suite costgate/suites/demo_suite.yaml \
  --rate-card costgate/rate_cards/default.yaml \
  --repeats 7 \
  --max-output-tokens 96 \
  --out .costgate/results.json \
  --baselines-root .costgate/baselines
```

### 4) Run again with no changes (should PASS)
```bash
costgate run \
  --provider openai \
  --model gpt-4o-mini \
  --suite costgate/suites/demo_suite.yaml \
  --rate-card costgate/rate_cards/default.yaml \
  --repeats 7 \
  --max-output-tokens 96 \
  --out .costgate/pr_results.json

costgate compare \
  --pr-results .costgate/pr_results.json \
  --baseline-root .costgate/baselines \
  --baseline-auto \
  --policy costgate/policies/default.yaml \
  --report-out .costgate/report.md \
  --compare-out .costgate/compare.json \
  --exit-on-regression
```

Open the report:
```bash
cat .costgate/report.md
```

## Baseline workflow (how it's namespaced)
Baselines are stored by family key:
```scss
(suite_hash, provider, resolved_model, params_hash, rate_card_hash)
```

The baseline key is materialized as a directory:
```bash
.costgate/baselines/<baseline_key>/baseline.json
```

Costgate refuses to compare if the baseline family mismatches (model, suite, params, or rate-card changed), unless you pass `--allow-family-mismatch`.

## PR workflow
In IC:
- On `push` to `main`: run baseline and upload it as a GitHub Actions artifact (`costgate-baseline`).
- On `pull_request`: download the latest baseline artifact from `main`, run the suite, compare, upload `report.md`, and fail the job on regressions.

Locally you can mimic CI with:
```bash
chmod +x scripts/ci_run.sh
scripts/ci_run.sh baseline
scripts/ci_run.sh pr
```

## Determinisic harness defaults
Costgate uses:
- `temperature=0`
- `top_p=1.0`
- fixed `max_output_tokens` (default 96, configurable)
- synthetic suite included in repo (`costgate/suites/demo_suite.yaml`)
- repeats `N` configurable (default 7)

## Measuring tokens at the paid boundary
Per call:
- Prefer token usafe returned by the provider API response
- If missing, estimate with `tiktoken` and set 'token_source="estimated"`
- Always record `token_source`

## Policy tuning
Policy lives in `costgate/policies/defualt.yaml`:

Key knobs:
- `metrics_to_gate`: list of metrics (v1 supports: `total_cost_usd`, `cost_per_success_usd`, `p50_latency_ms`, `p95_latency_ms`, `mean_input_tokens`, `mean_output_tokens`, `retry_rate`)
- `regression_threshold_pct`: per-metric pratical thresholds (default 10%, retry default 25%)
- `min_absolute_delta_usd`: absolute floor for cost metrics (default `1e-05`)
- `alpha`: statistical significance (default 0.05)
- `min_repeats`, `min_sample_size`: must be satisfied or compare errors
- `variance_aware`: if enabled, effective threshold is: `max(user_threshold, k * baseline_std / baseline_mean)` with `k` default 3

Gate triggers only if BOTH:
- Practical threshold exceeded, AND
- Mann-Whitney U one-sided test inidicates PR worse (p < alpha)

Also reported: bootstrap CI for mean difference, and Cliff's delta effect size with CI.

## Troubleshooting

### "OPENAI_API_KEY is not set"
Set:
```bash
export OPENAI_API_KEY="..."
```

### "No rate card rule matches resolved_model=..."
Update `costgate/rate_cards/default.yaml` to include a matching `model_glob`, or run with:
```bash
--allow-missing-rate
```
(then cost will be NaN and cost metrics are not meaningful)

### "Baseline family mismatch
This happens if you change suite, model, deterministic params, or rate card. Regenerate baseline:
```bash
costgate baseline ...
```
Or override (not recommended for CI):
```bash
--allow-family-mismatch
```