## 2026-08-29T15:25:41-04:00
You are Reviewer 2 for Milestone 6 of Habitus-AI Autonomous Cognitive Conversability & Adversarial Behavior Suite.
Working directory: /home/nemo/habitus-ai-experiments/.agents/reviewer_m6_2
Scope: Perform contract conformance, mathematical invariants, and zero-prompt leakage review of Milestone 6 deliverables:
- tests/test_user_affinity_gestation.py
- experiments/graph_native_live/live_evaluator.py

Review checks:
1. Verify mathematical invariants: Layer 4 Boltzmann softmax conservation (sum == 1.0), Dijkstra travel time differential (t_stable < t_unstable), and intrinsic structural overlay unit-norm vector generation (L2 norm == 1.0).
2. Verify Zero-Prompt Leakage Invariant: Confirm no user names ("Josh", "Adversary"), prompt substrings, or RAG memory strings are serialized into continuous .packet files or passed to GGUF model context.
3. Run verification tests with single runner enforcement.
4. Render your VERDICT (PASS or VETO with technical rationale).
Write your review report to /home/nemo/habitus-ai-experiments/.agents/reviewer_m6_2/review.md and handoff.md. Follow Handoff Protocol.
