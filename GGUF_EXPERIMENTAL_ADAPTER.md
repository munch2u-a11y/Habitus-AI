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

### 4. Fitted Continuous Projector (Replacing the Authored Codebook)
`projector.py` fits the graph-to-embedding map from the mind's own records instead of
hand-picked anchors. Closed-form ridge regression, numpy only, no training loop:

```text
graph state features (3078D)  ->  W  ->  1024D row in the model's input embedding space
primal  W = (XᵀX + λI)⁻¹XᵀY        dual  W = Xᵀ(XXᵀ + λI)⁻¹Y
```

Features are structural only — concept centroid, Layer 3 overlay, dominant preference-node
vector, and the six valence diagnostics. Targets are the model's own token-embedding rows for
the text each record actually deposited, so the pairing is whatever the curriculum produced.

Measured on a mind gestated with 10 differential turns (71 pairs, 25% held out, seeded shuffle):

| λ | train cosine | holdout cosine (fitted) | holdout cosine (codebook) | fitted wins |
|---|---|---|---|---|
| 0.1 | 0.643 | 0.420 | 0.142 | 94% |
| 1.0 | 0.639 | **0.425** | 0.142 | 94% |
| 10.0 | 0.583 | 0.424 | 0.142 | 94% |

Roughly **3× better alignment** with the true text embedding on unseen states, stable across two
orders of magnitude of regularization. Fitting takes seconds; the only model cost is one
`lexeme_codec` invocation, which embeds the whole corpus in a single process.

Run it, then use it in the loop:

```bash
PYTHONPATH=src:experiments/graph_native_live python3 \
  experiments/graph_native_live/projector.py --database MIND.sqlite

PYTHONPATH=src:experiments/graph_native_live python3 \
  experiments/graph_native_live/live_evaluator.py --packet-mode projected \
  --projector experiments/graph_native_live/projector_runs/projector.json ...
```

**What this does not yet fix.** A better-aligned row did *not* produce better generated language:
`projected` turns still decode to the same generic output as the other raw-vector modes. The
bottleneck is the target, not the fit — `lexeme_codec` returns a *mean-pooled* embedding, and
pooling a seven-token sentence collapses the row norm from ~0.9 to ~0.36, so even a perfect fit
reproduces a blurred sentence centroid. One such row is also thin next to the 3–8 anchor-snapped
slots `soft_basis` emits. The next step is per-token targets: predict k rows against the actual
token-embedding sequence rather than its mean, which stays closed-form ridge with a wider Y.

### 5. Per-Concept Vocabulary Projection (State → Words)

Regressing onto pooled *sentence* embeddings caps out because pooling blurs the target. The
per-concept form fixes the granularity to the one the substrate actually has, and learns each
concept's anchors instead of authoring them:

1. Group records by crown concept (trunk, preference and `SELF` nodes excluded — every record
   touches them, so they carry no distinguishing vocabulary).
2. Score each concept's words by tf-idf and drop any word appearing in more than 10% of
   concepts. A developmental curriculum is templated, so frame vocabulary ("broader",
   "coactivation") recurs everywhere and describes the curriculum rather than any concept.
3. Embed the surviving words with a leading space — the tokenizer's mid-sentence form, and the
   same convention the authored anchors use — and average them into one direction per concept.
4. Fit structural state features → that direction, closed-form ridge as before.
5. Decode predictions back through the model's vocabulary projection with `lexeme_codec nearest`.

Measured on a gestated mind (`accelerated_gestation`, 276 concepts, 494 records, 86 crown
concepts with ≥3 records):

| Ubiquity cutoff | Template-contaminated concepts | Train cosine | **State → words** |
|---|---|---|---|
| 0.25 | 16 / 86 | 0.905 | 81% |
| **0.10** | **0 / 86** | 0.881 | **91%** |
| 0.05 | 0 / 86 | 0.881 | 91% |

**39 of 43 lexical concepts decode to one of their own discriminative words**, most of them to
all three:

```
concept:auto:2aca685c...  own=[files, hold, named]              decoded=[files, hold, named]
concept:auto:4ca66979...  own=[confidence, capability, success] decoded=[confidence, capability, success]
concept:auto:1d3cf27f...  own=[commands, executable, request]   decoded=[executable, commands, Commands]
concept:auto:3246afed...  own=[curiosity, investigation, invites] decoded=[investigation, curiosity, invites]
concept:auto:0445e82d...  own=[friendship, people, share]       decoded=[friendship, share, people]
```

Run it:

```bash
PYTHONPATH=src:experiments/graph_native_live python3 \
  experiments/graph_native_live/projector.py --mode concept --embedder native \
  --database experiments/graph_native_live/accelerated_gestation_runs/MIND.sqlite
```

**Two honest limits.**

*Opaque children do not decode.* Of 86 crown concepts, 43 carry a centroid and 43 are
`child:auto:*` nodes stored with a zero embedding by design — the architecture's own invariant,
asserted by `test_child_concepts_have_zero_lexical_terms_and_zero_embedding`. Their predictions
land at the origin and `nearest` returns nothing. That is the design working, not the projector
failing, but it does mean half the crown is unreachable by this route.

*Unseen concepts do not generalize.* Holding out whole concepts and predicting their vocabulary
direction from structural neighbourhood alone gives cosine 0.14–0.18 — barely above nothing. With
86 samples in 3078 dimensions that is expected; predicting the vocabulary of a concept the mind
has never lexicalized is a genuinely harder problem than reading out one it has. Known concepts
are the case that matters for generation, and that case works.

### 6. GPU Offload

The adapter loads every ggml backend it can find and honours `HABITUS_NATIVE_GPU_LAYERS`:

```bash
HABITUS_NATIVE_GPU_LAYERS=99 PYTHONPATH=src:experiments/graph_native_live python3 ...
```

On an AMD Phoenix3 APU (Radeon 780M, RADV, uma, fp16, KHR_coopmat, 23 GB visible) all 28 layers
offload through Vulkan, worth about **25%** on this model — 50 tok/s CPU vs 63 tok/s Vulkan,
including a load that dominates at 0.6B. ROCm loads but reports no capable device: gfx1103 needs
`HSA_OVERRIDE_GFX_VERSION` and a ROCm userspace that the shipped build does not provide.

**The default stays CPU.** Backend choice changes float ordering and therefore generated text, and
byte-reproducibility across machines is worth more than 25% here.

### 7. Formal Verification
* **407/407 Tests Passing** (29 suites, single foreground process, 826 s): base engine, graph-native seam, cognitive conversability, user affinity, adversarial bounds, and the per-milestone challenger suites.
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
