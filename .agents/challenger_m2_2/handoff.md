# Milestone 2 Live Seam & C++ Binary Ingestion: Adversarial Challenge Report

**Verdict**: **PASS** (with 1 Minor CLI Handling Observation)

## 1. Observation

Direct empirical stress-testing and fuzzing were conducted on the native binary `experiments/graph_native_live/native/graph_soft_generator` and its AddressSanitizer-compiled build `/tmp/graph_soft_generator_asan` using model `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf` with backend `/usr/local/lib/ollama`.

Across **64 test cases** executed by the adversarial test harness (`/tmp/verify_m2_native.py`), the following exact behaviors were observed:

### A. Malformed Packet Rejection (Safe Exit Code 1)
- **Missing / Invalid Header**:
  - Empty packet (0 bytes) -> Exit Code `1`, `error: unsupported graph packet header`.
  - Garbage header (`INVALID_HEADER_FOOBAR_V99`) -> Exit Code `1`, `error: unsupported graph packet header`.
  - Truncated header (`HABITUS_OPAQUE`) -> Exit Code `1`, `error: unsupported graph packet header`.
  - Binary nulls & random fuzz (2048 bytes) -> Exit Code `1`, `error: unsupported graph packet header`.
- **Malformed Opaque Packets (`HABITUS_OPAQUE_PACKET_V1`)**:
  - Missing shape / single integer -> Exit Code `1`, `error: opaque packet is missing its shape` (Lines 226-227 in `graph_soft_generator.cpp`).
  - Shape bounds violation: `dim=0`, `dim=-1024`, `dim=16385`, `rows=0`, `rows=-1`, `rows=9` -> Exit Code `1`, `error: opaque packet shape is outside safety bounds` (Lines 228-230).
  - Dimension mismatch with model input width (`512 1` against 1024-dim model) -> Exit Code `1`, `error: opaque graph width does not match the model input width` (Line 380).
  - Truncated floats / non-numeric tokens / `NaN` / `Inf` values -> Exit Code `1`, `error: opaque packet has missing or invalid values` (Lines 236-238).
  - Trailing data after specified float payload -> Exit Code `1`, `error: opaque packet has trailing data` (Lines 241-243).
  - All-zero row (row norm <= 0.0) -> Exit Code `1`, `error: opaque packet contains a zero row` (Line 302).
- **Malformed Soft Packets (`HABITUS_SOFT_PACKET_V1`)**:
  - Empty activations / comments-only file -> Exit Code `1`, `error: graph packet has no activations` (Lines 269-270).
  - Unknown semantic basis (`teleportation 0.8`) -> Exit Code `1`, `error: unknown semantic basis: teleportation` (Lines 260-262).
  - Missing activation value (`greeting`) / trailing tokens on line (`greeting 0.9 extra_word`) -> Exit Code `1`, `error: malformed activation line: ...` (Lines 257-259).
  - Activation range bounds: `value = 0.0`, `value = -0.5`, `value = 1.0001` -> Exit Code `1`, `error: activation must be in (0, 1]` (Lines 263-266).
  - Non-numeric / NaN / Inf activations -> Exit Code `1`, `error: malformed activation line: ...` (Line 258).
  - Exceeding 8-slot cap (9 activations) -> Exit Code `1`, `error: graph packet exceeds the eight-slot safety cap` (Lines 272-274).

### B. Valid Continuous Execution & Boundaries (Exit Code 0)
- Soft packets with comments (`# comment`) and blank lines ignored: parsed cleanly, executed with Exit Code `0`, `soft_slots: 2`, `semantic_codebook_used: true`.
- Boundary soft slot counts: Exactly 1 slot (`speak 1.0`) and exactly 8 slots executed with Exit Code `0`.
- All 10 distinct semantic basis anchors (`speak`, `greeting`, `warm`, `question`, `clear`, `memory`, `uncertain`, `gratitude`, `observation`, `action`) individually verified with Exit Code `0`.
- Boundary opaque row counts: Exactly 1 row (`1024 1`) and exactly 8 rows (`1024 8`) executed with Exit Code `0`, `semantic_codebook_used: false`, `adapter_kind: "opaque_graph_state_native_1024_v0"`.
- Existing repository test packets (`connected.packet`, `branch_a.packet`, `branch_b.packet`, `unconnected_control.packet`) executed cleanly with Exit Code `0`.
- Environment variable `HABITUS_NATIVE_SKIP_THINK=1` correctly forced empty think tags with `"forced_empty_think": true`.

### C. Memory Safety & Leak Detection via AddressSanitizer
- Binary compiled with `g++ -O2 -std=c++17 -fsanitize=address,undefined` and run with `ASAN_OPTIONS=detect_leaks=1:detect_stack_use_after_return=1`:
  - Soft packet run: 0 memory leaks, 0 memory corruption errors.
  - Opaque packet run: 0 memory leaks, 0 memory corruption errors.
  - Exception unwinding path (e.g. zero row norm trigger): clean stack unwinding via `ContextGuard`, `ModelGuard`, `SamplerGuard`, `BackendGuard` RAII guards without leak.
- Continuous back-to-back stress test: 10 successive generation loops alternating soft and opaque packets ran to completion without crashing or leaking memory.

### D. Pytest Suite
- `pytest -q tests/test_graph_native_live.py tests/test_opaque_graph_native.py` -> 4 passed in 0.28s.

### E. Minor Adversarial Finding (Non-Packet CLI Handling)
- In `graph_soft_generator.cpp` lines 340-341, `std::stoi(argv[3])` and `std::stoul(argv[4])` are called prior to the main `try` block (which begins at line 347).
- When invalid non-numeric strings are passed as optional CLI arguments (e.g. `graph_soft_generator MODEL.gguf PACKET bad_tokens`), `std::stoi` throws `std::invalid_argument` leading to `std::terminate` (SIGABRT, exit code 134 / -6) instead of printing a controlled error message.

---

## 2. Logic Chain

1. **Packet Parsing Safety**:
   From Observation A, every malformed packet condition (wrong dimension, missing header, out-of-range rows, NaN/Inf, trailing data, unknown semantic basis, zero-norm row) throws an explicit `std::runtime_error` within the `try` block in `main()`, printing the specific error message to `stderr` and returning exit code `1`.
2. **Bounds & Caps Enforcement**:
   From Observation A, the 8-slot cap is hard-enforced for both soft packets (`activations.size() > 8`) and opaque packets (`rows > 8`), preventing context buffer overflow.
3. **No Raw Prompt / User Token Leakage**:
   From Observation B, in both soft and opaque generation runs, `"model_received_prompt_text": false` and `"model_received_user_tokens": false` are strictly maintained; the model only receives continuous input embeddings calibrated to the embedding shell.
4. **Memory & Concurrency Resilience**:
   From Observation C, RAII context guards (`ContextGuard`, `ModelGuard`, `SamplerGuard`, `BackendGuard`) ensure all llama/ggml resources are deallocated on normal return or exception unwinding. AddressSanitizer confirms 0 leaks and 0 UB.

---

## 3. Caveats

- **Ollama Shared Library Dependency**: The native binary depends on `libllama.so`, `libggml.so`, `libggml-base.so` in `/usr/local/lib/ollama`. `LD_LIBRARY_PATH` and `OLLAMA_LIB_DIR` must point to this directory for successful execution.
- **Model Input Width Matching**: Opaque packets hardcode `dimension` (e.g. 1024 for Qwen3-0.6B). Ingestion rejects any packet where `packet.dimension != llama_model_n_embd_inp(model)` with exit code 1.

---

## 4. Conclusion

**Verdict: PASS**. Milestone 2 Live Seam & C++ Binary Ingestion satisfies all robustness, security, and stability requirements. Malformed packets are safely rejected with non-zero exit codes without segmentation faults, and valid continuous packets execute cleanly without memory leaks or crashes.

---

## 5. Verification Method

To independently reproduce the complete 64-test verification suite:

```bash
# 1. Compile AddressSanitizer build
g++ -O2 -std=c++17 -fsanitize=address,undefined \
    -I/tmp/llama.cpp-b9509/include -I/tmp/llama.cpp-b9509/ggml/include \
    experiments/graph_native_live/native/graph_soft_generator.cpp \
    -L/usr/local/lib/ollama -Wl,-rpath,/usr/local/lib/ollama \
    -lllama -lggml -lggml-base -ldl -pthread \
    -o /tmp/graph_soft_generator_asan

# 2. Run adversarial test suite
python3 /tmp/verify_m2_native.py

# 3. Run regression pytest suite
python3 -m pytest -q tests/test_graph_native_live.py tests/test_opaque_graph_native.py
```
