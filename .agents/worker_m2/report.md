# Milestone 2 Verification Report: Native GGUF Soft-Input Adapter Execution & Verification

**Date**: 2026-08-29  
**Agent**: worker_m2  
**Status**: COMPLETE / VERIFIED  
**Target Milestone**: M2 — Native GGUF Soft-Input Adapter  
**Model Asset**: `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf` (610MB, 1024D native hidden dimension, Q8_0)

---

## 1. Executive Summary

Milestone 2 establishes and verifies the direct C++ native bridge (`graph_soft_generator` and `lexeme_codec`) connecting Habitus-AI's continuous topological memory substrate with Qwen3 GGUF transformer inference. The system eliminates prompt serialization, token generation, and dictionary text injection across the inference boundary.

All verification steps, experimental controls, live seam evaluations, and automated test suites executed successfully with 100% pass rates. Zero user prompt text and zero retrieved memory strings crossed the native model boundaries.

---

## 2. Compilation & Asset Verification

### 2.1 Model Asset Verification
- **File**: `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf`
- **File Size**: `639,446,688 bytes` (610 MB)
- **Architecture**: Qwen3 0.6B (1024D hidden dimension `n_embd`, Q8_0 quantization)

### 2.2 Native Binary Compilation
- **Build Command**: `make -C experiments/graph_native_live build`
- **Compiler**: `g++ -O2 -std=c++17`
- **Include Paths**: `-I/tmp/llama.cpp-b9509/include -I/tmp/llama.cpp-b9509/ggml/include`
- **Link Libraries**: `-L/usr/local/lib/ollama -Wl,-rpath,/usr/local/lib/ollama -lllama -lggml -lggml-base -ldl -pthread`
- **Compiled Binaries**:
  - `experiments/graph_native_live/native/graph_soft_generator` (68,320 bytes)
  - `experiments/graph_native_live/native/lexeme_codec` (52,696 bytes)
- **Compilation Status**: Clean build, zero warnings, zero errors.

---

## 3. Opaque Continuous Graph State Generator Execution

### 3.1 Execution Command
```bash
PYTHONPATH=src python3 experiments/graph_native_live/opaque_skeleton.py
```

### 3.2 Methodology & Protocol
- Tested a synthetic opaque graph skeleton containing strictly synthetic concept identifiers (`U3:00000000`, `U3:00000001`, `U3:00000002`) and no lexical terms (`terms=()`).
- High-dimensional vectors (1024D) generated strictly via cryptographic hash projection (SHAKE-256) onto the unit sphere, ensuring pairwise orthogonality ($|\text{cosine}| < 0.12$).
- State encoder generated 4 continuous 1024D rows:
  1. `input_slot`: Inward path node embeddings weighted by depth.
  2. `edge_slot`: Accumulated reinforcement weight mass on traversed edges.
  3. `temporal_slot`: Recency-decayed historical pulse nodes + polarity axis.
  4. `output_slot`: Outward path node embeddings weighted by depth.
- Serialized to `HABITUS_OPAQUE_PACKET_V1` format (1024 4).

### 3.3 Experimental Condition Results
Evaluated 7 rigorous experimental conditions:

| Condition | Inward Target | Outward Target | Packet SHA256 | Zero Prompt Injected | Status |
|---|---|---|---|---|---|
| `branch_a` | `U3:00000000` | `U3:00000000` | `5c84d720...` | **True** | PASSED |
| `branch_b` | `U3:00000001` | `U3:00000001` | `bc4f5ee3...` | **True** | PASSED |
| `connected` | `U3:00000002` | `U3:00000002` | `e2a7776b...` | **True** | PASSED |
| `connected_repeat` | `U3:00000002` | `U3:00000002` | `e2a7776b...` | **True** | PASSED (Deterministic) |
| `connected_row_reversal` | `U3:00000002` | `U3:00000002` | `13ba2dc1...` | **True** | PASSED (Differentiated) |
| `connected_sign_inversion` | `U3:00000002` | `U3:00000002` | `7cc78f09...` | **True** | PASSED (Differentiated) |
| `unconnected_control` | `None` | `None` | `38b55e7d...` | **True** | PASSED (Noise floor) |

- **Summary Receipt**: `experiments/graph_native_live/opaque_runs/matrix.json`
- **Key Invariants Verified**:
  - Deterministic generation under identical state: `True` (`connected` vs `connected_repeat` match bit-for-bit).
  - Structural sensitivity: Row order reversal and sign inversion produce distinct outputs.
  - Zero dictionary or prompt words injected across all conditions.

---

## 4. Live Graph Native Seam Execution

### 4.1 Execution Command
```bash
PYTHONPATH=src python3 experiments/graph_native_live/live_tester.py --once "hello there" --show-trace
```

### 4.2 Topological Traversal & Activation Trace
- **Input Stimulus**: `"hello there"`
- **Input SHA-256**: `12998c017066eb0d2a70b94e6ed3192985855ce390f321bbdb832022888bd251`
- **Perceptual Trunk (+Y)**: `SELF` $\rightarrow$ `IN:HEAR` $\rightarrow$ `native:greeting` (joint score: `0.243997`)
- **Effector Trunk (-Y)**: `SELF` $\rightarrow$ `OUT:SPEAK` $\rightarrow$ `native:greeting` (travel time: `16.999893`)
- **Continuous Basis Activations**:
  - `speak`: `1.00000000`
  - `greeting`: `0.54399717`
  - `warm`: `0.46239759`
  - `clear`: `0.24479873`
- **Emitted Packet File**: `experiments/graph_native_live/runs/turn-1787970764024176559.packet`
- **Output JSON Receipt**: `experiments/graph_native_live/runs/turn-1787970764024176559.json`

### 4.3 Isolation Verification
- `packet_contains_raw_input`: **`false`**
- `packet_contains_memory_text`: **`false`**
- `model_received_prompt_text`: **`false`**
- `model_received_user_tokens`: **`false`**
- `adapter_kind`: `"train_free_semantic_codebook_v0"`
- `embedding_rows`: 12 (8 structural delimiter tokens + 4 soft continuous embedding rows fed via `llama_batch.embd`)

### 4.4 Model Continuation
- **Generated Tokens**: 144
- **Decoded Response**: Coherent greeting and helpful opening matching the activated `greeting`, `warm`, and `clear` continuous slots without tokenized prompt text.

---

## 5. Automated Pytest Verification

### 5.1 Milestone 2 Test Suite Execution
```bash
PYTHONPATH=src:experiments/graph_native_live pytest -v tests/test_opaque_graph_native.py tests/test_graph_native_live.py
```
**Results**:
- `tests/test_opaque_graph_native.py::test_opaque_connected_packet_has_no_language_anchors`: **PASSED**
- `tests/test_opaque_graph_native.py::test_opaque_identity_has_no_lexical_similarity_rule`: **PASSED**
- `tests/test_graph_native_live.py::test_graph_packet_omits_raw_input_and_memory_text`: **PASSED**
- `tests/test_graph_native_live.py::test_novel_input_uses_bounded_unknown_state`: **PASSED**
- **Summary**: 4 passed in 0.71s.

### 5.2 Full Repository Regression Test Suite
```bash
PYTHONPATH=src:experiments/graph_native_live pytest -v tests/
```
**Results**:
- `tests/test_accelerated_gestation.py`: **PASSED**
- `tests/test_graph_native_live.py`: **PASSED**
- `tests/test_nursery.py`: **PASSED**
- `tests/test_opaque_graph_native.py`: **PASSED**
- `tests/test_reverse_nursery.py`: **PASSED**
- `tests/test_transformer_hatch.py`: **PASSED**
- **Summary**: 10 passed in 1.48s. Zero regressions across the entire codebase.

---

## 6. Artifact Index & File Verification

| Artifact Path | Description | Verification Status |
|---|---|---|
| `experiments/graph_native_live/native/graph_soft_generator` | Native C++ soft-input generator binary | Compiled & Verified |
| `experiments/graph_native_live/native/lexeme_codec` | Native C++ vocab projection / codec binary | Compiled & Verified |
| `experiments/graph_native_live/runs/turn-*.packet` | Continuous soft basis activation packet | Verified (Zero text) |
| `experiments/graph_native_live/runs/turn-*.json` | Live turn execution receipt | Verified (Valid JSON schema) |
| `experiments/graph_native_live/opaque_runs/*.packet` | 1024D opaque vector packet files | Verified (7 conditions) |
| `experiments/graph_native_live/opaque_runs/matrix.json` | Opaque state condition summary matrix | Verified (Deterministic & isolated) |

---

## 7. Conclusion

Milestone 2 requirements are fully satisfied and verified:
1. Native C++ generator compiles cleanly and links against dynamic llama/ggml libraries.
2. 1024D continuous vectors directly condition Qwen3 GGUF via `llama_batch.embd` without prompt token serialization.
3. Both opaque (hash-derived unit vectors) and bootstrap semantic basis slots operate under complete prompt and memory isolation.
4. All test suites pass 100%.
