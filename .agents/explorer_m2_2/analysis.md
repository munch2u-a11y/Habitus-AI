# Milestone 2 Analysis: Opaque Continuous Graph State Encoding

## Executive Summary
This document provides a comprehensive technical investigation of Milestone 2's opaque continuous graph state encoding implementation (`experiments/graph_native_live/opaque_skeleton.py`) and its verification suite (`tests/test_opaque_graph_native.py`). The system implements a label-free, train-free continuous state encoder that transforms agentic memory graph topology, edge reinforcement mass, and temporal pulse history into 4 multi-slot 1024D continuous float vectors. These vectors are formatted into the `HABITUS_OPAQUE_PACKET_V1` specification and fed directly into the native Qwen3 GGUF soft-input adapter (`graph_soft_generator`), completely bypassing lexical token prompt injection and semantic dictionary codebooks.

---

## 1. Mathematical and Structural Encoding into 4 Multi-Slot 1024D Rows

### 1.1 Dense Direction Generation (`opaque_unit_vector` & `OpaqueIdentityEmbedder`)
In `opaque_skeleton.py` (lines 48–65):
- **Deterministic Hashing**: For any arbitrary key string $k \in \Sigma^*$, the vector generation function calculates a SHAKE-256 extendable-output hash digest of length $2 \times \text{DIMENSION} = 2048$ bytes:
  $$\text{digest} = \text{SHAKE-256}(k, 2048)$$
- **Integer Unpacking & Value Mapping**: The 2048 bytes are unpacked as $1024$ little-endian unsigned 16-bit integers $u_i \in [0, 65535]$:
  $$v_i = \frac{u_i}{32767.5} - 1.0 \in [-1.0, 1.0]$$
- **L2 Sphere Normalization**: The resulting vector $\mathbf{v} \in \mathbb{R}^{1024}$ is normalized to the unit hypersphere:
  $$\hat{\mathbf{v}} = \frac{\mathbf{v}}{\|\mathbf{v}\|_2}$$
- **Opaque Identity Embedder**: The `OpaqueIdentityEmbedder` maps `text` to `opaque_unit_vector(f"symbol:{text}")`. Identical strings map to identical unit vectors ($\mathbf{u} = \mathbf{u}'$), while distinct strings yield statistically orthogonal pseudo-random vectors on the 1024D sphere ($\mathbb{E}[\langle \mathbf{u}, \mathbf{w} \rangle] = 0$, with empirical $|\langle \mathbf{u}, \mathbf{w} \rangle| < 0.12$). No lexical, subword, Word2Vec, or pre-trained embedding semantics exist.

### 1.2 Graph Substrate Initialization and Traversal Topology
- **Opaque Nodes**:
  - `OPAQUE_A = "U3:00000000"` (Seed branch A)
  - `OPAQUE_B = "U3:00000001"` (Seed branch B)
  - `OPAQUE_JOIN = "U3:00000002"` (Conjunction node)
- **Topological Ingestion**:
  - `seed_skeleton(mind)`:
    - Connects `PREF:HEAR:STABLE` $\xrightarrow{\text{INPUT}}$ `OPAQUE_A`
    - Connects `PREF:HEAR:UNSTABLE` $\xrightarrow{\text{INPUT}}$ `OPAQUE_B`
    - Connects `OUT:SPEAK` $\xrightarrow{\text{OUTPUT}}$ `OPAQUE_A`
    - Connects `OUT:SPEAK` $\xrightarrow{\text{OUTPUT}}$ `OPAQUE_B`
  - `connect_branches(mind)`:
    - Connects `OPAQUE_A` $\xrightarrow{\text{INPUT, OUTPUT}}$ `OPAQUE_JOIN`
    - Connects `OPAQUE_B` $\xrightarrow{\text{INPUT, OUTPUT}}$ `OPAQUE_JOIN`
- **Firing & Edge Reinforcement (`fire`)**:
  - Fires traversal on both `GraphSide.INPUT` (from `InputTrunk.HEAR`) and `GraphSide.OUTPUT` (to `OutputTrunk.SPEAK`).
  - Edge paths from both traces are credited and reinforced via `mind.graph.reinforce_edges(credited, stability_delta=stability, verified=True, evidence_quality=1.0)`.
  - Developmental history records the pulse counter, target, signed stability, and traversed node/edge IDs.

### 1.3 The 4 Multi-Slot 1024D Rows (`encode_state`)
In `opaque_skeleton.py` (lines 212–283), `encode_state(mind, target, history)` constructs exactly 4 dense 1024D vectors using `weighted_sum(vectors)` (which accumulates weighted vectors and normalizes the sum to unit L2-norm):

| Slot Index | Row Name | Formulation & Source | Weighting Scheme & Semantics |
|---|---|---|---|
| **Row 0** | `input_slot` | Node vectors along `input_trace.path_node_ids` | $w_{\text{node}} = 0.35 + \frac{\text{depth} + 1}{|\text{input\_nodes}|}$<br>Hierarchically weights nodes along the perceptual trunk path, giving highest activation to nodes near the target concept. |
| **Row 1** | `edge_slot` | Opaque edge basis vectors `opaque_unit_vector(f"edge-code:{edge_id}")` along input and output traversal paths | $w_{\text{edge}} = 0.10 + M_{\text{edge}}$, where $M_{\text{edge}} = \text{snapshot.global\_weights}[e]$<br>Encodes total accumulated reinforcement mass / learned habitual weight across all traversed structural relations. |
| **Row 2** | `temporal_slot` | Recency-weighted history blend of target node vectors + scalar polarity axis | Considers last $N \le 8$ history events with harmonic decay $r(t) = \frac{1}{1 + \text{age}}$:<br>1. Target geometry: $(\mathbf{v}_{\text{target}}, r(t))$<br>2. Signed stability: $(\mathbf{u}_{\text{scalar-axis:0}}, r(t) \times \text{stability})$<br>Encodes recency, target sequence, and scalar valence without linguistic emotion labels. Empty history fallback: $(\mathbf{u}_{\text{empty-history}}, 1.0)$. |
| **Row 3** | `output_slot` | Node vectors along `output_trace.path_node_ids` | $w_{\text{node}} = 0.35 + \frac{\text{depth} + 1}{|\text{output\_nodes}|}$<br>Hierarchically weights nodes along the effector trunk path towards the target concept. |

---

## 2. Packet Format (`HABITUS_OPAQUE_PACKET_V1`) Specification

### 2.1 File Structure & Encoding
Written by `write_packet(path, rows)` (lines 289–299):
- **Line 1 (Magic Header)**: `HABITUS_OPAQUE_PACKET_V1`
- **Line 2 (Shape Dimensions)**: `<DIMENSION> <NUM_ROWS>` (e.g. `1024 4`)
- **Lines 3..N (Row Vectors)**: Space-separated 9-digit floating-point representations (`{value:.9g}`) of each row's 1024 elements.
- **Character Encoding**: Strictly ASCII text.

```
HABITUS_OPAQUE_PACKET_V1
1024 4
0.012345678 -0.054321098 ... (1024 floats)
-0.098765432 0.043210987 ... (1024 floats)
0.003456789 0.087654321 ... (1024 floats)
-0.012345678 -0.065432109 ... (1024 floats)
```

### 2.2 Native Ingestion in C++ (`native/graph_soft_generator.cpp`)
In `load_packet` (lines 215–245) and `main` (lines 378–393):
1. **Header Branching**: Identifies `HABITUS_OPAQUE_PACKET_V1` and sets `packet.opaque = true`.
2. **Bounds Checking**:
   - `1 <= dimension <= 16384` (strictly verified against model embedding width $n_{\text{embd}} = 1024$).
   - `1 <= rows <= 8` (enforcing safety cap).
   - Validates all $1024 \times 4 = 4096$ values with `std::isfinite(value)` and verifies no trailing data.
3. **Embedding Shell Calibration (`place_on_embedding_shell`)**:
   - Computes the average L2-norm $\bar{N}_{\text{struct}}$ of standard prompt delimiters (`<|im_start|>user\n` and `<|im_end|>\n<|im_start|>assistant\n`).
   - Normalizes and scales each opaque 1024D row:
     $$\mathbf{x}_{\text{calibrated}} = \mathbf{x} \cdot \left(\frac{\bar{N}_{\text{struct}}}{\|\mathbf{x}\|_2}\right)$$
   - Ensures graph soft-tokens reside precisely on the model's familiar representation manifold shell without amplitude distortion.
4. **Context Injection**:
   - The calibrated 4 rows are concatenated directly between prefix and suffix token embeddings into `input_embeddings`.
   - Passes directly into `llama_decode(context, batch)` with `batch.embd = input_embeddings.data()`.
   - **No semantic codebook dictionary, no tokenizer vocabulary lookup, and zero token prompt text is presented to the model.**

---

## 3. Test Requirements & Experimental Control Matrix

### 3.1 Test Requirements in `tests/test_opaque_graph_native.py`
The test file verifies two core invariants:

1. **`test_opaque_connected_packet_has_no_language_anchors(tmp_path)`** (lines 21–46):
   - Initializes `BaseAgenticMemoryRAG` backed by `OpaqueIdentityEmbedder`.
   - Seeds skeleton (`OPAQUE_A`, `OPAQUE_B`), fires `OPAQUE_A` (+0.8), fires `OPAQUE_B` (-0.6), connects `OPAQUE_JOIN`, and fires `OPAQUE_JOIN` (+0.4).
   - Encodes state for `OPAQUE_JOIN` and validates:
     - `mind.graph.validate_invariants() == []` (dual-cipher topology and bicone reachability preserved).
     - Serializes packet to disk using `write_packet`.
     - Asserts packet header: `payload.startswith("HABITUS_OPAQUE_PACKET_V1\n1024 4\n")`.
     - Asserts zero lexical terms: `"hello" not in payload.casefold()`, `"greeting" not in payload.casefold()`, `"friendly" not in payload.casefold()`.
     - Asserts trace metadata: `trace["semantic_labels"] == []`, `trace["language_anchors"] == []`.
     - Asserts path continuity: `trace["input_path"][-1] == "U3:00000002"`, `trace["output_path"][-1] == "U3:00000002"`.

2. **`test_opaque_identity_has_no_lexical_similarity_rule()`** (lines 48–57):
   - Verifies `OpaqueIdentityEmbedder` has deterministic identity:
     $$\text{embed}("hello") \equiv \text{embed}("hello")$$
   - Verifies absence of semantic correlation:
     $$|\langle \text{embed}("hello"), \text{embed}("greeting") \rangle| < 0.12$$

### 3.2 Experimental Control Conditions in `opaque_skeleton.py`
In `run_experiment` (lines 347–390), 7 distinct test cases and controls are evaluated:

| Case ID | Target / State | Description & Experimental Purpose |
|---|---|---|
| `branch_a` | `OPAQUE_A` | Single-branch state reinforced with positive stability (+0.8). |
| `branch_b` | `OPAQUE_B` | Single-branch state reinforced with negative stability (-0.6). |
| `connected` | `OPAQUE_JOIN` | Dual-branch conjunction state reinforced with escalating stability (0.25, 0.40, 0.55, 0.70). |
| `connected_repeat` | `OPAQUE_JOIN` | Exact bitwise duplicate of `connected` rows to verify determinism in native runner output. |
| `connected_row_reversal` | `reversed(connected)` | Reverses the row sequence: `[output_slot, temporal_slot, edge_slot, input_slot]`. Tests slot positional sensitivity in transformer soft-token ingestion. |
| `connected_sign_inversion` | `-[connected]` | Negates all elements across all 4 rows ($-\mathbf{x}_i$). Tests geometric directionality and polarity sensitivity. |
| `unconnected_control` | Control vectors | 4 independent random unit vectors (`control_rows()`) lacking any graph topology, edge weights, or pulse history. |

---

## 4. Discrete Lexical Term Elimination Audit

A forensic review of the entire pipeline confirms zero discrete lexical terms or words are present in the opaque encoding path:

| Layer | Implementation Mechanism | Verification / Assertion Evidence |
|---|---|---|
| **Concept Definition** | Nodes are assigned synthetic identifiers (`"U3:00000000"`, etc.) with `terms=()`. | `node.terms == ()` across all opaque concepts. |
| **Vector Embedding** | `OpaqueIdentityEmbedder` computes SHAKE-256 cryptographic hashes, bypassing any Word2Vec / transformer token embeddings. | `test_opaque_identity_has_no_lexical_similarity_rule` verifies $|\text{cosine}| < 0.12$. |
| **Packet Serialization** | `write_packet` outputs exclusively ASCII numbers (`HABITUS_OPAQUE_PACKET_V1`, shape `1024 4`, and floats). | `assert "hello" not in payload.casefold()`, `assert "greeting" not in payload.casefold()`, `assert "friendly" not in payload.casefold()`. |
| **Trace Metadata** | Explicitly recorded metadata confirms the absence of semantic labels. | `assert trace["semantic_labels"] == []`, `assert trace["language_anchors"] == []`, `skeleton["language_labels_attached"] = False`. |
| **C++ Native Runner** | `graph_soft_generator.cpp` flags `packet.opaque = true`, bypassing the `BASIS` dictionary completely. | Native output receipt confirms:<br>`"semantic_codebook_used": false`<br>`"model_received_prompt_text": false`<br>`"model_received_user_tokens": false`<br>`"adapter_kind": "opaque_graph_state_native_1024_v0"`. |

---

## Conclusion
`experiments/graph_native_live/opaque_skeleton.py` and `tests/test_opaque_graph_native.py` provide a mathematically robust, label-free continuous graph state interface for Milestone 2. By encoding perceptual trunk traversal, effector trunk traversal, edge reinforcement mass, and temporal history into 4 normalized 1024D continuous soft-input slots, Habitus-AI directly stimulates native GGUF transformers without intermediate prompt serialization or semantic codebook scaffolding.
