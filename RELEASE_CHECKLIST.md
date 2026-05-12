# Costgate Release Checklist

Use this checklist before cutting `v1.0.0`.

## Before Final Version Bump

- Run `python -m pytest`.
- Run `bash scripts/release_check.sh`.
- Run `python -m json.tool .zenodo.json`.
- Run `python - <<'PY'` with `yaml.safe_load(Path("CITATION.cff").read_text())` or another CFF validator if available.
- Verify README examples still match the current CLI.
- Verify OpenAI examples are optional and use `OPENAI_API_KEY` from secrets or the local environment.

## Final Version Bump

- Change `pyproject.toml` from `1.0.0rc1` to `1.0.0`.
- Change `costgate/__init__.py` from `1.0.0rc1` to `1.0.0`.
- Verify `python -m costgate.cli version` matches `pyproject.toml`.
- Verify `CITATION.cff` and `.zenodo.json` say `1.0.0`.

## Required Final Checks

- Run `python -m pytest`.
- Run `bash scripts/release_check.sh`.
- Run `ruff check .` if Ruff is installed, or install dev extras with `python -m pip install -e '.[dev]'`.
- Run `actionlint` against `.github/workflows/` and `action.yml` if available.
- Run the mock-provider quickstart from `README.md`.
- Run a mock-provider baseline/candidate comparison and verify a PASS report.
- Run `python benchmarks/costregbench/run.py --scenario neutral_noop`.
- Run `python benchmarks/costregbench/run.py` and verify all CostRegBench scenarios have `status=ok`.
- Run `gitleaks detect --source . --no-git --redact` or an equivalent secret scan.
- Verify `paper_artifact/results/v1.0.0/` exists and contains the final frozen artifact generated from the final release commit.
- Verify `paper_artifact/results/v1.0.0/summary.csv` and `summary.md` match the final benchmark run.
- Verify `paper_artifact/results/v1.0.0/benchmark_manifest.json` points at the final release commit.
- Verify citation metadata is present in `CITATION.cff`.
- Verify Zenodo metadata is present in `.zenodo.json`.
- Verify release notes are present in `docs/release-v1.0.0.md`.
- Verify GitHub Actions pass on the final release commit.
- Verify no generated `.costgate/` artifacts, virtual environments, coverage output, logs, or private run artifacts are committed.

## Final Artifact Command

```bash
python scripts/freeze_release_artifact.py --clean --out paper_artifact/results/v1.0.0
```

## GitHub Release Steps

- Enable the Zenodo GitHub integration before or immediately after creating the GitHub release.
- Commit final metadata and frozen artifacts.
- Tag the final release with `git tag v1.0.0`.
- Push the branch and tag.
- Create the GitHub release for `v1.0.0`.
- Verify Zenodo archives the GitHub release and generates a DOI.
- Do not invent or commit a DOI before Zenodo creates one.

Convenience validation command:

```bash
bash scripts/release_check.sh
```
