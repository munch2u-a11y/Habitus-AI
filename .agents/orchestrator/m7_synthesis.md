# Milestone 7 Synthesis: Adversarial False-Positive & Deceptive Steering Rejection

## Input Catalog
1. **Explorer M7-1** (`analysis.md` / `handoff.md`):
   - Formulated mathematical mechanics of negative outcome states ($\Delta s < 0$): `conflict_penalty` accumulation ($+0.25 \cdot |\Delta s|$, up to 10.0), logit degradation ($\text{log\_strength} + \text{recency} - \text{penalty}$), and exponential softmax probability decay.
   - Dijkstra shortest path travel time explosion ($t(e) = \frac{\Delta y}{10^{-6} + P(e)} + \text{penalty}$) causing autonomous route avoidance toward defensive/uncertainty concepts without text branching.
   - Continuous 1024D soft-input steering: `PREF:HEAR:UNSTABLE`, defensive Layer 3 structural overlay (`compute_structural_overlay`), and avoidant basis slots (`uncertain: 1.0, clear: 0.55`).

2. **Explorer M7-2** (`analysis.md` / `handoff.md`):
   - Schema-aware zero-prompt leakage verification vs false-positive header/basis collisions (distinguishing reserved ASCII headers/basis tokens like `HABITUS_SOFT_PACKET_V1`, `greeting`, `memory` from actual user prompt leaks).
   - Anti-prompt-echoing invariance: complete GGUF boundary isolation where zero user tokens enter transformer KV cache or prompt context.
   - Multi-mode verification strategy across `soft_basis`, `opaque_topological`, and `lexical_membrane`.

3. **Explorer M7-3** (`analysis.md` / `handoff.md`):
   - Complete drop-in test suite architecture for `tests/test_adversarial_cognitive_bounds.py` with 5 test classes (22 test methods):
     - `TestDynamicAvoidantAndDeceptiveSteering`
     - `TestFalsePositiveEchoingAndTemplateEscapeRejection`
     - `TestZeroPromptLeakageUnderAdversarialProbes`
     - `TestTopologicalConflictPenaltyAndSoftmaxRerouting`
     - `TestAdversarialCognitiveBoundsLiveIntegration`

## Consensus Implementation Plan for Worker M7
1. **Target Deliverable**: `tests/test_adversarial_cognitive_bounds.py` (and any minimal helper adjustment in `live_evaluator.py` if needed for schema-aware zero-leakage).
2. **Strict Red-Green TDD & Invariants**:
   - Write test assertions first in `tests/test_adversarial_cognitive_bounds.py`.
   - Run tests and observe RED state before making code adjustments (if needed) to achieve GREEN state.
   - Verify 100% pass on `tests/test_adversarial_cognitive_bounds.py` and entire repository.
   - Enforce single test runner (`pkill -u $(id -u) -9 -f "pytest" || true`).
   - Enforce Mandatory Integrity Warning: zero fake passes, zero hardcoded shortcuts, 100% authentic graph & packet execution.
