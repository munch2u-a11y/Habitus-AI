## 2026-08-28T22:40:20-04:00

You are Worker M4 for Milestone 4 (Full Suite E2E Verification & Victory Audit) of Habitus-AI.
Your working directory is /home/nemo/habitus-ai-experiments/.agents/worker_m4.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Context & Objectives:
You must execute, verify, and document the complete full-suite E2E regression and live verification for Habitus-AI:
1. Process & Environment Safety:
   - Ensure clean single test runner: execute `pkill -9 -f "python3"` before running tests.
   - Set environment variable: `export LD_LIBRARY_PATH=/usr/local/lib/ollama:$LD_LIBRARY_PATH`.
   - Set `export PYTHONPATH=src:experiments/graph_native_live:$PYTHONPATH`.
   - Ensure working directory is `/home/nemo/habitus-ai-experiments`.

2. Full Regression Suite Execution:
   - Run the complete pytest test suite across all tests in `tests/`:
     `pytest -v tests/`
   - Capture pass/fail counts, execution times, and any warnings.

3. Live Multi-Domain End-to-End Synthesis:
   - Execute `python3 experiments/graph_native_live/live_tester.py` across diverse stimuli.
   - Verify that all stimuli produce valid 1024D continuous slot activations and fluent plain language text output via `graph_soft_generator` and `Qwen3-0.6B-Q8_0.gguf`.
   - Verify zero prompt text leakage throughout execution.

4. Deliverables:
   - Output your comprehensive handoff report directly in your message response with:
     * Full `pytest -v tests/` output table.
     * Raw live tester execution transcript with generated plain-language samples.
     * Verification of binary links, GGUF model properties, and SQLite database integrity.
     * Summary of acceptance criteria satisfaction for R1, R2, R3.
