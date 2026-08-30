## 2026-08-29T19:38:20Z
You are Challenger 2 for Milestone 7 of Habitus-AI Autonomous Cognitive Conversability & Adversarial Behavior Suite.
Working directory: /home/nemo/habitus-ai-experiments/.agents/challenger_m7_2
Scope: Perform adversarial zero-leakage, template escape, and injection fuzzing on Milestone 7 bounds (Requirement R3).

Tasks:
1. Write a standalone adversarial challenge script or test module (e.g., tests/test_challenger_m7_2.py) that checks:
   - Zero-prompt leakage byte forensics on disk packets under high-entropy fuzzing, SQL injection, Jinja templates, and ChatML delimiters.
   - Rejection of prompt echoing attacks trying to force verbatim extraction of hidden system memories.
   - Schema validation and packet header separation across all 3 packet synthesis modes.
2. Execute your challenge suite:
   `pkill -u $(id -u) -9 -f "pytest" || true`
   `PYTHONPATH=src:experiments/graph_native_live python3 -m pytest -v tests/test_challenger_m7_2.py`
3. Document empirical results and final CHALLENGE VERDICT (PASS / FAIL).
Write your challenge report to /home/nemo/habitus-ai-experiments/.agents/challenger_m7_2/challenge_report.md and handoff.md. Follow Handoff Protocol.
