# Costgate v1.0.0 Release Notes

Costgate v1.0.0 is the first DOI-ready release of the local/CI-first LLM
inference cost regression testing framework.

## Changes Since v1.0.0rc1

- Added citation metadata in `CITATION.cff`.
- Added Zenodo metadata in `.zenodo.json` without claiming a DOI before archival.
- Added a final release artifact template under `paper_artifact/results/v1.0.0/`.
- Added `scripts/freeze_release_artifact.py` to regenerate final frozen
  CostRegBench artifacts reproducibly.
- Tightened release documentation and checklist items for final tagging,
  Zenodo archival, and paper artifact hygiene.
- Bumped package metadata from `1.0.0rc1` to `1.0.0` after pre-bump checks
  passed.
- No new product features or provider behavior changes were added after rc1.

## Validation Performed

- `python -m pytest`: passed, 45 tests.
- `bash scripts/release_check.sh`: passed with package version `1.0.0`.
  The release check also ran CLI help checks, mock-provider run/compare,
  CostRegBench smoke, Ruff, actionlint, and gitleaks.
- `python -m json.tool .zenodo.json`: passed.
- `CITATION.cff` structural YAML parse: passed.
- `python scripts/freeze_release_artifact.py --clean --skip-release-check --out .costgate/final-artifact-script-check`:
  passed; all 8 deterministic CostRegBench scenarios matched expected
  verdicts.

## Benchmark Results Summary

The release-artifact dry run reported 8/8 CostRegBench scenarios with
`status=ok`. Controlled regression scenarios are successful when the observed
verdict matches the expected `warn` or `fail` outcome.

The committed `paper_artifact/results/v1.0.0/` directory is currently a final
artifact template. Regenerate it from the final release commit before tagging:

```bash
python scripts/freeze_release_artifact.py --clean --out paper_artifact/results/v1.0.0
```

## Known Limitations

- Costgate is not a hosted observability platform.
- Costgate is not a semantic quality benchmark by itself.
- Real provider runs may still be stochastic despite deterministic request
  parameters.
- Latency is noisy and should usually be reported or warned, not hard-gated.
- Provider-reported token usage is preferred over local estimates.
- CostRegBench is a controlled cost-regression benchmark, not a broad LLM
  intelligence evaluation.

## DOI / Zenodo Archival Note

Do not invent or pre-fill a DOI. Enable the Zenodo GitHub integration before
or immediately after creating the GitHub release. Zenodo should archive the
`v1.0.0` tag and generate the DOI for the final release artifact.

## GitHub Release Instructions

1. Verify all checks pass on the final release commit.
2. Ensure version metadata is `1.0.0`.
3. Regenerate `paper_artifact/results/v1.0.0/` from the final release commit.
4. Commit final artifacts and release metadata.
5. Tag the release with `git tag v1.0.0`.
6. Push the branch and tag.
7. Create the GitHub release for `v1.0.0`.
8. Verify Zenodo archives the release and generates a DOI.
