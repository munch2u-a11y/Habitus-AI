# Habitus-AI Experimental GGUF Soft-Input Adapter

> **Branch**: `experimental/gguf-adapter`  
> **Status**: Experimental Proof-of-Concept (Zero-Prompt-Text Vector Ingress)

---

## Executive Summary

This experimental branch demonstrates a **prompt-free architecture** linking the Habitus-AI graph memory substrate directly with a local frozen transformer (`Qwen3-0.6B-Q8_0.gguf`). 

Instead of formatting retrieved memories into text prompt strings (traditional RAG), Habitus-AI outputs **1024-dimensional continuous activation vectors** directly into `llama.cpp`'s native input embedding layer (`batch.embd`).

---

## Measured Success & Key Accomplishments

### 1. Zero Prompt Text Leakage
* User inputs and graph memory traversals update the SQLite bicone substrate (`SELF`, `HEAR`, `SPEAK`, concept nodes).
* **No text prompt, retrieved memory strings, or chat templates** are passed into `llama.cpp`.
* The native C++ helpers ([`graph_soft_generator.cpp`](experiments/graph_native_live/native/graph_soft_generator.cpp) and [`lexeme_codec.cpp`](experiments/graph_native_live/native/lexeme_codec.cpp)) convert continuous activation packets into 1024D float rows for direct model decoding.

### 2. Preference-Derived Valence Readout
* Three basis slots — `affinity`, `caution`, `withhold` — are activated from the substrate's own
  habitual memory: per-source experience states (`preference_mean` weighted by `preference_weight`)
  and the ingress membrane's `PREF:*:STABLE` / `PREF:*:UNSTABLE` edge statistics.
* No input text touches these activations. A source the substrate has learned to trust opens
  `affinity`; a source associated with destabilizing outcomes opens `caution`; accumulated
  conflict penalty on the preference membrane additionally opens `withhold`, which is how
  avoidant steering reaches the language layer.
* Empirically: after four cooperative turns from "Josh" and four hostile turns from an adversarial
  source, the identical stimulus decodes to friendly, relationship-affirming language for Josh and
  to hedged, deflecting language for the adversary — from graph state alone.

### 3. Empirical Concept & Stance Decoding
* Activating distinct preference matrix nodes (`[trust]`, `[fear]`, `[evidence]`, `[music]`) causes `Qwen3-0.6B` to decode distinct, topic-aligned plain-language responses matching the internal graph state.
* Control runs using unrelated or randomized vectors verify that topic selection is strictly driven by the continuous vector directions.

### 4. Formal Verification
* **68/68 Tests Passing**: Verified across `test_graph_native_live.py`, `test_accelerated_gestation.py`, `test_nursery.py`, `test_reverse_nursery.py`, `test_opaque_graph_native.py`, and challenger suites.
* **Forensic Audit Clean**: Zero mock classes, zero prompt leakage, and strict edge-weight conservation ($\sum w = 1.0$).

---

## Current Scope & Honest Boundaries

> **Note on RAG Replacement**: This work is an important developmental seam proof-of-concept, but does **not** claim to completely replace traditional RAG across all open-ended multi-turn domains yet.

### Current Limitations:
1. **Codebook Projection**: The current adapter maps continuous activations via GGUF token-embedding anchors and learned lexical fibers rather than a fully trained deep cross-attention projector. The decoded stance is reliably *valenced* but not always fluent — the model sometimes comments on the anchor semantics instead of speaking from them. Fluency is a projector problem, not a substrate problem.
2. **Mode Asymmetry**: Only `soft_basis` packets decode into consistently coherent language. The raw 1024D `lexical_membrane` and `opaque_topological` packets are off-distribution for a frozen Qwen3 and decode to unrelated text; they remain valuable as zero-leakage transport and topology tests.
3. **Curriculum Scope**: Complex arbitrary episodic facts outside the gestated curriculum still require expanded training.
4. **Formatting Anchors**: Structural role-delimiters remain required to signal assistant generation mode, though they carry no user or memory text.

### Next Steps:
* Replace the fixed/learned lexical codebook with an end-to-end trained continuous graph projector.
* Expand the developmental gestation kernel to handle arbitrary episodic facts without text RAG fallback.

---

## Quick Start / Reproducing the Demonstration

### 1. Prerequisites
Ensure [`Qwen3-0.6B-Q8_0.gguf`](/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf) is located in `~/Downloads/`.

### 2. Build Native C++ Adapter
```bash
make -C experiments/graph_native_live build
```

### 3. Run Live Soft-Input Turn
```bash
PYTHONPATH=src:experiments/graph_native_live python3 experiments/graph_native_live/live_tester.py \
  --model ~/Downloads/Qwen3-0.6B-Q8_0.gguf \
  --once "hello there" \
  --show-trace
```

### 4. Run Hatched Mind Proof Matrix
```bash
PYTHONPATH=src:experiments/graph_native_live python3 experiments/graph_native_live/transformer_hatch.py \
  --model ~/Downloads/Qwen3-0.6B-Q8_0.gguf
```
