#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

MODE="${1:-pr}"

load_env_file() {
  local env_file="$1"
  local line key value

  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -z "${line}" || "${line}" == \#* ]] && continue

    if [[ "${line}" =~ ^export[[:space:]]+(.+)$ ]]; then
      line="${BASH_REMATCH[1]}"
    fi

    if [[ "${line}" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      value="${BASH_REMATCH[2]}"

      if [[ "${value}" == \"*\" && "${value}" == *\" ]]; then
        value="${value:1:${#value}-2}"
      elif [[ "${value}" == \'*\' && "${value}" == *\' ]]; then
        value="${value:1:${#value}-2}"
      fi

      if [[ -z "${!key:-}" ]]; then
        export "${key}=${value}"
      fi
    fi
  done < "${env_file}"
}

ENV_FILE="${COSTGATE_ENV_FILE:-.env}"
if [[ -f "${ENV_FILE}" ]]; then
  load_env_file "${ENV_FILE}"
fi

SUITE="${COSTGATE_SUITE:-costgate/suites/demo_suite.yaml}"
RATE="${COSTGATE_RATE_CARD:-costgate/rate_cards/default.yaml}"
POLICY="${COSTGATE_POLICY:-costgate/policies/default.yaml}"

PROVIDER="${COSTGATE_PROVIDER:-openai}"
MODEL="${COSTGATE_MODEL:-gpt-4o-mini}"
REPEATS="${COSTGATE_REPEATS:-7}"
MAX_OUT="${COSTGATE_MAX_OUTPUT_TOKENS:-96}"

if [[ "${MODE}" != "baseline" && "${MODE}" != "pr" ]]; then
  echo "Usage: scripts/ci_run.sh [baseline|pr]" >&2
  exit 2
fi

if [[ "${PROVIDER}" == "openai" && -z "${OPENAI_API_KEY:-}" ]]; then
  echo "ERROR: OPENAI_API_KEY is not set. Export it or copy .env.example to .env and fill it in." >&2
  exit 1
fi

mkdir -p .costgate

if [[ "${MODE}" == "baseline" ]]; then
  echo "[costgate] Running baseline..."
  costgate validate --suite "${SUITE}" --rate-card "${RATE}" --policy "${POLICY}"

  costgate baseline \
    --provider "${PROVIDER}" \
    --model "${MODEL}" \
    --suite "${SUITE}" \
    --rate-card "${RATE}" \
    --repeats "${REPEATS}" \
    --max-output-tokens "${MAX_OUT}" \
    --out .costgate/results.json \
    --baselines-root .costgate/baselines

  echo "[costgate] Baseline done."
  exit 0
fi

if [[ "${MODE}" == "pr" ]]; then
  echo "[costgate] Running PR compare..."
  costgate validate --suite "${SUITE}" --rate-card "${RATE}" --policy "${POLICY}"

  if [[ ! -d ".costgate/baselines" ]]; then
    echo "ERROR: .costgate/baselines not found. Download baseline artifact first." >&2
    exit 1
  fi

  costgate run \
    --provider "${PROVIDER}" \
    --model "${MODEL}" \
    --suite "${SUITE}" \
    --rate-card "${RATE}" \
    --repeats "${REPEATS}" \
    --max-output-tokens "${MAX_OUT}" \
    --out .costgate/pr_results.json

  # Compare against latest baseline under .costgate/baselines.
  set +e
  costgate compare \
    --pr-results .costgate/pr_results.json \
    --baseline-root .costgate/baselines \
    --baseline-auto \
    --policy "${POLICY}" \
    --report-out .costgate/report.md \
    --compare-out .costgate/compare.json \
    --exit-on-regression
  CODE=$?
  set -e

  echo "[costgate] Compare exit code: ${CODE}"
  exit "${CODE}"
fi
