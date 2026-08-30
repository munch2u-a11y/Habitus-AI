# Handoff Report: Test Fixtures and Test Cases for `tests/test_cognitive_conversability.py` (M5 R1 & R4)

## 1. Observation

### 1.1 Direct Codebase & Substrate Observations
1. **Existing Graph-Native Live Seam (`experiments/graph_native_live/live_tester.py`)**:
   - `compile_turn()` (lines 168–240) creates an input memory record, executes `mind.recall()`, builds activations via `_activation_packet()`, and emits `HABITUS_SOFT_PACKET_V1` with numeric floats and basis identifiers.
   - Lines 195–196 explicitly assert that user input does not leak into the packet text:
     ```python
     if len(user_text.strip()) > 1 and user_text.strip() in packet_text:
         raise RuntimeError("raw user input leaked into the native graph packet")
     ```
   - Lines 237–238 record `packet_contains_raw_input: False` and `packet_contains_memory_text: False`.
   - `run_native()` (lines 243–276) invokes `DEFAULT_RUNNER` (`graph_soft_generator`) with model `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf` (lines 43–49).

2. **Topological Layers & Structural Mini-Maps (`src/habitus_ai/types.py` & `src/habitus_ai/graph.py`)**:
   - `ConceptNode` (`src/habitus_ai/types.py:87–99`) contains `structural_map: StructuralMiniMap | None = None`, `invocation_count: int = 0`, and `softmax_weight: float = 1.0`.
   - `StructuralMiniMap` (`src/habitus_ai/types.py:78–84`) defines `map_id`, `parent_node_ids`, `child_node_ids`, `relations: tuple[StructuralRelation, ...]`, and `total_coactivations: int`.
   - `compute_structural_overlay()` (`src/habitus_ai/graph.py:30–75`) synthesizes a 1024D vector directly from mini-map parent/child hash projections, relation coactivation densities, and concept `invocation_count` / `softmax_weight`.
   - `MindStore.update_softmax_weights_for_source()` (`src/habitus_ai/store.py:565–585`) updates `edges.softmax_weight` via Boltzmann softmax over `log_strength` with a conservation sum equal to 1.0.

3. **Existing Pytest Patterns (`tests/test_graph_native_live.py`, `tests/test_accelerated_gestation.py`, `tests/test_challenger_m3_1.py`)**:
   - `tests/test_graph_native_live.py:21–39` verifies `packet.read_text()` contains no raw input or memory text, and asserts `trace["output_trunk"] == "SPEAK"`.
   - `tests/test_challenger_m3_1.py:68–108` and `tests/test_challenger_m3_2.py:101–150` test boundary stimuli, float32 bounds, zero raw prompt text injection, and model receipts.

---

## 2. Logic Chain

1. **Premise 1 (R1 Continuous Cognitive Loop)**: To evaluate the continuous cognitive loop between Layer 4 semantic crown concepts and Layer 2/0 `SELF` preference nodes, the test suite must execute sequential turns, measure monotonic pulse increments, verify bidirectional `experience_projections` across layers (0, 1, 2, 3, 4), and assert that positive/negative stimuli shift `experience_state.preference_mean` and `GraphEdge.softmax_weight` accordingly.
2. **Premise 2 (Zero-Prompt Leakage Invariant)**: The Habitus-AI architecture enforces strict decoupling between linguistic prompts and continuous soft generation. Therefore, test cases must systematically verify that across standard, adversarial, SQL injection, script injection, and Unicode emoji inputs, neither the raw user prompt nor retrieved memory text appears in the generated `.packet` payload or the native model context receipt (`model_received_prompt_text == False`).
3. **Premise 3 (Layer 3 Mini-Map & Layer 4 Softmax Invariants)**: `compute_structural_overlay()` and `update_softmax_weights_for_source()` govern the conversion of graph topology into continuous geometry. Therefore, test assertions must verify L2 normalization ($\|v\|_2 = 1.0$), mathematical determinism, topological sensitivity, and that softmax weights across outgoing edges from any source sum strictly to $1.0 \pm 10^{-5}$.
4. **Premise 4 (Resilience & Evaluator Contracts)**: For robust live evaluation (`live_evaluator.py`), tests must verify bounded fallback behavior on novel out-of-vocabulary inputs (activating `{"speak": 1.0, "uncertain": 0.55, "clear": 0.45}`), graceful handling of empty/whitespace inputs, and full compatibility with the Python API and CLI JSON telemetry schemas.

---

## 3. Caveats

- **Native Binary Execution Dependency**: End-to-end execution of `run_native()` requires `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf` and the compiled `graph_soft_generator` binary. The designed test suite uses `@pytest.mark.skipif(not HAS_NATIVE_ASSETS)` so that all structural, invariant, loop, and packet tests run 100% reliably in any development/CI environment, while live GGUF generation executes whenever native assets are present.
- **Read-Only Explorer Scope**: Per instructions, no production source code has been modified and no tests have been executed during this exploration phase.

---

## 4. Conclusion

A comprehensive test suite architecture and concrete implementation design for `tests/test_cognitive_conversability.py` has been established and fully specified in `analysis.md`. The design comprises 4 major test classes with 12 distinct test cases covering:
1. `TestContinuousCognitiveLoop`: Single-turn lifecycle, multi-turn preference polarization, destabilization & recovery, and bidirectional feedback.
2. `TestZeroPromptLeakageInvariant`: Adversarial string rejection, float numerical bounds, and native runner receipt guarantees.
3. `TestLayer3StructuralMiniMapAndLayer4Softmax`: SQLite roundtrip persistence, `compute_structural_overlay` invariants, and softmax weight conservation ($\sum = 1.0$).
4. `TestLiveEvaluatorIntegrationAndEdgeCases`: Novel OOV bounded uncertainty fallback, minimal/empty input resilience, and live Qwen3 GGUF soft generation.

---

## 5. Verification Method

To independently verify the test suite once implemented:
1. **Source Inspection**:
   - Inspect `/home/nemo/habitus-ai-experiments/.agents/explorer_m5_3/analysis.md` for complete code and architectural rationale.
   - Inspect proposed test file `tests/test_cognitive_conversability.py`.
2. **Project Test Execution**:
   - Once implementation is authorized and completed, execute:
     ```bash
     PYTHONPATH=src:experiments/graph_native_live pytest -v tests/test_cognitive_conversability.py
     ```
   - Execute full test suite to ensure 100% pass rate:
     ```bash
     PYTHONPATH=src:experiments/graph_native_live pytest -v
     ```
3. **Invalidation Conditions**:
   - Any raw prompt substring appearing in a `.packet` buffer.
   - Softmax weights across outgoing edges from any node failing to sum to $1.0 \pm 10^{-5}$.
   - Unhandled exceptions or crashes on empty, single-character, or out-of-vocabulary stimuli.
