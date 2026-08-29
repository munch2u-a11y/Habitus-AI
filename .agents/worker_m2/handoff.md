# Milestone 2 Hard Handoff Report: Native GGUF Soft-Input Adapter Execution & Verification

**Agent**: worker_m2  
**Working Directory**: `/home/nemo/habitus-ai-experiments/.agents/worker_m2`  
**Target Milestone**: M2 — Native GGUF Soft-Input Adapter  
**Handoff Type**: Hard (Task Complete)  

---

## 1. Observation

Direct observations from tool executions, compilation logs, system traces, test runs, and generated artifacts:

1. **Model Asset & Native Compilation**:
   - Model file `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf` exists with size `639,446,688 bytes` (610 MB) and native embedding dimension $d=1024$.
   - Compilation command `make -C experiments/graph_native_live build` executes:
     ```
     g++ -O2 -std=c++17 -I/tmp/llama.cpp-b9509/include -I/tmp/llama.cpp-b9509/ggml/include graph_soft_generator.cpp -L/usr/local/lib/ollama -Wl,-rpath,/usr/local/lib/ollama -lllama -lggml -lggml-base -ldl -pthread -o graph_soft_generator
     g++ -O2 -std=c++17 -I/tmp/llama.cpp-b9509/include -I/tmp/llama.cpp-b9509/ggml/include lexeme_codec.cpp -L/usr/local/lib/ollama -Wl,-rpath,/usr/local/lib/ollama -lllama -lggml -lggml-base -ldl -pthread -o lexeme_codec
     ```
   - Produced executable binaries `experiments/graph_native_live/native/graph_soft_generator` (68,320 bytes) and `lexeme_codec` (52,696 bytes) with zero compiler errors or warnings.

2. **Opaque Continuous Graph State Execution**:
   - Execution command `PYTHONPATH=src python3 experiments/graph_native_live/opaque_skeleton.py` evaluated all 7 conditions: `branch_a`, `branch_b`, `connected`, `connected_repeat`, `connected_row_reversal`, `connected_sign_inversion`, and `unconnected_control`.
   - Summary receipt `experiments/graph_native_live/opaque_runs/matrix.json` (627 lines, 22,526 bytes) records:
     - `schema`: `"habitus.opaque-graph-native.v1"`
     - `dimension`: `1024`
     - `language_labels_attached`: `false`
     - `semantic_embedding_model_used`: `false`
     - `handwritten_semantic_codebook_used`: `false`
     - Zero prompt text injected across all 7 conditions: `True`
     - Determinism: `connected` and `connected_repeat` produced identical packet SHA256 `e2a7776b...` and identical model token generations.
     - Sensitivity: `connected_row_reversal` (SHA256 `13ba2dc1...`) and `connected_sign_inversion` (SHA256 `7cc78f09...`) produced distinct packets and model outputs.

3. **Live Graph Native Seam Execution**:
   - Execution command `PYTHONPATH=src python3 experiments/graph_native_live/live_tester.py --once "hello there" --show-trace` generated:
     - Input SHA256: `12998c017066eb0d2a70b94e6ed3192985855ce390f321bbdb832022888bd251`
     - Inward traversal (+Y): `SELF` $\rightarrow$ `IN:HEAR` $\rightarrow$ `native:greeting` (joint score: 0.243997)
     - Outward traversal (-Y): `SELF` $\rightarrow$ `OUT:SPEAK` $\rightarrow$ `native:greeting`
     - Numeric activations: `speak` (1.00000000), `greeting` (0.54399717), `warm` (0.46239759), `clear` (0.24479873)
     - Packet file `experiments/graph_native_live/runs/turn-1787970764024176559.packet` contains only basis activations, zero user prompt text.
     - Receipt `experiments/graph_native_live/runs/turn-1787970764024176559.json` records `packet_contains_raw_input: false`, `packet_contains_memory_text: false`, `model_received_prompt_text: false`, `model_received_user_tokens: false`.
     - Model generated 144 tokens: Coherent greeting continuation matching the activated emotional/functional state.

4. **Pytest Suite Verification**:
   - Execution command `PYTHONPATH=src:experiments/graph_native_live pytest -v tests/test_opaque_graph_native.py tests/test_graph_native_live.py`:
     - `test_opaque_connected_packet_has_no_language_anchors`: PASSED
     - `test_opaque_identity_has_no_lexical_similarity_rule`: PASSED
     - `test_graph_packet_omits_raw_input_and_memory_text`: PASSED
     - `test_novel_input_uses_bounded_unknown_state`: PASSED
     - Result: 4 passed in 0.71s.
   - Full test suite `PYTHONPATH=src:experiments/graph_native_live pytest -v tests/`:
     - Result: 10 passed in 1.48s (100% pass across all gestation, nursery, reverse-nursery, hatch, and live native tests).

---

## 2. Logic Chain

1. *From Observations 1 & 2*:
   The native C++ bridge compiles against llama.cpp headers and dynamic libraries without external dependencies. When provided with `.packet` files containing continuous 1024D vectors (`HABITUS_OPAQUE_PACKET_V1` or `HABITUS_SOFT_PACKET_V1`), `graph_soft_generator` bypasses tokenization and prompt formatting entirely. It populates `llama_batch.embd` with the normalized continuous embedding rows and passes them directly to `llama_decode()`.

2. *From Observations 2 & 4*:
   The opaque graph encoding relies on SHAKE-256 cryptographic hashing to synthesize orthogonal unit vectors in 1024D ($|\text{cosine}| < 0.12$). Concepts possess synthetic hex IDs (`U3:...`) and empty term sets (`terms=()`). The generated packet payloads contain zero dictionary tokens or text strings, proving that continuous state dynamics can condition autoregressive transformer generation without linguistic prompts.

3. *From Observations 3 & 4*:
   The live graph native seam routes incoming stimuli through dual-trunk Y-traversal (+Y perceptual trunk for recall and candidate scoring; -Y effector trunk for action nomination and basis activation). The compiler enforces an 8-slot cap and explicitly verifies that `user_text` and retrieved memory texts are absent from the packet payload. Autoregressive sampling consumes the continuous soft slots and emits natural plain-language responses aligned with the activated concept states.

4. *From Observations 1–4*:
   All interface contracts defined in `PROJECT.md` § Interface Contracts are met. The end-to-end native execution path from graph traversal $\rightarrow$ continuous packet serialization $\rightarrow$ native `llama_batch.embd` ingestion $\rightarrow$ token generation is verified and fully functional.

---

## 3. Caveats

- Model generation execution requires the local Qwen3 GGUF file located at `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf` and dynamic libraries in `/usr/local/lib/ollama`. Unit tests in `tests/test_opaque_graph_native.py` and `tests/test_graph_native_live.py` verify Python-side packet construction, invariant checking, and isolation properties without requiring GPU or model weights.
- The bootstrap semantic codebook in `live_tester.py` uses fixed centroid anchors across 10 basis categories; continuous projection in `opaque_skeleton.py` demonstrates label-free dense state ingestion.

---

## 4. Conclusion

Milestone 2 (Native GGUF Soft-Input Adapter Execution & Verification) is 100% complete and verified:
- Native C++ binaries (`graph_soft_generator`, `lexeme_codec`) compiled cleanly.
- Opaque continuous graph state generator executed across 7 conditions with verified determinism, state differentiation, and zero prompt injection.
- Live graph native seam tester executed with verified Y-axis topological traversal, zero prompt leakage, and coherent plain-language generation.
- Milestone 2 test suites and full project test suites passed with 0 failures.

---

## 5. Verification Method

To independently reproduce and verify this milestone:

1. **Verify Native Binaries**:
   ```bash
   make -C experiments/graph_native_live build
   ```

2. **Execute Opaque Continuous Graph State Ingestion**:
   ```bash
   PYTHONPATH=src python3 experiments/graph_native_live/opaque_skeleton.py
   ```
   Inspect receipt: `experiments/graph_native_live/opaque_runs/matrix.json`.

3. **Execute Live Graph Native Seam**:
   ```bash
   PYTHONPATH=src python3 experiments/graph_native_live/live_tester.py --once "hello there" --show-trace
   ```
   Inspect emitted packet and JSON receipt in `experiments/graph_native_live/runs/`.

4. **Execute Pytest Suite**:
   ```bash
   PYTHONPATH=src:experiments/graph_native_live pytest -v tests/test_opaque_graph_native.py tests/test_graph_native_live.py
   ```
   Expected: 4 passed in ~0.7s.

5. **Full Repository Regression Suite**:
   ```bash
   PYTHONPATH=src:experiments/graph_native_live pytest -v tests/
   ```
   Expected: 10 passed in ~1.5s.

6. **Invalidation Conditions**:
   - Any compiler error in `make -C experiments/graph_native_live build`.
   - Any assertion failure in `tests/test_opaque_graph_native.py` or `tests/test_graph_native_live.py`.
   - Any user prompt text or retrieved memory strings present in generated `.packet` files.
   - Any non-zero cosine similarity ($> 0.15$) between unrelated synthetic hash embeddings in `OpaqueIdentityEmbedder`.
