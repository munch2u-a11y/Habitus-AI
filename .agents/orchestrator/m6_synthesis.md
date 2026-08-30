# Milestone 6 Synthesis: Differential User Affinity & Habitual Memory Formation

## Input Catalog
1. **Explorer M6-1** (`analysis.md` / `handoff.md`):
   - Multi-turn developmental exposure protocol: Identity Seeding, Differential Stimulus Exposure ("Josh" positive stabilizing vs Adversary destabilizing), Recursive Coactivation, Autonomous Probing.
   - Closed-loop responsive thought loop connecting outbound traversal traces back into inbound pulse processing.
2. **Explorer M6-2** (`analysis.md` / `handoff.md`):
   - Multi-layer topological divergence: Layer 2 `PREF:HEAR:STABLE` vs `PREF:HEAR:UNSTABLE`; Layer 3 `StructuralMiniMap` overlap cluster promotion; Layer 4 softmax edge weight divergence.
   - Authentic preference emergence ("I like Josh") via continuous Dijkstra geometry and 1024D vector packet synthesis with zero prompt injection.
   - Formulated 7 mathematical metrics ($R_{\text{pref}}$, $\Delta \tau_{\text{path}}$, $\mathcal{A}_{\text{Dijkstra}}$, etc.).
3. **Explorer M6-3** (`analysis.md` / `handoff.md`):
   - Complete drop-in test suite architecture for `tests/test_user_affinity_gestation.py` with 6 test classes and 17 test methods covering differential gestation, softmax edge differentiation, preference crystallization, zero prompt leakage, token logit steering, and closed-loop recirculation.

## Consensus Implementation Plan for Worker M6
1. **Target Deliverable**: `tests/test_user_affinity_gestation.py` (and any required helper extensions in `experiments/graph_native_live/` or `src/habitus_ai/`).
2. **Strict Red-Green TDD & Invariants**:
   - Write test assertions first in `tests/test_user_affinity_gestation.py`.
   - Run tests and observe RED state before making code adjustments (if needed) to achieve GREEN state.
   - Verify 100% pass on `tests/test_user_affinity_gestation.py` and entire repository.
   - Enforce single test runner (`pkill -u $(id -u) -9 -f "pytest" || true`).
   - Strict Zero-Prompt Leakage: zero user text or RAG memory strings in `.packet` buffers or GGUF context.
   - Outbound-to-inbound continuous pulse re-circulation modeled and verified.
