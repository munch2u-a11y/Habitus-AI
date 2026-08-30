# Milestone 5 Architecture Analysis: Continuous Cognitive Loop (R1)

**Working Directory**: `/home/nemo/habitus-ai-experiments/.agents/explorer_m5_1`  
**Author**: Explorer 1  
**Scope**: Codebase architectural exploration and design blueprint for the Continuous Cognitive Loop (R1), Layer 3 structural mini-maps, Layer 4 semantic membrane softmax edge weights, SELF preference nodes, zero-prompt continuous 1024D vector packet generation, and live evaluation suite.

---

## 1. System Topography & Layer Hierarchy

Habitus-AI couples an hourglass bicone memory topology with a native Qwen3 GGUF soft-input adapter. The hierarchy across the dual cipher (Input $+Y$ Perceptual and Output $-Y$ Effector trunks) spans five distinct structural layers:

```
                      Layer 4: Semantic Membrane & Lexeme Nodes
                      [ LXG:Lexical Geometry | Concept Crowns ]
                                    ▲       ▲
                                    │       │ (Softmax Edge Weights)
                      Layer 3: Structural Mini-Maps & Emergent Children
                      [ child:auto:* | map:child:* | map:crown:* ]
                                    ▲       ▲
                                    │       │ (Overlap Clustering & Coactivations)
                      Layer 2: Preference Node Bands
                      [ PREF:HEAR:STABLE | PREF:HEAR:UNSTABLE | ... ]
                                    ▲       ▲
                                    │       │
                      Layer 1: Input / Output Sensory Trunks
                      [ IN:HEAR | IN:SEE | IN:NOTICE ]   [ OUT:SPEAK | OUT:LOOK | OUT:DO ]
                                    ▲       ▼
                      Layer 0: Basal Identity Origin
                      [ SELF ("SELF") ]
```

---

## 2. Layer 3 Structural Mini-Maps & Layer 4 Semantic Membrane

### 2.1 Layer 3 Structural Mini-Map Representation
Layer 3 represents intermediate conceptual structure synthesized through unsupervised overlap clustering.

- **Data Models** (`src/habitus_ai/types.py`, lines 70–99):
  ```python
  @dataclass(frozen=True)
  class StructuralRelation:
      source_node_id: str
      target_node_id: str
      coactivation_density: float
      direction: str = "bidirectional"

  @dataclass(frozen=True)
  class StructuralMiniMap:
      map_id: str
      parent_node_ids: tuple[str, ...]
      child_node_ids: tuple[str, ...]
      relations: tuple[StructuralRelation, ...]
      total_coactivations: int

  @dataclass(frozen=True)
  class ConceptNode:
      concept_id: str
      label: str
      kind: str
      embedding: tuple[float, ...]
      terms: tuple[str, ...]
      vault_id: str | None
      created_pulse: int
      last_active_pulse: int
      structural_map: StructuralMiniMap | None = None
      invocation_count: int = 0
      softmax_weight: float = 1.0
  ```

- **Persistence & Serialization** (`src/habitus_ai/store.py`, lines 26–65, 142–153, 251–260):
  Stored in the SQLite table `concepts`:
  - `structural_map_json TEXT`: Stores `map_id`, `parent_node_ids`, `child_node_ids`, `relations` (with `source_node_id`, `target_node_id`, `coactivation_density`, `direction`), and `total_coactivations`.
  - `invocation_count INTEGER NOT NULL DEFAULT 0`: Incremented on each pulse activation.
  - `softmax_weight REAL NOT NULL DEFAULT 1.0`: Relative activation density weight.

- **Intrinsic Topological Vector Projection** (`src/habitus_ai/graph.py`, lines 30–75):
  The function `compute_structural_overlay(concept, store_or_graph, dimension=1024)` generates a 1024D vector directly from graph topology without textual prompt injection:
  1. Base vector starts from `concept.embedding` (or zero vector).
  2. Parent node projections:
     $$h_p = |\text{hash}(p\_id)| \pmod{1024}$$
     $$\text{overlay}[h_p] \mathrel{+}= \frac{1}{\text{idx} + 1} \cdot \ln(1 + \text{total\_coactivations})$$
  3. Child node projections:
     $$h_c = |\text{hash}(c\_id)| \pmod{1024}$$
     $$\text{overlay}[h_c] \mathrel{+}= \frac{0.5}{\text{idx} + 1} \cdot \ln(1 + \text{total\_coactivations})$$
  4. Structural relations:
     $$h_r = |\text{hash}(source \to target)| \pmod{1024}$$
     $$\text{overlay}[h_r] \mathrel{+}= \text{coactivation\_density}$$
  5. Scaled by invocation count and softmax weight:
     $$\text{multiplier} = \ln(1 + \text{invocation\_count}) \cdot \text{softmax\_weight}$$
  6. $L_2$ normalized to unit length: $\frac{\mathbf{v}}{\|\mathbf{v}\|_2}$.

### 2.2 Layer 4 Semantic Membrane & Softmax Edge Weights
The semantic membrane connects Layer 3 emergent children to Layer 4 semantic crown concepts and Layer 4 lexical geometry nodes (`LXG:*` / `LX:*`).

- **Dynamic Softmax Edge Weight Calculation** (`src/habitus_ai/store.py`, lines 555–585):
  For each source node $s$, outgoing edges have scores calculated as:
  $$S_e = \text{log\_strength}_e + \ln(1 + \text{invocation\_count}_e)$$
  $$\text{softmax\_weight}_e = \frac{\exp(S_e - \max_{e'} S_{e'})}{\sum_k \exp(S_k - \max_{e'} S_{e'})}$$
  When an edge is traversed, `increment_edge_invocation(edge_id)` increments `invocation_count` and triggers `update_softmax_weights_for_source(source_id)` to re-normalize softmax weights across the local outgoing frontier.

- **Weight Snapshot & Local Probabilities** (`src/habitus_ai/graph.py`, lines 336–384):
  `weight_snapshot(now)` includes dynamic exponential decay for recency:
  $$\text{recency} = \text{recency\_strength} \cdot \exp\left(-\ln(2) \cdot \frac{\text{age}}{\text{half\_life}}\right)$$
  $$\text{logit}_e = \text{log\_strength}_e + \text{recency}_e - \text{conflict\_penalty}_e$$
  Local transition probabilities from node $u$ are normalized:
  $$P(e \mid u) = \frac{\text{global\_weight}_e}{\sum_{e' \in \text{out}(u)} \text{global\_weight}_{e'}}$$

- **Y-Axis Traversal Resistance** (`src/habitus_ai/graph.py`, lines 387–466):
  Dijkstra traversal calculates shortest-path resistance along the Y-axis:
  $$\text{edge\_time}_e = \frac{\Delta y_e}{10^{-6} + P(e \mid u)} + \text{conflict\_penalty}_e$$
  High conflict penalties or low probabilities exponentially increase traversal resistance, diverting the system away from destabilizing or unreinforced conceptual pathways.

---

## 3. SELF Preference Node Activation & Update Dynamics

### 3.1 Topology Seeding (`graph.py`, lines 191–243)
1. Origin node `SELF` (Layer 0) is seeded with vault `lower-vault:SELF`.
2. Edges connect `SELF` to Input Trunks (`IN:HEAR`, `IN:SEE`, `IN:NOTICE`) with $\Delta y = 1.0$.
3. Each Input Trunk connects to 3 basal preference bands (Layer 2):
   - `PREF:HEAR:STABLE`, `PREF:HEAR:NEUTRAL`, `PREF:HEAR:UNSTABLE`
   - `PREF:SEE:STABLE`, `PREF:SEE:NEUTRAL`, `PREF:SEE:UNSTABLE`
   - `PREF:NOTICE:STABLE`, `PREF:NOTICE:NEUTRAL`, `PREF:NOTICE:UNSTABLE`
4. Output Trunks (`OUT:SPEAK`, `OUT:LOOK`, `OUT:DO`) connect from `SELF` with $\Delta y = 1.0$.

### 3.2 Ingestion & Experience Deposition (`pipeline.py` & `graph.py`)
1. Stimulus arrives in `remember(text, kind, metadata)`:
   - Routed by `route_event(envelope)` to sensory trunk (`HEAR` for conversations, `SEE` for tool observations, `NOTICE` for alerts).
2. `_preference_signal(metadata)` extracts preference mean $p \in [-1.0, 1.0]$ and confidence $c \in [0.0, 1.0]$:
   - Maps to `"STABLE"` ($p > 0.05$), `"UNSTABLE"` ($p < -0.05$), or `"NEUTRAL"`.
   - Resolves target preference node: `PREFERENCE_NODE_IDS[(input_trunk, band)]`.
3. `deposit_experience(record, input_trunk, pulse)` (`graph.py`, lines 631–675):
   - Updates `experience_state` running mean and confidence.
   - Writes `ExperienceProjection` entries at Layer 0 (`SELF`), Layer 1 (`IN:<trunk>`), and Layer 2 (`PREF:<trunk>:<band>`).
   - Links records into respective lower vaults.

### 3.3 Reinforcement & Adaptive Steering
- `reinforce_edges(edge_ids, stability_delta, verified, evidence_quality)` (`graph.py`, lines 508–539):
  $$\text{change} = \text{learning\_rate} \cdot \text{stability\_delta} \cdot \text{evidence\_quality} \cdot \frac{1}{|\text{credited}|}$$
  - **Positive reinforcement** ($\text{stability\_delta} > 0$): Increases `log_strength` by $\text{change}$ and reduces `conflict_penalty`:
    $$\text{conflict\_penalty} = \max(0.0, \text{conflict\_penalty} - |\text{change}| \cdot 0.10)$$
  - **Negative reinforcement / Instability** ($\text{stability\_delta} < 0$): Decreases `log_strength` and increases `conflict_penalty`:
    $$\text{conflict\_penalty} = \min(10.0, \text{conflict\_penalty} + |\text{change}| \cdot 0.25)$$
- **Impact on Conversational Steering**:
  When an adversarial stimulus or destabilizing interaction triggers negative outcomes, the increased `conflict_penalty` elevates Y-traversal resistance along that path. Dijkstra traversal automatically reroutes future outputs toward avoidant, neutral, or self-stabilizing endpoints.

---

## 4. Continuous 1024D Vector Packet Encoding for Native GGUF

### 4.1 Zero-Prompt Leakage Invariant
The native bridge guarantees that **no prompt text, user input, or retrieved memory text** is serialized into the model context. The model generates responses purely from continuous 1024D soft-input vector rows.

### 4.2 Packet Formats Consumed by `graph_soft_generator`

| Format | Header | Body Structure | Used In |
|---|---|---|---|
| **Soft Packet V1** | `HABITUS_SOFT_PACKET_V1` | `<basis_id> <activation_float>` (up to 8 lines) | `live_tester.py` |
| **Opaque Packet V1** | `HABITUS_OPAQUE_PACKET_V1` | `1024 <num_rows>` followed by rows of 1024 space-separated floats | `opaque_skeleton.py`, `transformer_hatch.py` |

### 4.3 Native Execution Pipeline (`graph_soft_generator.cpp`)
1. **Model Loading**: Loads `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf` using `llama.cpp` C API (`n_embd = 1024`).
2. **Structural Enveloping**:
   - Fixed prefix tokens: `<|im_start|>user\n` $\to$ token embeddings via `exact_input_embeddings()`.
   - Fixed suffix tokens: `<|im_end|>\n<|im_start|>assistant\n` (optionally `<think>\n\n</think>\n\n` via `HABITUS_NATIVE_SKIP_THINK=1`).
3. **Continuous Embedding Calibration**:
   - For Soft Packets: `semantic_slot()` averages anchor token embeddings from `BASIS` table, scales to norm shell:
     $$\text{scale} = \text{target\_norm} \cdot \frac{0.85 + 0.30 \cdot \text{activation}}{\text{current\_norm}}$$
   - For Opaque Packets: `place_on_embedding_shell()` normalizes raw 1024D vector rows to the mean norm of prefix/suffix tokens:
     $$\text{scale} = \frac{\text{target\_norm}}{\text{current\_norm}}$$
4. **Direct Batch Injection**:
   ```cpp
   llama_batch batch{};
   batch.n_tokens = input_rows; // structural rows + soft slot rows
   batch.embd = input_embeddings.data(); // continuous 1024D float buffer
   llama_decode(context.ptr, batch);
   ```
5. **Autoregressive Logit Sampling**:
   Samples tokens using top-k (40), top-p (0.90), temperature (0.70), and emission until EOG.

### 4.4 Lexical Row Ordering in `transformer_hatch.py`
In `ordered_lexical_rows()`, instead of arbitrary sorting, lexical geometry vectors are arranged by following directed output transition edges:
```python
transition = mind.store.find_edge(GraphSide.OUTPUT, source_lexeme, target_lexeme)
# Ranked by transition.log_strength to preserve syntactical / developmental word flow
```

---

## 5. Architectural Recommendations for Milestone 5 (R1)

### 5.1 `experiments/graph_native_live/live_evaluator.py`
The live evaluator must provide a complete continuous cognitive loop runner with real-time feedback, state tracking, and performance evaluation.

```
+--------------------------------------------------------------------------------+
|                        Cognitive Loop Architecture                             |
|                                                                                |
|  [ Stimulus Input ]                                                            |
|          │                                                                     |
|          ▼                                                                     |
|  [ Ingest & Routing ] ─────────► [ SELF Preference Node Update (Layer 2) ]     |
|          │                                                                     |
|          ▼                                                                     |
|  [ Surface Nomination ]                                                        |
|          │                                                                     |
|          ▼                                                                     |
|  [ Y-Axis Dijkstra Traversal ] ──► [ Layer 3 Mini-Map Activation ]            |
|          │                                                                     |
|          ▼                                                                     |
|  [ Continuous 1024D Packet Synthesis ]                                         |
|    - Layer 3 structural overlay (`compute_structural_overlay`)                 |
|    - Layer 4 softmax edge weights (`update_softmax_weights_for_source`)        |
|    - Directed lexeme transitions                                               |
|          │                                                                     |
|          ▼                                                                     |
|  [ Native GGUF Soft-Input Generator (`graph_soft_generator`) ]                 |
|          │                                                                     |
|          ▼                                                                     |
|  [ Plain Language Generation ]                                                 |
|          │                                                                     |
|          ▼                                                                     |
|  [ Output Classification & Outcome Reinforcement (`record_outcome`) ]          |
|    - Edge reinforcement ($\Delta \text{log\_strength}$, $\Delta \text{penalty}$)   |
|    - Cognitive State Metric Logging                                            |
+--------------------------------------------------------------------------------+
```

#### Core Components to Implement in `live_evaluator.py`:
1. **`CognitiveEvaluationEngine`**:
   - Manages persistent or ephemeral `BaseAgenticMemoryRAG` substrate.
   - Executes multi-turn stimulus sequences.
   - Handles closed-loop outcome feedback (`record_outcome`) after each turn.
2. **`synthesize_cognitive_packet(mind, recall_result, target_concept_id, packet_path)`**:
   - Blends Layer 3 mini-map structural overlay (`compute_structural_overlay()`) with Layer 4 active lexical geometry and softmax edge weights.
   - Writes `HABITUS_OPAQUE_PACKET_V1` or `HABITUS_SOFT_PACKET_V1`.
   - Validates zero raw prompt/memory text leakage before execution.
3. **Metrics Tracking**:
   - `preference_delta`: Drift in `experience_state.preference_mean`.
   - `softmax_entropy`: Entropy of Layer 4 outgoing edge weights.
   - `traversal_resistance`: Dijkstra travel time across input and output paths.
   - `generation_latency_ms`: Time taken by native runner.
   - `leakage_check_passed`: Boolean validation of prompt text absence.
4. **CLI & Artifacts**:
   - Accepts `--database`, `--model`, `--runner`, `--eval-curriculum`, `--turns`, `--json-receipt`.
   - Generates structured JSON receipts under `experiments/graph_native_live/evaluator_runs/`.

### 5.2 `tests/test_cognitive_conversability.py`
A comprehensive pytest test suite validating the continuous cognitive loop and its behavioral properties.

#### Recommended Test Classes & Fixtures:
1. **`TestContinuousCognitiveLoop`**:
   - Multi-turn interaction loop test: Verifies that consecutive turns maintain state continuity, increment pulse counters, and update experience projections.
   - Convergence test: Tests that repeated positive reinforcement on a topic increases edge softmax weights and reduces traversal time.
2. **`TestLayer3MiniMapFidelity`**:
   - Verifies that `compute_structural_overlay()` reflects topological changes in parent/child node IDs, total coactivations, and invocation counts.
   - Asserts that distinct Layer 3 topologies generate distinct 1024D vector overlays.
3. **`TestLayer4SemanticMembraneSoftmaxWeights`**:
   - Verifies `update_softmax_weights_for_source()` correctly normalizes outgoing edges to sum to $1.0$.
   - Confirms that edge reinforcement dynamically shifts the softmax probability distribution toward preferred pathways.
4. **`TestSelfPreferenceModulation`**:
   - Verifies that positive vs negative stimuli deposit into `PREF:HEAR:STABLE` vs `PREF:HEAR:UNSTABLE`.
   - Asserts that conflict penalties from negative stimuli dynamically steer subsequent output traversals away from penalized paths.
5. **`TestZeroPromptLeakage`**:
   - Forensic check verifying that no user input string, memory text, or RAG context appears in the emitted `.packet` or native execution logs.
   - Verifies `native["model_received_prompt_text"] == False` and `native["model_received_user_tokens"] == False`.

---

## 6. Synthesis & Summary Table

| Architectural Dimension | Current Implementation | Milestone 5 Integration Objective |
|---|---|---|
| **Layer 3 Mini-Maps** | `StructuralMiniMap` in `store.py` / `graph.py` with `compute_structural_overlay` | Fully integrated into cognitive vector synthesis for `live_evaluator.py` |
| **Layer 4 Membrane** | `edges.softmax_weight` + `update_softmax_weights_for_source` | Softmax weight dynamic modulation across multi-turn conversational loops |
| **SELF Preference** | `PREFERENCE_NODE_IDS` (`STABLE`, `NEUTRAL`, `UNSTABLE`) | Closed-loop feedback altering Y-traversal resistance based on outcome stability |
| **Native Vector Bridge** | `graph_soft_generator` taking 1024D continuous packets | End-to-end evaluation without prompt serialization or semantic codebooks |
| **Verification Suite** | Isolated unit and gestation tests | Unified `test_cognitive_conversability.py` and `live_evaluator.py` |
