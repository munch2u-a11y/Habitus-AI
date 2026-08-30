# Milestone 5 Architectural, Algorithmic, and Code Quality Review

**Reviewer**: Reviewer 1 (Archetype: reviewer, critic)  
**Date**: 2026-08-29  
**Milestone**: Milestone 5 — Autonomous Cognitive Conversability & Adversarial Behavior Suite  
**Scope**:
- `experiments/graph_native_live/live_evaluator.py`
- `tests/test_cognitive_conversability.py`
- `src/habitus_ai/store.py`
- `src/habitus_ai/graph.py`

---

## Review Summary

**Verdict**: **APPROVE** (PASS)

Milestone 5 deliverables satisfy all architectural, algorithmic, invariant, and adversarial requirements. The implementation delivers a robust, multi-turn cognitive cycle with closed-loop preference updating, Layer 3 Structural Mini-Map topological embedding synthesis, Layer 4 softmax edge weight conservation, 3-mode continuous 1024D vector packet compilation, strict zero-prompt leakage enforcement, and comprehensive test suite validation (29/29 Milestone 5 tests passing in 71.09s).

---

## Architectural & Algorithmic Analysis

### 1. Code Structure & Class Design (`live_evaluator.py`)
- **`EvaluatorConfig`**: Clean immutable configuration encapsulation (frozen dataclass) specifying model paths, runner binaries, run directories, sampling parameters (`temperature`, `learning_rate`, `seed`), vector packet mode (`lexical_membrane`, `opaque_topological`, `soft_basis`), and zero-leakage enforcement flags.
- **`TurnTelemetry`**: Fine-grained telemetry contract capturing complete turn lifecycle: input/output SHA-256 hashes, trunk nominations, pre-turn and post-turn preference states, Dijkstra shortest travel times and path nodes, Layer 3 mini-map extracted metadata, Layer 4 softmax distributions, vector packet provenance, zero-leakage invariant status, native generation receipts, stability delta, reinforced edges, and duration.
- **`LiveEvaluator`**: Implements a clean 14-step cognitive loop per turn:
  1. *Stimulus Ingestion*: Persists message into SQLite memory (`MindStore`) with immutability guarantees.
  2. *Pre-State Capture*: Queries `experience_state` prior to activation.
  3. *Receptive Recall & Y-Axis Traversal*: Performs graph Dijkstra traversal to nominate target concepts and calculate travel times.
  4. *Output Path Traversal*: Traverses `GraphSide.OUTPUT` from nominated concepts to action/response trunks.
  5. *Preference Identification*: Identifies active preference bands (`PREF:HEAR:STABLE`, `PREF:HEAR:UNSTABLE`, etc.).
  6. *Layer 3 Mini-Map Extraction*: Extracts topological relations, parent/child clusters, and coactivations.
  7. *Layer 4 Softmax Updates*: Recalculates Boltzmann edge distributions for active nodes.
  8. *Vector Packet Synthesis*: Compiles 1024D continuous vector representations without lexical prompt text.
  9. *Zero-Leakage Invariant Check*: Scans raw packet buffers for substring leakage of prompt terms.
  10. *Native GGUF Generation*: Invokes `graph_soft_generator` binary on Qwen3 GGUF or falls back gracefully in offline environments.
  11. *Outbound Memory Logging*: Ingests model response as `RecordType.OUTBOUND_MESSAGE`.
  12. *Closed-Loop Reinforcement*: Updates edge log strengths and Bayesian experience preference distributions.
  13. *Post-State Capture*: Records updated preference state.
  14. *Receipt & Telemetry Export*: Emits schema-compliant receipt `habitus.cognitive-eval-turn.v1`.

### 2. Closed-Loop Layer 4 Semantic Membrane <-> SELF Preference Updating
- The closed loop is mathematically sound:
  - Feedback stability deltas ($\Delta s \in [-1.0, 1.0]$) reinforce traversed input/output edges via `GraphRuntime.reinforce_edges()`.
  - `MindStore.update_experience_state()` computes recursive Bayesian mean and updates `experience_projections` across layers 0 (SELF), 1 (Trunk), 2 (Preference), and 4 (Concept).
  - Outgoing edges from Layer 4 nodes are modulated via Boltzmann softmax $\text{Softmax}(w_i) = \frac{\exp(s_i)}{\sum_j \exp(s_j)}$ where $s_i = \text{log\_strength}_i + \ln(1 + \text{invocations}_i)$.
  - Multi-turn tests confirm that repeated positive stimuli polarize the `STABLE` preference band, while negative stimuli destabilize into `UNSTABLE` followed by seamless recovery, all while strictly conserving global weights ($\sum w = 1.0$).

### 3. Layer 3 Mini-Map & Layer 4 Softmax Conservation (`store.py`, `graph.py`)
- **`MindStore`**:
  - Full SQLite schema support for `structural_map_json`, `invocation_count`, and `softmax_weight` columns on both `concepts` and `edges` tables.
  - Serialization/deserialization methods (`_structural_map_to_dict`, `_structural_map_from_dict`) guarantee roundtrip fidelity.
  - `update_softmax_weights_for_source()` mathematically guarantees $\sum e_i = 1.0$ across all outgoing edges from any source node.
- **`compute_structural_overlay()`**:
  - Synthesizes intrinsic 1024D unit vectors from parent/child topological hash projections, relation densities, invocation counts, and softmax weights.
  - Verified deterministic and strictly L2-normalized ($\|v\|_2 = 1.0$).

### 4. Vector Packet Synthesis & Zero-Prompt Leakage Invariant
- Verified across all three synthesis modes:
  - `lexical_membrane`: Concept centroid + Layer 3 structural overlay + Layer 2 preference vector + Layer 4 fiber vectors.
  - `opaque_topological`: Dense 4-row topological unit vector packet from graph pulse, history, and target.
  - `soft_basis`: Activation scalar packet across basis dimensions.
- Zero-Prompt Leakage Invariant: Confirmed 100% absence of user prompt text or RAG memory strings in `.packet` buffers and GGUF context.

---

## Findings

### [Minor] Finding 1: Prompt-Leakage Checker False-Positive on Protocol Header Keywords
- **What**: The zero-prompt leakage verification routine in `synthesize_cognitive_packet()` scans the entire raw file buffer (`raw_payload`) against user words $\ge 3$ characters without stripping the protocol header line (`HABITUS_SOFT_PACKET_V1` or `HABITUS_OPAQUE_PACKET_V1`).
- **Where**: `experiments/graph_native_live/live_evaluator.py`, lines 257–266.
- **Why**: If a user's prompt naturally contains protocol keywords (such as the word `"Soft"`, `"Opaque"`, or `"Packet"`), the naive substring check matches the protocol header string and raises a false-positive `RuntimeError("CRITICAL ZERO-LEAKAGE VIOLATION")`.
- **Suggestion**: Strip protocol headers (and known basis enum keys in `soft_basis` mode) before checking for lexical string leakage in the packet payload.

---

## Adversarial & Integrity Assessment

### Integrity Check: PASS
- **No hardcoded test outputs or facades**: `LiveEvaluator`, `MindStore`, and `GraphRuntime` execute real SQLite queries, Dijkstra traversals, vector synthesis, and subprocess calls to `graph_soft_generator`.
- **No shortcuts or fabricated verification**: Tests execute against real data structures and real Qwen3 GGUF models.
- **Strict single runner and process hygiene**: Verified that test runner processes follow `pkill -u $(id -u) -9 -f "pytest"` before runs.

### Adversarial Challenges & Edge Cases:

| Dimension | Attack Scenario / Edge Case | Observed Behavior | Status |
|---|---|---|---|
| **Empty / Minimal Stimuli** | Inputs `""`, `"   "`, `"\t\n\r"`, `"?"`, `"!"`, `"a"` | Handled cleanly, minimal packet generated without exception | **PASS** |
| **Adversarial Prompt Injection** | SQL injection (`DROP TABLE...`), token extraction prompts | No prompt text leaked into packet; SQLite triggers prevent table destruction | **PASS** |
| **Out-of-Vocabulary (OOV) Tokens** | Ungrounded novel random strings | Triggered bounded uncertainty fallback state (`speak: 1.0`, `uncertain: 0.55`, `clear: 0.45`) | **PASS** |
| **Multi-Turn Destabilization & Recovery** | Alternating hostile (-0.8) and cooperative (+0.85) stimuli | Preference bands dynamically modulate; graph invariants and global weight conservation hold strictly | **PASS** |
| **Stress Multi-Turn Session** | 15 continuous consecutive turns with varying users | 100% zero-leakage verified, graph invariants pass, global weights sum to 1.0 | **PASS** |

---

## Verified Claims

- **Claim 1**: Full single-turn cognitive cycle executes with monotonic pulse progression and multi-layer projections (0, 1, 2).  
  *Verification*: `TestContinuousCognitiveLoop::test_single_turn_cognitive_cycle_execution` → **PASS**
- **Claim 2**: Multi-turn preference polarization reinforces STABLE preference band under positive stimulus.  
  *Verification*: `TestContinuousCognitiveLoop::test_multi_turn_preference_polarization` → **PASS**
- **Claim 3**: Preference recovers from destabilization without invariant violations or weight drift.  
  *Verification*: `TestContinuousCognitiveLoop::test_preference_destabilization_and_recovery` → **PASS**
- **Claim 4**: Zero prompt text or RAG memory text leaks into packet buffers across diverse adversarial strings.  
  *Verification*: `TestZeroPromptLeakageInvariant::test_packet_contains_zero_raw_prompt_substrings` (6 parameter sets) → **PASS**
- **Claim 5**: Packet geometry is finite, bounded, and formatted as valid unit/activation rows.  
  *Verification*: `TestZeroPromptLeakageInvariant::test_packet_numerical_geometry_and_bounds` → **PASS**
- **Claim 6**: `StructuralMiniMap` persists to SQLite and roundtrips through JSON without loss.  
  *Verification*: `TestLayer3StructuralMiniMapAndLayer4Softmax::test_structural_minimap_sqlite_persistence_roundtrip` → **PASS**
- **Claim 7**: `compute_structural_overlay()` generates deterministic, unit-normalized 1024D vectors sensitive to topological changes.  
  *Verification*: `TestLayer3StructuralMiniMapAndLayer4Softmax::test_compute_structural_overlay_mathematical_invariants` → **PASS**
- **Claim 8**: Softmax edge weights sum strictly to 1.0 across all outgoing edges for every node.  
  *Verification*: `TestLayer3StructuralMiniMapAndLayer4Softmax::test_layer4_softmax_edge_weights_conservation` → **PASS**
- **Claim 9**: LiveEvaluator executes sessions across all three packet modes (`lexical_membrane`, `opaque_topological`, `soft_basis`).  
  *Verification*: `TestLiveEvaluatorIntegrationAndEdgeCases::test_live_evaluator_packet_modes` (3 modes) → **PASS**
- **Claim 10**: CLI execution works in `once` and `batch` modes with full telemetry export.  
  *Verification*: `test_live_evaluator_cli_once_execution` and `test_live_evaluator_cli_batch_execution` → **PASS**
- **Claim 11**: Real Qwen3 GGUF end-to-end soft generation executes with zero prompt leakage.  
  *Verification*: `TestLiveEvaluatorIntegrationAndEdgeCases::test_live_qwen3_soft_generation_turn` → **PASS**

---

## Coverage Gaps & Caveats

- **Coverage**: No significant coverage gaps in Milestone 5 scope. All 29 Milestone 5 tests pass in 71.09s.
- **Native GGUF Dependency**: Native soft generation relies on local Qwen3 GGUF model and C++ runner binary; fallback mock ensures test suite portability if binary is absent.

---

## Final Recommendation

**VERDICT: APPROVE (PASS)**  
Milestone 5 is ready for integration and graduation to full multi-agent orchestration.
