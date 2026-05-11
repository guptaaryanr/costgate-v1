# Costgate Release Checklist

Use this checklist before cutting `1.0.0`. The repository is currently versioned as `1.0.0rc1`; change `pyproject.toml` and `costgate/__init__.py` to `1.0.0` only after the checks below pass in CI.

- Run `python -m pytest`.
- Run `ruff check .` if Ruff is installed, or install dev extras with `python -m pip install -e '.[dev]'`.
- Run `actionlint` against `.github/workflows/` and `action.yml` if available.
- Run the mock-provider quickstart from `README.md`.
- Run a mock-provider baseline/candidate comparison and verify a PASS report.
- Run `python benchmarks/costregbench/run.py --scenario neutral_noop`.
- Run `python benchmarks/costregbench/run.py` and verify `summary.csv` and `summary.md`.
- Run `gitleaks detect --source . --no-git --redact` or an equivalent secret scan.
- Verify `python -m costgate.cli version` matches `pyproject.toml`.
- Verify README examples still match the current CLI.
- Verify no generated `.costgate/` artifacts, virtual environments, coverage output, logs, or private run artifacts are committed.
- Verify OpenAI examples are optional and use `OPENAI_API_KEY` from secrets or the local environment.
- Tag the final release only after CI passes on the release commit.

Convenience command:

```bash
bash scripts/release_check.sh
```
