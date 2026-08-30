# Comprehensive Architectural Design: Habitus-AI Live Cognitive Evaluator (`live_evaluator.py`)

## Executive Summary

This document specifies the complete architectural design, Python/CLI interfaces, continuous cognitive feedback loop, vector packet generation pipelines, and telemetry export schemas for `experiments/graph_native_live/live_evaluator.py` under Milestone 5 (Requirement R1).

The `live_evaluator.py` engine serves as the canonical live evaluation harness for Habitus-AI. It evolves the bootstrap prototype (`live_tester.py`) into an autonomous, multi-turn cognitive evaluation system that bridges the **Layer 4 Semantic Membrane**, **Layer 3 Structural Mini-Maps**, and **Layer 2 SELF Preference Nodes** with native GGUF soft-input generation (`graph_soft_generator`) across continuous 1024D token manifolds—guaranteeing 100% zero-prompt leakage.

---

## 1. Architectural Structure & API Design

### 1.1 High-Level Architecture

`live_evaluator.py` is organized into modular subsystems:

```
+-----------------------------------------------------------------------------------+
|                              LiveEvaluator Engine                                 |
+-----------------------------------------------------------------------------------+
       |                                      ^                         ^
       v                                      | (Reinforcement)         | (Telemetry)
+------------------------+          +--------------------+    +--------------------+
|   Stimulus Ingestion   |          | Cognitive Feedback |    | Cognitive Metrics  |
| & Layer 2 Preference   |          |  & Edge Updating   |    |  & State Exporter  |
+------------------------+          +--------------------+    +--------------------+
       |                                      ^                         ^
       v                                      |                         |
+-----------------------------------------------------------------------------------+
|                           Dual-Cipher Graph Substrate                             |
|  - Layer 1: Basal Bicone Origin (SELF, IN:HEAR/SEE/NOTICE, OUT:SPEAK/LOOK/DO)     |
|  - Layer 2: Conserved Preference Matrix (PREF:HEAR:STABLE/NEUTRAL/UNSTABLE)        |
|  - Layer 3: Structural Mini-Maps (Emergent Children, Coactivation Relations)      |
|  - Layer 4: Semantic Membrane & Lexical Fibers (Softmax Edges, Directed Lexemes)  |
+-----------------------------------------------------------------------------------+
       |                                                                ^
       v (Shortest Y-Axis Paths)                                        | (Output Event)
+-----------------------------------------------------------------------------------+
|                      Continuous 1024D Packet Synthesizer                          |
|  - Mode 1: Soft Basis (`HABITUS_SOFT_PACKET_V1`)                                  |
|  - Mode 2: Opaque Topological (`HABITUS_OPAQUE_PACKET_V1`)                         |
|  - Mode 3: Lexical Geometry Membrane (`HABITUS_OPAQUE_PACKET_V1`)                 |
+-----------------------------------------------------------------------------------+
       | (Bounded Float Rows, No Text / No Tokens)
       v
+-----------------------------------------------------------------------------------+
|               Native GGUF Soft Generator (`graph_soft_generator`)                 |
|  - Target Model: Qwen3-0.6B-Q8_0.gguf (Native 1024D Input Width)                  |
|  - Soft-Input Injection: Continuous Non-Token Embedding Manifold Rows             |
|  - Plain-Language Logit Emission & Token Sampling                                 |
+-----------------------------------------------------------------------------------+
```

### 1.2 Python API Specification

The core class `LiveEvaluator` encapsulates all session state, database interactions, model execution, and telemetry logging:

```python
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

from habitus_ai.embeddings import Embedder, cosine_similarity
from habitus_ai.graph import (
    INPUT_NODE_IDS,
    OUTPUT_NODE_IDS,
    PREFERENCE_NODE_IDS,
    SELF_ID,
    compute_structural_overlay,
)
from habitus_ai.pipeline import BaseAgenticMemoryRAG
from habitus_ai.types import (
    ConceptNode,
    EventKind,
    GraphEdge,
    GraphSide,
    InputTrunk,
    MemoryRecord,
    OutputTrunk,
    RecordType,
    StructuralMiniMap,
    TraversalTrace,
)

@dataclass(frozen=True)
class EvaluatorConfig:
    database_path: Path
    model_path: Path
    runner_path: Path
    run_directory: Path
    max_tokens: int = 256
    seed: int = 42
    skip_think: bool = True
    temperature: float = 1.0
    learning_rate: float = 0.35
    packet_mode: str = "lexical_membrane"  # "lexical_membrane" | "opaque_topological" | "soft_basis"
    enforce_zero_leakage: bool = True

@dataclass
class TurnTelemetry:
    turn_index: int
    turn_id: str
    pulse_id: str
    input_sha256: str
    source_id: str
    input_trunk: str
    preference_node: str | None
    preference_state_before: dict[str, float]
    preference_state_after: dict[str, float]
    nominated_concept_id: str | None
    input_path: list[str]
    input_edge_ids: list[str]
    output_path: list[str]
    output_edge_ids: list[str]
    input_travel_time: float
    output_travel_time: float
    layer3_minimap: dict[str, Any] | None
    layer4_softmax_weights: dict[str, float]
    packet_path: str
    packet_sha256: str
    packet_rows: int
    packet_mode: str
    zero_leakage_verified: bool
    response_text: str
    response_record_id: str
    stability_delta: float
    reinforced_edges: list[str]
    duration_ms: float

class LiveEvaluator:
    """Production cognitive evaluator and continuous loop orchestrator."""

    def __init__(self, config: EvaluatorConfig, embedder: Embedder | None = None) -> None:
        self.config = config
        self.embedder = embedder
        self.mind = BaseAgenticMemoryRAG(
            self.config.database_path,
            embedder=self.embedder,
            learning_rate=self.config.learning_rate,
        )
        self.history: list[TurnTelemetry] = []
        self._ensure_prerequisites()

    def _ensure_prerequisites(self) -> None:
        """Verify model, runner, database, and seed topology."""
        ...

    def step(
        self,
        stimulus_text: str,
        *,
        source_id: str = "human",
        expected_outcome_stability: float | None = None,
        reinforce: bool = True,
    ) -> TurnTelemetry:
        """Execute one complete multi-turn cognitive loop step."""
        ...

    def run_multi_turn_session(
        self,
        stimuli: Sequence[str | tuple[str, float]],
        *,
        source_id: str = "human",
    ) -> list[TurnTelemetry]:
        """Execute a batch multi-turn scenario and return turn receipts."""
        ...

    def export_state_report(self, export_path: Path | None = None) -> dict[str, Any]:
        """Generate a complete forensic cognitive state and metrics report."""
        ...

    def verify_invariants(self) -> dict[str, bool]:
        """Validate conserved mass, reachability, and zero-prompt leakage."""
        ...

    def close(self) -> None:
        self.mind.close()

    def __enter__(self) -> LiveEvaluator:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
```

### 1.3 CLI Interface Specification

The CLI provides interactive, scripted, and benchmark modes:

```text
usage: live_evaluator.py [-h] [--model PATH] [--runner PATH] [--db PATH]
                         [--run-directory PATH] [--mode {interactive,once,benchmark,batch}]
                         [--stimuli PATH] [--stimulus-text TEXT] [--source-id ID]
                         [--packet-mode {lexical_membrane,opaque_topological,soft_basis}]
                         [--stability-delta FLOAT] [--max-tokens INT] [--seed INT]
                         [--no-skip-think] [--export-report PATH] [--show-trace]
                         [--verify-invariants]

Habitus-AI Continuous Cognitive Evaluator & Soft Generation Suite

options:
  -h, --help            show this help message and exit
  --model PATH          Path to Qwen3 GGUF model (default: /home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf)
  --runner PATH         Path to compiled native runner (default: native/graph_soft_generator)
  --db PATH             Path to SQLite mind database (default: live_mind.sqlite)
  --run-directory PATH  Directory to store .packet and receipt .json files (default: runs/)
  --mode {interactive,once,benchmark,batch}
                        Execution mode (default: interactive)
  --stimuli PATH        Path to JSON or text file containing multi-turn stimuli
  --stimulus-text TEXT  Single stimulus text for --mode once
  --source-id ID        Stimulus source identifier e.g. "josh", "adversary" (default: human)
  --packet-mode {lexical_membrane,opaque_topological,soft_basis}
                        1024D vector packet synthesis strategy (default: lexical_membrane)
  --stability-delta FLOAT
                        Manual outcome stability reinforcement (-1.0 to 1.0)
  --max-tokens INT      Maximum generation tokens (default: 256)
  --seed INT            RNG seed for model sampling (default: 42)
  --no-skip-think       Do not skip thinking/reasoning delimiters in Qwen3
  --export-report PATH  Path to write complete JSON evaluation session report
  --show-trace          Print complete layer telemetry JSON to stdout per turn
  --verify-invariants   Run full invariant audits before and after evaluation
```

---

## 2. Continuous Cognitive Loop: Layer 4 Semantic Membrane $\leftrightarrow$ SELF Preference Nodes

### 2.1 The Four Cognitive Layers

```
+-----------------------------------------------------------------------------+
| Layer 4: Semantic Membrane & Lexical Geometry                               |
| - Crown concept centroids in 1024D native space                            |
| - Dynamic softmax edge weights: P(e) = exp(logit_e / T) / sum(exp(logit_k / T)) |
| - Bidirectional productive fibers & learned directed lexical transitions    |
+-----------------------------------------------------------------------------+
                                     ^  |
                                     |  | (Bidirectional Projections & Traversal)
                                     |  v
+-----------------------------------------------------------------------------+
| Layer 3: Structural Mini-Maps                                               |
| - Emergent intermediate pattern child nodes (`child:auto:*`)               |
| - `StructuralMiniMap`: parent/child IDs, relations, coactivation density    |
| - Topological coordinate overlay synthesized via intrinsic graph embedder   |
+-----------------------------------------------------------------------------+
                                     ^  |
                                     |  | (Y-Axis Shortest Path Travel)
                                     |  v
+-----------------------------------------------------------------------------+
| Layer 2: Conserved Preference Matrix                                        |
| - Fixed Preference Bands: `PREF:<trunk>:STABLE`, `NEUTRAL`, `UNSTABLE`      |
| - Experience state tracking: `preference_mean`, `preference_weight`         |
| - Moving average experience accumulation & vault projections                |
+-----------------------------------------------------------------------------+
                                     ^  |
                                     |  | (Conserved Delta-Y Edges)
                                     |  v
+-----------------------------------------------------------------------------+
| Layer 1: Basal Bicone Origin                                                |
| - `SELF_ID = "SELF"` root origin coordinate                                 |
| - Perceptual Trunks: `IN:HEAR`, `IN:SEE`, `IN:NOTICE` (+Y direction)       |
| - Effector Trunks: `OUT:SPEAK`, `OUT:LOOK`, `OUT:DO` (-Y direction)        |
+-----------------------------------------------------------------------------+
```

### 2.2 Mathematical Mechanics of the Cognitive Loop

1. **Preference Deposition & Update (Layer 2)**:
   When an input event arrives with polarity / stability $\delta \in [-1.0, 1.0]$:
   $$\text{target\_band} = \begin{cases} \text{STABLE} & \text{if } \delta \ge 0.20 \\ \text{UNSTABLE} & \text{if } \delta \le -0.20 \\ \text{NEUTRAL} & \text{otherwise} \end{cases}$$
   The experience state updates incrementally:
   $$\mu_{n} = \mu_{n-1} + \frac{\delta - \mu_{n-1}}{n}$$
   $$W_{n} = \min(1.0, W_{n-1} + 0.15)$$

2. **Dijkstra Y-Axis Traversal with Dynamic Softmax Resistances**:
   Every edge $e$ in side $S$ has effective travel time:
   $$\text{Time}(e) = \frac{\Delta Y_e}{10^{-6} + P(e)} + \text{ConflictPenalty}(e)$$
   Where $P(e)$ is computed via the Layer 4 softmax membrane:
   $$\text{Logit}(e) = \text{LogStrength}(e) + \text{Recency}(e) - \text{ConflictPenalty}(e)$$
   $$\text{Recency}(e) = \alpha_{\text{rec}} \cdot \exp\left(-\frac{\ln(2) \cdot \text{Age}(e)}{T_{\text{half}}}\right)$$
   $$P_{\text{local}}(e \mid u) = \frac{\exp\left(\frac{\text{Logit}(e) - \max_{k \in \text{Out}(u)} \text{Logit}(k)}{T}\right)}{\sum_{k \in \text{Out}(u)} \exp\left(\frac{\text{Logit}(k) - \max_{j \in \text{Out}(u)} \text{Logit}(j)}{T}\right)}$$

3. **Cognitive Feedback & Edge Plasticity**:
   After plain language synthesis and environmental response evaluation, outcome feedback $\Delta_{\text{stab}} \in [-1.0, 1.0]$ reinforces all credited edges along the traversal path:
   $$\Delta_{\text{weight}} = \eta \cdot \Delta_{\text{stab}} \cdot Q_{\text{evidence}} \cdot \frac{1}{|\text{Path}|}$$
   $$\text{LogStrength}(e) \leftarrow \text{LogStrength}(e) + \Delta_{\text{weight}}$$
   If $\Delta_{\text{stab}} < 0$, conflict penalty accumulates:
   $$\text{ConflictPenalty}(e) \leftarrow \min\left(10.0, \text{ConflictPenalty}(e) + 0.25 \cdot |\Delta_{\text{weight}}|\right)$$
   If $\Delta_{\text{stab}} > 0$, conflict penalty dissipates:
   $$\text{ConflictPenalty}(e) \leftarrow \max\left(0.0, \text{ConflictPenalty}(e) - 0.10 \cdot \Delta_{\text{weight}}\right)$$

---

## 3. Multi-Turn Ingestion, Packet Construction & Soft Generation

### 3.1 Step-by-Step Multi-Turn Pipeline

For each stimulus turn $t = 1, \dots, N$:

```
[User Text T_in]
       |
       v
(1) MindStore.add_record(T_in) [Persisted strictly in SQLite; NEVER sent to model]
       |
       v
(2) Graph.deposit_experience() -> Updates Layer 2 Preference Node (PREF:HEAR:STABLE/UNSTABLE)
       |
       v
(3) SemanticSurface.project() -> Nominates Top Layer 4 Crown Concept C*
       |
       v
(4) Graph.traverse(side=INPUT, target=C*)  -> Path: SELF -> IN:HEAR -> PREF -> Layer 3 Child -> Layer 4 Crown
    Graph.traverse(side=OUTPUT, target=C*) -> Path: SELF -> OUT:SPEAK -> Layer 4 Crown
       |
       v
(5) Extract Layer 3 Mini-Map (StructuralMiniMap relations & coactivations)
       |
       v
(6) Synthesize 1024D Continuous Vector Packet (Up to 8 Dense Unit Vectors)
       |
       v
(7) Zero-Leakage Assertion: Verify no substring of T_in or memory records appears in packet
       |
       v
(8) Native Soft Generation: graph_soft_generator(Model_GGUF, Packet) -> Generated Text T_out
       |
       v
(9) MindStore.remember(T_out, RecordType.OUTBOUND_MESSAGE)
       |
       v
(10) Reinforce Path Edges: reinforce_edges(Path, delta=stability)
```

### 3.2 1024D Packet Synthesis Strategies

`live_evaluator.py` implements three selectable packet synthesis modes:

#### Mode A: Lexical Geometry Membrane (`lexical_membrane`) — Primary Canonical Mode
1. **Row 0 (Concept Centroid)**: $V_0 = \text{L2Normalize}(\text{Embedding}(C^*))$
2. **Row 1 (Weighted Productive State)**: Blended 1024D lexical state from reverse nursery output fibers:
   $$V_1 = \text{L2Normalize}\left(\sum_{f \in \text{Fibers}(C^*)} P(f) \cdot \text{Embedding}(\text{Lexeme}(f))\right)$$
3. **Rows 2..7 (Directed Lexical Transitions)**: Up to 6 productive lexeme embeddings ordered along the maximal directed transition chain learned during developmental gestation:
   $$\text{NextLexeme}(L_i) = \arg\max_{L_j \in \text{Remaining}} \left(\text{EdgeLogStrength}(L_i \to L_j) + \text{ProductiveProb}(L_j)\right)$$
   $$V_{k} = \text{L2Normalize}(\text{Embedding}(L_k))$$

#### Mode B: Opaque Topological Packet (`opaque_topological`) — Structural Baseline
Four 1024D rows derived purely from graph structure without lexical anchors:
1. **Row 0 (Input Path Slot)**: $\sum_{i=1}^{D_{\text{in}}} w_i \cdot \text{NodeVector}(n_i^{\text{in}})$
2. **Row 1 (Layer 4 Edge & Membrane Slot)**: $\sum_{e \in \text{Edges}} (0.10 + P_{\text{softmax}}(e)) \cdot \text{EdgeCode}(e)$
3. **Row 2 (Temporal Recency & Preference Polarity Slot)**: $\sum_{\tau=0}^{K} \frac{1}{1+\tau} \left(\text{TargetVector}_\tau + \delta_\tau \cdot \text{PolarityAxis}\right)$
4. **Row 3 (Output Path Slot)**: $\sum_{j=1}^{D_{\text{out}}} w_j \cdot \text{NodeVector}(n_j^{\text{out}})$

#### Mode C: Soft Basis Packet (`soft_basis`) — Bootstrap Compatibility Mode
Combines token-embedding anchors for admitted semantic bases (`speak`, `greeting`, `warm`, `question`, `clear`, `uncertain`, `memory`) scaled by graph activation strength:
$$\text{HABITUS\_SOFT\_PACKET\_V1}$$
$$\text{basis\_name}\quad \text{scalar\_activation}$$

---

## 4. Telemetry, Metric Tracking & Export Schema

### 4.1 Per-Turn Receipt Schema (`habitus.cognitive-eval-turn.v1`)

```json
{
  "$schema": "https://habitus.ai/schemas/cognitive-eval-turn.v1.json",
  "schema": "habitus.cognitive-eval-turn.v1",
  "turn_index": 1,
  "turn_id": "turn-1788029000000000000",
  "timestamp": "2026-08-29T18:50:00.000000Z",
  "pulse_id": "pulse:42",
  "stimulus": {
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "source_id": "josh",
    "input_trunk": "HEAR",
    "record_id": "record:a1b2c3d4"
  },
  "layer2_preference": {
    "activated_node_id": "PREF:HEAR:STABLE",
    "preference_band": "STABLE",
    "experience_mean_before": 0.65,
    "experience_mean_after": 0.72,
    "confidence_weight": 0.85
  },
  "layer3_structural_minimap": {
    "map_id": "map:child:8a7f2e1c",
    "parent_node_ids": ["PREF:HEAR:STABLE"],
    "child_node_ids": ["concept:auto:8a7f2e1c"],
    "total_coactivations": 14,
    "relations": [
      {
        "source": "PREF:HEAR:STABLE",
        "target": "child:auto:8a7f2e1c",
        "density": 14.0,
        "direction": "input"
      }
    ]
  },
  "layer4_semantic_membrane": {
    "nominated_concept_id": "concept:auto:8a7f2e1c",
    "concept_label": "Trust Reliable",
    "joint_score": 0.9124,
    "softmax_edge_weights": {
      "edge:input:4f9a...": 0.6421,
      "edge:input:8b2c...": 0.3579
    },
    "global_weight_snapshot_sum": 1.0,
    "active_fibers": [
      {"lexeme_id": "lex:trust", "probability": 0.82},
      {"lexeme_id": "lex:safe", "probability": 0.76}
    ]
  },
  "traversal": {
    "input_path": ["SELF", "IN:HEAR", "PREF:HEAR:STABLE", "child:auto:8a7f2e1c", "concept:auto:8a7f2e1c"],
    "input_travel_time": 2.1458,
    "output_path": ["SELF", "OUT:SPEAK", "concept:auto:8a7f2e1c"],
    "output_travel_time": 1.4821
  },
  "packet": {
    "path": "/path/to/runs/turn-1788029000000000000.packet",
    "sha256": "9f83c...4a2",
    "mode": "lexical_membrane",
    "dimension": 1024,
    "rows": 4,
    "zero_leakage_verified": true
  },
  "native_generation": {
    "model": "/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf",
    "runner": "native/graph_soft_generator",
    "tokens_generated": 28,
    "prompt_eval_time_ms": 12.4,
    "token_eval_time_ms": 142.1,
    "response_text": "I feel safe when cooperation remains reliable.",
    "response_record_id": "record:e5f6g7h8"
  },
  "outcome_reinforcement": {
    "stability_delta": 0.75,
    "credited_edge_ids": ["edge:input:4f9a...", "edge:output:91ac..."],
    "verified": true
  },
  "duration_ms": 218.6
}
```

### 4.2 Forensic Invariant Auditing Specification

The evaluator enforces five mathematical invariants:

| Invariant | Method | Pass Criteria |
|-----------|--------|---------------|
| **Zero-Prompt Leakage** | SHA256 + substring search | $0$ occurrences of input text or memory strings in `.packet` |
| **Global Edge Conservation** | $\sum_{e \in E} P_{\text{global}}(e)$ | $| \sum P(e) - 1.0 | < 10^{-9}$ |
| **Local Node Conservation** | $\sum_{e \in \text{Out}(u)} P_{\text{local}}(e \mid u)$ | $| \sum P(e \mid u) - 1.0 | < 10^{-9}$ for all $u$ |
| **Bicone Frontier Invariant** | Outgoing from `SELF` | Input set == `(IN:HEAR, IN:SEE, IN:NOTICE)`, Output set == `(OUT:SPEAK, OUT:LOOK, OUT:DO)` |
| **Reachability Preservation** | Dijkstra travel time | $\text{TravelTime}(\text{Target}) < \infty$ for all active crown concepts |

---

## 5. Implementation Roadmap for Milestone 5

1. **Step 1: Module Creation (`experiments/graph_native_live/live_evaluator.py`)**:
   - Implement `EvaluatorConfig`, `TurnTelemetry`, and `LiveEvaluator`.
   - Implement packet compilation for `lexical_membrane`, `opaque_topological`, and `soft_basis`.
   - Implement native runner invocation and receipt generation.
2. **Step 2: Continuous Cognitive Loop Implementation**:
   - Link Layer 2 preference updating with `deposit_experience()` and `record_outcome()`.
   - Implement Layer 3 mini-map extraction and telemetry formatting.
   - Implement Layer 4 softmax membrane computation and edge reinforcement.
3. **Step 3: Pytest Integration (`tests/test_cognitive_conversability.py`)**:
   - Test multi-turn state transitions, differential preference shifts, and zero-prompt leakage assertions.
4. **Step 4: Verification & Performance Profiling**:
   - Validate invariant compliance, sub-250ms turn latency, and 100% test pass rate.
