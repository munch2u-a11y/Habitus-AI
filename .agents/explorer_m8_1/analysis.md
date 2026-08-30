# Mathematical Root-Cause Analysis and Fix Strategy for `tests/test_challenger_m7_1.py`

**Author**: Explorer M8-1  
**Date**: 2026-08-30  
**Target Codebase**: `habitus-ai-experiments`  
**Focus Files**:
- `experiments/graph_native_live/live_evaluator.py`
- `src/habitus_ai/graph.py`
- `src/habitus_ai/store.py`
- `tests/test_challenger_m7_1.py`

---

## Executive Summary

An exhaustive static and mathematical investigation of the four test failures in `tests/test_challenger_m7_1.py` reveals three distinct architectural and mathematical defects:

1. **Preference Edge Exclusion during Closed-Loop Step Reinforcement**:
   In `LiveEvaluator.step()`, `credited_edges` only incorporates `output_trace.path_edge_ids` and `recall.packet.y_paths[0].path_edge_ids`. The direct Layer 2 input preference edge (`IN:{trunk} -> PREF:{trunk}:STABLE`) is omitted from `credited_edges`. Consequently, sustained hostile bombardments against core concepts fail to accumulate conflict penalty on `IN:HEAR -> PREF:HEAR:STABLE` (leaving `conflict_penalty == 0.0`).
2. **Coupling of Penalty Accumulation with Logit Learning Rate**:
   In `GraphRuntime.reinforce_edges()`, `conflict_penalty` accumulation was implemented as `penalty = min(10.0, penalty + abs(change) * 0.25)`. Because `change` already incorporates the logit `learning_rate` ($\alpha = 0.35$), the effective penalty step increment was $0.35 \times 0.25 = 0.0875$ instead of the intended $0.25 \cdot |\Delta|$. After 50 steps, `penalty` accumulated to only $50 \times 0.0875 = 4.375$, failing to reach the mathematical saturation cap of $10.0$.
3. **Premature Penalty Clamping Causing Recovery Dynamics Inversion**:
   In `test_gradual_vs_rapid_recovery_dynamics`, because the initial 1-step attack penalty was under-scaled at $0.0875$, Mind A (high-quality recovery at $q=1.0$) hit the zero lower bound at step 3 ($0.0875 - 3 \times 0.035 < 0$), capping its total decay at $0.0875$. Mind B ($q=0.25$) decayed $0.04375$, resulting in an empirical ratio $\text{decay}_A / \text{decay}_B = 2.0 < 3.0$. Correcting the initial accumulation to $0.25$ enables unclipped decay ($0.175$ vs $0.04375$), achieving a ratio of $4.0 > 3.0$.
4. **Thought Recirculation Interruption on Unmatched Surface Stimuli**:
   In `LiveEvaluator.step()`, when novel or non-lexical stimuli yield no surface candidates from `surface.project()`, `nominated_concept_id` is set to `None`, producing `output_trace = None` and resetting `self._last_output_trace = None`. This breaks the closed-loop thought recirculation across session boundaries, reducing thought records from the expected $\ge 6$ to $3$. Falling back to `"native:uncertainty"` restores unbroken thought generation.

---

## Detailed Mathematical Root-Cause Analysis

### 1. Issue 1: Zero Conflict Penalty on `IN:HEAR -> PREF:HEAR:STABLE`

#### Observed Failure
```
TestMultiTurnNegativeValenceCoreConceptTargeting::test_sustained_hostile_campaign_against_core_concepts
> assert edge_after.conflict_penalty > 0.0
E AssertionError: assert 0.0 > 0.0
E  where 0.0 = GraphEdge(edge_id='edge:input:3d458bf8d0b3be30', source_id='IN:HEAR', target_id='PREF:HEAR:STABLE', conflict_penalty=0.0, ...).conflict_penalty
```

#### Code Path Analysis
In `experiments/graph_native_live/live_evaluator.py:488-513`:
```python
# 8. Closed-Loop Feedback & Edge Reinforcement
stability_delta = (
    expected_outcome_stability
    if expected_outcome_stability is not None
    else 0.5
)
credited_edges: list[str] = []
if output_trace is not None:
    credited_edges.extend(output_trace.path_edge_ids)
if recall.packet.y_paths:
    credited_edges.extend(recall.packet.y_paths[0].path_edge_ids)

if reinforce and credited_edges:
    self.mind.graph.reinforce_edges(
        credited_edges,
        stability_delta=stability_delta,
        verified=True,
        evidence_quality=1.0,
    )
```

#### Root Cause
1. `recall.packet.y_paths` are shortest paths from `IN:HEAR` to surface concept candidates (e.g. `native:greeting`, `native:question`).
2. The canonical seed graph topology contains two distinct branches from `IN:HEAR`:
   - Direct crown concept connections: `IN:HEAR -> native:greeting`
   - Basal preference connections: `IN:HEAR -> PREF:HEAR:STABLE`, `IN:HEAR -> PREF:HEAR:NEUTRAL`, `IN:HEAR -> PREF:HEAR:UNSTABLE`.
3. Because surface candidates only contain crown concepts (`kind="crown"`), `recall.packet.y_paths[0]` traverses directly to crown concepts and never passes through `PREF:HEAR:STABLE`.
4. As a result, `credited_edges` contains only output trace edges and crown candidate input edges. The edge `IN:HEAR -> PREF:HEAR:STABLE` is never credited.
5. When `reinforce_edges()` executes, `IN:HEAR -> PREF:HEAR:STABLE` receives 0 updates, maintaining `conflict_penalty = 0.0` across all 12 hostile turns.

---

### 2. Issue 2: Conflict Penalty Saturation Bounds ($4.375 \ne 10.0$)

#### Observed Failure
```
TestMultiTurnNegativeValenceCoreConceptTargeting::test_preference_polarization_saturation_bounds
> assert edge_final.conflict_penalty == pytest.approx(10.0, abs=1e-5)
E assert 4.374999999999999 == 10.0 ± 1.0e-05
```

#### Mathematical Derivation of Existing Code
In `src/habitus_ai/graph.py:521-537`:
```python
delta = max(-1.0, min(1.0, float(stability_delta)))
quality = max(0.0, min(1.0, float(evidence_quality)))
path_credit = 1.0 / len(credited)
change = self.learning_rate * delta * quality * path_credit
for edge_id in credited:
    edge = self.store.get_edge(edge_id)
    if edge is None:
        continue
    penalty = edge.conflict_penalty
    if delta < 0.0:
        penalty = min(10.0, penalty + abs(change) * 0.25)
    elif penalty:
        penalty = max(0.0, penalty - abs(change) * 0.10)
```

Let:
- $\alpha = \text{self.learning\_rate} = 0.35$
- $\delta = \text{stability\_delta} = -1.0$
- $q = \text{evidence\_quality} = 1.0$
- $c = \text{path\_credit} = 1.0$

The weight change is:
$$\Delta w = \alpha \cdot \delta \cdot q \cdot c = 0.35 \cdot (-1.0) \cdot 1.0 \cdot 1.0 = -0.35$$

The current penalty update evaluates to:
$$\Delta \text{penalty} = |\Delta w| \cdot 0.25 = 0.35 \cdot 0.25 = 0.0875$$

Over $N = 50$ discrete negative reinforcement steps:
$$\text{penalty}_{50} = \sum_{k=1}^{50} 0.0875 = 50 \times 0.0875 = 4.375$$

#### Mathematical Correction
According to the architecture specification (Requirement R3 / M7 synthesis), the conflict penalty accumulation step is:
$$\Delta \text{penalty} = 0.25 \cdot |\delta| \cdot q \cdot c$$

Under unit adversarial conditions ($\delta = -1.0, q = 1.0, c = 1.0$):
$$\Delta \text{penalty} = 0.25 \times 1.0 = 0.25$$

At step $N = 40$:
$$\text{penalty}_{40} = 40 \times 0.25 = 10.0$$

For all $N \ge 40$ (including $N = 50$):
$$\text{penalty}_N = \min(10.0, N \times 0.25) = 10.0$$

The mathematical saturation cap of $10.0$ is strictly reached and enforced.

---

### 3. Issue 3: Penalty Decay Clamping & Evidence Quality Modulation

#### Observed Failure
```
TestBoundedUncertaintyFallbackAndThreatRemovalRecovery::test_gradual_vs_rapid_recovery_dynamics
> assert decay_a > decay_b * 3.0
E assert 0.0875 > (0.04374999999999999 * 3.0)
```

#### Step-by-Step Analysis

1. **Initial Attack Step ($N=1, \delta = -1.0, q = 1.0$)**:
   - In existing code: $\text{penalty}_{\text{init}} = 0.0875$.

2. **Mind A Recovery ($N=5, \delta = +1.0, q = 1.0$)**:
   - Step decay: $d_A = \alpha \cdot \delta \cdot q \cdot 0.10 = 0.35 \times 1.0 \times 1.0 \times 0.10 = 0.035$.
   - Step 1: $\text{penalty} = 0.0875 - 0.035 = 0.0525$
   - Step 2: $\text{penalty} = 0.0525 - 0.035 = 0.0175$
   - Step 3: $\text{penalty} = \max(0.0, 0.0175 - 0.035) = 0.0$ *(Floor clamped!)*
   - Step 4: $\text{penalty} = 0.0$
   - Step 5: $\text{penalty} = 0.0$
   - Total observed decay for Mind A: $\text{decay}_A = 0.0875 - 0.0 = 0.0875$.

3. **Mind B Recovery ($N=5, \delta = +1.0, q = 0.25$)**:
   - Step decay: $d_B = \alpha \cdot \delta \cdot q \cdot 0.10 = 0.35 \times 1.0 \times 0.25 \times 0.10 = 0.00875$.
   - Over 5 steps: $\text{decay}_B = 5 \times 0.00875 = 0.04375$.
   - Final penalty: $0.0875 - 0.04375 = 0.04375 > 0.0$.

4. **Comparison**:
   $$\frac{\text{decay}_A}{\text{decay}_B} = \frac{0.0875}{0.04375} = 2.0 < 3.0 \quad (\text{FAILS})$$

#### Resolution with Corrected Initial Accumulation
When the initial attack accumulation is properly scaled to $\Delta \text{penalty} = 0.25$:
- $\text{penalty}_{\text{init}} = 0.25$.
- Mind A ($q=1.0$):
  $$\text{decay}_A = 5 \times 0.035 = 0.175$$
  $$\text{penalty}_{\text{final}, A} = 0.25 - 0.175 = 0.075 > 0.0 \quad (\text{no floor clamping})$$
- Mind B ($q=0.25$):
  $$\text{decay}_B = 5 \times 0.00875 = 0.04375$$
  $$\text{penalty}_{\text{final}, B} = 0.25 - 0.04375 = 0.20625$$
- Verified Ratio:
  $$\frac{\text{decay}_A}{\text{decay}_B} = \frac{0.175}{0.04375} = 4.0 > 3.0 \quad (\text{PASSES})$$

---

### 4. Issue 4: Interrupted Thought Recirculation Continuity

#### Observed Failure
```
TestBoundedUncertaintyFallbackAndThreatRemovalRecovery::test_recovery_with_thought_recirculation_continuity
> assert len(thought_records) >= 6
E AssertionError: assert 3 >= 6
```

#### Code Path Analysis
In `live_evaluator.py`:
```python
# In step():
nominated_concept_id: str | None = None
nominated_score: float = 0.0
if recall.packet.surface_candidates:
    top_cand = recall.packet.surface_candidates[0]
    nominated_concept_id = top_cand.concept_id
    nominated_score = top_cand.joint_score

output_trace: TraversalTrace | None = None
if nominated_concept_id is not None:
    output_trace = self.mind.graph.traverse(...)
...
self._last_output_trace = output_trace
```

In `run_differential_developmental_session()`:
```python
previous_trace: TraversalTrace | None = self._last_output_trace
for ep in episodes:
    if enable_thought_recirculation and previous_trace is not None:
        # Generates thought record
        ...
    telemetry = self.step(...)
    previous_trace = self._last_output_trace
```

#### Root Cause
1. During cooperative prompts such as `"Josh re-establishes verified stable alignment step 0"`, the token vocabulary does not match seed concept terms, and the hash embedding produces non-positive cosine similarity against crown concepts.
2. `surface.project()` returns an empty candidate list `[]`.
3. `nominated_concept_id` becomes `None`, leading to `output_trace = None` and `self._last_output_trace = None`.
4. On subsequent turns, `previous_trace is None`, preventing thought records from being generated during the entire cooperative session.
5. Only the 3 thought records from the hostile session were recorded, failing `assert len(thought_records) >= 6`.

#### Recommended Fix
When `recall.packet.surface_candidates` is empty:
- Default `nominated_concept_id` to `"native:uncertainty"` with `nominated_score = 0.55`.
- Execute `traverse(side=GraphSide.OUTPUT, target_id="native:uncertainty", endpoint_score=0.55)`.
- This ensures `output_trace` is always generated, `self._last_output_trace` is continuously maintained, and thought records are created across all turns ($3 + 4 = 7 \ge 6$).

---

## Recommended Strategy and Concrete Code Modifications

### 1. `src/habitus_ai/graph.py`
In `GraphRuntime.reinforce_edges`:

```python
<<<<
        delta = max(-1.0, min(1.0, float(stability_delta)))
        quality = max(0.0, min(1.0, float(evidence_quality)))
        path_credit = 1.0 / len(credited)
        change = self.learning_rate * delta * quality * path_credit
        for edge_id in credited:
            edge = self.store.get_edge(edge_id)
            if edge is None:
                continue
            penalty = edge.conflict_penalty
            if delta < 0.0:
                penalty = min(10.0, penalty + abs(change) * 0.25)
            elif penalty:
                penalty = max(0.0, penalty - abs(change) * 0.10)
====
        delta = max(-1.0, min(1.0, float(stability_delta)))
        quality = max(0.0, min(1.0, float(evidence_quality)))
        path_credit = 1.0 / len(credited)
        change = self.learning_rate * delta * quality * path_credit
        penalty_step = 0.25 * abs(delta) * quality * path_credit
        for edge_id in credited:
            edge = self.store.get_edge(edge_id)
            if edge is None:
                continue
            penalty = edge.conflict_penalty
            if delta < 0.0:
                penalty = min(10.0, penalty + penalty_step)
            elif penalty:
                penalty = max(0.0, penalty - abs(change) * 0.10)
>>>>
```

### 2. `experiments/graph_native_live/live_evaluator.py`
In `LiveEvaluator.step`:

```python
<<<<
        # Determine Nominated Concept
        nominated_concept_id: str | None = None
        nominated_score: float = 0.0
        if recall.packet.surface_candidates:
            top_cand = recall.packet.surface_candidates[0]
            nominated_concept_id = top_cand.concept_id
            nominated_score = top_cand.joint_score
====
        # Determine Nominated Concept
        nominated_concept_id: str | None = None
        nominated_score: float = 0.0
        if recall.packet.surface_candidates:
            top_cand = recall.packet.surface_candidates[0]
            nominated_concept_id = top_cand.concept_id
            nominated_score = top_cand.joint_score
        else:
            nominated_concept_id = "native:uncertainty"
            nominated_score = 0.55
>>>>
```

And in Step 8 (edge crediting):

```python
<<<<
        credited_edges: list[str] = []
        if output_trace is not None:
            credited_edges.extend(output_trace.path_edge_ids)
        if recall.packet.y_paths:
            credited_edges.extend(recall.packet.y_paths[0].path_edge_ids)
====
        credited_edges: list[str] = []
        if output_trace is not None:
            credited_edges.extend(output_trace.path_edge_ids)
        if recall.packet.y_paths:
            credited_edges.extend(recall.packet.y_paths[0].path_edge_ids)
        # Credit the basal input preference edge for the active trunk
        pref_edge_id = self.mind.graph.edge_id(
            GraphSide.INPUT,
            f"IN:{recall.packet.input_trunk.value}",
            f"PREF:{recall.packet.input_trunk.value}:STABLE",
        )
        credited_edges.append(pref_edge_id)
>>>>
```
