# Analysis: Milestone 2 — Live Graph Native Seam & Tests

## 1. Executive Summary
This analysis investigates the Milestone 2 Live Graph Native Seam implementation in `experiments/graph_native_live/live_tester.py` and its corresponding test suite in `tests/test_graph_native_live.py`. 

The system implements a train-free, bootstrap graph-to-model bridge. Live user messages enter the Habitus memory substrate, are recorded immutably, and trigger dual-trunk Y-axis graph traversals across an hourglass bicone topology (+Y Perceptual trunk and -Y Effector trunk). The resulting admitted semantic endpoints are encoded into a bounded numeric activation packet (`HABITUS_SOFT_PACKET_V1`). This packet is consumed by a native C++ runner (`graph_soft_generator`) that builds continuous 1024D soft-input embedding rows for a frozen Qwen3-0.6B GGUF model, producing generated responses with zero raw text or prompt token injection.

---

## 2. Live Input Pulses, Y-Path Traversal, Crown Selection & Packet Formatting

### 2.1 Component Architecture and Data Flow
```
User Message ("hello there")
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ BaseAgenticMemoryRAG Ingestion                         │
│ 1. mind.remember() -> Immutable RAW_MEMORY record      │
│ 2. mind.recall()   -> Pulse generation & Event routing │
└────────────────────────────────────────────────────────┘
       │
       ├── +Y Perceptual Traversal (HEAR Trunk -> Crown Concepts)
       ▼
┌────────────────────────────────────────────────────────┐
│ Crown Endpoint Nomination & Admission                  │
│ Filter: candidate in SEED_CONCEPTS                     │
│ Dynamic Threshold: floor = max(0.08, top_score * 0.35) │
└────────────────────────────────────────────────────────┘
       │
       ├── Top Candidate Target Selected (e.g., native:greeting)
       ├── -Y Effector Traversal (SELF -> OUTPUT:SPEAK -> Target)
       ▼
┌────────────────────────────────────────────────────────┐
│ Activation Packet Construction                         │
│ - Base Effector: speak = 1.0                           │
│ - Basis activations weighted by joint score & rank     │
│ - Novel input fallback: {uncertain: 0.55, clear: 0.45} │
│ - Safety cap: <= 8 slots                               │
└────────────────────────────────────────────────────────┘
       │
       ▼
Bounded Soft Packet (`HABITUS_SOFT_PACKET_V1`)
```

### 2.2 Detailed Mechanism in `live_tester.py`

#### 2.2.1 Seed Initialization (`ensure_seed`)
- **Location**: `experiments/graph_native_live/live_tester.py:55-117`
- Defines seven canonical semantic crown concepts:
  - `native:greeting`: terms `('hello', 'hi', 'hey', 'greetings', 'morning', 'evening')`, basis: `greeting: 1.0`, `warm: 0.85`, `clear: 0.45`
  - `native:question`: terms `('what', 'why', 'how', 'which', 'who', 'question', 'explain')`, basis: `question: 1.0`, `clear: 0.85`
  - `native:gratitude`: terms `('thanks', 'thank', 'appreciate', 'grateful')`, basis: `gratitude: 1.0`, `warm: 0.80`
  - `native:memory`: terms `('remember', 'recall', 'memory', 'before', 'earlier')`, basis: `memory: 1.0`, `clear: 0.65`
  - `native:uncertainty`: terms `('unsure', 'uncertain', 'maybe', 'unknown', 'guess')`, basis: `uncertain: 1.0`, `clear: 0.55`
  - `native:observation`: terms `('see', 'look', 'notice', 'observe', 'describe')`, basis: `observation: 1.0`, `clear: 0.65`
  - `native:action`: terms `('do', 'run', 'make', 'build', 'create', 'execute')`, basis: `action: 1.0`, `clear: 0.65`
- Registers these concepts in `mind.store` attached to `InputTrunk.HEAR` and `OutputTrunk.SPEAK` and deposits seed raw memories with `allow_growth=False`.

#### 2.2.2 Turn Compilation (`compile_turn`)
- **Location**: `experiments/graph_native_live/live_tester.py:168-241`
- **Step 1: Ingestion**:
  ```python
  record = mind.remember(
      user_text,
      kind=EventKind.MESSAGE,
      source_id="live-human",
      provenance={"kind": "graph_native_live_input"},
  )
  ```
- **Step 2: Recall & Perception**:
  ```python
  recall = mind.recall(
      user_text,
      kind=EventKind.MESSAGE,
      source_id="live-human",
      exclude_record_ids=(record.record_id,),
      include_current_input=False,
  )
  ```
  This routes the event envelope through `InputTrunk.HEAR`, embeds the query, projects candidates on the semantic surface (X-axis), and performs +Y perceptual path traversal.

#### 2.2.3 Crown Endpoint Selection & Output Y-Traversal (`_activation_packet`)
- **Location**: `experiments/graph_native_live/live_tester.py:119-166`
- **Candidate Filtering & Dynamic Thresholding**:
  ```python
  ranked = [c for c in recall.packet.surface_candidates if c.concept_id in SEED_CONCEPTS]
  if ranked and ranked[0].joint_score >= 0.08:
      floor = max(0.08, ranked[0].joint_score * 0.35)
      admitted = [c for c in ranked if c.joint_score >= floor]
  else:
      admitted = []
  ```
- **Continuous Activation Calculation**:
  - Initializes `activations = {"speak": 1.0}`.
  - Iterates over top admitted candidates (`admitted[:3]`):
    - `rank_discount = 1.0 / (1.0 + 0.35 * rank)`
    - `graph_strength = max(0.20, min(1.0, candidate.joint_score + 0.30))`
    - For each `(basis, seed_strength)`:
      `activations[basis] = max(activations.get(basis, 0.0), min(1.0, seed_strength * graph_strength * rank_discount))`
- **Novel / Unadmitted Input Fallback**:
  - If `admitted` is empty:
    `activations.update({"uncertain": 0.55, "clear": 0.45})`
- **Slot Priority and Cap**:
  - Ordered by `(item[0] != "speak", -item[1], item[0])` and capped at 8 slots: `[:8]`.
- **Output Y-Path Traversal**:
  - If admitted candidates exist, top target `target = admitted[0]` is traversed on the output side:
    ```python
    output_trace = mind.graph.traverse(
        pulse_id=f"{recall.packet.pulse_id}:native-output",
        side=GraphSide.OUTPUT,
        target_id=target.concept_id,
        endpoint_score=target.joint_score,
        mark_active=True,
    )
    ```

#### 2.2.4 Soft Packet Formatting and Verification
- **Location**: `experiments/graph_native_live/live_tester.py:190-197`
- Written to `.packet` file in standard format:
  ```text
  HABITUS_SOFT_PACKET_V1
  speak 1.00000000
  greeting 1.00000000
  warm 0.85000000
  clear 0.45000000
  ```
- Strict Leak Check:
  ```python
  if user_text in packet_text:
      raise RuntimeError("raw user input leaked into the native graph packet")
  ```

---

## 3. Probe Assertions in `tests/test_graph_native_live.py`

### 3.1 Overview of Test Structure
`tests/test_graph_native_live.py` contains 57 lines and uses `pytest` with a temporary SQLite database to probe the seam without running inference.

### 3.2 Test 1: `test_graph_packet_omits_raw_input_and_memory_text`
- **Location**: `tests/test_graph_native_live.py:21-39`
- **Input**: `"hello there"`
- **Verified Assertions**:
  1. **Prompt Isolation**: `assert "hello there" not in payload`
  2. **Metadata / Label Isolation**: `assert "Greeting exchange" not in payload`
  3. **Trace Flags**:
     - `assert trace["packet_contains_raw_input"] is False`
     - `assert trace["packet_contains_memory_text"] is False`
  4. **Output Routing**:
     - `assert trace["output_trunk"] == "SPEAK"`
     - `assert trace["output_path"]["target"] == "native:greeting"`
  5. **Basis Inclusion**:
     - `assert {item["basis"] for item in trace["numeric_activations"]} >= {"speak", "greeting", "warm"}`

### 3.3 Test 2: `test_novel_input_uses_bounded_unknown_state`
- **Location**: `tests/test_graph_native_live.py:41-57`
- **Input**: `"violet engines drift sideways"` (out-of-domain vocabulary)
- **Verified Assertions**:
  1. **Fallback Activation State**:
     - `assert activations == {"speak": 1.0, "uncertain": 0.55, "clear": 0.45}`
  2. **Output Path Suppression**:
     - `assert trace["output_path"] is None` (no output trace traversed)
  3. **Safety Bound**:
     - `assert len(activations) <= 8`

---

## 4. Runtime Requirements, Environment Variables & Failure Modes

### 4.1 Runtime Requirements
1. **Model Weights**:
   - Primary: `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf` (native 1024D input embedding width).
   - Fallback: `/usr/share/ollama/.ollama/models/blobs/sha256-c5396e06af294bd101b30dce59131a76d2b773e76950acc870eda801d3ab0515` (Qwen2.5 0.5B).
2. **Native C++ Runner**:
   - Binary: `experiments/graph_native_live/native/graph_soft_generator`
   - Compiled with C++17 (`g++ -O2 -std=c++17`) linked against `libllama`, `libggml`, `libggml-base`, `libdl`, `pthread`.
3. **GGML Backend Libraries**:
   - Loaded dynamically at runtime via `ggml_backend_load_all_from_path(backend_dir.c_str())`.

### 4.2 Environment Variables

| Variable | Default Value | Purpose |
|---|---|---|
| `OLLAMA_LIB_DIR` | `/usr/local/lib/ollama` | Specifies path to Ollama's shared libraries (`libllama.so`, `libggml.so`, `libggml-base.so`). Used for compilation `-L`, rpath `-Wl,-rpath`, and runtime backend plugin loading. |
| `LD_LIBRARY_PATH` | (Prepended in Python) | `live_tester.py:254-256` prepends `OLLAMA_LIB_DIR` to `LD_LIBRARY_PATH` when spawning the native subprocess. |
| `HABITUS_NATIVE_VERBOSE` | Unset (silenced) | When set, enables standard llama.cpp debug logging to stderr. When unset, `llama_log_set(quiet_log, nullptr)` silences backend noise. |
| `HABITUS_NATIVE_SKIP_THINK` | Unset | When set, closes the Qwen3 `<think>` tags immediately (`<think>\n\n</think>\n\n`) to prevent the model from spending all generated tokens in internal reasoning blocks. |

### 4.3 Failure Modes and Defense Mechanisms

| Failure Mode | Root Cause | Detection Point | Handling / Result |
|---|---|---|---|
| **Model file missing** | Missing GGUF file path | `live_tester.py:348` | `SystemExit("model not found: ...")` |
| **Native binary missing** | C++ binary not compiled | `live_tester.py:350` | `SystemExit("native runner not found: ... Build with: make -C ...")` |
| **Shared library link error** | Missing/mismatched `libllama.so` | `run_native()` subprocess | `RuntimeError: native adapter exited ...` with stderr details |
| **Raw prompt leakage** | User string matches packet payload | `live_tester.py:195` | Immediate `RuntimeError("raw user input leaked into the native graph packet")` |
| **Packet format error** | Bad header, unknown basis, NaN/inf scalar | `graph_soft_generator.cpp:215-277` | Exception thrown: `unknown semantic basis`, `activation must be in (0, 1]`, `unsupported graph packet header` |
| **Safety cap violation** | More than 8 activations in packet | `graph_soft_generator.cpp:273` | Exception thrown: `graph packet exceeds the eight-slot safety cap` |
| **Embedding dimension mismatch** | Opaque packet width != model `n_embd` | `graph_soft_generator.cpp:380` | Exception thrown: `opaque graph width does not match the model input width` |
| **Inference decode error** | `llama_decode` failure on batch | `graph_soft_generator.cpp:412` | Exception thrown: `initial embedding decode failed` |
| **Subprocess timeout** | Hang or infinite loop in runner | `live_tester.py:270` | Python `subprocess.TimeoutExpired` (180s limit) |

---

## 5. Architectural Synthesis & Milestone Context

Milestone 2 establishes the **Live Graph Native Seam** as an un-prompted, graph-guided generative bridge:
1. **Separation of Concerns**: User messages are remembered and parsed exclusively by the graph substrate; the LLM never sees raw token prompts.
2. **Deterministic Bounded Representation**: The graph activation packet translates topological state and Y-traversals into a strict 8-slot continuous vector space.
3. **Execution Verification**: Proved end-to-end through `compile_turn`, unit isolation tests in `test_graph_native_live.py`, and executable native generation receipts (`*.packet` and `*.json`).
