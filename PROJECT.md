# Project: Habitus-AI GGUF-Unified Mind Substrate

## Architecture
Habitus-AI couples a dual-cipher conserved-weight agentic memory substrate (Hourglass bicone topology with +Y Perceptual and -Y Effector trunks) with a native Qwen3 GGUF soft-input adapter.

1. **Gestation & Behavioral Reinforcement**:
   - `accelerated_gestation.py` & `nursery.py`: Builds, populates, and stabilizes conceptual preference graph nodes and lexical fibers across 1024D native token geometry.
   - Preserves conserved edge weights, layer reachability, and lexical projection bindings.
2. **Native GGUF Soft-Input Adapter**:
   - `graph_soft_generator.cpp` & `lexeme_codec.cpp`: Direct C++ / llama.cpp bridge compiling to native binaries (`graph_soft_generator`, `lexeme_codec`).
   - Ingests 1024D continuous preference vectors and outputs transformer logit vectors using `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf` without token prompt serialization.
3. **End-to-End Plain Language Synthesis**:
   - `transformer_hatch.py` & `live_tester.py`: Encodes incoming stimuli, nominates crown concepts, executes Y-axis traversal, constructs bounded continuous slot activations, and synthesizes coherent plain-language continuations.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Gestation Pipeline & Substrate | Verify & execute gestation curriculum, preference matrix growth, nursery lexical bindings | None | DONE |
| M2 | Native GGUF Soft-Input Adapter | Verify C++ binary builds, continuous 1024D vector feeding to Qwen3 GGUF, and logit emission | M1 | DONE |
| M3 | End-to-End Unified Synthesis | Execute transformer hatch & live tester pipelines from stimulus to plain language output | M2 | DONE |
| M4 | Comprehensive E2E Verification | Execute full graph-native test suite, adversarial tests, and forensic integrity audit | M3 | DONE |
| M5 | Continuous Cognitive Loop & Live Evaluator | Implement live_evaluator.py and test_cognitive_conversability.py for Layer 4 semantic membrane & SELF preference loop | M4 | DONE |
| M6 | Differential User Affinity & Habitual Memory | Implement test_user_affinity_gestation.py for differential developmental stimuli & habitual memory crystallization | M5 | DONE |
| M7 | Adversarial Bounds & Deceptive Steering | Implement test_adversarial_cognitive_bounds.py for false-positive rejection & self-preservation steering | M6 | DONE |
| M8 | Complete Test Suite Integrity & Victory Audit | Run 100% pytest suite, adversarial verification, and victory forensic audit | M7 | DONE |
| M9 | Affinity Language Readout | Project habitual preference state onto `affinity`/`caution`/`withhold` basis slots so plain language tracks learned stance | M8 | DONE |



## Interface Contracts
### Gestation Substrate ↔ Soft-Input Generator
- Binary input: Continuous 1024D float vectors formatted into `.packet` buffers containing layer activations and categorical basis slots.
- Execution contract: `graph_soft_generator --model /home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf --packet <path>` emits valid token logits and continuous text.
- Output contract: Plain language decoded text matching preference state without raw user prompt injection.

### Preference Membrane ↔ Valence Basis Slots
- `affinity`, `caution`, `withhold` are activated only from persisted experience states
  (`preference_mean` × `preference_weight` per source) and `PREF:*:STABLE` / `PREF:*:UNSTABLE`
  edge statistics — never from stimulus text.
- Contract: `preference_valence_activations(mind, source_id=...)` returns `(activations, diagnostics)`
  with every slot in `RESERVED_BASIS_SLOTS` and every activation in `(0.0, 1.0]`.
- The C++ `BASIS` table in `native/graph_soft_generator.cpp` is the authoritative anchor map;
  `RESERVED_BASIS_SLOTS` in `live_evaluator.py` must stay in sync with it.

## Code Layout
- `src/habitus_ai/`: Core Habitus-AI Python engine (store, graph, topology, retrieval, tools)
- `experiments/graph_native_live/`: Native experiment scripts, gestation pipelines, and C++ source (`native/`)
- `tests/`: Test suite including `test_graph_native_live.py`, `test_opaque_graph_native.py`, `test_accelerated_gestation.py`, `test_nursery.py`, `test_reverse_nursery.py`
