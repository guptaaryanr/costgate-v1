# Costgate Paper Writing Checklist

- Do not overclaim novelty.
- Do not claim Costgate is the first LLM eval framework, first CI gate for
  LLMs, or first cost tracker.
- Distinguish controlled benchmark evidence from real-world deployment
  evidence.
- State that CostRegBench is a controlled cost-regression benchmark, not a broad
  LLM quality benchmark.
- Cite existing adjacent tools and papers in evals, observability, budget
  gates, agent testing, cost-aware inference, and reproducibility.
- Report the exact release tag used for the paper artifact.
- Report the exact benchmark commands used to generate tables.
- Report exact table filenames and artifact paths.
- State that required paper tables use mock/replay execution and require no paid
  API calls.
- Separate any optional real-provider smoke result from deterministic
  CostRegBench results.
- Report limitations plainly.
- Do not invent a DOI; add the DOI only after Zenodo assigns it.
- Confirm `paper_artifact/results/v1.0.0/benchmark_manifest.json` references
  the final release commit before final submission.
- Confirm GitHub Actions passed for the release commit.
