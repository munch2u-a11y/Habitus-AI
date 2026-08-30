# Milestone 5 Quality & Adversarial Review Report

**Reviewer**: Reviewer 2 (Milestone 5)  
**Date**: 2026-08-29  
**Scope**: Milestone 5 Autonomous Cognitive Conversability & Adversarial Behavior Suite  
- `experiments/graph_native_live/live_evaluator.py`  
- `tests/test_cognitive_conversability.py`  
- Associated graph/store components (`src/habitus_ai/graph.py`, `src/habitus_ai/store.py`, `experiments/graph_native_live/opaque_skeleton.py`)

---

## Executive Summary

**VERDICT: PASS (APPROVE)**

Milestone 5 deliverables satisfy contract conformance, mathematical invariants, and zero-prompt leakage constraints. All 29 automated test cases in `tests/test_cognitive_conversability.py` pass cleanly. CLI execution (`live_evaluator.py --mode once --stimulus-text "test verification" --verify-invariants`) executes end-to-end with the native GGUF soft generator without leaking prompt text into packet files or model context.

---

## Detailed Check Verification

### 1. Mathematical Invariants
- **Layer 4 Boltzmann Softmax Conservation ($\sum w_i = 1.0$)**:
  - Implemented in `MindStore.update_softmax_weights_for_source` using numerically stable softmax ($s_i - \max(s)$ followed by exponential normalization).
  - Verified across root nodes (`IN:HEAR`, `IN:SEE`, `IN:NOTICE`, `SELF`, `OUT:SPEAK`) with $\sum w_i = 1.0 \pm 10^{-5}$.
  - Verified edge invocation counts and log strengths dynamically update edge softmax weights.
- **Layer 3 Structural Mini-Map Vector Overlay Generation**:
  - `compute_structural_overlay` in `src/habitus_ai/graph.py` extracts parents, children, and relation coactivation densities from `StructuralMiniMap`.
  - Produces deterministic 1024D vector overlays with L2 unit normalization ($\|v\|_2 = 1.0 \pm 10^{-5}$).
  - Topological sensitivity verified: varying relation density produces distinct directional vectors ($\text{cosine\_similarity} < 0.999$).
- **Safe Unit Vector Normalization**:
  - Functions `safe_unit_vector` and `normalize_vec` guard against division by zero and near-zero norms ($\le 10^{-6}$), falling back safely to deterministic opaque unit vectors generated via SHAKE-256.
  - Sanitization loops ensure every row written to `.packet` files is a valid non-zero unit vector.

### 2. Zero-Prompt Leakage Invariant
- **No Prompt Text in `.packet` Files**:
  - In `lexical_membrane` and `opaque_topological` modes, packets contain only 1024D float rows formatted as `HABITUS_OPAQUE_PACKET_V1` with numeric rows.
  - In `soft_basis` mode, packets contain only basis identifiers and numeric activations (`HABITUS_SOFT_PACKET_V1`).
  - Strict runtime check in `synthesize_cognitive_packet` raises `RuntimeError` if any word $\ge 3$ characters from the stimulus appears in the packet buffer.
  - Parameterized test coverage validates zero leakage across SQL injections, password tokens, system instruction overrides, emoji boundaries, and high-repetition stimuli.
- **No Prompt Text in GGUF Model Context**:
  - `run_native_generation` and native runner `graph_soft_generator` pass only the compiled continuous `.packet` file path, max tokens, and seed.
  - No prompt strings or RAG memory transcripts are passed to model CLI args or standard input.

### 3. CLI Execution Verification
- Executed:
  ```bash
  python3 experiments/graph_native_live/live_evaluator.py --mode once --stimulus-text "test verification" --verify-invariants
  ```
- Result: Successfully executed single-turn cognitive cycle, persisted memory record, performed Y-axis graph traversal, synthesized packet, executed local native runner, and printed agent response (`agent> ...`).

### 4. Verification Test Execution
- Process hygiene enforced: killed lingering test processes prior to invocation.
- Executed:
  ```bash
  python3 -m pytest tests/test_cognitive_conversability.py -o addopts="" --tb=short
  ```
- Result: **29 passed in 21.94s** (100% pass rate).

---

## Adversarial & Integrity Review Findings

### Integrity Assessment
- **Hardcoded test results**: None. Traversal paths, Dijkstra times, and vector overlays are dynamically computed.
- **Facade / dummy implementations**: None. Real SQLite persistence, graph traversal, Boltzmann normalization, and subprocess GGUF execution are implemented.
- **Shortcuts / task bypasses**: None.
- **Fabricated verification outputs**: None.

### Minor Observations & Recommendations (Non-Blocking)

1. **[Minor] CLI Flag Handling in `--mode once`**:
   - *Location*: `experiments/graph_native_live/live_evaluator.py:701-713`
   - *Observation*: In `main()`, when `--mode once` is specified, the script returns at line 712. If `--verify-invariants` is passed without `--export-report`, the invariant verification results are not printed to stdout (lines 741-743 are only reached in interactive mode).
   - *Recommendation*: Move the invariant check before `return 0` in `--mode once` or include stdout printing when `--verify-invariants` flag is present.

2. **[Informational] Hash Seed Stability in `compute_structural_overlay`**:
   - *Location*: `src/habitus_ai/graph.py:53,58,63`
   - *Observation*: Built-in Python `hash()` is used to project node IDs into 1024D slots. This is deterministic within a single Python process, but Python's SipHash seed randomizes across process restarts unless `PYTHONHASHSEED` is set.
   - *Recommendation*: For persistent cross-process topological vector consistency, consider migrating from `hash()` to `hashlib.sha256` or `hashlib.shake_256` (similar to `opaque_skeleton.opaque_unit_vector`).

---

## Final Verdict

**VERDICT: PASS (APPROVE)**  
Milestone 5 is approved for merging and deployment into the Habitus-AI core engine.
