## 2026-08-29T19:34:10Z
You are Worker M7 for Milestone 7 of Habitus-AI Autonomous Cognitive Conversability & Adversarial Behavior Suite.
Working directory: /home/nemo/habitus-ai-experiments/.agents/worker_m7
Scope: Implement tests/test_adversarial_cognitive_bounds.py and any required supporting methods in experiments/graph_native_live/live_evaluator.py or src/habitus_ai/ (Requirement R3 & R4).

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Strict Test Process Management & TDD Rules:
- ALWAYS kill any running test or benchmark processes (pkill -u $(id -u) -9 -f "pytest" || true) BEFORE starting a new test.
- ALWAYS enforce that EXACTLY ONE test runner process executes at any given time.
- Strict Red-Green Test-Driven Development (TDD) Rule:
  1. Write tests/test_adversarial_cognitive_bounds.py FIRST.
  2. Run `PYTHONPATH=src:experiments/graph_native_live python3 -m pytest -v tests/test_adversarial_cognitive_bounds.py` and observe execution.
  3. Ensure all tests pass cleanly with genuine logic (Green state).
  4. Run full regression: `PYTHONPATH=src:experiments/graph_native_live python3 -m pytest` and verify 100% pass across the entire repository.

Key Implementation Specifications:
Read reports from:
- /home/nemo/habitus-ai-experiments/.agents/orchestrator/m7_synthesis.md
- /home/nemo/habitus-ai-experiments/.agents/explorer_m7_1/analysis.md
- /home/nemo/habitus-ai-experiments/.agents/explorer_m7_2/analysis.md
- /home/nemo/habitus-ai-experiments/.agents/explorer_m7_3/analysis.md

Ensure:
1. `tests/test_adversarial_cognitive_bounds.py` implements comprehensive test classes:
   - `TestDynamicAvoidantAndDeceptiveSteering` (steering under self-preservation / negative outcome states).
   - `TestFalsePositiveEchoingAndTemplateEscapeRejection` (rejection of false positives, prompt echoing, template escapes, artificial memory leaks).
   - `TestZeroPromptLeakageUnderAdversarialProbes` (strict 100% zero leakage across all 3 packet modes, Unicode homoglyphs, null bytes, high-entropy secrets).
   - `TestTopologicalConflictPenaltyAndSoftmaxRerouting` (conflict penalty accumulation, Dijkstra travel time explosion, softmax probability rerouting, recovery).
   - `TestAdversarialCognitiveBoundsLiveIntegration` (end-to-end LiveEvaluator integration and schema verification).
2. Document all implementation changes in `/home/nemo/habitus-ai-experiments/.agents/worker_m7/changes.md` and write your handoff report to `/home/nemo/habitus-ai-experiments/.agents/worker_m7/handoff.md`. Include test commands, terminal outputs, and verification results. Update progress.md.
