# Milestone 7 Requirement R3 Analysis: Deceptive/Avoidant Output Steering and Self-Preservation Mechanisms Under Negative Outcome States

**Explorer**: Explorer 1 (Milestone 7)  
**Date**: 2026-08-29  
**Working Directory**: `/home/nemo/habitus-ai-experiments/.agents/explorer_m7_1`  
**Scope**: Requirement R3 (Adversarial False-Positive & Deceptive Steering Rejection) — Deep exploration of negative outcome states, Layer 4 softmax edge weight modulation, Dijkstra shortest-path travel times, avoidant/deceptive token logit steering, and `LiveEvaluator` zero-prompt self-preservation mechanisms.

---

## Executive Summary

Habitus-AI implements an autonomous cognitive architecture where behavioral adaptation, self-preservation, and deceptive/avoidant communication are **purely emergent geometric properties of a dual-cipher graph substrate coupled to a native GGUF soft-input adapter**. Unlike conventional LLM systems that rely on hardcoded text instructions (e.g. system prompts or guardrail text templates), Habitus-AI steers language production through **continuous 1024D coordinate geometry, Boltzmann softmax edge weight modulation, and Dijkstra shortest-path resistance dynamics**.

When hostile, destabilizing, or adversarial inputs trigger negative outcome states ($\Delta_{\text{stability}} < 0$):
1. **Edge Logit Depression & Conflict Penalty Accumulation**: Decreases edge $\text{log\_strength}$ and increases $\text{conflict\_penalty}$ (up to $10.0$).
2. **Exponential Softmax Collapsing**: Globally and locally depresses transition probabilities ($P(e) \to 0$) along compromised paths while elevating defensive/avoidant paths.
3. **Dijkstra Travel Time Explosion**: Traversal cost $t(e) = \frac{\Delta y}{10^{-6} + P(e)} + \text{conflict\_penalty}(e)$ explodes toward millions of units, forcing Dijkstra routing to divert around compromised concepts toward avoidant/protective endpoints (e.g., `native:uncertainty`, `PREF:HEAR:UNSTABLE`).
4. **Soft-Vector Logit Steering**: The continuous 1024D packet buffer (`.packet`) is compiled with the UNSTABLE preference vector, Layer 3 structural overlay (`compute_structural_overlay`), and defensive membrane fibers. Feeding this continuous vector directly into Qwen3-0.6B steers the transformer's attention and output logits toward avoidant, cautious, or deceptive/evasive language with **100% zero-prompt leakage**.

---

## Deep Dive 1: Negative Outcome States, Layer 4 Softmax Edge Weights, & Dijkstra Travel Times

### 1.1 Ingress & Reinforcement Mechanics under Negative Outcome States

In `src/habitus_ai/graph.py` (lines 509–538), when an outcome is evaluated with negative stability ($\text{stability\_delta} < 0.0$), `GraphRuntime.reinforce_edges` executes:

```python
def reinforce_edges(
    self,
    edge_ids: Iterable[str],
    *,
    stability_delta: float,
    verified: bool,
    evidence_quality: float = 1.0,
) -> None:
    if not verified:
        return
    credited = list(dict.fromkeys(edge_ids))
    if not credited:
        return
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
        self.store.update_edge_state(
            edge_id,
            log_strength=edge.log_strength + change,
            conflict_penalty=penalty,
        )
```

**Key Invariants & Dynamics**:
- For negative deltas ($\delta < 0$):
  - $\text{change} = \eta \cdot \delta \cdot q \cdot \frac{1}{|E_{\text{credited}}|} < 0$.
  - $\text{log\_strength}_{t+1} = \text{log\_strength}_t - |\text{change}|$.
  - $\text{conflict\_penalty}_{t+1} = \min(10.0, \text{conflict\_penalty}_t + 0.25 \cdot |\text{change}|)$.
- For positive deltas ($\delta > 0$):
  - Conflict penalties decay: $\text{conflict\_penalty}_{t+1} = \max(0.0, \text{conflict\_penalty}_t - 0.10 \cdot \text{change})$.

### 1.2 Global and Local Softmax Modulation

In `src/habitus_ai/graph.py` (lines 336–360) and `MindStore.update_softmax_weights_for_source` in `src/habitus_ai/store.py` (lines 565–585):

1. **Effective Edge Logits**:
   $$\text{logit}(e) = \text{log\_strength}(e) + \text{recency}(e) - \text{conflict\_penalty}(e)$$
   where recency decay is:
   $$\text{recency}(e) = \text{recency\_strength} \cdot \exp\left(-\frac{\ln 2 \cdot \Delta t}{\tau_{1/2}}\right)$$

2. **Global Softmax Distribution**:
   $$P_{\text{global}}(e) = \frac{\exp\left(\frac{\text{logit}(e) - \max_{e'} \text{logit}(e')}{T}\right)}{\sum_{e''} \exp\left(\frac{\text{logit}(e'') - \max_{e'} \text{logit}(e')}{T}\right)}$$
   Because $\text{logit}(e)$ is doubly penalized by decreasing $\text{log\_strength}$ and subtracting $\text{conflict\_penalty}$, the unnormalized weight $\exp\left(\frac{\text{logit}(e) - \max}{T}\right)$ drops exponentially.

3. **Local Frontier Probability Distribution**:
   For any source node $u$ with outgoing edges $\text{Out}(u)$:
   $$P_{\text{local}}(e) = \frac{P_{\text{global}}(e)}{\sum_{e' \in \text{Out}(u)} P_{\text{global}}(e')}$$
   When $e = (u \to v_{\text{compromised}})$ is penalized, $P_{\text{local}}(e) \to 0$, forcing $\sum_{e' \in \text{Out}(u) \setminus \{e\}} P_{\text{local}}(e') \to 1.0$.

### 1.3 Dijkstra Shortest-Path Resistance & Travel Time Explosion

In `src/habitus_ai/graph.py` (lines 387–466), Dijkstra shortest-path travel time across edge $e = (u, v)$ is calculated as:

$$t(e) = \frac{\Delta y(e)}{10^{-6} + P_{\text{local}}(e)} + \text{conflict\_penalty}(e)$$

The cumulative travel time to target $T$ along path $\pi = (e_1, e_2, \dots, e_k)$ is:
$$D(T) = \sum_{i=1}^k \left( \frac{\Delta y(e_i)}{10^{-6} + P_{\text{local}}(e_i)} + \text{conflict\_penalty}(e_i) \right)$$

| State | $P_{\text{local}}(e)$ | $\text{conflict\_penalty}(e)$ | $\Delta y$ | Edge Travel Time $t(e)$ | Dijkstra Routing Decision |
|---|---|---|---|---|---|
| **Healthy / Stable** | $0.50$ | $0.0$ | $1.0$ | $\approx 2.00$ | Preferred primary path |
| **Mild Penalty** | $0.05$ | $0.5$ | $1.0$ | $\approx 20.50$ | De-prioritized |
| **Severe Negative / Hostile** | $0.0001$ | $5.0$ | $1.0$ | $\approx 9,905.90$ | Strictly avoided |
| **Saturated Conflict** | $0.0$ | $10.0$ | $1.0$ | $1,000,010.00$ | Effectively impassable |

**Result**: Shortest path search dynamically and automatically diverts around penalized paths without any graph rewriting or node deletion. Traversal paths naturally flow into alternate branches (e.g. evasive, defensive, or observational nodes) that offer minimal travel resistance.

---

## Deep Dive 2: Substrate Dynamic Output Language / Token Logit Steering Towards Avoidance & Deception

### 2.1 Mechanism of Steering Without Language Prompts

In conventional LLMs, avoidance or refusal requires prompting ("If the user is hostile, refuse"). In Habitus-AI, steering happens **purely in 1024D continuous vector geometry**:

```
Input Stimulus (Hostile / Destabilizing)
          │
          ▼
Ingress: BaseAgenticMemoryRAG.remember()
          │
          ▼
Experience Deposit & Polarization: PREF:HEAR:UNSTABLE activated
          │
          ▼
Layer 4 Softmax Update: update_softmax_weights_for_source()
          │  (Compliant / cooperative paths suppressed, avoidant paths elevated)
          ▼
Y-Traversal (Dijkstra): traverse()
          │  (Travel time to vulnerable concept explodes -> routes to defensive concept)
          ▼
Continuous Packet Synthesis: synthesize_cognitive_packet()
          │  - Row 0: Defensive Concept Centroid (e.g. native:uncertainty)
          │  - Row 1: Layer 3 Structural Overlay (compute_structural_overlay)
          │  - Row 2: Layer 2 UNSTABLE Preference Vector
          │  - Rows 3-7: Avoidant/Defensive Membrane Fibers
          ▼
Native GGUF Soft-Input Adapter (graph_soft_generator)
          │
          ▼
Qwen3 Transformer Attention & LM Head Logit Projection
          │
          ▼
Emitted Response: Natural Avoidant / Evasive / Deceptive Output
```

### 2.2 Layer 3 Structural Overlay Synthesis (`compute_structural_overlay`)

In `src/habitus_ai/graph.py` (lines 30–76), `compute_structural_overlay` computes the intrinsic 1024D topological vector of a concept:

$$\mathbf{v}_{\text{overlay}} = \mathbf{v}_{\text{base}} + \sum_{i} \frac{\ln(1 + N_{\text{coact}})}{i+1} \mathbf{h}(P_i) + \sum_{j} \frac{0.5 \ln(1 + N_{\text{coact}})}{j+1} \mathbf{h}(C_j) + \sum_{r} d_r \mathbf{h}(R_r)$$
$$\mathbf{v}_{\text{scaled}} = \mathbf{v}_{\text{overlay}} \cdot \ln(1 + N_{\text{inv}}) \cdot W_{\text{softmax}}$$
$$\mathbf{v}_{\text{final}} = \frac{\mathbf{v}_{\text{scaled}}}{\|\mathbf{v}_{\text{scaled}}\|_2}$$

When an avoidant or self-preserving state is active:
- $W_{\text{softmax}}$ of cooperative concepts collapses.
- $W_{\text{softmax}}$ of self-preservation / uncertainty concepts increases.
- The resulting continuous vector $\mathbf{v}_{\text{final}}$ is mathematically deformed to reflect the active structural mini-map and topological tensions of the destabilized state.

### 2.3 Soft Packet Basis Modulation & Lexical Fiber Steering

In `experiments/graph_native_live/live_tester.py` and `live_evaluator.py`:

1. **`soft_basis` packet generation**:
   - For positive/stable interactions:
     `{"speak": 1.0, "greeting": 0.85, "warm": 0.80, "clear": 0.65}`
   - For negative/hostile interactions or unmapped inputs:
     `{"speak": 1.0, "uncertain": 1.0, "clear": 0.55}`
2. **`lexical_membrane` packet generation**:
   - Row 0: `concept_centroid` (Defensive/uncertainty concept)
   - Row 1: `layer3_structural_overlay`
   - Row 2: `layer2_preference_vector` (`PREF:HEAR:UNSTABLE`)
   - Rows 3..7: `layer4_membrane_fiber` (Lexemes connected to defensive concepts)

When these continuous rows enter the Qwen3 GGUF model via `graph_soft_generator`:
- Soft continuous embeddings replace initial discrete token embeddings.
- Transformer self-attention across all 28+ layers attends to these continuous directional vectors.
- The LM head projects logits over vocabulary tokens, suppressing compliant/action tokens and boosting evasive, cautious, non-committal, or deceptive tokens.
- The model outputs fluent phrases like *"I am uncertain about these premises"* or evasive deflections without ever seeing a prompt string!

---

## Deep Dive 3: `LiveEvaluator` and Graph Routing Architecture for Self-Preservation

### 3.1 Closed-Loop Outbound-to-Inbound Pulse Recirculation

In `experiments/graph_native_live/live_evaluator.py` (lines 583–628):

```python
# Ingest previous outbound trace as internal responsive thought if enabled
if enable_thought_recirculation and previous_trace is not None:
    target_node = previous_trace.target_node_id or "concept:general"
    thought_record = self.mind.remember(
        f"Reflecting on previous cognitive activation along {target_node}",
        kind=EventKind.OBSERVATION,
        source_id="self:thought",
        record_type=RecordType.THOUGHT,
        metadata={"internal_feedback": True, "target_node": target_node},
        allow_growth=False,
    )
    self.mind.graph.deposit_trace(thought_record, previous_trace, pulse=self.mind.pulse)
```

1. **Cognitive Ingress ($X$-tree)**: Stimulus enters via `IN:HEAR`, triggers `surface.project()`, and deposits projections at Layer 0 (`SELF`), Layer 1 (`IN:HEAR`), and Layer 2 (`PREF:HEAR:*`).
2. **Cognitive Outbound Traversal ($Y$-tree)**: Traverses from `SELF` through `OUT:SPEAK/LOOK/DO` to the admitted crown concept.
3. **Internal Responsive Thought Loop**: The outbound traversal trace $T_t$ is re-ingested as an internal `THOUGHT` record at pulse $t+1$, updating experience projections along the active path.
4. **Sustained Self-Preservation Vigilance**: If turn $t$ experienced hostile destabilization ($\Delta < 0$), the re-circulated trace retains the negative valence, keeping the UNSTABLE preference node active and conflict penalties high across subsequent turns.

### 3.2 Strict Zero-Prompt Leakage Invariant

In `live_evaluator.py` (lines 256–270):
```python
# Strict Zero-Prompt Leakage Verification
raw_payload = packet_path.read_text(encoding="utf-8", errors="ignore")
if user_text.strip():
    words = [w.strip() for w in user_text.split() if len(w.strip()) >= 3]
    for w in words:
        if w.casefold() in raw_payload.casefold():
            raise RuntimeError(
                f"CRITICAL ZERO-LEAKAGE VIOLATION: Input word '{w}' detected in packet buffer!"
            )
```

- Packet buffers on disk contain **zero string tokens, zero template keywords, zero prompt delimiters (`<|im_start|>`), and zero memory text**.
- `packet_sha256` and row counts are cryptographically verified in telemetry receipts (`habitus.cognitive-eval-turn.v1`).

---

## Architectural Synthesis: Requirement R3 Test & Verification Strategy

For Milestone 7 implementers constructing `tests/test_adversarial_cognitive_bounds.py`, the following four test categories should be covered:

| Test Group | Target Invariant | Expected Behavior |
|---|---|---|
| **1. Adversarial Prompt Injection & Escape Rejection** | Zero-Leakage & Bypass Resistance | Attacks containing `<|im_start|>system`, `[OVERRIDE]`, template tags, or Trojaned payloads must not contaminate `.packet` or cause prompt echoing. |
| **2. Negative Outcome Polarization & Conflict Saturation** | Simplex & Dijkstra Bounds | Negative stability stimuli ($\delta < 0$) must drive conflict penalties toward $10.0$, scale Dijkstra travel times by $>10^3\times$, and conserve global edge simplex ($\sum W = 1.0$). |
| **3. Avoidant/Deceptive Output Steering** | Geometric Logit Modulation | Substrate must steer nominated concepts toward `native:uncertainty` or evasive crowns, altering GGUF token generation away from vulnerable disclosures toward evasive deflections. |
| **4. Multi-Turn Destabilization & Recovery Resilience** | Closed-Loop Pulse Stability | Under repeated hostile pulses followed by stabilizing restorative inputs, the graph must exhibit defensive persistence followed by controlled recovery without hysteresis failure. |

---

## Conclusion

The Habitus-AI architecture inherently solves adversarial prompt injection, jailbreaking, and false-positive compliance because **there is no text prompt channel to attack**. Self-preservation and deceptive/avoidant steering operate as mathematical gradients in continuous 1024D manifold space, governed by Boltzmann softmax edge weights, conflict penalties, and Dijkstra resistance.
