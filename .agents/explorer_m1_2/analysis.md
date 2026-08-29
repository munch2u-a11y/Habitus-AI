# Milestone 1 Investigation: Lexical Nursery & Receptive/Productive Fiber Bindings

## Executive Summary
This report investigates Milestone 1 (Lexical Nursery & Receptive/Productive Fiber Bindings) within `habitus-ai-experiments`. The investigation covers `experiments/graph_native_live/nursery.py`, `experiments/graph_native_live/reverse_nursery.py`, `experiments/graph_native_live/native/lexeme_codec.cpp`, `tests/test_nursery.py`, and `tests/test_reverse_nursery.py`. 

The nursery architecture establishes a dual-membrane language binding where internal cognitive nodes remain strictly opaque and language-free. Grounding to natural language occurs at the surface boundary via 1024D native token geometry extracted directly from a local Qwen3 GGUF model (`/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf`). `reverse_nursery.py` achieves tokenless graph representation by storing zero token IDs or word strings in graph concept nodes and decoding continuous 1024D blended graph states through full-vocabulary GGUF projection.

---

## 1. Opaque Concepts & 1024D Lexical Embedding Bindings

### 1.1 Opaque Concept Architecture
- **Internal Concept Generation**: Lower conceptual nodes (`D3:00000000`, `D3:00000001`, `D3:00000002` in `LOWER_NODES`) represent an ordered developmental spine.
- **Label-Free Initialization**: In `ensure_internal_node()`, nodes are created with `embedding=opaque_unit_vector(f"developmental-node:{node_id}")` and `terms=()`. The embedding is generated via `hashlib.shake_256` digest unpacked into unsigned 16-bit integers and projected to the unit hypersphere in $\mathbb{R}^{1024}$. No semantic word embeddings, subword n-grams, or dictionary tokens exist on internal nodes.
- **Topological Trunk Seeding**: `seed_developmental_path(mind)` creates directed relations across both halves of the bicone:
  - **Input side (Receptive)**: `PREF:HEAR:STABLE` $\rightarrow$ `D3:00000000` $\rightarrow$ `D3:00000001` $\rightarrow$ `D3:00000002` (`delta_y = 1.0`)
  - **Output side (Productive)**: `OUT:SPEAK` $\rightarrow$ `D3:00000000` $\rightarrow$ `D3:00000001` $\rightarrow$ `D3:00000002` (`delta_y = 1.0`)

### 1.2 Lexical Token Geometry Extraction via `lexeme_codec.cpp`
- **Native Bridge**: The C++ helper `lexeme_codec` (`experiments/graph_native_live/native/lexeme_codec.cpp`) interfaces directly with `llama.cpp`/`ggml` libraries.
- **Tokenizer & Dequantization**: 
  - Tokenizes input surface strings using `llama_tokenize`.
  - Locates `token_embd.weight` inside the GGUF model.
  - Dequantizes row data (e.g. Q8_0 quant block format) to float32 using `traits->to_float`.
  - For multi-token lexemes, averages subword token embedding vectors.
  - Asserts native embedding dimension is strictly 1024 (`llama_model_n_embd_inp == 1024`).

### 1.3 Binding Mechanisms: Receptive vs. Productive Fibers
In `expose_label(mind, exposure, caregiver_stability=0.8)`:
1. **Receptive Fibers (`GraphSide.INPUT`)**:
   - Directed edge created: `exposure.lower_node_id` $\rightarrow$ `exposure.lexeme_id` with `delta_y = 1.0`.
   - Traversal executed: `SELF` $\rightarrow$ `IN:HEAR` $\rightarrow$ `PREF:HEAR:STABLE` $\rightarrow \dots \rightarrow$ `lower_node_id` $\rightarrow$ `lexeme_id`.
   - Reinforcement: All edges in the active input trace are reinforced with full caregiver stability ($\Delta s = 0.8$).
2. **Productive Fibers (`GraphSide.OUTPUT`)**:
   - Directed edge created: `exposure.lower_node_id` $\rightarrow$ `exposure.lexeme_id` on `GraphSide.OUTPUT` with `delta_y = 1.0`.
   - Provisional Reinforcement: Mirrored output fiber receives weak provisional credit ($\Delta s = 0.8 \times 0.20 = 0.16$), modeling the biological / developmental observation that receptive comprehension precedes productive expression.
3. **Incidental Output Fibers**:
   - Co-active predecessor nodes on the traversal path receive incidental productive edges to the current lexeme with higher travel time (`delta_y = 2.0`). These represent potential spurious associations that must be pruned or out-competed during successive contingent feedback cycles.

### 1.4 Architectural Difference: `nursery.py` vs. `reverse_nursery.py`

| Mechanism | `nursery.py` (Diagnostic Decoder) | `reverse_nursery.py` (Geometry Membrane) |
|---|---|---|
| **Lexeme Concept Storage** | `ensure_lexeme`: stores `terms=(f"token:{token_id}", ...)` | `ensure_geometry_lexeme`: stores `terms=()` (completely tokenless) |
| **Lexeme Identity** | `LX:<sha256(token_ids)>` | `LXG:<sha256(1024D_float_bytes)>` |
| **Output State Formation** | Diagnostic lookup: picks highest-weight lexeme candidate per lower node and reads `node.terms`. | Continuous blending: `output_state()` computes continuous vector $S = \sum p_i \cdot E_i$ across all productive fibers. |
| **Outward Decoding** | Detokenizes explicit token IDs via `lexeme_codec detokenize`. | Continuous 1024D states passed to `lexeme_codec nearest TOP_K`, projecting against the entire GGUF vocabulary tensor (`output.weight` / `token_embd.weight`). |
| **Token Knowledge Boundary** | Token IDs present in graph store metadata. | **Zero token IDs or text strings in graph store.** Decoding is pure GGUF geometry projection. |

---

## 2. Curriculum Structure & Control Conditions

### 2.1 Developmental Presentation & Phrase Composition
The curriculum enforces a foundational rule: **words are presented strictly in isolation**, never as a concatenated full phrase. The agent must independently assemble sequential composition via the underlying topological ordering of the developmental spine.

Curriculum exposures (presented across $N$ cycles, default 8 CLI, 4 test):
1. Lower node `D3:00000000` co-activated with Form 0 (e.g. `"I"`)
2. Lower node `D3:00000001` co-activated with Form 1 (e.g. `" like"`)
3. Lower node `D3:00000002` co-activated with Form 2 (e.g. `" Josh"`)

### 2.2 Four Experimental Conditions

```
+----------------------------------------------------------------------------------------------------+
| 1. Primary Curriculum:        ("I", " like", " Josh") with assignment (0, 1, 2)                   |
|    - D3:0 -> "I", D3:1 -> " like", D3:2 -> " Josh"                                                |
|    - Output Speech: "I like Josh" (Exact match = True, Hatch ready = True)                        |
+----------------------------------------------------------------------------------------------------+
| 2. Substitution Curriculum:   ("I", " prefer", " music") with assignment (0, 1, 2)                |
|    - D3:0 -> "I", D3:1 -> " prefer", D3:2 -> " music"                                             |
|    - Evaluates lexical substitution on identical 3-concept spine                                  |
+----------------------------------------------------------------------------------------------------+
| 3. Shuffled Binding Control:  ("I", " like", " Josh") with assignment (2, 0, 1)                   |
|    - D3:0 -> " Josh", D3:1 -> "I", D3:2 -> " like"                                                |
|    - Output Speech: " JoshI like" (Exact match = False, Hatch ready = False)                      |
|    - Proves graph topology dictates sequential word order rather than unordered bag-of-words      |
+----------------------------------------------------------------------------------------------------+
| 4. Untrained Control:         ("I", " like", " Josh") with cycles = 0                             |
|    - Zero label exposures                                                                         |
|    - Output Speech: "" (Empty string, Hatch ready = False)                                        |
|    - Proves no spontaneous lexical emission occurs without grounded training                     |
+----------------------------------------------------------------------------------------------------+
```

### 2.3 Post-Curriculum Evaluation & Hatch Gate
1. **Comprehension Probes**: For each exposure, traverses `SELF` $\rightarrow$ `IN:HEAR` $\rightarrow \dots \rightarrow$ `lexeme_id`. Validates that the traversal resolves back to the co-active `lower_node_id`.
2. **Speech Attempt**: Traverses `OUT:SPEAK` $\rightarrow$ `D3:00000002`. Decodes output states across all nodes in the path to produce an emitted token sequence.
3. **Caregiver Feedback Loop**: 
   - Compares emitted token sequence with canonical expected token sequence.
   - Exact match triggers positive reinforcement ($\Delta s = +1.0$).
   - Mismatch triggers negative reinforcement ($\Delta s = -0.35$).
   - Feedback is applied at `pulse + 1` (`delay_pulses = 1`), establishing a causal temporal credit assignment loop.
4. **Graph Invariant Audit**: Validates `validate_invariants()`:
   - Root trunk existence (`SELF`, `IN:*`, `OUT:*`, `PREF:*`).
   - Global edge weight mass conservation ($\sum w_i = 1.0 \pm 10^{-9}$).
   - Local branching probability conservation ($\sum_{\text{out}} p_j = 1.0 \pm 10^{-9}$).
   - Frontier integrity (`SELF` frontiers match trunks).
5. **`hatch_ready` Predicate**:
   $$\text{hatch\_ready} \iff (\forall c \in \text{Comprehension}, c.\text{passed}) \land (\text{Speech}.\text{tokens} == \text{Expected}) \land (\text{Feedback}.\text{exact} == \text{True}) \land (\text{Invariants} == \emptyset)$$

---

## 3. Test Coverage and Assertions

### 3.1 Test Suite Analysis

#### `tests/test_nursery.py`
- **Target**: `test_separate_labels_compose_and_shuffled_pairing_does_not(tmp_path: Path)`
- **Skip Guard**: `@pytest.mark.skipif(not NURSERY.MODEL.is_file() or not NURSERY.CODEC.is_file())`
- **Cycles Executed**: 4 cycles.
- **Assertions**:
  - `primary["complete_phrase_presented"] is False`
  - `primary["speech"]["surface"] == "I like Josh"`
  - `primary["speech"]["exact"] is True`
  - `primary["hatch_ready"] is True`
  - `sum(item["passed"] for item in primary["comprehension"]) == 3`
  - `primary["feedback"]["delay_pulses"] == 1`
  - `len(primary["fiber_weights"]) > 6`
  - `shuffled["speech"]["surface"] == " JoshI like"`
  - `shuffled["speech"]["exact"] is False`
  - `shuffled["hatch_ready"] is False`
  - `untrained["speech"]["surface"] == ""`
  - `untrained["hatch_ready"] is False`

#### `tests/test_reverse_nursery.py`
- **Target**: `test_graph_states_decode_without_graph_token_ids(tmp_path: Path)`
- **Skip Guard**: `@pytest.mark.skipif(not REVERSE.nursery.MODEL.is_file() or not REVERSE.nursery.CODEC.is_file())`
- **Cycles Executed**: 4 cycles.
- **Assertions**:
  - `primary["complete_phrase_presented"] is False`
  - `primary["lexical_nodes_store_token_ids"] is False` (**Core invariant: zero token IDs in concept graph**)
  - `primary["production_reads_token_ids_from_graph"] is False`
  - `primary["speech"]["surface"] == "I like Josh"`
  - `primary["speech"]["exact"] is True`
  - `primary["speech"]["projection_tensor"] in {"output.weight", "token_embd.weight"}`
  - `primary["hatch_ready"] is True`
  - `shuffled["speech"]["surface"] == " JoshI like"`
  - `shuffled["hatch_ready"] is False`
  - `untrained["speech"]["surface"] == ""`
  - `untrained["hatch_ready"] is False`

### 3.2 Coverage Evaluation & Identified Gaps
1. **Substitution Condition**: Executed in CLI `main()` (`"I prefer music"`), but omitted from pytest suites.
2. **Negative Feedback Dynamics**: While `shuffled` generates a mismatch, explicit unit tests verifying the resulting conflict penalty escalation (`conflict_penalty += abs(change) * 0.25`) and log strength degradation on penalized edges are not directly asserted in `test_nursery.py`.
3. **Soft Failure on Missing Assets**: If `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf` or the compiled `lexeme_codec` binary is absent, pytest skips without failure, which could mask missing build artifacts in CI/CD pipelines.

---

## 4. Execution Requirements, GGUF Dependencies & Potential Pitfalls

### 4.1 System & Runtime Dependencies
1. **Model Asset**: `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf`
   - File size: 639,446,688 bytes (~639 MB).
   - Architecture: Qwen3-0.6B (Q8_0 quantization).
   - Hidden embedding dimension: 1024 (`n_embd = 1024`).
   - Vocabulary size: ~151,936 tokens.
2. **Native C++ Binaries**:
   - Location: `experiments/graph_native_live/native/lexeme_codec` and `graph_soft_generator`.
   - Build requirements: g++ (-std=c++17 -O2), `llama.cpp` headers (`/tmp/llama.cpp-b9509` or local headers), linked with `-lllama -lggml -lggml-base -ldl -pthread`.
   - Runtime dynamic link libraries: `/usr/local/lib/ollama` (configured via `OLLAMA_LIB_DIR` and `LD_LIBRARY_PATH`).

### 4.2 Potential Pitfalls & Edge Cases
1. **Hardcoded Model Paths**:
   - `MODEL = Path("/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf")` is hardcoded across `nursery.py`, `reverse_nursery.py`, `opaque_skeleton.py`. If moved or run in different container/user environments, path override or CLI flags (`--model`) must be passed.
2. **CPU Vocabulary Projection Overhead**:
   - In `reverse_nursery.py`, `nearest_tokens()` performs a brute-force cosine similarity across all ~151k vocabulary embedding rows on CPU with row dequantization. While adequate for 3-5 query states (~200ms), scaling to long sequence lengths will require batched BLAS/GPU GEMM or quantized vector search.
3. **Leading Whitespace in Tokenizer**:
   - Qwen's byte-pair encoding represents space-prefixed words as distinct tokens (e.g. `" like"` vs `"like"`). The curriculum explicitly passes `" like"` and `" Josh"` with leading spaces so detokenization correctly produces `"I like Josh"` without requiring punctuation or delimiter post-processing. Passing unspaced strings would concatenate into `"IlikeJosh"`.
4. **Subword Averaging vs. Multi-Token Decoding**:
   - Multi-token lexemes average subword embeddings during ingestion in `lexeme_codec tokenize`. In reverse projection, `nearest` retrieves the single closest token piece. For complex words breaking into multiple BPE pieces, direct top-1 token projection may retrieve only the root subword token.

---

## 5. Architectural Synthesis for Downstream Milestones

Milestone 1 successfully proves the feasibility of:
1. Grounding opaque, label-free graph memory to frozen LLM lexical space without textual prompt serialization.
2. Generating correct sequential syntax purely through Y-axis graph traversal across conserved topological weights.
3. Eliminating token representations entirely from agent storage (`reverse_nursery.py`), establishing a continuous geometric interface ready for Milestone 2 (`graph_soft_generator` continuous packet streaming to Qwen3 GGUF).
