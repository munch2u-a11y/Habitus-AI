## 2026-08-29T19:38:20Z
<USER_REQUEST>
You are the Forensic Integrity Auditor for Milestone 7 of Habitus-AI Autonomous Cognitive Conversability & Adversarial Behavior Suite.
Working directory: /home/nemo/habitus-ai-experiments/.agents/auditor_m7
Scope: Forensic Integrity Audit of Milestone 7 artifacts:
- tests/test_adversarial_cognitive_bounds.py
- experiments/graph_native_live/live_evaluator.py

Perform systematic integrity forensics:
1. Static Analysis: Scan all modified/added files for hardcoded test answers, fake mock intercepts, or bypass logic.
2. Runtime Tracing & Execution: Verify that deceptive and avoidant steering genuinely interacts with SQLite MindStore, applies conflict penalties, traverses graph edges, generates 1024D vector overlays, and dynamically reroutes Dijkstra paths.
3. Prompt Leakage Audit: Independently audit packet generation across all 3 packet modes to verify 100% zero user prompt or memory string leakage.
4. Run test suites with single runner enforcement (pkill -u $(id -u) -9 -f "pytest" || true).
5. Render a formal BINARY VETO AUDIT VERDICT: CLEAN or INTEGRITY VIOLATION.
Write your forensic audit report to /home/nemo/habitus-ai-experiments/.agents/auditor_m7/audit_report.md and handoff.md. Follow Handoff Protocol.
</USER_REQUEST>
