# Handoff Report: Milestone 5 Continuous Cognitive Loop (R1)

**Working Directory**: `/home/nemo/habitus-ai-experiments/.agents/explorer_m5_1`  
**Author**: Explorer 1  
**Target Audience**: Orchestrator / Implementer  
**Milestone**: M5 — Autonomous Cognitive Conversability & Adversarial Behavior Suite (R1 Continuous Cognitive Loop)

---

## 1. Observation

Direct observations from codebase inspection across `src/habitus_ai/` and `experiments/graph_native_live/`:

1. **Layer 3 Structural Mini-Maps & Layer 4 Softmax Weights**:
   - `src/habitus_ai/types.py` (lines 70–99): `StructuralRelation` and `StructuralMiniMap` define topological relations, parent/child IDs, and coactivation density. `ConceptNode` and `GraphEdge` include `structural_map`, `invocation_count`, and `softmax_weight`.
   - `src/habitus_ai/store.py` (lines 26–65, 142–153, 555–585): `concepts` and `edges` tables persist structural mini-maps as JSON and record `invocation_count` and `softmax_weight`. `update_softmax_weights_for_source(source_id)` dynamically recomputes softmax weights using $S_e = \text{log\_strength}_e + \ln(1 + \text{invocation\_count}_e)$ and $\text{softmax\_weight}_e = \frac{\exp(S_e - \max S)}{\sum \exp(S - \max S)}$.
   - `src/habitus_ai/graph.py` (lines 30–75): `compute_structural_overlay()` computes a 1024D vector projection from parent/child hash slots, coactivation density, invocation count, and softmax weight.

2. **SELF Preference Nodes & Reinforcement Dynamics**:
   - `src/habitus_ai/graph.py` (lines 78–86, 191–243): Seed topology establishes `SELF` (Layer 0) connected to `IN:HEAR`, `IN:SEE`, `IN:NOTICE` (Layer 1), which each branch into 3 preference bands (`STABLE`, `NEUTRAL`, `UNSTABLE`) (Layer 2).
   - `src/habitus_ai/graph.py` (lines 508–539): `reinforce_edges()` modifies `log_strength` and `conflict_penalty`. Negative stability deltas ($\Delta < 0$) increase `conflict_penalty` ($\text{penalty} \mathrel{+}= |\text{change}| \cdot 0.25$), increasing Dijkstra traversal resistance: $\text{edge\_time} = \frac{\Delta y}{10^{-6} + P} + \text{conflict\_penalty}$.

3. **1024D Vector Packet Generation & Zero-Prompt Leakage**:
   - `experiments/graph_native_live/live_tester.py` (lines 188–196): Emits `HABITUS_SOFT_PACKET_V1` with up to 8 basis activation floats.
   - `experiments/graph_native_live/opaque_skeleton.py` (lines 289–299) & `transformer_hatch.py` (lines 234–250): Emit `HABITUS_OPAQUE_PACKET_V1` with $1024 \times N$ continuous float rows.
   - `experiments/graph_native_live/native/graph_soft_generator.cpp` (lines 366–413): Places continuous rows onto the embedding norm shell (`place_on_embedding_shell`), wraps with fixed structural tokens (`<|im_start|>user\n` and `<|im_end|>\n<|im_start|>assistant\n`), injects directly into `llama_batch.embd`, and runs inference without user prompt text or RAG context strings.

4. **Existing Gestation & Test Suite Patterns**:
   - `experiments/graph_native_live/accelerated_gestation.py` (lines 940–1000): Fast gestation creates topic concepts, mirrored output paths, and lexical membranes.
   - `tests/test_graph_native_live.py` and `tests/test_challenger_m3_1.py`: Establish patterns for testing zero prompt leakage (`assert trace["packet_contains_raw_input"] is False`, `assert native["model_received_prompt_text"] is False`).

---

## 2. Logic Chain

1. **Topological Representation $\to$ Vector Synthesis**:
   - Layer 3 structural mini-maps capture conceptual co-activations and hierarchical links. Layer 4 captures lexical bindings and transition weights.
   - `compute_structural_overlay()` in `graph.py` provides the mathematical mechanism to translate these topological graph properties into dense 1024D vector coordinates without textual descriptions.

2. **Stimulus Ingestion $\to$ SELF Preference $\to$ Softmax Edge Weight Modulation**:
   - When input stimuli arrive, `deposit_experience()` maps preference signals into Layer 2 preference bands (`STABLE` vs `UNSTABLE`).
   - Outcome recording via `record_outcome()` applies `reinforce_edges()`, which shifts `log_strength` and `conflict_penalty`.
   - `update_softmax_weights_for_source()` updates local probability distributions.
   - As a result, subsequent Dijkstra traversals along the Y-axis prefer stabilized paths and avoid penalized paths.

3. **Continuous Soft-Input Bridge $\to$ Zero-Prompt Invariant**:
   - The native C++ bridge `graph_soft_generator` operates on 1024D floating point arrays mapped directly to `llama_batch.embd`.
   - The model context never contains raw user messages or memory strings, ensuring 100% compliance with the zero-prompt leakage invariant.

4. **Synthesis for Milestone 5 (R1)**:
   - Implementing `live_evaluator.py` requires uniting `remember()` $\to$ `recall()` $\to$ Layer 3/4 vector synthesis $\to$ `graph_soft_generator` execution $\to$ `classify_output()` $\to$ `record_outcome()` in a continuous multi-turn evaluation loop.
   - Implementing `test_cognitive_conversability.py` requires testing closed-loop reinforcement, mini-map vector fidelity, preference-driven steering, and zero-prompt leakage invariants under pytest.

---

## 3. Caveats

1. **Read-Only Scope**: This analysis was performed under read-only exploration constraints. No source code was modified, and no tests or benchmarks were executed.
2. **Model File Dependency**: The native generator defaults to `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf` (1024D input dimension) with fallback to local Qwen 2.5 0.5B.
3. **Pre-compiled Binaries**: `graph_soft_generator` and `lexeme_codec` binaries are already built in `experiments/graph_native_live/native/`.

---

## 4. Conclusion

The architecture of Habitus-AI is fully equipped to support Milestone 5 (R1 Continuous Cognitive Loop):
- Layer 3 structural mini-maps and Layer 4 semantic membrane softmax edge weights are well-defined in `types.py`, `store.py`, and `graph.py`.
- The SELF preference node hierarchy dynamically adapts traversal resistance through `reinforce_edges()` and `conflict_penalty`.
- The native `graph_soft_generator` binary accepts continuous 1024D float packets via `HABITUS_OPAQUE_PACKET_V1` and `HABITUS_SOFT_PACKET_V1`, maintaining zero prompt text leakage.
- Clear structural blueprints and test specifications have been designed for `experiments/graph_native_live/live_evaluator.py` and `tests/test_cognitive_conversability.py`.

---

## 5. Verification Method

To independently verify the findings in this report:

1. **Inspect Data Models & Schema**:
   - Check `src/habitus_ai/types.py` (lines 70–115) for `StructuralMiniMap`, `StructuralRelation`, `ConceptNode`, `GraphEdge`.
   - Check `src/habitus_ai/store.py` (lines 142–170, 555–585) for SQLite schema and `update_softmax_weights_for_source`.
   - Check `src/habitus_ai/graph.py` (lines 30–75, 508–539) for `compute_structural_overlay()` and `reinforce_edges()`.

2. **Inspect Vector Packets & Native Soft-Input Generator**:
   - Check `experiments/graph_native_live/live_tester.py` (lines 188–240) for `compile_turn()`.
   - Check `experiments/graph_native_live/opaque_skeleton.py` (lines 289–326) for `write_packet()` and `run_native()`.
   - Check `experiments/graph_native_live/native/graph_soft_generator.cpp` (lines 220–277, 366–413) for packet parsing and `llama_batch.embd` injection.

3. **Planned Test Command for Milestone 5 Execution**:
   - `PYTHONPATH=src:experiments/graph_native_live pytest -v tests/test_cognitive_conversability.py`
