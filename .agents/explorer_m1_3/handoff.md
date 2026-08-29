# Handoff Report: Milestone 1 - Core Habitus Substrate & Preference Matrix

**Agent**: `explorer_m1_3`  
**Working Directory**: `/home/nemo/habitus-ai-experiments/.agents/explorer_m1_3`  
**Report Type**: Hard Handoff (Investigation Complete)

---

## 1. Observation

Direct code observations from the Habitus-AI repository (`src/habitus_ai/` and `experiments/graph_native_live/`):

1. **Topology & Invariants**:
   - `SELF` root origin and $+Y$/$-Y$ frontiers defined in `src/habitus_ai/graph.py:28-36` and seeded in `src/habitus_ai/graph.py:141-193`:
     ```python
     SELF_ID = "SELF"
     INPUT_NODE_IDS = {trunk: f"IN:{trunk.value}" for trunk in InputTrunk}
     OUTPUT_NODE_IDS = {trunk: f"OUT:{trunk.value}" for trunk in OutputTrunk}
     PREFERENCE_BANDS = ("STABLE", "NEUTRAL", "UNSTABLE")
     ```
   - Invariant validation in `src/habitus_ai/graph.py:490-543` (`validate_invariants()`) asserts:
     - `SELF` is present (`line 492`).
     - Input frontier is strictly `HEAR`, `SEE`, `NOTICE` (`lines 527-528`).
     - Output frontier is strictly `SPEAK`, `LOOK`, `DO` (`lines 529-530`).
     - Global edge mass sums to $1.0 \pm 10^{-9}$ (`lines 509-510`).
     - Local outgoing frontiers each sum to $1.0 \pm 10^{-9}$ (`lines 514-518`).
     - Lower child nodes carry zero embedding and no lexical terms (`lines 536-537`).

2. **Conserved Weight Normalization**:
   - In `src/habitus_ai/graph.py:286-309`, global weights are computed via softmax:
     ```python
     logits[edge.edge_id] = edge.log_strength + recency - edge.conflict_penalty
     maximum = max(logits.values())
     exponentials = {
         edge_id: math.exp((value - maximum) / self.temperature)
         for edge_id, value in logits.items()
     }
     total = sum(exponentials.values()) or 1.0
     ```
   - Local outgoing probabilities are partitioned per node in `src/habitus_ai/graph.py:311-333`:
     ```python
     total = sum(snap.global_weights.get(edge.edge_id, 0.0) for edge in outgoing)
     return {
         edge.edge_id: snap.global_weights.get(edge.edge_id, 0.0) / total
         for edge in outgoing
     }
     ```

3. **Y-Axis Traversal Travel Time**:
   - In `src/habitus_ai/graph.py:377-380`:
     ```python
     probability = local.get(edge.edge_id, 0.0)
     edge_time = (
         edge.delta_y / (1e-6 + probability)
         + edge.conflict_penalty
     )
     ```
   - Semantic score is decoupled from $Y$ resistance: `endpoint_score` is stored for telemetry but never enters `edge_time` (`src/habitus_ai/graph.py:377-380, 411-412`).

4. **Immutable SQLite Records & Multi-Resolution Experience Storage**:
   - `src/habitus_ai/store.py:80-88` implements triggers blocking record updates and deletes:
     ```sql
     CREATE TRIGGER IF NOT EXISTS records_are_immutable_update
     BEFORE UPDATE ON records BEGIN
         SELECT RAISE(ABORT, 'canonical records are immutable');
     END;
     ```
   - `src/habitus_ai/store.py:160-173` establishes `experience_projections` without text fields.
   - `src/habitus_ai/store.py:558-604` updates confidence-weighted running means in `experience_state` and synchronizes all projection rows sharing the `experience_id`.

5. **Clustering & Promotion Dynamics**:
   - In `src/habitus_ai/graph.py:698-878` (`stage_growth`):
     - Calculates cosine similarity against parent vault cluster centroids (`line 737`).
     - Enforces `abs(preference - cluster.preference_mean) <= tolerance` (`line 740`).
     - Promotion requires distinct experiences $\ge \max(\text{base\_count}, \lceil\log_2(\text{parent\_vault\_experiences}+1)\rceil)$ (`lines 724-727`).
     - Creates unlabelled child (`kind="child"`, embedding $[0.0]\times 1024$) and crown semantic port (`kind="crown"`, embedding = cluster centroid) (`lines 806-832`).

6. **Continuous Activation Extraction & Vector Serialization**:
   - In `experiments/graph_native_live/opaque_skeleton.py:224-283` (`encode_state`):
     - Serializes multi-slot 1024D vectors (Input Y-path slot, Output Y-path slot, Edge Mass slot, Temporal Recency/Polarity slot).
   - In `experiments/graph_native_live/transformer_hatch.py:85-214`:
     - Extracts ordered lexical rows based on directed output transitions (`ordered_lexical_rows`).
   - In `experiments/graph_native_live/opaque_skeleton.py:289-299` (`write_packet`):
     - Writes `HABITUS_OPAQUE_PACKET_V1` with `<dimension> <rows>` followed by float rows.
   - In `experiments/graph_native_live/native/graph_soft_generator.cpp:122-213`:
     - Reads `token_embd.weight`, normalizes soft slots to the target model embedding shell, and injects rows directly into the transformer forward pass.

---

## 2. Logic Chain

1. **Topological Separation & Invariant Guarantees** (supported by Observation 1):
   - The bicone structure with `SELF` at $(0,0,0)$ cleanly decouples sensory intake ($+Y$ trunks) from motor execution ($-Y$ trunks).
   - Because both input and output sides terminate at shared crown concepts and vaults, concepts act as dual-facet bridges (perceptual recognition on $+Y$, action/speech initiation on $-Y$).

2. **Zero-Drift Routing via Fluid Edge Mass** (supported by Observations 2 & 3):
   - Because all live edges are normalized globally via softmax ($\sum w = 1.0$) and locally partitioned ($\sum p_{\text{local}} = 1.0$), strengthening a successful path necessarily reduces competitor paths without unbounded score inflation.
   - Decoupling semantic score ($X$-axis) from $Y$ traversal ensures that semantic similarity only identifies destination candidates, while structural familiarity determines the lowest-resistance traversal path.

3. **Multi-Resolution Dual-Authority Memory** (supported by Observation 4):
   - Full natural-language statements and 1024D embeddings remain strictly canonical and immutable in SQLite `records`.
   - Structural nodes and projections in `experience_projections` remain language-free, storing only numeric activations, preferences, and confidences.
   - Subsequent outcome feedback updates the running mean preference for an `experience_id`, updating all layer projections without corrupting or modifying canonical text.

4. **Self-Organizing Concept Formation** (supported by Observation 5):
   - Incoming stimuli cluster based on embedding cosine similarity and preference compatibility.
   - When evidence exceeds logarithmic support thresholds, the engine grows a two-stage hierarchy: an unlabeled lower structural pattern node (Layer 3) bridged to a semantic crown port (Layer 4).

5. **Soft-Input Plain Language Synthesis** (supported by Observation 6):
   - The graph state (concept centroid, Y-traversal paths, conserved edge mass, and ordered productive lexeme transitions) encodes directly into 1024D continuous float vectors.
   - The native C++ GGUF adapter ingests these continuous slot packets directly into the transformer embedding space, generating coherent language continuations reflecting internal preference states without raw text prompt serialization.

---

## 3. Caveats

1. **Model Weight Availability**: Native soft-input generation and lexical tokenization assume `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf` and compiled binaries in `experiments/graph_native_live/native/`. If the model path is missing or different, offline fallback embedders (`DeterministicHashEmbedder`, `OpaqueIdentityEmbedder`) are used.
2. **Destructive Merging**: Merging of duplicate concept clusters is intentionally not implemented in this version (as documented in `ARCHITECTURE.md:191-193`); distinct branches remain linked by reversible bridges.
3. **No Unverified Actions**: The substrate stops at classification; external action execution requires an external gateway harness to supply `ActionReceipt` with a valid `receipt_id`.

---

## 4. Conclusion

Milestone 1 Core Habitus Substrate & Preference Matrix (`src/habitus_ai/`) provides a complete, mathematically conserved, multi-resolution cognitive substrate:
- Graph topology is strictly structured across 5 distinct layers with conserved edge mass and Y-axis traversal dynamics.
- Stimulus experiences update running preference states and trigger logarithmic evidence-backed concept promotion.
- Graph activation states serialize cleanly into multi-slot 1024D vectors formatted for native GGUF soft-input ingestion.

---

## 5. Verification Method

To independently verify the substrate architecture and findings without mutating production code:

1. **Inspect Invariant & Topology Definitions**:
   ```bash
   # Verify GraphRuntime invariants and seed topology
   grep -n "def validate_invariants" src/habitus_ai/graph.py
   grep -n "def seed_topology" src/habitus_ai/graph.py
   ```
2. **Inspect SQLite Authority & Triggers**:
   ```bash
   grep -n "records_are_immutable" src/habitus_ai/store.py
   grep -n "CREATE TABLE IF NOT EXISTS experience_projections" src/habitus_ai/store.py
   ```
3. **Inspect Vector & Packet Serialization**:
   ```bash
   grep -n "def encode_state" experiments/graph_native_live/opaque_skeleton.py
   grep -n "def write_packet" experiments/graph_native_live/opaque_skeleton.py
   grep -n "exact_input_embeddings" experiments/graph_native_live/native/graph_soft_generator.cpp
   ```
4. **When Authorized by User to Run Tests**:
   - `pytest tests/test_store_and_topology.py`
   - `pytest tests/test_graph_and_learning.py`
   - `pytest tests/test_multiresolution_memory.py`
