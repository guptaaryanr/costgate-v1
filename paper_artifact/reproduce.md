# Reproducing Costgate Benchmark Results

## Install

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

For core/mock-only use:

```bash
python -m pip install -e .
```

For OpenAI examples:

```bash
python -m pip install -e '.[openai]'
export OPENAI_API_KEY="..."
```

## Deterministic Free Experiments

Run unit tests and the controlled benchmark matrix:

```bash
python -m pytest
python benchmarks/costregbench/run.py --out .costgate/costregbench
```

The benchmark writes per-scenario artifacts plus:

- `.costgate/costregbench/summary.csv`
- `.costgate/costregbench/summary.md`

These summaries include expected verdict, observed verdict, false-positive/false-negative markers, and major metric deltas.

## Smoke Test

```bash
python scripts/run_costregbench_smoke.py
```

## What To Archive

For a release or Zenodo artifact, archive:

- repository source at the release tag
- `benchmarks/costregbench/`
- `paper_artifact/`
- generated `summary.csv` and `summary.md`
- optional per-scenario `compare.json` and `report.md`

Avoid archiving local `.venv/`, `.pytest_cache/`, private `.costgate/` runs from sensitive suites, API keys, or environment files.

## Paid/Non-Deterministic Experiments

OpenAI provider examples are optional. Even with deterministic request parameters, real provider runs can vary because hosted model behavior, latency, and retry conditions can change.
