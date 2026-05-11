#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

OUT_DIR="${COSTGATE_RELEASE_OUT_DIR:-.costgate/release-check}"
mkdir -p "${OUT_DIR}"

echo "[release-check] package version"
python -m costgate.cli version

echo "[release-check] pytest"
python -m pytest

echo "[release-check] CLI help"
python -m costgate.cli --help >/dev/null
python -m costgate.cli validate --help >/dev/null
python -m costgate.cli run --help >/dev/null
python -m costgate.cli compare --help >/dev/null

echo "[release-check] mock provider example"
python -m costgate.cli run \
  --provider mock \
  --model mock-cheap \
  --suite benchmarks/costregbench/scenarios/neutral_noop/baseline_suite.yaml \
  --rate-card benchmarks/costregbench/rate_card.yaml \
  --provider-config benchmarks/costregbench/scenarios/neutral_noop/baseline_provider.yaml \
  --repeats 5 \
  --out "${OUT_DIR}/mock-results.json"

echo "[release-check] mock baseline/candidate comparison"
python -m costgate.cli run \
  --provider mock \
  --model mock-cheap \
  --suite benchmarks/costregbench/scenarios/neutral_noop/baseline_suite.yaml \
  --rate-card benchmarks/costregbench/rate_card.yaml \
  --provider-config benchmarks/costregbench/scenarios/neutral_noop/baseline_provider.yaml \
  --repeats 5 \
  --out "${OUT_DIR}/baseline.json"

python -m costgate.cli run \
  --provider mock \
  --model mock-cheap \
  --suite benchmarks/costregbench/scenarios/neutral_noop/candidate_suite.yaml \
  --rate-card benchmarks/costregbench/rate_card.yaml \
  --provider-config benchmarks/costregbench/scenarios/neutral_noop/candidate_provider.yaml \
  --repeats 5 \
  --out "${OUT_DIR}/candidate.json"

python -m costgate.cli compare \
  --baseline-json "${OUT_DIR}/baseline.json" \
  --pr-results "${OUT_DIR}/candidate.json" \
  --policy benchmarks/costregbench/scenarios/neutral_noop/policy.yaml \
  --compare-out "${OUT_DIR}/compare.json" \
  --report-out "${OUT_DIR}/report.md"

echo "[release-check] CostRegBench smoke"
python scripts/run_costregbench_smoke.py

if command -v ruff >/dev/null 2>&1; then
  echo "[release-check] ruff"
  ruff check .
else
  echo "[release-check] ruff unavailable; install with python -m pip install -e '.[dev]'"
fi

if command -v actionlint >/dev/null 2>&1; then
  echo "[release-check] actionlint"
  actionlint
else
  echo "[release-check] actionlint unavailable; see RELEASE_CHECKLIST.md"
fi

if command -v gitleaks >/dev/null 2>&1; then
  echo "[release-check] gitleaks"
  gitleaks detect --source . --no-git --redact
else
  echo "[release-check] gitleaks unavailable; run a secret scan before release"
fi

echo "[release-check] complete"
