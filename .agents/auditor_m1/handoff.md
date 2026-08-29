# Forensic Audit Report — Milestone 1: Gestation Pipeline & Preference Graph Substrate

**Auditor**: `auditor_m1`  
**Audit Target**: Milestone 1 (Gestation Pipeline & Preference Graph Substrate)  
**Integrity Mode**: Development  
**Auditor Verdict**: **CLEAN**  
**Handoff Type**: Hard Handoff (Audit Complete)

---

## 1. Observation

A comprehensive forensic audit was conducted across all Milestone 1 source code, compiled binaries, gestated SQLite databases, GGUF model files, and test suites.

### 1.1 GGUF Model File Integrity
- Model file: `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf`
- File size: `639,446,688` bytes (~609.82 MB)
- Header inspection via binary unpacking (`struct.unpack('<IQI', ...)`):
  - Magic bytes: `GGUF` (ASCII `0x47 0x47 0x55 0x46`)
  - Version: `3`
  - Tensor count: `310`
  - Metadata KV count: `28`
  - Embedding dimension: `1024`
  - Quantization type: `Q8_0`

### 1.2 Native C++ Binaries & Execution Forensics
The native binaries located in `experiments/graph_native_live/native/` were inspected and directly executed:
- `lexeme_codec` (`52,696` bytes, ELF 64-bit LSB pie executable, x86-64, dynamically linked against `/usr/local/lib/ollama/libllama.so` and `libggml.so`).
  - Source inspection (`lexeme_codec.cpp`, 309 lines): Employs `llama_model_load_from_file`, retrieves `token_embd.weight` and `output.weight`, dequantizes row tensors via `ggml_get_type_traits(tensor->type)->to_float`, and tokenizes/detokenizes using `llama_tokenize` / `llama_token_to_piece`.
  - Empirical execution:
    ```
    $ ./experiments/graph_native_live/native/lexeme_codec /home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf tokenize I like Josh
    -> PASS: dimension=1024, items=3 (Token 'I': token_id=40, norm=0.8879; Token 'like': token_id=4803, norm=0.9912; Token 'Josh': token_id=50744, norm=0.8566)
    $ ./experiments/graph_native_live/native/lexeme_codec /home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf detokenize 40 4803 50744
    -> PASS: text='IlikeJosh'
    ```
- `graph_soft_generator` (`68,320` bytes, ELF 64-bit LSB pie executable).
  - Source inspection (`graph_soft_generator.cpp`, 464 lines): Directly feeds continuous 1024D vector rows into `llama_batch` via `batch.embd = input_embeddings.data()`, decodes via `llama_decode(context.ptr, batch)`, and samples output tokens with `llama_sampler_chain`. Zero raw text prompts or retrieved text memories cross the model boundary.

### 1.3 Gestated SQLite Database Forensics
Inspected database `experiments/graph_native_live/accelerated_gestation_runs/habitus-1787969878668476910.sqlite` (size: `16,838,656` bytes):
- **Schema & Triggers**: All 12 tables present (`metadata`, `records`, `record_links`, `concepts`, `edges`, `edge_evidence`, `vault_membership`, `traces`, `outcomes`, `experience_state`, `experience_projections`, `overlap_clusters`). Immutability triggers `records_are_immutable_update` and `records_are_immutable_delete` active and verified.
- **Concept Breakdown (276 total concepts)**:
  - `self`: 1 concept (`identity:self`)
  - `input_trunk`: 3 concepts (`IN:HEAR`, `IN:SEE`, `IN:NOTICE`)
  - `output_trunk`: 3 concepts (`OUT:SPEAK`, `OUT:LOOK`, `OUT:DO`)
  - `lower_preference`: 9 concepts (`PREF:*:*`, correctly zero-embedded for basal routing)
  - `child`: 43 concepts (unlabelled routing nodes, correctly zero-embedded `[0.0]*1024`)
  - `crown`: 46 concepts (semantic centroids, genuine 1024D non-zero float vectors with norms `0.3927` to `1.0000`)
  - `lexeme`: 171 concepts (genuine 1024D token embeddings extracted from Qwen3 GGUF weights, with empty terms `terms_json="[]"` guaranteeing tokenless memory)
- **Embedding & Centroid Verification**:
  - Non-zero vectors: `224`
  - Zero vectors: `52` (strictly the 43 child routing nodes and 9 lower preference routing nodes)
  - Lexeme nodes with explicit token/text labels: `0`
- **Edge Topology & Invariant Conservation**:
  - Total edges: `1,379` (`input`: 708, `output`: 671)
  - Global edge mass: `1.000000000` ($\pm 10^{-9}$)
  - Graph invariant violations (`mind.graph.validate_invariants()`): `[]` (CLEAN)
  - Assembly depth: Max input traversal depth is `8` across domain assemblies (`domain:relational`, `domain:operational`).
- **Gestation Manifest Metadata**:
  - `hatch_ready`: `True`
  - `coverage_accuracy_at_1`: `0.9722` (35/36 topics)
  - `semantic_accuracy_at_1`: `0.8889` (16/18 held-out paraphrases)
  - `semantic_y_reachable`: `1.0000`
  - `semantic_probe_text_leakage`: `[]` (0 leakage)
  - `productive accuracy_at_1`: `0.8889`
  - `productive accuracy_at_5`: `1.0000`
  - `shuffled_control_at_1`: `0.0000`

### 1.4 Independent Test Suite Execution
Independent empirical execution of all test targets yielded 100% pass rates:
1. `pytest -v tests/test_nursery.py`: **1 passed in 3.16s**
2. `pytest -v tests/test_reverse_nursery.py`: **1 passed in 4.41s**
3. `pytest -v tests/test_graph_native_live.py tests/test_opaque_graph_native.py`: **4 passed in 0.70s**
4. `pytest -v tests/test_accelerated_gestation.py`: **1 passed in 49.90s**
5. Full repository unit test suite (10 test modules, 37 test items): **37 passed in 2.07s**
Total: **44 passed, 0 failed, 0 skipped**.

### 1.5 Prohibited Pattern & Facade Checks
- Search for `mock`, `unittest.mock`, `MagicMock`: 0 occurrences in codebase.
- Search for `assert True`, dummy returns, or artificial pass short-circuits: 0 found.
- Control conditions: Shuffled assignments (`assignment=(2, 0, 1)`) and untrained baselines (`cycles=0`) produce verified negative outcomes (`exact=False`, `hatch_ready=False`, `surface=""`, `shuffled_control_at_1=0.0`), confirming tests are non-trivial and falsifiable.

---

## 2. Logic Chain

1. **GGUF Model Validity**:
   - Direct binary inspection of `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf` confirmed valid GGUF v3 magic, 310 tensors, and 1024D native geometry matching Qwen3-0.6B-Q8_0 specifications.

2. **Absence of Facades or Mock Bypasses**:
   - The C++ source code in `experiments/graph_native_live/native/` contains authentic implementations using `llama.h` and `ggml.h`.
   - Execution of `test_accelerated_gestation.py` took 49.90 seconds of real CPU tensor computation, demonstrating genuine forward passes through llama.cpp rather than mocked returns.

3. **Substrate Integrity & Conceptual Geometry**:
   - The gestated SQLite database contains 276 concepts across all structural layers: 171 lexeme nodes, 46 crown centroids, 43 child routing nodes, 9 preference nodes, 6 trunk nodes, and 1 self node.
   - Lexeme nodes store no text strings or token IDs in their metadata (`terms_json = "[]"`), proving tokenless memory.
   - Centroids and embeddings have valid non-zero norms in 1024D Euclidean space.

4. **Mathematical & Topological Consistency**:
   - All graph invariants hold without errors (`validate_invariants() == []`).
   - Global edge mass is strictly conserved at $1.000000000$.
   - Receptive reachability across the bicone graph achieves depth 8 for recursive domain assemblies.

---

## 3. Caveats

- **Execution Environment Dependency**: The native C++ binaries require runtime dynamic linkage with `/usr/local/lib/ollama/libllama.so` and `libggml.so`, configured via `OLLAMA_LIB_DIR` / `LD_LIBRARY_PATH`.
- **Local Model Path**: The pipeline relies on the fixed local GGUF asset path `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf`.

---

## 4. Conclusion

**Binary Verdict: CLEAN**

Milestone 1 (Gestation Pipeline & Preference Graph Substrate) satisfies all integrity requirements with zero tolerance for violations:
1. No hardcoded test passes or artificial return values.
2. No dummy or facade implementations.
3. The gestated SQLite database contains genuine conceptual nodes, non-trivial 1024D embedding centroids, and valid edge topologies with strictly conserved edge mass ($1.0$).
4. The Qwen3 GGUF model and native binaries (`lexeme_codec`, `graph_soft_generator`) execute authentically without mock bypasses.

Milestone 1 is certified **CLEAN** and approved for Milestone 2 advancement.

---

## 5. Verification Method

To independently reproduce this forensic verification:

1. **Verify Model & Native Binaries**:
   ```bash
   python3 -c "import struct; f=open('/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf', 'rb'); assert f.read(4)==b'GGUF'; print('GGUF OK')"
   make -C /home/nemo/habitus-ai-experiments/experiments/graph_native_live build
   ```

2. **Execute Forensic Inspection Utility**:
   ```bash
   python3 /home/nemo/habitus-ai-experiments/.agents/auditor_m1/forensic_inspect.py
   ```

3. **Execute Full Test Suite**:
   ```bash
   pkill -9 -f "python3.*pytest" || true
   cd /home/nemo/habitus-ai-experiments
   PYTHONPATH=src:experiments/graph_native_live pytest -v tests/test_nursery.py tests/test_reverse_nursery.py tests/test_graph_native_live.py tests/test_opaque_graph_native.py tests/test_accelerated_gestation.py
   ```

4. **Invalidation Conditions**:
   - Any test failure in the Milestone 1 suite.
   - Any non-empty return from `mind.graph.validate_invariants()`.
   - Any deviation of global edge mass from $1.0 \pm 10^{-6}$.
   - Any text token leakage in lexeme nodes or soft-input packets.
