# Technical Analysis: Core Habitus Substrate & Preference Matrix (Milestone 1)

**Investigator**: Explorer Agent (`explorer_m1_3`)  
**Scope**: Core Habitus Engine (`src/habitus_ai/`), Gestation Pipelines (`experiments/graph_native_live/`), and Architecture Contracts (`ARCHITECTURE.md`, `DEVELOPMENT.md`).

---

## 1. Graph Topology, Conserved Edge Weights, Y-Axis Traversal, and SQLite Authority

### 1.1 Structural Topology & Trunks
The Habitus cognitive graph operates as an **Hourglass bicone folded in 3D Toroidal Space** with a single structural origin:
- **Layer 0 (`SELF`)**: Unlabeled waist root node `SELF` at coordinate $(0, 0, 0)$. It is the single structural origin for all directional traversals.
- **Layer 1 ($+Y$ Sensory Trunks & $-Y$ Effector Trunks)**:
  - **$+Y$ Perceptual Trunks**: `HEAR` (`IN:HEAR`), `SEE` (`IN:SEE`), `NOTICE` (`IN:NOTICE`).
    - Event routing logic (`GraphRuntime.route_event` in `src/habitus_ai/graph.py:195-201`):
      - `EventKind.MESSAGE` $\rightarrow$ `HEAR` (conversational input).
      - `EventKind.OBSERVATION` with `correlation_id` $\rightarrow$ `SEE` (immediate correlated observation / tool return).
      - `EventKind.OBSERVATION` without `correlation_id` or `EventKind.NOTIFICATION` $\rightarrow$ `NOTICE` (delayed/uncorrelated alert).
  - **$-Y$ Effector Trunks**: `SPEAK` (`OUT:SPEAK`), `LOOK` (`OUT:LOOK`), `DO` (`OUT:DO`).
    - `SPEAK`: External verbal communication.
    - `LOOK`: Non-mutating environment/state inspection.
    - `DO`: External state mutation / execution.
- **Layer 2 (Preference Bands & Concept Mesh)**:
  - Input branches sprout into three lower preference nodes per trunk: `PREF:<trunk>:STABLE`, `PREF:<trunk>:NEUTRAL`, `PREF:<trunk>:UNSTABLE` (`src/habitus_ai/graph.py:28-36, 168-184`).
- **Layer 3 (Emergent Children / Structural Pattern Nodes)**:
  - Unlabeled child nodes (`kind="child"`) with zero semantic vector (`[0.0] * dimension`), empty lexical terms, and a numeric lower vault (`src/habitus_ai/graph.py:806-819`).
- **Layer 4 / Surface (Semantic Crown Plane)**:
  - Dual-facet crown concept nodes (`kind="crown"`) holding dense 1024D centroid embeddings, lexical terms, and language vaults (`vault:<concept_id>`). Both $+Y$ input and $-Y$ output paths converge upon shared crown concepts (`src/habitus_ai/graph.py:204-258`).

### 1.2 Conserved Fluid Edge Weights
Edge weights in Habitus follow strict physical fluid conservation rather than unbounded accumulation (`src/habitus_ai/graph.py:286-334`):
1. **Effective Logit**:
   $$\text{effective\_logit}(e, t) = \text{log\_strength}(e) + \text{fast\_recency}(e, t) - \text{conflict\_penalty}(e)$$
   - **Fast Recency**: $\text{recency\_strength} \cdot \exp\left(-\ln(2) \cdot \frac{\text{age}}{\text{half\_life}}\right)$, where default $\text{recency\_strength} = 0.8$, $\text{half\_life} = 300\text{ s}$ (`src/habitus_ai/graph.py:57-58, 296-298`).
   - **Conflict Penalty**: Damped penalty accumulated during negative feedback / contradictions (`src/habitus_ai/graph.py:479-484`).
2. **Global Softmax Normalization**:
   $$\text{global\_weight}(e, t) = \frac{\exp\left(\frac{\text{effective\_logit}(e, t) - \max(\text{logits})}{T}\right)}{\sum_{e' \in \text{Edges}} \exp\left(\frac{\text{effective\_logit}(e', t) - \max(\text{logits})}{T}\right)}$$
   - Default temperature $T = 1.0$. All live global edge weights strictly sum to $1.0$ (`src/habitus_ai/graph.py:300-309`).
3. **Local Outgoing Frontier Normalization**:
   $$\text{local\_probability}(e \mid v) = \frac{\text{global\_weight}(e, t)}{\sum_{e' \in \text{Outgoing}(v)} \text{global\_weight}(e', t)}$$
   - Every non-empty outgoing frontier sums to $1.0$ (`src/habitus_ai/graph.py:311-333`). Strengthening one branch automatically depresses competing routes.

### 1.3 Y-Axis Traversal Dynamics
Traversal computes the path of least resistance through graph topology from `SELF` (`src/habitus_ai/graph.py:337-416`):
1. **Travel Time Formulation**:
   $$\text{travel\_time}(e) = \frac{\Delta y(e)}{\epsilon + \text{local\_probability}(e \mid v)} + \text{conflict\_penalty}(e)$$
   where $\epsilon = 10^{-6}$, and $\Delta y(e) \ge 1.0$.
2. **Path Selection**:
   $$\text{path\_time}(\text{path}) = \sum_{e \in \text{path}} \text{travel\_time}(e)$$
   Evaluated via Dijkstra's algorithm with a priority queue (`heapq`).
3. **Orthogonality of X (Semantic) and Y (Structural Traversal)**:
   - The semantic surface ($X$) nominates candidate crown endpoints via joint cosine + lexical similarity (`src/habitus_ai/surface.py:37-90`).
   - Traversal ($Y$) determines the structural path cost to that endpoint.
   - Invariant: Semantic endpoint scores admit candidates but **never alter or rewrite Y-edge travel time** (`tests/test_graph_and_learning.py:29-55`).
   - Invariant: $Y$ resistance cannot replace an $X$-selected endpoint with an easier, unrelated target (`tests/test_graph_and_learning.py:57-93`).

### 1.4 SQLite Authority & Immutable Evidence Schema
SQLite (`src/habitus_ai/store.py`) serves as the single source of truth for canonical evidence.
- **Immutability Enforcement via SQL Triggers** (`src/habitus_ai/store.py:80-88`):
  ```sql
  CREATE TRIGGER IF NOT EXISTS records_are_immutable_update
  BEFORE UPDATE ON records BEGIN
      SELECT RAISE(ABORT, 'canonical records are immutable');
  END;

  CREATE TRIGGER IF NOT EXISTS records_are_immutable_delete
  BEFORE DELETE ON records BEGIN
      SELECT RAISE(ABORT, 'canonical records are immutable');
  END;
  ```
- **Supersession Model**: Corrections do not overwrite existing records; they create a new record referencing `supersedes_id` (`src/habitus_ai/store.py:67-78`). Active records are queried using `NOT EXISTS (SELECT 1 FROM records newer WHERE newer.supersedes_id = r.record_id)` (`src/habitus_ai/store.py:298-308`).
- **Core Schema Tables**:
  - `records`: Canonical text, timestamp, 1024D embedding JSON, provenance JSON, metadata JSON.
  - `concepts`: Structural node identities (`SELF`, trunks, preference nodes, children, crown concepts).
  - `edges`: Directed edges with `side` (`input`/`output`), `delta_y`, `log_strength`, `conflict_penalty`.
  - `edge_evidence`: Links edges to supporting canonical records.
  - `vault_membership`: Binds canonical records to concept vaults.
  - `experience_state`: Maintains running confidence-weighted preference means per `experience_id`.
  - `experience_projections`: Multi-resolution language-free projections across graph layers.
  - `overlap_clusters`: Centroid vectors and supporting record/experience IDs for emergent node growth.
  - `metadata`: Binds `embedding_space_id`, `embedding_dimension`, `gestation_profile`, and `pulse_counter`.

---

## 2. Internal Preference States & Conceptual Node Growth Under Stimulus Exposure

### 2.1 Preference Signal Extraction and State Updating
When a stimulus event is ingested (`BaseAgenticMemoryRAG.remember` in `src/habitus_ai/pipeline.py:231-337`):
1. **Signal Extraction** (`src/habitus_ai/graph.py:551-574`):
   - Extracts numeric values from `preference_signals`, `preference`, and `stability_delta` in record metadata.
   - Bounds signals to $[-1.0, 1.0]$ and confidence to $[0.0, 1.0]$.
2. **Confidence-Weighted Running Mean** (`src/habitus_ai/store.py:558-610`):
   $$\text{total\_weight} = \text{old\_weight} + \text{confidence}$$
   $$\text{preference\_mean} = \frac{\text{old\_mean} \cdot \text{old\_weight} + \text{preference} \cdot \text{confidence}}{\text{total\_weight}}$$
3. **Multi-Resolution Experience Projections** (`src/habitus_ai/graph.py:581-624`):
   - Determines the target preference band:
     - `NEUTRAL` if $\text{confidence} \le 0.0$ or $|\text{preference}| < 0.05$.
     - `STABLE` if $\text{preference} \ge 0.05$.
     - `UNSTABLE` if $\text{preference} \le -0.05$.
   - Deposits language-free projection rows into `experience_projections` at:
     - Layer 0: `SELF`
     - Layer 1: Stimulus trunk (`IN:HEAR`, `IN:SEE`, or `IN:NOTICE`)
     - Layer 2: Preference band node (`PREF:<trunk>:<band>`)
   - Every projection record contains: `(experience_id, record_id, node_id, layer, side, activation=1.0, preference, confidence, pulse)`. **Crucially, no natural-language text is stored in `experience_projections`** (`ARCHITECTURE.md:146-149`, `tests/test_multiresolution_memory.py:33-39`).

### 2.2 Evidence-Backed Overlap Clustering & Node Promotion
Conceptual node growth occurs organically from stimulus clustering (`src/habitus_ai/graph.py:698-879`):
1. **Overlap Evaluation**:
   - Compares the new record's 1024D embedding with existing `OverlapCluster` centroids in the parent preference vault using cosine similarity.
   - Compatibility check:
     $$\text{cosine\_similarity}(\text{record.embedding}, \text{cluster.centroid}) \ge \text{overlap\_threshold} \quad (0.70)$$
     $$|\text{record.preference} - \text{cluster.preference\_mean}| \le \text{preference\_tolerance} \quad (0.35)$$
2. **Cluster Updating**:
   - If compatible: Updates the cluster centroid as a running normalized vector sum, appends `record_id` and `experience_id`, and updates `preference_mean` and `confidence_mean` (`src/habitus_ai/graph.py:748-774`).
   - If incompatible: Initializes a new `OverlapCluster` with a unique hash ID (`src/habitus_ai/graph.py:775-790`).
3. **Promotion Threshold**:
   - Required distinct experiences:
     $$\text{required\_support} = \max\left(\text{base\_promotion\_count}, \lceil \log_2(\text{parent\_vault\_experiences} + 1) \rceil\right)$$
4. **Two-Stage Structural Promotion**:
   When `len(cluster.experience_ids) >= required_support`:
   - **Step A: Unlabeled Child Node (Layer 3)**:
     - Creates `ConceptNode(concept_id="child:auto:<hash>", kind="child", embedding=[0.0]*1024, terms=(), vault_id="lower-vault:...")`.
     - Connects edge `parent_pref_node -> child_node` with $\Delta y = 1.0$.
     - Deposits `ExperienceProjection` at layer 3 with kind `emergent_child`.
   - **Step B: Crown Semantic Port (Layer 4)**:
     - Extracts top non-stopword lexical tokens across supporting records.
     - Creates `ConceptNode(concept_id="concept:auto:<hash>", kind="crown", embedding=centroid, terms=terms, vault_id="vault:...")`.
     - Connects edge `child_node -> semantic_port` with $\Delta y = 1.0$.
     - Attaches supporting record IDs as evidence to both edges and registers vault memberships.

### 2.3 Verified Outcome Reinforcement
Durable learning requires external verification (`src/habitus_ai/graph.py:459-489`, `src/habitus_ai/pipeline.py:492-525`):
- Unverified model outputs cannot modify durable edge strengths (`verified=True` and `receipt_id` required for external effects).
- When verified:
  $$\Delta \text{strength} = \text{learning\_rate} \cdot \text{stability\_delta} \cdot \text{evidence\_quality} \cdot \frac{1}{|\text{credited\_edges}|}$$
  - $\Delta > 0$: Increases `log_strength`, decreases `conflict_penalty`.
  - $\Delta < 0$: Decreases `log_strength`, increases `conflict_penalty`.

---

## 3. Continuous Activation State Extraction & Vector Serialization

### 3.1 Multi-Resolution Representation
Habitus translates symbolic and structural graph states into continuous vectors without passing prompt templates or injected user prose to the transformer backend:
- **Level 0-2 (Lower Substrate)**: Activations, confidence-weighted preferences, and pulse timestamps.
- **Level 3 (Emergent Assemblies)**: Structural graph topology, traversal depth, and routing probabilities.
- **Level 4 (Lexeme Fibers / Semantic Crown)**: 1024D native token geometry aligned with the underlying LLM embedding space (`Qwen3-0.6B-Q8_0.gguf`).

### 3.2 Slot-Based Continuous Vector Encoding
In `experiments/graph_native_live/opaque_skeleton.py:212-283` and `transformer_hatch.py:85-214`, continuous state matrices are serialized into distinct functional slot rows:
1. **Concept Centroid Slot**:
   - Unit-normalized 1024D embedding of the active crown concept: $\hat{v}_{\text{concept}} = \frac{v}{\|v\|}$.
2. **Input Traversal Slot**:
   - Depth-weighted normalized sum of node embeddings visited along the $+Y$ input Y-path:
     $$v_{\text{input\_slot}} = \sum_{d=0}^{L-1} \left(0.35 + \frac{d+1}{L}\right) \hat{v}_{\text{node}_d}$$
3. **Output Traversal Slot**:
   - Depth-weighted normalized sum of node embeddings visited along the $-Y$ output Y-path.
4. **Conserved Edge Mass Slot**:
   - Weighted superposition of dense edge direction vectors scaled by active global softmax weights:
     $$v_{\text{edge\_slot}} = \sum_{e \in \text{path}} (0.10 + \text{global\_weight}(e)) \cdot \hat{v}_{\text{edge}(e)}$$
5. **Temporal Recency & Polarity Slot**:
   - Recency-decayed historical activation vectors coupled with a dense scalar polarity axis:
     $$v_{\text{temporal\_slot}} = \sum_{\text{age}=0}^{K-1} \frac{1}{1 + \text{age}} \left( \hat{v}_{\text{target}(\text{age})} + \text{stability}(\text{age}) \cdot \hat{v}_{\text{polarity\_axis}} \right)$$
6. **Ordered Lexical Fibers Slot (`ordered_lexical_rows`)**:
   - Ingests model-token lexemes connected via productive fibers (`LX:<hash>`), ordered according to learned output transition edge strengths (`mind.store.find_edge(GraphSide.OUTPUT, source_lexeme, target_lexeme)`).

### 3.3 Packet Buffer Binary / ASCII Protocol
The serialized activation states are exported to `.packet` files for ingestion by native binaries (`experiments/graph_native_live/opaque_skeleton.py:289-299`):
```text
HABITUS_OPAQUE_PACKET_V1
1024 4
<float_0> <float_1> ... <float_1023>
<float_0> <float_1> ... <float_1023>
<float_0> <float_1> ... <float_1023>
<float_0> <float_1> ... <float_1023>
```
Or for soft categorical basis packets:
```text
HABITUS_SOFT_PACKET_V1
speak 1.0
greeting 0.85
warm 0.70
...
```

### 3.4 Native GGUF Soft-Input Bridge (`graph_soft_generator.cpp`)
The C++ bridge (`experiments/graph_native_live/native/graph_soft_generator.cpp`) ingests the `.packet` buffer directly into llama.cpp without string tokenization:
1. **Direct Tensor Extraction**: Locates `token_embd.weight` directly in the GGUF model via `llama_internal_get_tensor_map` (`graph_soft_generator.cpp:122-163`).
2. **Embedding Norm Scaling**:
   - Computes target embedding norm shell $\bar{\mu}_{\|\cdot\|}$.
   - Scales soft slot rows to preserve the model's native activation radius while applying bounded amplitude modulation:
     $$\text{scale} = \frac{\bar{\mu}_{\|\cdot\|}}{\|v_{\text{slot}}\|} \cdot (0.85 + 0.30 \cdot \text{activation})$$
3. **KV Cache Injection & Logit Decoding**:
   - Directly feeds the 1024D float rows as soft inputs into the transformer forward pass.
   - Evaluates logits and samples continuations matching the graph's internal preference state.

---

## 4. Key Architectural Invariants Summary

| # | Invariant Rule | Implementation Location | Enforcement Mechanism |
|---|---|---|---|
| 1 | Single `SELF` origin | `graph.py:74-148, 492` | `validate_invariants()` checks `SELF` exists |
| 2 | Input frontier strictly `HEAR`, `SEE`, `NOTICE` | `graph.py:159-167, 520-528` | Verified against `INPUT_NODE_IDS` |
| 3 | Output frontier strictly `SPEAK`, `LOOK`, `DO` | `graph.py:184-192, 529-530` | Verified against `OUTPUT_NODE_IDS` |
| 4 | Directional paths share crown concepts & vaults | `graph.py:204-258` | Both trunks link to same `vault:<concept_id>` |
| 5 | Global live edge mass sums to $1.0$ | `graph.py:300-309, 509-510` | Global softmax normalization |
| 6 | Local outgoing frontiers sum to $1.0$ | `graph.py:311-333, 514-518` | Outgoing edge partition normalization |
| 7 | Endpoint semantic score cannot alter Y travel time | `graph.py:377-380`, `test_graph_and_learning.py:29` | Travel time uses only edge properties and local probabilities |
| 8 | Multi-hop expansion starts from visited Y-path nodes | `graph.py:417-448`, `retrieval.py:257-262` | `expanded_concept_ids()` filters by `path_nodes` |
| 9 | Direct dense safety rail cannot be evicted | `retrieval.py:85-115, 273-279` | Top-3 direct hits guaranteed inclusion |
| 10 | Canonical records are immutable with supersessions | `store.py:80-88, 298-308` | SQLite triggers block `UPDATE`/`DELETE` |
| 11 | Unverified output cannot durably reinforce paths | `graph.py:459-467`, `pipeline.py:503-504` | `verified=True` and receipt ID checked |
| 12 | Persisted embedding identity cannot change silently | `store.py:203-225` | Schema validation verifies `space_id` & `dimension` |
| 13 | Lower projections contain no language payload | `store.py:160-173`, `graph.py:611-624` | Schema has no natural language field |
| 14 | Promoted child retains all supporting experiences | `graph.py:839-864` | All supporting records linked as vault/projection evidence |
| 15 | Opposing preference bands cannot collapse in same cluster | `graph.py:736-743` | `abs(preference - cluster.preference_mean) <= tolerance` |
