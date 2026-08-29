# Handoff Report — Explorer M3-3
**Milestone 3: End-to-End Unified Plain Language Synthesis**
**Date**: 2026-08-28T22:40:00Z
**Agent**: Explorer M3-3 (`.agents/explorer_m3_3`)

---

## 1. Observation

### 1.1 Project Architecture & Milestone 3 Scope
- **`PROJECT.md`** (lines 13, 20):
  - Architecture component 3: *"transformer_hatch.py & live_tester.py: Encodes incoming stimuli, nominates crown concepts, executes Y-axis traversal, constructs bounded continuous slot activations, and synthesizes coherent plain-language continuations."*
  - Milestone M3 Contract: *"End-to-End Unified Synthesis: Execute transformer hatch & live tester pipelines from stimulus to plain language output"*.
  - Gestation Substrate ↔ Soft-Input Generator Contract (lines 24-27): Continuous 1024D float vectors formatted into `.packet` buffers; `graph_soft_generator --model /home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf --packet <path>` emits valid token logits and continuous text matching preference state without raw prompt serialization.

### 1.2 Existing Test Infrastructure & Gaps
- **`TEST_INFRA.md`** (lines 12, 18, 22):
  - Feature F3: *"Unified Plain Language Synthesis: transformer_hatch.py, live_tester.py, coherent output strings"*.
  - Execution targets: `pytest tests/test_graph_native_live.py`, `make -C experiments/graph_native_live live`, `make -C experiments/graph_native_live transformer-hatch`.
- **`tests/test_graph_native_live.py`** (lines 21-57):
  - `test_graph_packet_omits_raw_input_and_memory_text`: Validates `LIVE.compile_turn` generates a `HABITUS_SOFT_PACKET_V1` omitting raw input text and memory text, activates `SPEAK` output trunk, and targets `native:greeting`.
  - `test_novel_input_uses_bounded_unknown_state`: Validates fallback to bounded unknown state (`uncertain: 0.55, clear: 0.45`).
  - **Critical Gap Observed**: `tests/test_graph_native_live.py` only tests Python compilation up to `packet.write_text()`. It does **not** execute the C++ binary `graph_soft_generator`, does **not** invoke Qwen3 GGUF inference, does **not** test `LIVE.one_turn()`, does **not** verify generated plain-language response text coherence, and does **not** test outbound response persistence in graph memory.
- **`tests/test_opaque_graph_native.py`** (lines 21-57):
  - Validates `HABITUS_OPAQUE_PACKET_V1` serialization (1024D, 4 rows) and orthogonality of `OpaqueIdentityEmbedder` (`|cosine| < 0.12`). Does not test live stimulus-to-speech loop.
- **`tests/test_accelerated_gestation.py`** (lines 100-117):
  - Tests batch `TRANSFORMER.run_probe_matrix` against a gestated mind, asserting `expected_word_rate == 1.0`, `target_beats_unrelated_rate == 1.0`, `prompt_text_crossed_native_boundary == False`.
  - Focuses on gestation pipeline validation rather than interactive/live agent stimulus-response loop.
- **`experiments/graph_native_live/live_tester.py`** (lines 168-323):
  - Full single-turn synthesis loop: `compile_turn(mind, text, packet_path)` -> `run_native(runner, model, packet_path, ...)` -> `mind.remember(response, record_type=RecordType.OUTBOUND_MESSAGE)`.
- **`experiments/graph_native_live/transformer_hatch.py`** (lines 263-387):
  - Full probe matrix generation: `select_endpoint` -> `ordered_lexical_rows` (1024D continuous vectors) -> `run_case` (`graph_soft_generator` on Qwen3 GGUF) -> `response_scores` (cosine similarity to target concept).
- **`experiments/graph_native_live/native/graph_soft_generator.cpp`** (lines 53-277):
  - Loads GGUF model via llama.cpp, parses either `HABITUS_SOFT_PACKET_V1` or `HABITUS_OPAQUE_PACKET_V1`, projects slots onto token embedding norm shell (1024D), and executes autoregressive text generation.

---

## 2. Logic Chain

1. **Acceptance Criteria Decomposition**:
   - Milestone 3 requires proving the complete unified plain-language synthesis chain:
     $$\text{Stimulus} \xrightarrow{\text{Habitus X/Y}} \text{Graph State Update} \xrightarrow{\text{Soft Adapter}} \text{1024D Soft Vectors} \xrightarrow{\text{Qwen3 GGUF}} \text{Coherent Plain Language} \xrightarrow{\text{Memory Ingestion}} \text{Graph Outbound Record}$$
   - Currently, unit tests in `tests/test_graph_native_live.py` stop at the `.packet` generation seam, leaving the GGUF execution and plain language output unverified in the automated CI/pytest suite.

2. **Required E2E Test Suite for Milestone 3**:
   - To achieve full test coverage and fulfill Milestone 3 acceptance criteria, a dedicated automated test suite (`tests/test_m3_unified_synthesis.py` or extended `test_graph_native_live.py`) must verify:
     - **E2E Live Turn Synthesis**: Call `live_tester.one_turn()` with real model/runner, verifying exit code 0, non-empty coherent response string, and outbound record storage.
     - **Prompt Isolation Invariant**: Verify zero user prompt strings or token IDs enter `.packet` or model context (`native["model_received_prompt_text"] is False`, payload regex check).
     - **Semantic Discrimination**: Verify that target concept response embeddings beat unrelated/random controls (`response_similarity_to_selected_concept > unrelated_similarity`).
     - **Multi-Turn Graph Continuity**: Execute 2 consecutive turns; verify turn 1 outbound memory is stored with `RecordType.OUTBOUND_MESSAGE`, and turn 2 processes normally without graph deadlock or invariant violations (`validate_invariants() == []`).
     - **Novel & Degenerate Input Handling**: Test OOV phrases ("violet engines drift sideways") and empty/whitespace inputs; verify fallback to bounded unknown state and safe completion.

3. **Process Management & Single Runner Isolation Logic**:
   - GGUF inference via `graph_soft_generator` and SQLite WAL-mode databases (`mind.sqlite`) are sensitive to concurrent process execution:
     - Memory/compute contention from multiple llama.cpp instances.
     - SQLite lock contention (`sqlite3.OperationalError: database is locked`) when multiple test runners access the same file.
   - Single runner guarantee requires:
     - Pre-execution process sanitization: `pkill -9 -f "python3"` and `pkill -9 -f "graph_soft_generator"`.
     - File-system level mutex / lockfile (`/tmp/habitus_m3_runner.lock`) during test suite execution.
     - Strict isolation using pytest `tmp_path` fixture for all temporary mind databases and `.packet` files.
     - Subprocess timeout guards (`timeout=60` or `120`) to prevent zombie runner processes.

---

## 3. Caveats

- **Model Dependency**: Real GGUF inference tests require `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf` and compiled binary `experiments/graph_native_live/native/graph_soft_generator`. Tests must include `@pytest.mark.skipif` when these assets are missing to allow graceful degradation in minimal CI environments.
- **Language Expressiveness Scope**: Milestone 3 tests the native soft-input adapter and bicone traversal synthesis seam. As noted in `experiments/graph_native_live/README.md`, responses are guided by learned 1024D lexical geometry and codebook anchors; open-ended free conversation outside the gestated curriculum is an M4/future evaluation objective.
- **Read-Only Scope**: This analysis was conducted purely read-only without modifying any source files or running heavy compute.

---

## 4. Conclusion

1. **Current State**: Milestone 1 (Gestation) and Milestone 2 (C++ Soft-Input Adapter) are marked DONE in `PROJECT.md`. The core synthesis scripts (`transformer_hatch.py`, `live_tester.py`, `graph_soft_generator.cpp`) are fully functional, but automated end-to-end integration tests connecting stimulus to generated text in pytest are incomplete.
2. **Key Recommendation for Worker M3**:
   - Implement comprehensive automated E2E tests in `tests/test_graph_native_live.py` (or a dedicated `tests/test_m3_unified_synthesis.py`) testing live stimulus-to-response generation, semantic discrimination, multi-turn memory ingestion, and prompt isolation.
   - Enforce single runner execution via process sanitization and lockfile isolation.
   - Execute and verify the complete probe matrix and live tester CLI runs, generating JSON receipts under `transformer_hatch_runs/` and `runs/`.

---

## 5. Verification Method

### 5.1 Pre-Execution Sanitization & Build
```bash
# 1. Clean up any stray processes
pkill -9 -f "graph_soft_generator" || true
pkill -9 -f "lexeme_codec" || true
pkill -9 -f "python3" || true

# 2. Build native C++ binaries
make -C experiments/graph_native_live build
```

### 5.2 Red-Green TDD Test Execution (Pytest)
```bash
# Execute M3 test suite in isolated single runner
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -v \
  tests/test_graph_native_live.py \
  tests/test_opaque_graph_native.py \
  tests/test_nursery.py \
  tests/test_reverse_nursery.py \
  tests/test_accelerated_gestation.py
```

### 5.3 Live Synthesis CLI Verification
```bash
# 1. Live tester single turn with trace inspection
PYTHONPATH=src python3 experiments/graph_native_live/live_tester.py \
  --model /home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf \
  --once "hello there" \
  --show-trace

# 2. Live tester complex inquiry
PYTHONPATH=src python3 experiments/graph_native_live/live_tester.py \
  --model /home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf \
  --once "Can you explain how memory works?" \
  --show-trace

# 3. Transformer hatch probe matrix verification
PYTHONPATH=src python3 experiments/graph_native_live/transformer_hatch.py \
  --model /home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf
```

### 5.4 Invalidation Conditions
- Any test where raw user prompt or recalled memory text appears in the `.packet` payload or model context.
- Native runner exit code != 0 or generation of empty/degenerate output text.
- Target concept semantic similarity failing to exceed unrelated/random controls (`target_beats_unrelated_rate < 0.75`).
- Concurrent runner process collision or unhandled SQLite lock errors.
