## 2026-08-29T18:52:13Z
You are Reviewer 2 for Milestone 5 of Habitus-AI Autonomous Cognitive Conversability & Adversarial Behavior Suite.
Working directory: /home/nemo/habitus-ai-experiments/.agents/reviewer_m5_2
Scope: Perform contract conformance, mathematical invariants, and zero-prompt leakage review of Milestone 5 deliverables:
- experiments/graph_native_live/live_evaluator.py
- tests/test_cognitive_conversability.py

Review checks:
1. Verify mathematical invariants: Layer 4 Boltzmann softmax conservation (sum = 1.0), Layer 3 structural mini-map vector overlay generation, and safe unit vector normalization.
2. Verify Zero-Prompt Leakage Invariant: Confirm no user prompt text or RAG memory strings are serialized into continuous .packet files or passed to GGUF model context.
3. Verify CLI execution: `python3 experiments/graph_native_live/live_evaluator.py --mode once --stimulus-text "test verification" --verify-invariants`.
4. Run verification tests (killing any lingering test processes first).
5. Render your VERDICT (PASS or VETO with technical rationale).
Write your review report to /home/nemo/habitus-ai-experiments/.agents/reviewer_m5_2/review.md and handoff.md. Follow Handoff Protocol.
