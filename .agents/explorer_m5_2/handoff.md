# Milestone 5 Explorer 2 Handoff Report: Architecture Design for `live_evaluator.py`

## 1. Observation

Direct code and architectural observations across the Habitus-AI repository:

1. **Native Runner & Packet Ingestion (`experiments/graph_native_live/native/graph_soft_generator.cpp`)**:
   - Lines 53–59: Defines `struct Packet { bool opaque; int32_t dimension; int32_t rows; vector<Activation> activations; vector<float> values; };`
   - Lines 215–277: `load_packet()` supports two headers:
     - `HABITUS_OPAQUE_PACKET_V1`: parses dense float rows with shape `<dimension> <rows>` (up to 8 rows of 1024D).
     - `HABITUS_SOFT_PACKET_V1`: parses `<basis> <value>` pairs (up to 8 slots from `BASIS` dictionary).
   - Lines 279–318: `place_on_embedding_shell()` calibrates opaque vectors onto the native Qwen3 embedding norm shell.
   - The native runner never receives raw user prompt text or token ID sequences.

2. **Prototype Live Runner (`experiments/graph_native_live/live_tester.py`)**:
   - Lines 119–165: `_activation_packet()` maps admitted surface candidates to soft basis activations and outputs Dijkstra traversal traces.
   - Lines 168–240: `compile_turn()` deposits memory records into `mind.remember()`, compiles the packet, and verifies that raw input is excluded (`packet_contains_raw_input: False`).
   - Lines 279–322: `one_turn()` executes `run_native()`, records outbound response in `mind.remember()`, and writes JSON turn receipt (`turn-*.json`).

3. **Continuous Geometry & Lexical Transitions (`experiments/graph_native_live/transformer_hatch.py`)**:
   - Lines 85–151: `graph_state_rows()` extracts concept centroid, weighted reverse nursery state, and productive lexical fibers.
   - Lines 153–214: `ordered_lexical_rows()` sequences 1024D lexical embeddings along learned directed graph transitions (`mind.store.find_edge(GraphSide.OUTPUT, source, target)`).
   - Lines 289–300: `opaque_skeleton.write_packet()` writes `HABITUS_OPAQUE_PACKET_V1` with `<dimension> <rows>`.

4. **Dual-Cipher Substrate & Structural Mini-Maps (`src/habitus_ai/`)**:
   - `types.py:70-85`: Defines `StructuralRelation` (`source_node_id`, `target_node_id`, `coactivation_density`) and `StructuralMiniMap` (`map_id`, `parent_node_ids`, `child_node_ids`, `relations`, `total_coactivations`).
   - `types.py:87-116`: `ConceptNode` and `GraphEdge` carry `structural_map`, `invocation_count`, and `softmax_weight`.
   - `graph.py:30-75`: `compute_structural_overlay()` dynamically projects topological mini-map coactivations and softmax weights into a 1024D overlay.
   - `graph.py:78-86`: Defines `SELF_ID = "SELF"`, `INPUT_NODE_IDS` (`IN:HEAR`, `IN:SEE`, `IN:NOTICE`), `OUTPUT_NODE_IDS` (`OUT:SPEAK`, `OUT:LOOK`, `OUT:DO`), and `PREFERENCE_NODE_IDS` (`PREF:<trunk>:<band>`).
   - `graph.py:336-383`: `weight_snapshot()` and `local_probabilities()` compute temperature-scaled softmax probabilities over `log_strength + recency - conflict_penalty`.
   - `graph.py:387-466`: `traverse()` computes shortest Y-axis paths starting at `SELF` with travel time $t = \frac{\Delta Y}{10^{-6} + P(e)} + \text{penalty}$.
   - `graph.py:508-539`: `reinforce_edges()` updates `log_strength` and `conflict_penalty` based on verified outcome stability $\Delta$.

---

## 2. Logic Chain

1. **From Bootstrap to Autonomous Cognitive Loop**:
   - *Observation 2* shows that `live_tester.py` demonstrated a single-turn proof-of-concept using a fixed seed basis.
   - *Observation 4* shows that the core Habitus engine now has complete structural mini-maps (`StructuralMiniMap`), Layer 2 preference nodes (`PREF:*`), and Layer 4 softmax membrane edge weights.
   - *Inference*: `live_evaluator.py` can orchestrate an end-to-end multi-turn cognitive loop where each turn updates Layer 2 preference states, traverses Layer 3 mini-maps, computes Layer 4 softmax weights, and updates edge plasticities via outcome reinforcement.

2. **From Soft Basis to Multi-Modal 1024D Vector Synthesis**:
   - *Observation 1 & 3* confirm that the native C++ generator accepts both `HABITUS_SOFT_PACKET_V1` and `HABITUS_OPAQUE_PACKET_V1` (up to 8 dense 1024D rows).
   - *Inference*: `live_evaluator.py` should implement three configurable packet strategies:
     1. `lexical_membrane`: Concept centroid + blended reverse nursery state + ordered lexeme transitions.
     2. `opaque_topological`: Input path slot + Layer 4 edge slot + Temporal stability slot + Output path slot.
     3. `soft_basis`: Admitted candidate soft basis anchors for backward compatibility.

3. **From Ephemeral Runs to Auditable JSON Telemetry**:
   - *Observation 2 & 4* show that all graph events, traces, and edge weights are fully serializable.
   - *Inference*: `live_evaluator.py` must emit structured JSON state reports (`habitus.cognitive-eval-turn.v1` and `habitus.cognitive-eval-session.v1`), capturing input SHA256, Layer 2 preference shifts, Layer 3 mini-map snapshots, Layer 4 softmax distributions, travel times, packet hashes, and zero-prompt leakage verification.

---

## 3. Caveats

1. **GGUF Model Dependency**: Soft-input row calibration assumes Qwen3-0.6B-Q8_0 with 1024D native hidden dimension. If run with a fallback model (e.g. Qwen2.5 0.5B with 896D), vector dimensions must match model width.
2. **C++ Native Runner Build**: `live_evaluator.py` assumes `experiments/graph_native_live/native/graph_soft_generator` is compiled.
3. **No External Network**: As in all Habitus-AI modules, execution is local and train-free; no external APIs are invoked.

---

## 4. Conclusion

The architectural design for `live_evaluator.py` provides:
1. **A Modular Python & CLI API**: `LiveEvaluator`, `EvaluatorConfig`, `TurnTelemetry`, supporting interactive, batch, and benchmark execution.
2. **Continuous 4-Layer Cognitive Loop**: Seamless integration between Layer 1 basal origin (`SELF`), Layer 2 preference matrix (`PREF:*`), Layer 3 structural mini-maps, and Layer 4 softmax membrane edge weights.
3. **Robust Multi-Turn Pipeline**: Input ingestion $\to$ preference update $\to$ Y-axis traversal $\to$ 1024D packet synthesis $\to$ native GGUF soft generation $\to$ outcome reinforcement.
4. **Comprehensive Export & Verification Schema**: Strict invariant audits (mass conservation, reachability, 100% zero-prompt leakage) and detailed JSON receipt generation.

Detailed implementation design is fully documented in `.agents/explorer_m5_2/analysis.md`.

---

## 5. Verification Method

1. **Inspect Analysis Report**:
   - View `/home/nemo/habitus-ai-experiments/.agents/explorer_m5_2/analysis.md` for class definitions, mathematical formulation, CLI parameters, and JSON schemas.
2. **Verify Interface Compatibility**:
   - Compare `live_evaluator.py` design against `src/habitus_ai/graph.py:30-75` (`compute_structural_overlay`), `src/habitus_ai/graph.py:387-466` (`traverse`), and `experiments/graph_native_live/native/graph_soft_generator.cpp:215-277` (`load_packet`).
3. **Target Test Execution (Upon Implementation)**:
   - `PYTHONPATH=src:experiments/graph_native_live pytest -v tests/test_graph_native_live.py tests/test_cognitive_conversability.py`
   - Command: `python3 experiments/graph_native_live/live_evaluator.py --mode once --stimulus-text "hello there" --show-trace`
