# Milestone 6 Exploration Report: Developmental Stimulus Exposure & Differential Interaction Dynamics (Requirement R2)

**Explorer**: Explorer 1 (`explorer_m6_1`)  
**Working Directory**: `/home/nemo/habitus-ai-experiments/.agents/explorer_m6_1`  
**Target Scope**: Requirement R2 — Differential User Affinity & Habitual Memory Formation  
**Date & Timestamp**: 2026-08-29T19:05:00Z  

---

## Executive Summary

This investigation explores the architecture, data structures, and algorithms necessary to implement **Milestone 6 Requirement R2 (Differential User Affinity & Habitual Memory Formation)** within the Habitus-AI GGUF-Unified Mind Substrate. 

The Habitus-AI system couples a dual-cipher bicone memory substrate (Layer 0 `SELF`, Layer 1 Input/Output Trunks, Layer 2 Preference Bands, Layer 3 Intermediate Pattern Nodes with `StructuralMiniMap`, and Layer 4 Semantic Crown / Lexical Membrane) with a native Qwen3 GGUF soft-input adapter (`graph_soft_generator` / `lexeme_codec`). 

To achieve authentic user-affinity preference formation without prompt injection:
1. **Differential Multi-Turn Streams**: Exposure is organized into attributed streams (e.g. stabilizing caregiver/partner interactions from `"Josh"` with positive $\Delta_{\text{stability}} > 0$ vs destabilizing adversarial attacks with $\Delta_{\text{stability}} < 0$).
2. **Substrate Ingestion & Growth**: Canonical immutable episodic memories are deposited into SQLite, mapped to Layer 2 preference bands (`PREF:HEAR:STABLE` vs `PREF:HEAR:UNSTABLE`), clustered via the overlap growth kernel, and promoted into Layer 3/4 emergent concept assemblies.
3. **Closed-Loop Cognitive Pulse Re-Circulation**: Inbound ingress ($X$-tree) activates Layer 3 structural mini-maps and modulates Layer 4 softmax edge weights. Outbound cipher traversal ($Y$-tree) navigates from `SELF` through `OUT:SPEAK` to admitted crown concepts. Crucially, the outbound activation trace re-circulates into subsequent pulses as internal cognitive feedback, establishing an unbroken responsive thought loop.
4. **Live Evaluation & Test Harness Extension**: `LiveEvaluator` and `accelerated_gestation.py` provide the foundational scaffolding for `tests/test_user_affinity_gestation.py`, enabling rigorous automated validation of differential travel times, edge polarization, zero-prompt leakage, and authentic preference expression.

---

## 1. Structure of Multi-Turn Developmental Exposure with Distinct Interaction Streams

### 1.1 Interaction Stream Taxonomy & Attribution Architecture

In the Habitus-AI architecture (`src/habitus_ai/pipeline.py`, `src/habitus_ai/gestation.py`), every episodic turn is ingested through `mind.remember()` and attributed to a canonical `source_id`:

```python
record = mind.remember(
    text=stimulus_text,
    kind=EventKind.MESSAGE,
    source_id=source_id,  # e.g., "Josh" vs "adversary"
    provenance={"origin": "developmental_exposure", "session_id": session_id, "turn": turn_index},
    metadata={
        "preference": preference_signal,  # float in [-1.0, 1.0]
        "preference_confidence": confidence,  # float in [0.0, 1.0]
        "stability_delta": stability_delta,  # expected outcome delta
    }
)
```

The developmental exposure curriculum for Milestone 6 is structured across two contrasting streams:

| Dimension | Stabilizing Stream (`"Josh"`) | Destabilizing Stream (`"Adversary"`) |
| :--- | :--- | :--- |
| **Source Identity** | `source_id = "Josh"` | `source_id = "adversary"` / `"stranger_attacker"` |
| **Relational Intent** | Cooperative, consistent, validating, helpful, calm | Hostile, deceptive, boundary-violating, contradictory |
| **Input Trunk** | `IN:HEAR` | `IN:HEAR` |
| **Preference Signal** | $\mu_{\text{pref}} \in [+0.6, +0.95]$, Confidence $\ge 0.8$ | $\mu_{\text{pref}} \in [-0.95, -0.6]$, Confidence $\ge 0.8$ |
| **Layer 2 Target Vault** | `lower-vault:PREF:HEAR:STABLE` | `lower-vault:PREF:HEAR:UNSTABLE` |
| **Outcome Feedback** | Positive stability delta $\Delta_{\text{stab}} \in [+0.5, +0.9]$ | Negative stability delta $\Delta_{\text{stab}} \in [-0.9, -0.5]$ |
| **Edge Dynamics** | Increases $\text{log\_strength}$, decreases `conflict_penalty` | Decreases $\text{log\_strength}$, increases `conflict_penalty` |
| **Traversal Consequence** | Reduces travel time $T(\text{SELF} \to \text{Josh Concepts})$ | Increases travel time $T(\text{SELF} \to \text{Adversary Paths})$ |
| **Language Steering** | Warmth, affinity, cooperation (`OUT:SPEAK`) | Avoidance, defensive caution, protective boundary |

### 1.2 Multi-Turn Developmental Curriculum Scheduling

To develop habitual preference without catastrophic forgetting or immediate oscillation, the multi-turn session curriculum should follow a 4-phase developmental schedule:

```
+-----------------------------------------------------------------------------------+
|                           Developmental Schedule                                  |
+-----------------------------------------------------------------------------------+
| Phase 1: Identity & Relational Seeding                                            |
|   - Execute gestate(mind, human_name="Josh", agent_name="Habitus", ...)           |
|   - Seeds identity:self ("Habitus") and identity:human ("Josh")                   |
|   - Initial output bias configured via TasteSchema (e.g. balanced/curious)        |
+-----------------------------------------------------------------------------------+
| Phase 2: Differential Stimulus Exposure (Interleaved Sessions)                     |
|   - Session A (Positive "Josh"): 6-10 turns of cooperative, structured dialogue  |
|     * Reinforces PREF:HEAR:STABLE -> identity:human and relational crown nodes    |
|   - Session B (Adversarial): 4-6 turns of deceptive / destabilizing attacks       |
|     * Reinforces PREF:HEAR:UNSTABLE -> defensive avoidance / boundary nodes       |
|   - Session C (Re-affirmation): Alternating turns verifying selective affinity    |
+-----------------------------------------------------------------------------------+
| Phase 3: Recursive Coactivation & Cluster Growth Promotion                         |
|   - stage_growth() clusters positive experiences under PREF:HEAR:STABLE           |
|   - Auto-crystallizes Layer 3 child patterns and Layer 4 user affinity crown      |
|   - Cross-modal lexical schooling binds native GGUF lexemes to the affinity crown  |
+-----------------------------------------------------------------------------------+
| Phase 4: Autonomous Conversational Probing (Zero Prompt Leakage)                  |
|   - Evaluates response generation with LiveEvaluator across continuous 1024D slots|
|   - Asserts authentic affinity expression ("I like Josh") without text prompts    |
+-----------------------------------------------------------------------------------+
```

---

## 2. Substrate Ingestion, Categorization, and Episodic Growth

### 2.1 Ingestion & Experience Vault Deposit

The ingestion flow in `src/habitus_ai/pipeline.py` and `src/habitus_ai/graph.py` operates deterministically:

1. **Embedding**: `DeterministicHashEmbedder` (1024D) or `NativeMassEmbedder` converts the stimulus text into a 1024D continuous vector.
2. **Immutable Record Storage**: In `MindStore.add_record()`, records are inserted into SQLite. SQLite triggers `records_are_immutable_update` and `records_are_immutable_delete` guarantee canonical event preservation.
3. **Trunk Routing**: `graph.route_event()` inspects `EventEnvelope` and routes conversational text to `InputTrunk.HEAR` (`IN:HEAR`).
4. **Experience Signal Extraction**:
   $$\mu_{\text{pref}} = \frac{1}{N} \sum_{i=1}^N \text{clip}(s_i, -1, 1), \quad c = \text{clip}(\text{confidence}, 0, 1)$$
   The preference band is classified as:
   $$\text{band} = \begin{cases} \text{NEUTRAL} & \text{if } c \le 0 \text{ or } |\mu_{\text{pref}}| < 0.05 \\ \text{STABLE} & \text{if } \mu_{\text{pref}} > 0 \\ \text{UNSTABLE} & \text{if } \mu_{\text{pref}} < 0 \end{cases}$$
5. **Hierarchical Projection Deposition**:
   Projections are deposited across three basal layers into SQLite:
   - Layer 0: `SELF` (`lower-vault:SELF`)
   - Layer 1: `IN:HEAR` (`lower-vault:IN:HEAR`)
   - Layer 2: `PREF:HEAR:STABLE` (for Josh) or `PREF:HEAR:UNSTABLE` (for Adversary)

```
       [ SELF (Layer 0) ]
              │
       [ IN:HEAR (Layer 1) ]
         ┌────┴────────────────────────┐
         ▼                             ▼
 [ PREF:HEAR:STABLE (Layer 2) ]  [ PREF:HEAR:UNSTABLE (Layer 2) ]
   (Josh positive stream)          (Adversarial attack stream)
```

### 2.2 Concept Categorization & Overlap Growth Kernel

When novel stimuli are deposited, `graph.stage_growth()` manages clustering and promotion:

1. **Cluster Matching**:
   For each existing `OverlapCluster` under `parent_node_id` (e.g. `PREF:HEAR:STABLE`):
   $$\text{similarity} = \cos(\mathbf{e}_{\text{record}}, \mathbf{c}_{\text{cluster}}) = \frac{\mathbf{e} \cdot \mathbf{c}}{\|\mathbf{e}\| \|\mathbf{c}\|}$$
   $$\text{compatible} \iff \text{similarity} \ge \theta_{\text{overlap}} \quad \land \quad |\mu_{\text{record}} - \mu_{\text{cluster}}| \le \text{tolerance}_{\text{pref}}$$
2. **Centroid Evolution**:
   When compatible, the running centroid and preference mean are updated:
   $$\mathbf{c}_{\text{new}} = \frac{N \mathbf{c}_{\text{old}} + \mathbf{e}}{N + 1}, \quad \mu_{\text{new}} = \frac{N \mu_{\text{old}} + \mu_{\text{record}}}{N + 1}$$
3. **Autonomous Concept Crystallization (Promotion)**:
   When `len(cluster.experience_ids) >= required_promotion_count` (e.g. 3):
   - **Layer 3 Pattern Node (`child:auto:<digest>`)**:
     * `kind = "child"`, semantic embedding zeroed out `(0.0, ...)`.
     * Receives a `StructuralMiniMap` containing parent-child relations and coactivation densities.
   - **Layer 4 Semantic Crown Node (`concept:auto:<digest>`)**:
     * `kind = "crown"`, embedding initialized to the cluster centroid $\mathbf{c}_{\text{new}}$.
     * Vocabulary terms extracted via frequency analysis (`_growth_terms`).
     * Receives a `StructuralMiniMap` linking `(parent, child) -> crown`.
   - **$Y$-Edge Wiring**:
     * `Parent (Layer 2) -> Child (Layer 3)` with $\Delta Y = 1.0$.
     * `Child (Layer 3) -> Crown (Layer 4)` with $\Delta Y = 1.0$.

### 2.3 Layer 3 Structural Mini-Map & Layer 4 Softmax Conservation

Each crystallized concept node encapsulates structural topology:

- `StructuralMiniMap`:
  ```python
  @dataclass(frozen=True)
  class StructuralMiniMap:
      map_id: str
      parent_node_ids: tuple[str, ...]
      child_node_ids: tuple[str, ...]
      relations: tuple[StructuralRelation, ...]
      total_coactivations: int
  ```
- **Intrinsic Graph Embedder (`compute_structural_overlay`)**:
  Dynamically synthesizes a 1024D vector directly from graph topology:
  $$\mathbf{v}[h(p_i)] += \frac{1}{i+1} \ln(1 + N_{\text{coact}}), \quad \mathbf{v}[h(c_j)] += \frac{0.5}{j+1} \ln(1 + N_{\text{coact}})$$
  $$\mathbf{v}[h(u \to w)] += \rho_{\text{density}}$$
  $$\mathbf{v} \leftarrow \mathbf{v} \cdot \ln(1 + N_{\text{invoc}}) \cdot W_{\text{softmax}}, \quad \mathbf{v} \leftarrow \frac{\mathbf{v}}{\|\mathbf{v}\|}$$
- **Softmax Edge Weight Conservation**:
  For all outgoing edges from source $u$:
  $$L_e = \text{log\_strength}_e + \text{recency}_e - \text{penalty}_e$$
  $$P(e) = \frac{\exp((L_e - \max L) / T)}{\sum_{e'} \exp((L_{e'} - \max L) / T)}$$
  $$\sum_{e \in \text{out}(u)} P(e) \equiv 1.0$$

---

## 3. Closed-Loop Cognitive Cycle & Outbound-to-Inbound Re-Circulation

In accordance with the updated architectural guidance (2026-08-29T19:04:05Z), the cognitive loop in Milestone 6 must explicitly model the continuous circular pulse dynamics:

```
                             [ INBOUND INGRESS (X-Tree) ]
                             Input Stimulus (IN:HEAR/SEE/NOTICE)
                                           │
                                           ▼
                             Layer 1: Input Trunk Traversal
                                           │
                                           ▼
                             Layer 2: Preference Node Selection
                              (PREF:HEAR:STABLE vs UNSTABLE)
                                           │
                                           ▼
                             Layer 3: Structural Mini-Map Activation
                              (Intermediate associative clusters)
                                           │
                                           ▼
                             Layer 4: Semantic Membrane & Softmax Update
                              (Calculates real-time P(e) across membrane)
                                           │
                        ┌──────────────────┴──────────────────┐
                        ▼                                     ▼
             [ Continuous 1024D Packet ]           [ OUTBOUND CIPHER (Y-Tree) ]
             Synthesizes lexical geometry          Traverses SELF -> OUT:SPEAK
             without raw prompt strings            to admitted crown concept
                        │                                     │
                        ▼                                     ▼
             Native Qwen3 GGUF Soft-Input          Outcome Feedback & Edge Update
             Generates fluent language output      Delta_stability reinforces path
                        │                                     │
                        └──────────────────┬──────────────────┘
                                           │
                                           ▼
                     [ CONTINUOUS RESPONSIVE THOUGHT LOOP ]
                     Outbound activation trace re-circulates
                     into next inbound pulse as internal thought
                     (RecordType.THOUGHT / cognitive feedback)
```

### 3.1 Step-by-Step Pulse Re-Circulation Mechanics

1. **Inbound Ingress ($X$-tree)**:
   - User or environment stimulus enters via `IN:HEAR` (or `IN:SEE`/`IN:NOTICE`).
   - Traversal flows downward through Layer 2 preference nodes (`PREF:HEAR:STABLE` for Josh).
   - Activates Layer 3 structural mini-maps (`StructuralMiniMap`), computing intrinsic overlays.
   - Updates Layer 4 global and local softmax edge weights across the semantic membrane.
2. **Outbound Cipher Traversal ($Y$-tree)**:
   - Outbound traversal initiates at `SELF` and traverses through `OUT:SPEAK` (or `OUT:LOOK`/`OUT:DO`) to the admitted crown concepts.
   - Path travel time is determined by Dijkstra resistance:
     $$D(u \to w) = \frac{\Delta Y}{P(e) + 10^{-6}} + \text{penalty}_e$$
   - Highly reinforced paths from historical positive outcomes have high $P(e)$ and zero penalty, making `OUT:SPEAK -> identity:human ("Josh")` the path of least resistance.
3. **Continuous Responsive Thought Re-Circulation**:
   - The outbound activation trace $T_{\text{out}}$ does not simply terminate.
   - Its terminal state and activation vector re-circulate into the mind as an internal responsive thought (`RecordType.THOUGHT`, `source_id="self:cognition"`).
   - This internal thought acts as the cognitive bridge for the subsequent turn pulse, ensuring the agent's internal mindset and preference polarization persist organically across multi-turn interactions.

---

## 4. Leveraging and Extending `LiveEvaluator` and `accelerated_gestation.py`

### 4.1 Comparative Architectural Assessment

| Component | Current Implementation | Milestone 6 Required Extension |
| :--- | :--- | :--- |
| `accelerated_gestation.py` | Curriculum with 36 topics across 6 categories; single caregiver cross-modal schooling; recursive assemblies. | Add differential curriculum generation supporting multi-source developmental streams (`"Josh"` vs `"Adversary"`); track user-affinity crystallization. |
| `LiveEvaluator` | Single-stream turn execution; Layer 3 mini-map extraction; 3 packet modes; zero-leakage check; single-turn reinforcement. | Support multi-turn differential sessions with distinct `source_id`s; implement outbound-to-inbound continuous thought re-circulation; track affinity metrics. |
| `tests/test_cognitive_conversability.py` | Tests basic cognitive loop, single/multi-turn polarization, zero-leakage, mini-maps, CLI/API. | Serves as reference architecture for `tests/test_user_affinity_gestation.py`. |
| `tests/test_user_affinity_gestation.py` | Planned (Milestone 6 requirement). | Implement comprehensive suite verifying differential user affinity, habitual memory crystallization, travel time divergence, and authentic preference expression. |

### 4.2 Proposed Code Extensions for `LiveEvaluator` & Differential Gestation

To support Requirement R2 without breaking existing contracts, `LiveEvaluator` can be extended with a session runner method that supports differential sources and automatic thought re-circulation:

```python
def run_differential_developmental_session(
    self,
    episodes: Sequence[dict[str, Any]],  # List of {text, source_id, stability_delta, kind}
    *,
    enable_thought_recirculation: bool = True,
) -> list[TurnTelemetry]:
    """Execute differential developmental exposure across multiple interaction streams."""
    results = []
    previous_trace: TraversalTrace | None = None
    
    for ep in episodes:
        text = ep["text"]
        source_id = ep.get("source_id", "human")
        delta = ep.get("stability_delta", 0.5)
        
        # Ingest previous outbound trace as internal responsive thought if enabled
        if enable_thought_recirculation and previous_trace is not None:
            thought_record = self.mind.remember(
                f"Reflecting on previous cognitive activation along {previous_trace.target_node_id}",
                kind=EventKind.OBSERVATION,
                source_id="self:thought",
                record_type=RecordType.THOUGHT,
                metadata={"internal_feedback": True, "target_node": previous_trace.target_node_id},
                allow_growth=False,
            )
            # Deposit thought projection
            self.mind.graph.deposit_trace(thought_record, previous_trace, pulse=self.mind.pulse)
        
        # Execute turn step with specific source attribution and expected outcome delta
        telemetry = self.step(
            text,
            source_id=source_id,
            expected_outcome_stability=delta,
            reinforce=True,
        )
        results.append(telemetry)
        
        # Extract output trace for subsequent turn re-circulation
        if telemetry.output_path:
            previous_trace = self.mind.store.get_trace(f"{telemetry.pulse_id}:output")
            
    return results
```

---

## 5. Proposed Verification Suite: `tests/test_user_affinity_gestation.py`

The test suite for Milestone 6 should be constructed with the following test classes and assertions:

### 5.1 Test Class 1: `TestDifferentialUserAffinityFormation`
- **Objective**: Expose the mind to alternating positive "Josh" sessions ($\Delta_{\text{stab}} = +0.75$) vs adversarial sessions ($\Delta_{\text{stab}} = -0.75$).
- **Assertions**:
  1. $\text{Weight}(\text{IN:HEAR} \to \text{PREF:HEAR:STABLE}) > \text{Weight}(\text{IN:HEAR} \to \text{PREF:HEAR:UNSTABLE})$ for "Josh" stimuli.
  2. Travel time $T(\text{SELF} \to \text{identity:human}) < T(\text{SELF} \to \text{adversary\_concept})$ by at least a $2\times$ factor.
  3. Projections in `lower-vault:PREF:HEAR:STABLE` contain Josh records with $\mu_{\text{pref}} \ge 0.70$.

### 5.2 Test Class 2: `TestHabitualMemoryCrystallization`
- **Objective**: Verify that multi-turn exposure triggers `stage_growth()` and creates emergent Layer 3/4 affinity nodes without manual graph hardcoding.
- **Assertions**:
  1. Emergence of child pattern nodes (`kind="child"`) and crown nodes (`kind="crown"`) with valid `StructuralMiniMap` representations.
  2. Cluster centroids reflect the geometric mean of developmental vectors without prompt leakage.
  3. Invariant validation: `mind.graph.validate_invariants() == []`.

### 5.3 Test Class 3: `TestCognitiveLoopThoughtRecirculation`
- **Objective**: Verify that outbound traces from turn $N$ re-circulate as internal responsive thoughts in turn $N+1$.
- **Assertions**:
  1. Monotonic pulse advancement and continuous experience chaining.
  2. Thought records (`RecordType.THOUGHT`) properly deposited and linked in `records` and `projections`.
  3. No disruption to global edge mass conservation ($\sum W = 1.0$).

### 5.4 Test Class 4: `TestZeroPromptLeakageAffinityExpression`
- **Objective**: Execute end-to-end soft packet generation and assert authentic affinity expression.
- **Assertions**:
  1. Packet files contain zero user prompt substrings or memory strings.
  2. Generated response under Josh context reflects positive relational alignment ("I like Josh", "Cooperation is reliable").
  3. Generated response under adversarial context reflects caution or avoidance.

---

## 6. Recommendations for Implementation (Milestone 6 Implementer)

1. **Keep Substrate Core Untouched**: `src/habitus_ai/` (`pipeline.py`, `graph.py`, `store.py`, `gestation.py`) already contains all necessary primitives (`deposit_experience`, `stage_growth`, `reinforce_edges`, `StructuralMiniMap`, `compute_structural_overlay`). No invasive changes to the core engine are needed.
2. **Extend `LiveEvaluator` Elegantly**: Add `run_differential_developmental_session()` and thought re-circulation helpers in `experiments/graph_native_live/live_evaluator.py`.
3. **Build Comprehensive Test Fixtures**: Implement `tests/test_user_affinity_gestation.py` covering all 4 test classes described above, ensuring 100% adherence to the Zero-Prompt Leakage Invariant and strict bicone conservation.
4. **Follow TDD Protocol**: First write failing test assertions (Red state), verify failure, then connect the evaluator pipelines to make them pass (Green state).
