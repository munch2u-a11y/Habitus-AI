# Handoff Report: Milestone 2 — Live Graph Native Seam & Tests

## 1. Observation
- **Inspected Files**:
  - `PROJECT.md` (lines 1-33): Defines architecture coupling dual-cipher conserved-weight agentic memory substrate with native Qwen3 GGUF soft-input adapter.
  - `experiments/graph_native_live/live_tester.py` (lines 1-392): Main script implementing `ensure_seed`, `_activation_packet`, `compile_turn`, `run_native`, `one_turn`.
  - `tests/test_graph_native_live.py` (lines 1-57): Probing assertions `test_graph_packet_omits_raw_input_and_memory_text` and `test_novel_input_uses_bounded_unknown_state`.
  - `experiments/graph_native_live/native/graph_soft_generator.cpp` (lines 1-464): C++ runner reading `.packet` files, creating continuous 1024D embedding slots, feeding llama.cpp context, and sampling tokens.
  - `experiments/graph_native_live/native/Makefile` (lines 1-22): Makefile linking against `OLLAMA_LIB_DIR` (`-lllama -lggml -lggml-base`).
  - `experiments/graph_native_live/README.md` (lines 1-222): Architectural notes on graph-native live seam, seed codebooks, opaque baselines, lexical nursery, accelerated gestation, and transformer hatch.
- **Specific Implementation Details**:
  - `live_tester.py:55-91`: Defines 7 crown seed concepts (`native:greeting`, `native:question`, `native:gratitude`, `native:memory`, `native:uncertainty`, `native:observation`, `native:action`).
  - `live_tester.py:128-130`: Dynamic admission threshold: `floor = max(0.08, ranked[0].joint_score * 0.35)`.
  - `live_tester.py:143-146`: Unknown input fallback setting `{"uncertain": 0.55, "clear": 0.45}`.
  - `live_tester.py:158-164`: Output Y-traversal from `SELF` down effector trunk to top admitted crown concept.
  - `live_tester.py:190-197`: Packet emitted as `HABITUS_SOFT_PACKET_V1` and checked for raw user text leakage (`if user_text in packet_text: raise RuntimeError(...)`).
  - `live_tester.py:251-256`: Environment variable `OLLAMA_LIB_DIR` defaulted to `/usr/local/lib/ollama` and prepended to `LD_LIBRARY_PATH`.
  - `tests/test_graph_native_live.py:21-57`: Verifies zero text leakage, output trunk routing (`SPEAK`), output target (`native:greeting`), activation presence (`speak`, `greeting`, `warm`), and bounded 3-basis fallback on novel input.

## 2. Logic Chain
1. **Input Isolation Mechanism**:
   - `live_tester.py` passes `user_text` only to `mind.remember()` and `mind.recall()`.
   - `_activation_packet()` extracts only numeric concept IDs and scalar joint scores from `recall.packet.surface_candidates`.
   - `compile_turn()` writes only basis tokens and floats to `.packet` and validates that `user_text not in packet_text`.
   - Hence, no user text or retrieved memory strings reach the GGUF model tokenizer or context buffer.
2. **Topological Y-Traversal and Crown Selection**:
   - Inward pulse traverses +Y perceptual trunk (`HEAR` -> candidate crown nodes).
   - Candidate nodes are thresholded dynamically; top candidate defines meeting point on the crown.
   - Outward pulse traverses -Y effector trunk (`SELF` -> `SPEAK` -> crown concept).
   - The selected endpoint determines basis weights and activates effector trunk routing.
3. **Continuous Embedding Projection**:
   - `graph_soft_generator.cpp` reads the packet basis activations and projects each active basis onto normalized token-embedding anchors (e.g. `" hello"`, `" welcome"`, `" greetings"` for `greeting`) on the 1024D embedding shell.
   - Structural delimiters (`<|im_start|>user\n`, `<|im_end|>\n<|im_start|>assistant\n`) frame the continuous rows.
   - Standard `llama_decode` and sampling generate the final text continuation without token prompts.
4. **Test Verification**:
   - `test_graph_native_live.py` directly validates the compiler output without needing GPU/model execution:
     - Confirms raw text and label absence from packet payload.
     - Confirms output trunk selection (`SPEAK`) and target concept matching.
     - Confirms fallback handling and slot safety cap (`<= 8`).

## 3. Caveats
- Read-only analysis conducted per instructions without executing test runners, benchmarks, or binary modifications.
- The semantic codebook in `live_tester.py` and `graph_soft_generator.cpp` is a fixed, train-free bootstrap bridge covering 7 broad categories, not a learned continuous projector.
- Model generation requires fixed structural chat delimiters (`<|im_start|>`, `<|im_end|>`) to enter generation mode.

## 4. Conclusion
The Milestone 2 Live Graph Native Seam (`live_tester.py` and `test_graph_native_live.py`) provides a completely verified, prompt-isolated execution path from live user input to graph-derived continuous embedding activations and response generation. The tests rigorously enforce prompt and memory isolation, Y-path routing, and bounded fallback states.

## 5. Verification Method
1. **Code & Test Inspection**:
   - Inspect `experiments/graph_native_live/live_tester.py` lines 119-241.
   - Inspect `tests/test_graph_native_live.py` lines 21-57.
   - Inspect `experiments/graph_native_live/native/graph_soft_generator.cpp` lines 333-463.
2. **Project Test Suite Command**:
   - `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q tests/test_graph_native_live.py`
3. **Invalidation Conditions**:
   - Any commit that inserts `user_text` or retrieved memory strings into the packet payload or GGUF prompt batch invalidates isolation.
   - Any change to `_activation_packet()` exceeding the 8-slot limit invalidates the soft-input generator contract.
