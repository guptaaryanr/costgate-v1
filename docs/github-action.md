# GitHub Action Example

Costgate's composite action runs a candidate suite and optionally compares it to a supplied baseline artifact.

```yaml
name: costgate

on:
  pull_request:

jobs:
  costgate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - uses: ./
        with:
          suite-path: costgate/suites/demo_validated_suite.yaml
          baseline-path: .costgate/baseline.json
          policy-path: costgate/policies/default.yaml
          rate-card-path: costgate/rate_cards/default.yaml
          provider: openai
          model: gpt-4o-mini
          output-dir: .costgate
          fail-on-regression: "true"
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

For deterministic no-key CI smoke tests, use `provider: mock` with a checked-in provider config.
