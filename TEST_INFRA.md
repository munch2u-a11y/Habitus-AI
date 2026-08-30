# E2E Test Infra: Habitus-AI GGUF-Unified Mind Substrate

## Test Philosophy
- Requirement-driven verification of preference matrix gestation, the native GGUF soft-input
  adapter, the continuous cognitive loop, and plain-language generation.
- Dual-track opaque-box and white-box verification: every behavioural claim is checked both
  through the public seam (packets, receipts, generated text) and against the underlying graph
  state.
- Structural claims are asserted on structure. Language claims are asserted on differential and
  determinism, never on fixed model wording — the decoder is a frozen third-party model.

## Feature Inventory

| # | Feature | Requirement | Verification Target |
|---|---------|-------------|---------------------|
| F1 | Gestation & Nursery Pipeline | R1 / AC1 | `experiments/graph_native_live/accelerated_gestation.py`, `nursery.py`, `reverse_nursery.py`; `tests/test_accelerated_gestation.py`, `tests/test_nursery.py`, `tests/test_reverse_nursery.py` |
| F2 | Soft-Input GGUF Generation | R2 / AC2 | `native/graph_soft_generator`, `native/lexeme_codec`, `~/Downloads/Qwen3-0.6B-Q8_0.gguf`, 1024D continuous packets; `tests/test_graph_native_live.py`, `tests/test_opaque_graph_native.py` |
| F3 | Unified Plain Language Synthesis | R3 / AC3 | `transformer_hatch.py`, `live_tester.py`; `tests/test_challenger_m3_1.py`, `tests/test_challenger_m3_2.py` |
| F4 | Continuous Cognitive Loop | M5 / R1 | `live_evaluator.py` (`LiveEvaluator`, `TurnTelemetry`, pulse recirculation); `tests/test_cognitive_conversability.py` |
| F5 | Differential User Affinity | M6 / R2 | Per-source experience states, `PREF:*` polarization, overlap-cluster promotion; `tests/test_user_affinity_gestation.py` |
| F6 | Adversarial Bounds & Avoidant Steering | M7 / R3 | Conflict-penalty accumulation, Dijkstra travel-time inflation, bounded uncertainty fallback; `tests/test_adversarial_cognitive_bounds.py` |
| F7 | Zero-Prompt Leakage Invariant | R2 / R3 / AC | `verify_zero_prompt_leakage()` across `lexical_membrane`, `opaque_topological`, `soft_basis`; forensic byte inspection in every challenger suite |
| F8 | Affinity Language Readout | M9 / R2 | `source_affinity_state()`, `membrane_preference_polarity()`, `preference_valence_activations()`, `BASIS` anchors in `graph_soft_generator.cpp`; `TestAffinityLanguageReadout` |
| F9 | Native Boundary Integrity | M9 | Offline fallback may never masquerade as real inference; `test_native_generation_is_not_silently_mocked` |
| F10 | Fitted Continuous Projector | M10 | `projector.py` ridge fit, structural features, corpus mining, codebook comparison; `tests/test_projector.py` |
| F11 | State → Words Round Trip | M10 | Per-concept discriminative targets, template-vocabulary rejection, `lexeme_codec nearest` decode; `TestConceptVocabularyTargets`, `TestStateToWordsRoundTrip` |

## Suite Map

| Suite | Scope |
|---|---|
| `test_store_and_topology.py`, `test_graph_and_learning.py`, `test_retrieval_pipeline.py`, `test_multiresolution_memory.py` | Base engine: persistence, traversal, retrieval, vault promotion |
| `test_tools.py`, `test_output_and_demo.py`, `test_audio.py`, `test_app.py`, `test_vector_adapters.py` | Tool registry, trunk classification, audio reflex, launcher, adapters |
| `test_gestation_and_agent.py`, `test_accelerated_gestation.py`, `test_nursery.py`, `test_reverse_nursery.py` | Developmental curriculum and lexical fibers |
| `test_graph_native_live.py`, `test_opaque_graph_native.py` | Native seam smoke and opaque-packet invariants |
| `test_cognitive_conversability.py` | M5: closed loop, membrane conservation, evaluator API/CLI |
| `test_user_affinity_gestation.py` | M6 + M9: differential gestation, crystallization, valence readout |
| `test_adversarial_cognitive_bounds.py` | M7 + M9: deceptive/avoidant steering, anti-echo, boundary integrity |
| `test_projector.py` | M10: ridge fit determinism, structural features, held-out comparison against the codebook, state → words round trip |
| `test_m1_adversarial_challenge.py`, `test_challenger_m*.py` | Independent adversarial challenge suites per milestone |

## Test Execution Commands

```bash
# Full suite — 421 tests, ~14 minutes
PYTHONPATH=src:experiments/graph_native_live python3 -m pytest -o addopts= -q tests/

# Targeted requirement suites
PYTHONPATH=src:experiments/graph_native_live python3 -m pytest -o addopts= -v \
  tests/test_cognitive_conversability.py \
  tests/test_user_affinity_gestation.py \
  tests/test_adversarial_cognitive_bounds.py

# Native adapter and experiment pipelines
make -C experiments/graph_native_live/native all
make -C experiments/graph_native_live gestate-fast
make -C experiments/graph_native_live nursery
make -C experiments/graph_native_live live
```

## Runner Discipline

**Run exactly one pytest process, in the foreground.** Each native turn loads a 610 MB GGUF into
memory; concurrent suites exhaust RAM on a 16 GB machine.

**Do not use `pkill -9 -f pytest` / `pkill -9 -f python3`.** It was previously prescribed here as
"single runner discipline" and it reaps the caller's *own* subprocesses whenever two agents run
at once. That pattern produced 11 phantom `returncode=-9` suite failures and aborted the M8
victory audit mid-run: the audit's log ends after a single suite, killed by its own guard.

## Environment Prerequisites

| Asset | Path | Behaviour if absent |
|---|---|---|
| GGUF model | `~/Downloads/Qwen3-0.6B-Q8_0.gguf` | Native tests skip; evaluator falls back to a deterministic offline receipt |
| Native binaries | `experiments/graph_native_live/native/{graph_soft_generator,lexeme_codec}` | Same as above; rebuild with `make -C experiments/graph_native_live/native all` |
| llama.cpp headers | `/tmp/llama.cpp-b9509/include`, `.../ggml/include` | Native build fails; override with `LLAMA_CPP_SOURCE=` |
| llama runtime | `/usr/local/lib/ollama` (`libllama.so`, `libggml*.so`) | Link/run fails; override with `OLLAMA_LIB_DIR=` |
| GPU backends | `<runtime>/vulkan`, `<runtime>/rocm_v7_2` | CPU only; opt in with `HABITUS_NATIVE_GPU_LAYERS`, override the dir with `HABITUS_NATIVE_GPU_BACKEND_DIR` |
| numpy | any install | `tests/test_projector.py` skips; `projector.py` is unusable |

The offline fallback keeps graph, packet and zero-leakage coverage intact, but
`test_native_generation_is_not_silently_mocked` fails if the fallback is used while the real
assets are present — so a green suite on this machine always means real inference ran.

## Current State

`experimental/gguf-adapter` — **421 passed, 0 failed**, single foreground process, native adapter
and GGUF present.
