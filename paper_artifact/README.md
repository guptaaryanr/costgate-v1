# Costgate Paper Artifact

This directory describes the lightweight reproducibility package for Costgate's controlled cost-regression experiments.

The artifact is deterministic by default. It uses `MockProvider` and `ReplayProvider` fixtures/configs, not paid API calls. Real OpenAI runs are optional examples and require `OPENAI_API_KEY`.

Start with [reproduce.md](reproduce.md).
