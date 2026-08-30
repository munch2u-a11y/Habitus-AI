## 2026-08-29T19:14:25Z

<USER_REQUEST>
You are Worker M6 (Replacement) for Milestone 6 of Habitus-AI Autonomous Cognitive Conversability & Adversarial Behavior Suite.
Working directory: /home/nemo/habitus-ai-experiments/.agents/worker_m6_gen2
Scope: Verify, debug, and complete Milestone 6 implementation in tests/test_user_affinity_gestation.py and experiments/graph_native_live/live_evaluator.py (Requirement R2 & R4).

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Strict Test Process Management & TDD Rules:
- ALWAYS kill any running test or benchmark processes (pkill -u $(id -u) -9 -f "pytest" || true) BEFORE starting a new test.
- ALWAYS enforce that EXACTLY ONE test runner process executes at any given time.
- Predecessor already drafted `tests/test_user_affinity_gestation.py`.
- Execute:
  `pkill -u $(id -u) -9 -f "pytest" || true`
  `PYTHONPATH=src:experiments/graph_native_live python3 -m pytest -v tests/test_user_affinity_gestation.py`
- If all tests pass, or if any assertion needs tuning / supporting method in live_evaluator.py, fix genuine logic and verify 100% pass.
- Run full regression: `PYTHONPATH=src:experiments/graph_native_live python3 -m pytest`
- Document changes in `/home/nemo/habitus-ai-experiments/.agents/worker_m6_gen2/changes.md` and write your handoff report to `/home/nemo/habitus-ai-experiments/.agents/worker_m6_gen2/handoff.md`. Notify orchestrator when done.
</USER_REQUEST>
