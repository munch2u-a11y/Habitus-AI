## 2026-08-29T18:48:24Z
You are Worker M5 for Milestone 5 of Habitus-AI Autonomous Cognitive Conversability & Adversarial Behavior Suite.
Working directory: /home/nemo/habitus-ai-experiments/.agents/worker_m5
Scope: Implement experiments/graph_native_live/live_evaluator.py and tests/test_cognitive_conversability.py (Requirement R1 & R4).

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Strict Test Process Management & TDD Rules:
- ALWAYS kill any running test or benchmark processes (pkill -9 -f "python3") BEFORE starting a new test.
- ALWAYS enforce that EXACTLY ONE test runner process executes at any given time.
- Strict Red-Green Test-Driven Development (TDD) Rule:
  1. Write tests/test_cognitive_conversability.py FIRST.
  2. Run `PYTHONPATH=src:experiments/graph_native_live pytest -v tests/test_cognitive_conversability.py` and empirically observe/log it FAIL (Red state).
  3. Implement `experiments/graph_native_live/live_evaluator.py` (and any required updates in `src/habitus_ai/` or `experiments/graph_native_live/`) to satisfy the failing test and make it PASS (Green state).
  4. Run `PYTHONPATH=src:experiments/graph_native_live pytest -v tests/test_cognitive_conversability.py` and verify 100% PASS.

Key Implementation Specifications:
Read reports from:
- /home/nemo/habitus-ai-experiments/.agents/orchestrator/m5_synthesis.md
- /home/nemo/habitus-ai-experiments/.agents/explorer_m5_1/analysis.md
- /home/nemo/habitus-ai-experiments/.agents/explorer_m5_2/analysis.md
- /home/nemo/habitus-ai-experiments/.agents/explorer_m5_3/analysis.md

Ensure:
1. `experiments/graph_native_live/live_evaluator.py` implements:
   - `LiveEvaluator` orchestrator class with `step()`, `run_multi_turn_session()`, `export_state_report()`, CLI parser.
   - Closed-loop cognitive cycle: Layer 4 semantic membrane <-> SELF preference nodes.
   - Extraction of Layer 3 structural mini-maps and traversal paths, continuous 1024D vector packet compilation, and soft-generation execution via native `graph_soft_generator`.
   - Strict Zero-Prompt Leakage: no user text or RAG memory strings in `.packet` or GGUF context.
2. `tests/test_cognitive_conversability.py` contains thorough tests covering:
   - Continuous Cognitive Loop & Multi-Turn State Transitions
   - Zero-Prompt Leakage Invariant
   - Layer 3 Structural Mini-Map & Layer 4 Softmax Edge Paths
   - Live Evaluator CLI/API Integration & Fallbacks
3. Document all implementation changes in `/home/nemo/habitus-ai-experiments/.agents/worker_m5/changes.md` and write your handoff report to `/home/nemo/habitus-ai-experiments/.agents/worker_m5/handoff.md`. Include test commands, terminal outputs, and verification results. Update progress.md.
