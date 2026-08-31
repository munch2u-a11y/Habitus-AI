# Schema-Free Actualizer Experiment

This branch carries the self-contained Habitus Actualizer proof of concept at
[`experiments/habitus-actualizer-poc/`](experiments/habitus-actualizer-poc/).

It explores persistent, receipt-backed workspace abilities activated from
ordinary model output without sending an LLM tool schema. The experiment keeps
the Habitus-AI mainline unchanged outside this branch and remains intentionally
isolated from the primary `habitus_ai` package.

Run its complete test suite with:

```bash
cd experiments/habitus-actualizer-poc
python3 -m pytest -q
```

The controlled longitudinal trial and known limitations are recorded in
[`benchmark_results/2026-08-31-live-agent-longitudinal.md`](experiments/habitus-actualizer-poc/benchmark_results/2026-08-31-live-agent-longitudinal.md).
