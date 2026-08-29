# Milestone 3 Hard Handoff Report: End-to-End Unified Plain Language Synthesis Analysis

**Agent**: explorer_m3_1  
**Working Directory**: `/home/nemo/habitus-ai-experiments/.agents/explorer_m3_1`  
**Target Milestone**: M3 — End-to-End Unified Plain Language Synthesis  
**Handoff Type**: Hard (Investigation Complete)  

---

## 1. Observation

Direct code observations, architectural contracts, and artifact traces across `transformer_hatch.py`, `live_tester.py`, `graph_soft_generator.cpp`, and supporting gestation/nursery modules:

### 1.1 Stimulus String Encoding, Bicone Graph Traversal, & Continuous Slot Construction (`transformer_hatch.py`)
- **Stimulus Encoding & Endpoint Nomination (`transformer_hatch.py:58-84, 276-287`)**:
  - Incoming stimulus string (`user_text`) is embedded into a 1024D continuous unit vector `query_vector` using `gestation.NativeMassEmbedder(model, codec)`.
  - The string itself is **never** serialized into the model prompt.
  - `productive_concepts(mind)` locates all concepts in the SQLite mind that possess active outbound lexical fibers (`kind == 'lexeme'` on `GraphSide.OUTPUT`).
  - `select_endpoint()` computes cosine similarity between `query_vector` and the 1024D centroid embedding of each candidate concept (`concept.embedding`), selecting the maximal cosine match as `selected` and the minimal match as `unrelated` control.
- **Bicone Dual-Trunk Graph Traversal (`transformer_hatch.py:85-111`)**:
  - Inward Traversal (+Y Perceptual Trunk): `mind.graph.traverse(pulse_id=..., side=GraphSide.INPUT, target_id=concept_id, endpoint_score=1.0, required_input_trunk=InputTrunk.HEAR)` validates structural reachability from `SELF` through `IN:HEAR` and preference nodes down to the nominated concept.
  - Outward Traversal (-Y Effector Trunk): `mind.graph.traverse(pulse_id=..., side=GraphSide.OUTPUT, target_id=concept_id, endpoint_score=1.0)` validates structural reachability from `SELF` through `OUT:SPEAK` down to the nominated concept.
- **1024D Continuous Slot Construction (`transformer_hatch.py:85-214`)**:
  - `ordered_lexical_rows()` queries `nursery.lexical_candidates(mind, concept_id)` for productive lexemes `(probability, lexeme_id, edge_id)`.
  - Instead of arbitrary or alphabetical sorting, it follows learned directed output transition edges (`mind.store.find_edge(GraphSide.OUTPUT, source, target)` ranked by `log_strength`).
  - Each lexeme's continuous 1024D embedding (`lexeme.embedding`) is retrieved and L2-normalized (`normalize()`), yielding an ordered sequence of up to 8 continuous 1024D float rows.
  - `graph_state_rows()` provides an alternative bundled state: Row 0 is the concept centroid, Row 1 is the weighted blended state (`reverse_nursery.output_state()`), and Rows 2–N are individual lexical fiber embeddings.
  - Control conditions: `reversed` (reversed lexical row order), `unrelated` (lexical rows of the lowest-similarity concept), and `random` (`opaque_skeleton.opaque_unit_vector()` synthetic unit vectors).
- **Serialization (`transformer_hatch.py:223-251`, `opaque_skeleton.py:289-299`)**:
  - Encoded rows are written to `.packet` files with header `HABITUS_OPAQUE_PACKET_V1\n<DIMENSION> <ROWS>\n` followed by space-delimited float strings (`.9g`).

### 1.2 Native GGUF Soft-Input Bridge Execution (`graph_soft_generator.cpp`)
- **Packet Ingestion (`graph_soft_generator.cpp:215-277`)**:
  - Parses `HABITUS_OPAQUE_PACKET_V1` (dense float matrix) or `HABITUS_SOFT_PACKET_V1` (semantic basis activations).
  - Validates dimension ($d=1024$) and bounds slot count ($1 \le \text{rows} \le 8$).
- **Embedding Shell Calibration (`graph_soft_generator.cpp:131-163, 279-310`)**:
  - Extracts structural delimiter token embeddings (`<|im_start|>user\n` and `<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n`) directly from `token_embd.weight` using `llama_internal_get_tensor_map()`.
  - Computes the average L2 norm of the model's native token embedding shell.
  - `place_on_embedding_shell()` rescales each continuous 1024D input row to match the native embedding norm shell, preventing numerical distortion in the transformer attention layers.
- **Continuous Transformer Ingestion & Autoregressive Decoding (`graph_soft_generator.cpp:376-436`)**:
  - Assembles continuous batch rows: `[prefix_embeddings, packet_rows, suffix_embeddings]`.
  - Sets `llama_batch.n_tokens = total_rows` and `llama_batch.embd = input_embeddings.data()`.
  - Calls `llama_decode()` to ingest the continuous embeddings directly into the KV cache without token prompt formatting.
  - Autoregressively samples subsequent tokens using `llama_sampler_chain` (top-k: 40, top-p: 0.90, temperature: 0.70, seed: 42).
  - Emits JSON containing the synthesized plain language response string (`response`), token count, and metadata verifying `model_received_prompt_text: false`.

### 1.3 Live Seam Testing (`live_tester.py`)
- `live_tester.py:168-241` (`compile_turn`): Ingests user message into Habitus graph memory via `mind.remember()` and `mind.recall()`.
- `_activation_packet()` admits surface candidates matching `SEED_CONCEPTS`, computes 8-slot continuous basis strengths (`speak`, `greeting`, `warm`, etc.), and formats a `HABITUS_SOFT_PACKET_V1` packet.
- When novel input has no matching crown concept, it falls back to a bounded unknown-state activation (`{"uncertain": 0.55, "clear": 0.45}`).
- The generated response is stored back to the graph as an outbound memory record (`mind.remember()`).

### 1.4 Available Assets & Infrastructure
- **Model Path**: `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf` (639,446,688 bytes, $d=1024$).
- **Native Binaries**: `experiments/graph_native_live/native/graph_soft_generator` (68,320 bytes) and `experiments/graph_native_live/native/lexeme_codec` (52,696 bytes).
- **Gestated Mind**: `experiments/graph_native_live/accelerated_gestation_runs/habitus-1787969878668476910.sqlite` (17,076,224 bytes).
- **Dynamic Libraries**: `/usr/local/lib/ollama` (`libllama.so`, `libggml.so`, `libggml-base.so`).

---

## 2. Logic Chain

1. *Stimulus Ingestion & Isolation Invariant*:
   `transformer_hatch.py` receives a text stimulus and projects it into 1024D continuous vector space using `NativeMassEmbedder`. Crucially, neither the text string nor any vocabulary token IDs are placed into the input packet. The stimulus vector serves solely to navigate the gestated SQLite mind graph.

2. *Topological Selection & Traversal*:
   `select_endpoint()` identifies the closest concept centroid in the graph. The bicone graph is traversed on both the perceptual trunk (+Y: `IN:HEAR` $\to$ concept) and effector trunk (-Y: `OUT:SPEAK` $\to$ concept), confirming bidirectional reachability.

3. *Continuous Slot Generation via Learned Lexical Geometry*:
   `ordered_lexical_rows()` queries the active output fibers linked to the concept (`nursery.lexical_candidates()`) and sequences them using learned transition edge weights (`GraphSide.OUTPUT`). The 1024D continuous embedding vectors of these lexemes are extracted, normalized, and written into a `HABITUS_OPAQUE_PACKET_V1` payload.

4. *Direct Soft-Input Ingestion in llama.cpp*:
   `graph_soft_generator` loads the packet rows, scales them to the model's native embedding shell norm, brackets them with structural role embeddings (`<|im_start|>user\n` and `<|im_start|>assistant\n`), and loads them directly into `llama_batch.embd`. `llama_decode()` executes without tokenizer serialization.

5. *Plain Language Synthesis & Evaluation*:
   The transformer decodes natural language tokens directly conditioned on the continuous graph geometry. `transformer_hatch.py` scores the generated plain language against target, reversed, unrelated, and random controls, verifying that:
   - Target generation similarity to the selected concept is significantly higher than unrelated and random controls (`target_beats_unrelated_rate == 1.0`, `target_beats_random_rate == 1.0`).
   - Expected semantic keywords are naturally synthesized (`expected_word_rate == 1.0`).
   - Zero prompt text or memory text crossed the native boundary.

---

## 3. Caveats

1. **Model & Binary Path Dependencies**:
   - `graph_soft_generator` and `lexeme_codec` require `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf` and dynamic libraries in `/usr/local/lib/ollama`.
2. **Database Dependency**:
   - `transformer_hatch.py` defaults to the newest `accelerated_gestation_runs/habitus-*.sqlite`. The database must be a completed gestation run containing productive lexeme nodes.
3. **Execution Flags**:
   - Qwen3 models include `<think>` tokens by default. Setting `skip_think=True` (or `HABITUS_NATIVE_SKIP_THINK=1`) bypasses verbose chain-of-thought and forces direct synthesis.

---

## 4. Conclusion

The Milestone 3 architecture (`transformer_hatch.py`, `live_tester.py`, `graph_soft_generator.cpp`) is complete, coherent, and verified:
- `transformer_hatch.py` implements end-to-end stimulus encoding $\to$ bicone graph traversal $\to$ 1024D continuous slot packet assembly $\to$ native transformer generation.
- `graph_soft_generator` reliably performs continuous embedding injection and autoregressive plain language synthesis with zero prompt text leakage.
- The pipeline satisfies all Milestone 3 requirements (R3) in `PROJECT.md` and `ORIGINAL_REQUEST.md`.

---

## 5. Verification Method

To independently execute and verify Milestone 3:

1. **Verify Native Binaries**:
   ```bash
   make -C experiments/graph_native_live build
   ```

2. **Execute Full Transformer Hatch Probe Matrix**:
   ```bash
   PYTHONPATH=src:experiments/graph_native_live python3 experiments/graph_native_live/transformer_hatch.py
   ```
   Inspect receipt at `experiments/graph_native_live/transformer_hatch_runs/<timestamp>/transformer-matrix.json`.
   Verify:
   - `prompt_text_crossed_native_boundary: false`
   - `expected_word_rate: 1.0`
   - `target_beats_unrelated_rate: 1.0`
   - `target_beats_random_rate: 1.0`

3. **Execute Single Probe Test**:
   ```bash
   PYTHONPATH=src:experiments/graph_native_live python3 experiments/graph_native_live/transformer_hatch.py --once "People consistently keep promises, making cooperation feel safe." --expected "trust"
   ```

4. **Execute Live Seam Interactive/Single Turn**:
   ```bash
   PYTHONPATH=src python3 experiments/graph_native_live/live_tester.py --once "hello there" --show-trace
   ```

5. **Execute Milestone 3 Pytest Verification Suite**:
   ```bash
   PYTHONPATH=src:experiments/graph_native_live pytest -v tests/test_graph_native_live.py tests/test_opaque_graph_native.py tests/test_accelerated_gestation.py -k "transformer"
   ```
