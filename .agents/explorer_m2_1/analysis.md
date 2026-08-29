# Milestone 2 Technical Analysis: Native GGUF Soft-Input C++ Generator

**Target System**: Habitus-AI Native GGUF Soft-Input Adapter (`experiments/graph_native_live/native/`)  
**Investigated Files**:
- `experiments/graph_native_live/native/graph_soft_generator.cpp`
- `experiments/graph_native_live/native/lexeme_codec.cpp`
- `experiments/graph_native_live/native/Makefile`
- `experiments/graph_native_live/live_tester.py`
- `experiments/graph_native_live/opaque_skeleton.py`
- `experiments/graph_native_live/transformer_hatch.py`
- Target Model: `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf`

---

## 1. Architectural Overview

Milestone 2 bridges the Habitus-AI graph memory substrate (Hourglass bicone topology with +Y perceptual and -Y effector trunks) directly with a native GGUF transformer model (`Qwen3-0.6B-Q8_0.gguf`) in C++ using `llama.cpp`.

Unlike standard LLM interfaces that convert internal states or graph traversals into natural language prompts before tokenization, the Habitus-AI Native Soft-Input Generator feeds **dense 1024D continuous activation vectors directly into the transformer's input embedding layers** (`llama_batch.embd`). The model generates coherent language continuations conditioned entirely on continuous internal preference activations and topological embeddings without seeing user prompt tokens or serialized text.

```
+-----------------------------------------------------------------------------------+
|                           Habitus Graph Memory Substrate                          |
|  - Dual-cipher conserved-weight graph                                            |
|  - Bicone topology (Perceptual +Y / Effector -Y)                                 |
|  - Pulse propagation, crown nomination, edge reinforcement                       |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                           Packet Formulation Layer                                |
|  - HABITUS_SOFT_PACKET_V1:   Basis anchors + scalar activations (0, 1]            |
|  - HABITUS_OPAQUE_PACKET_V1: Dense 1024D float rows (topology/state/centroids)   |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|               graph_soft_generator (Native C++ / llama.cpp Bridge)                |
|                                                                                   |
|  1. Packet Parser: Ingests .packet, validates bounds, extracts continuous rows     |
|  2. Embedding Shell Projector: Calibrates vectors to target model norm shell      |
|  3. Sequence Assembler:                                                           |
|     [prefix_embd] + [projected_soft_embd_rows] + [suffix_embd]                    |
|  4. llama.cpp Batch Ingestion:                                                    |
|     batch.n_tokens = total_rows; batch.embd = input_embeddings.data();            |
|     llama_decode(ctx, batch); // Zero-token prompt decoding                       |
|  5. Autoregressive Sampler:                                                       |
|     llama_sampler_sample() -> top_k, top_p, temp, dist -> token_piece()           |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|               Plain Language Continuation (JSON Response Envelope)                |
+-----------------------------------------------------------------------------------+
```

---

## 2. Packet Parsing, Vector Extraction & Shell Normalization

### 2.1 Packet Formats and Parser Implementation
`graph_soft_generator.cpp` implements `load_packet(const std::string & path)` (lines 215–277) to parse two distinct packet types:

#### A. Opaque Packet (`HABITUS_OPAQUE_PACKET_V1`)
Used by `opaque_skeleton.py` and `transformer_hatch.py` to transmit pure topological vectors, pulse history vectors, or lexeme centroid embeddings:
```text
HABITUS_OPAQUE_PACKET_V1
<dimension: int32> <rows: int32>
<float_0_0> <float_0_1> ... <float_0_1023>
<float_1_0> <float_1_1> ... <float_1_1023>
...
```
- **Parsing Logic (lines 223–244)**:
  - Verifies header is exactly `"HABITUS_OPAQUE_PACKET_V1"`.
  - Reads `dimension` and `rows`.
  - Safety assertions: `1 <= dimension <= 16384` and `1 <= rows <= 8` (enforcing the 8-slot cognitive bound).
  - Reads `dimension * rows` floats into `packet.values`.
  - Validates `std::isfinite(value)` on every float.
  - Ensures no trailing data exists after the specified rows.

#### B. Semantic Soft Packet (`HABITUS_SOFT_PACKET_V1`)
Used by `live_tester.py` to transmit graph crown nominations as semantic basis activations:
```text
HABITUS_SOFT_PACKET_V1
speak 1.00000000
greeting 0.85000000
warm 0.68000000
```
- **Parsing Logic (lines 246–276)**:
  - Reads line-by-line, ignoring empty lines and comments (`#`).
  - Parses each line into `basis` (string) and `value` (float).
  - Validates `basis` against predefined `BASIS` codebook (lines 61–72) containing 10 categories: `speak`, `greeting`, `warm`, `question`, `clear`, `memory`, `uncertain`, `gratitude`, `observation`, `action`.
  - Validates `std::isfinite(value)` and range `0.0 < value <= 1.0`.
  - Enforces non-empty activations and maximum 8 slots cap.

---

### 2.2 Projection and Shell Normalization

Language model embedding spaces have specific geometric properties: input embeddings reside on a hyperspherical shell with characteristic L2 norms ($||e_i||_2$). If input vectors have arbitrary or uncalibrated magnitudes, the transformer's attention heads and RMSNorm layers will suffer from numerical saturation, out-of-distribution softmax distributions, or degraded attention patterns.

`graph_soft_generator.cpp` implements two normalization mechanisms:

#### A. Opaque Embedding Shell Projection (`place_on_embedding_shell`, lines 279–310)
For opaque packets, raw 1024D vectors are projected to match the empirical mean L2 norm of the model's structural delimiter tokens:
1. Calculates `target_norm`:
   $$\text{target\_norm} = \frac{1}{M} \sum_{m=1}^M ||e_{\text{structural}, m}||_2$$
   where structural rows are the exact embeddings of `<|im_start|>user\n` and `<|im_end|>\n<|im_start|>assistant\n`.
2. For each opaque input row $r \in [0, \text{rows}-1]$:
   $$\text{current\_norm}_r = ||v_r||_2 = \sqrt{\sum_{d=0}^{1023} (v_{r, d})^2}$$
3. Checks $\text{current\_norm}_r > 0$, then scales:
   $$v'_{r, d} = v_{r, d} \times \left(\frac{\text{target\_norm}}{\text{current\_norm}_r}\right)$$
4. Result: Every continuous input row lands exactly on the native embedding shell of the model without altering its angular orientation.

#### B. Semantic Slot Synthesis (`semantic_slot`, lines 173–213)
For semantic basis activations:
1. For basis anchors (e.g. `greeting` $\to$ `{" hello", " welcome", " greetings"}`), tokenizes each anchor word without special tokens.
2. Extracts raw weights from `token_embd.weight` via `exact_input_embeddings`.
3. Computes the centroid direction:
   $$\mathbf{s} = \frac{1}{N} \sum_{i=1}^N \mathbf{e}_{\text{anchor}, i}$$
4. Computes target norm as the mean anchor norm:
   $$\text{target\_norm} = \frac{1}{N} \sum_{i=1}^N ||\mathbf{e}_{\text{anchor}, i}||_2$$
5. Computes current centroid norm $||\mathbf{s}||_2$.
6. Applies bounded activation amplitude scaling:
   $$\text{scale} = \frac{\text{target\_norm} \times (0.85 + 0.30 \times \text{clamp}(\text{activation}, 0, 1))}{||\mathbf{s}||_2}$$
   $$\mathbf{s}' = \mathbf{s} \times \text{scale}$$
7. Result: The norm of the synthesized slot is strictly bounded in $[0.85 \times \text{target\_norm}, 1.15 \times \text{target\_norm}]$, preserving the model's native shell geometry while allowing graph activation strength to modulate vector amplitude by $\pm 15\%$.

---

## 3. llama.cpp `llama_batch` Ingestion & Zero-Token-Prompt Decoding

### 3.1 Direct Embedding Sequence Construction
In `graph_soft_generator.cpp` (lines 366–396):
1. **Prefix Tokens**: `<|im_start|>user\n` $\to$ tokenized and converted to exact embedding rows via `exact_input_embeddings()`.
2. **Soft Slots**: 1 to 8 rows of continuous 1024D float vectors (either `place_on_embedding_shell()` output or `semantic_slot()` outputs).
3. **Suffix Tokens**: `<|im_end|>\n<|im_start|>assistant\n` (or with `<think>\n\n</think>\n\n` if `HABITUS_NATIVE_SKIP_THINK` is active) $\to$ tokenized and converted to exact embedding rows.
4. **Combined Buffer**: All rows are sequentially appended into `std::vector<float> input_embeddings`. Total length is $\text{input\_rows} \times n\_embd$.

### 3.2 `llama_batch` Embedding Ingestion
In llama.cpp, `llama_batch` supports two mutually exclusive input modes:
- **Token ID Mode**: `batch.token` points to an array of `llama_token` integers.
- **Embedding Mode**: `batch.embd` points to a contiguous float buffer of shape $(\text{n\_tokens} \times n\_embd)$.

`graph_soft_generator.cpp` configures the batch exclusively in Embedding Mode (lines 408–413):
```cpp
llama_batch batch{};
batch.n_tokens = input_rows;
batch.embd = input_embeddings.data();
if (llama_decode(context.ptr, batch) != 0) {
    throw std::runtime_error("initial embedding decode failed");
}
```
- `batch.token` remains `nullptr` / unset.
- `batch.embd` provides raw float embeddings directly to the model's first transformer block, bypassing the token ID lookup table entirely.
- `llama_decode(context.ptr, batch)` processes the full sequence in a single forward pass, populating the KV cache across all `input_rows` positions and computing output logits at position $\text{input\_rows} - 1$.

### 3.3 Zero Prompt Serialization Guarantee
- At no point is the user prompt, memory text, or node label converted into tokens or passed to `llama_decode`.
- The structural prefix and suffix role tokens provide the minimal framing required by the ChatML template.
- The entire semantic payload consists strictly of floating-point embedding rows derived from graph state.

---

## 4. Logit Generation, Sampling, and Detokenization

### 4.1 Sampler Chain Pipeline
`graph_soft_generator.cpp` builds a modular `llama_sampler` chain (lines 415–422):
1. `llama_sampler_init_top_k(40)`: Restricts candidate logits to top 40 probability mass.
2. `llama_sampler_init_top_p(0.90f, 1)`: Nucleus sampling retaining cumulative probability $\le 0.90$ (minimum 1 token kept).
3. `llama_sampler_init_temp(0.70f)`: Softens logit distribution ($T = 0.70$).
4. `llama_sampler_init_dist(seed)`: Samples from the softmax probability distribution using the specified PRNG seed (default `42u`).

### 4.2 Autoregressive Loop
The autoregressive generation loop (lines 424–436) proceeds as follows:
```cpp
std::string response;
int32_t generated = 0;
for (; generated < maximum_tokens; ++generated) {
    const llama_token token = llama_sampler_sample(sampler.ptr, context.ptr, -1);
    if (llama_vocab_is_eog(vocab, token)) {
        break;
    }
    response += token_piece(vocab, token);
    llama_token mutable_token = token;
    llama_batch next = llama_batch_get_one(&mutable_token, 1);
    if (llama_decode(context.ptr, next) != 0) {
        throw std::runtime_error("generated-token decode failed");
    }
}
```
1. **Sampling**: `llama_sampler_sample(sampler.ptr, context.ptr, -1)` samples a token ID from logits at the latest sequence position (`-1`).
2. **EOG Detection**: `llama_vocab_is_eog(vocab, token)` checks if the sampled token is an End-Of-Generation token (`<|im_end|>`, `<|endoftext|>`). If true, generation terminates immediately.
3. **Detokenization**: `token_piece(vocab, token)` invokes `llama_token_to_piece()` with dynamic buffer allocation, converting the token ID into UTF-8 text and appending to `response`.
4. **Feedback Step**: `llama_batch_get_one(&mutable_token, 1)` creates a 1-token batch in Token ID Mode (`batch.token` set) and passes it to `llama_decode(context.ptr, next)`. This increments sequence length by 1 and produces logits for the next position.

### 4.3 JSON Envelope Output
On completion, the binary outputs a complete JSON trace to stdout (lines 438–457):
```json
{
  "response": "...",
  "generated_tokens": 18,
  "soft_slots": 4,
  "structural_rows": 9,
  "embedding_rows": 13,
  "model_received_prompt_text": false,
  "model_received_user_tokens": false,
  "forced_empty_think": false,
  "semantic_codebook_used": true,
  "adapter_kind": "train_free_semantic_codebook_v0"
}
```

---

## 5. Auxiliary Utility: `lexeme_codec.cpp`

`lexeme_codec.cpp` is a companion C++ utility providing low-level vocabulary access, token-embedding dequantization, and reverse nearest-neighbor projection:

| Mode | Input Arguments | Operation | Output JSON |
|---|---|---|---|
| `tokenize` | `MODEL.gguf tokenize TEXT...` | Tokenizes text, extracts and dequantizes `token_embd.weight` rows, averages tokens to produce 1024D centroid vector | `{"dimension": 1024, "items": [{"text": ..., "token_ids": [...], "embedding": [...]}]}` |
| `detokenize` | `MODEL.gguf detokenize TOKEN_ID...` | Renders token ID sequence into UTF-8 text via `llama_token_to_piece` | `{"text": "..."}` |
| `nearest` | `MODEL.gguf nearest TOP_K VECTOR...` | Parses 1024D comma-separated float vectors, calculates cosine similarity against all valid tokens in `output.weight` (or `token_embd.weight`), returns top-K nearest tokens | `{"dimension": 1024, "tensor": "output.weight", "items": [{"candidates": [{"token_id": ..., "piece": ..., "score": ...}]}]}` |

---

## 6. Model Compatibility & Build Infrastructure

### 6.1 Model Compatibility: `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf`
- **File Verification**: Verified present at `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf` (639,446,688 bytes).
- **Native Dimension**: Qwen3-0.6B has hidden dimension $d_{model} = 1024$.
- **Tensor Dequantization**:
  - `token_embd.weight` is quantized in `Q8_0` (8-bit quantization).
  - Both `graph_soft_generator.cpp` and `lexeme_codec.cpp` use `ggml_get_type_traits(tensor->type)->to_float` and `ggml_backend_tensor_get()` to dequantize Q8_0 blocks into FP32 arrays on the fly.
  - Dimension checks in code verify `tensor->ne[0] == 1024`.

### 6.2 Compilation Architecture & Makefile Analysis
`experiments/graph_native_live/native/Makefile`:
```makefile
CXX ?= g++
CXXFLAGS ?= -O2 -std=c++17
LLAMA_CPP_SOURCE ?= /tmp/llama.cpp-b9509
OLLAMA_LIB_DIR ?= /usr/local/lib/ollama

INCLUDES = -I$(LLAMA_CPP_SOURCE)/include -I$(LLAMA_CPP_SOURCE)/ggml/include
LIBS = -L$(OLLAMA_LIB_DIR) -Wl,-rpath,$(OLLAMA_LIB_DIR) \
	-lllama -lggml -lggml-base -ldl -pthread

.PHONY: all clean

all: graph_soft_generator lexeme_codec

graph_soft_generator: graph_soft_generator.cpp
	$(CXX) $(CXXFLAGS) $(INCLUDES) $< $(LIBS) -o $@

lexeme_codec: lexeme_codec.cpp
	$(CXX) $(CXXFLAGS) $(INCLUDES) $< $(LIBS) -o $@

clean:
	rm -f graph_soft_generator lexeme_codec
```

- **Include Headers**:
  - Located at `/tmp/llama.cpp-b9509/include` (`llama.h`) and `/tmp/llama.cpp-b9509/ggml/include` (`ggml.h`, `ggml-backend.h`). Verified present on filesystem.
- **Dynamic Libraries & RPATH**:
  - Located in `/usr/local/lib/ollama` (`libllama.so`, `libggml.so`, `libggml-base.so`).
  - `-Wl,-rpath,$(OLLAMA_LIB_DIR)` embeds runtime library path directly into binary ELF header.
- **Internal Symbol Binding**:
  - Declares `extern const std::vector<std::pair<std::string, ggml_tensor *>> & llama_internal_get_tensor_map(const llama_model * model);`. This symbol is exported by the Ollama-pinned `libllama.so.0.0.1` in `/usr/local/lib/ollama`.
- **Dynamic CPU Backend Loading**:
  - `ggml_backend_load_all_from_path(backend_dir.c_str())` loads CPU acceleration plugins (AVX2, AVX512, Zen4, SSE4.2) dynamically at runtime.

---

## 7. Summary Table of Component Interfaces

| Component | Responsibility | Inputs | Outputs | Verification Method |
|---|---|---|---|---|
| `graph_soft_generator` | Ingests packet + model, runs embedding decode, emits sampled text | GGUF model path, `.packet` file path, max_tokens, seed | JSON containing response text, token counts, adapter metadata | Run with test packet and check `model_received_prompt_text: false` |
| `lexeme_codec` | Tokenization, dequantization, nearest-token vocabulary lookup | GGUF model path, mode (`tokenize`/`detokenize`/`nearest`), args | JSON with token IDs, 1024D embeddings, or candidate tokens | Execute `tokenize "hello"` and verify `dimension == 1024` |
| `.packet` Parser | Reads structured ASCII packet files | File path to `.packet` | `Packet` struct with rows and continuous values | Unit test parsing against corrupted/out-of-bounds files |
| Shell Normalizer | Projects vectors to model embedding sphere | 1024D continuous vectors + structural token embeddings | Calibrated 1024D vectors matching target L2 norm | Verify vector norm equals structural token mean norm |
| llama.cpp Ingestion | Feeds embeddings directly to decoder | `llama_batch` with `batch.embd` pointer and `batch.n_tokens` | KV cache populated, logits generated at final position | Check `llama_decode` return code == 0 |
