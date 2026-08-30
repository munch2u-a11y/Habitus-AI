# Milestone 5 Synthesis: Continuous Cognitive Loop & Organic Conversability Suite

## Input Catalog
1. **Explorer M5-1** (`analysis.md` / `handoff.md`):
   - Comprehensive codebase mapping: Layer 3 `StructuralMiniMap` in SQLite (`concepts.structural_map_json`) and `compute_structural_overlay()`; Layer 4 softmax membrane edge weights recomputed on invocation; `SELF` preference nodes with outcome reinforcement (`reinforce_edges()`).
   - Verified zero-prompt leakage mechanics: `graph_soft_generator` takes `HABITUS_OPAQUE_PACKET_V1` and `HABITUS_SOFT_PACKET_V1` with normalized continuous vector slots without prompt injection.
2. **Explorer M5-2** (`analysis.md` / `handoff.md`):
   - Detailed blueprint for `experiments/graph_native_live/live_evaluator.py`: `LiveEvaluator` class, `step()`, `run_multi_turn_session()`, `export_state_report()`, CLI arguments, three packet strategies (`lexical_membrane`, `opaque_topological`, `soft_basis`), JSON turn telemetry (`habitus.cognitive-eval-turn.v1`).
3. **Explorer M5-3** (`analysis.md` / `handoff.md`):
   - Complete drop-in test suite for `tests/test_cognitive_conversability.py`: 4 test classes (`TestContinuousCognitiveLoop`, `TestZeroPromptLeakageInvariant`, `TestLayer3StructuralMiniMapAndLayer4Softmax`, `TestLiveEvaluatorIntegrationAndEdgeCases`).
   - Validates Layer 3 mini-maps, Layer 4 softmax sum-to-1 invariants, zero text leakage, and live GGUF soft generator integration.

## Consensus Architecture & Implementation Plan for Worker M5
1. **Target Files to Create/Update**:
   - `experiments/graph_native_live/live_evaluator.py`: Complete cognitive loop evaluator implementation.
   - `tests/test_cognitive_conversability.py`: Pytest test suite exercising live evaluator and cognitive loop invariants.
2. **Strict Invariants**:
   - Strict Red-Green TDD where test assertions are executed and verified.
   - Exactly one test runner process at any time (`pkill -9 -f "python3"` before running tests).
   - Zero Prompt Leakage: no user text or RAG memory strings in `.packet` or GGUF context.
   - Layer 3 structural mini-map vector overlay generation and Layer 4 softmax edge weight conservation ($\sum = 1.0$).
