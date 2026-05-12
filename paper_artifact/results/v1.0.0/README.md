# Costgate v1.0.0 Final Artifact Template

This directory is reserved for the final v1.0.0 frozen CostRegBench artifact.
It is intentionally not populated with copied v1.0.0rc1 results.

After the final version bump to `1.0.0` and after local/CI checks pass, generate
the final contents from the release commit:

```bash
python scripts/freeze_release_artifact.py --clean --out paper_artifact/results/v1.0.0
```

Expected generated files include `summary.csv`, `summary.md`,
`benchmark_manifest.json`, `release_check.txt`, `secret_scan.txt`,
`ci_status.txt`, and per-scenario reports under `scenario_reports/`.
