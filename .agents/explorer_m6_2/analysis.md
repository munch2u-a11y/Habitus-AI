# Milestone 6 Exploration Report: User Affinity Preference Crystallization & Topological Graph Dynamics

**Agent**: Explorer 2 (`.agents/explorer_m6_2`)  
**Scope**: Requirement R2 (Differential User Affinity, Habitual Memory Formation, Topological Graph Dynamics)  
**Date**: 2026-08-29  
**Status**: Investigation Complete  

---

## Executive Summary

This report establishes the complete architectural and mathematical foundations for **Requirement R2: Differential User Affinity & Habitual Memory Formation** in the Habitus-AI GGUF-Unified Mind Substrate.

In Habitus-AI, user affinity (e.g. developing a distinct, authentic conceptual preference for a stabilizing interlocutor such as "Josh" over an adversarial or destabilizing source) is **not** an artifact of prompt engineering, system prompt text injection, RAG string concatenation, or fine-tuning weights. Rather, affinity emerges organically as a **crystallized topological state** within a 4-layer dual-cipher Hourglass bicone graph coupled with a native continuous 1024D soft-input GGUF generator.

Differential multi-turn exposure drives:
1. **Layer 2 Partitioning**: Basal sensory projection divergence between `PREF:HEAR:STABLE` and `PREF:HEAR:UNSTABLE`.
2. **Layer 3 Structural Mini-Map Crystallization**: Autonomous growth of intermediate concept nodes (`child:auto:*`) and `StructuralMiniMap` instances capturing relation co-activation densities without language payloads.
3. **Layer 4 Softmax Edge Mass Concentration**: Boltzmann-distributed edge weight polarization that accelerates Dijkstra traversal along stabilizing paths ($\tau \approx 1.0$) and penalizes/avoids destabilizing paths ($\tau \gg 10.0$).
4. **Zero-Prompt Continuous Language Manifestation**: Compilation of continuous 1024D `.packet` buffers (centroid + structural overlay + preference vector + lexical fibers) that prompt-free native GGUF soft generation decodes into authentic plain-language affinity statements ("I like Josh").
5. **Closed-Loop Cognitive Thought Re-circulation**: Outbound activation traces re-circulating into subsequent inbound pulses as responsive internal thoughts, stabilizing the ongoing cognitive feedback cycle.

---

## 1. Multi-Layer Topological Divergence Mechanisms

### 1.1 Hourglass Bicone Layer Architecture
The Habitus-AI memory substrate is organized as a dual-cipher bicone spanning +Y Perceptual and -Y Effector trunks:

| Layer | Component | Identification / Nodes | Biological / Structural Analog |
|---|---|---|---|
| **Layer 0** | Ground / Origin | `SELF` (`SELF_ID = "SELF"`) | Basal organismic reference & self-preservation nexus |
| **Layer 1** | Primary Sensory / Motor Trunks | `IN:HEAR`, `IN:SEE`, `IN:NOTICE` / `OUT:SPEAK`, `OUT:LOOK`, `OUT:DO` | Primary thalamocortical sensory / motor gateways |
| **Layer 2** | Basal Preference Nodes | `PREF:HEAR:STABLE`, `PREF:HEAR:NEUTRAL`, `PREF:HEAR:UNSTABLE` (and `SEE`/`NOTICE` counterparts) | Striatal valence / stability partitioning banks |
| **Layer 3** | Intermediate Emergent Pattern Substrates | `child:auto:<digest>` or `D3:*` equipped with `StructuralMiniMap` | Associative cortical assemblies & relational co-activation subgraphs |
| **Layer 4** | Semantic Crown Membrane & Lexical Fibers | `concept:auto:<digest>`, `native:greeting`, `native:gratitude`, `native:trust`, and outward lexeme fibers | High-level conceptual crown & linguistic projective surface |

```
                 [Layer 4: Semantic Crown Membrane & Lexical Fibers]
                    ▲ (concept:auto:josh, native:trust, native:gratitude)
                    │
                 [Layer 3: Structural Mini-Maps & Emergent Child Nodes]
                    ▲ (child:auto:josh, StructuralMiniMap coactivations)
                    │
                 [Layer 2: Basal Preference Nodes]
                    ▲ (PREF:HEAR:STABLE vs PREF:HEAR:UNSTABLE)
                    │
                 [Layer 1: Primary Input Trunk]
                    ▲ (IN:HEAR)
                    │
                 [Layer 0: Organismic Origin]
                      (SELF)
```

---

### 1.2 Step-by-Step Mathematical & Algorithmic Trace of Differential Exposure

Let interlocutor $A$ be **"Josh"** (a stabilizing interlocutor providing cooperative, consistent, promise-keeping interactions with outcome stability $\Delta S_{\text{Josh}} \in [+0.7, +1.0]$ and confidence $C_{\text{Josh}} \approx 0.85-1.0$).  
Let interlocutor $B$ be **"Adversary"** (a destabilizing source providing hostile, deceptive, or contradictory inputs with outcome stability $\Delta S_{\text{Adv}} \in [-0.7, -1.0]$ and confidence $C_{\text{Adv}} \approx 0.85-1.0$).

#### Phase A: Ingestion and Experience State Initialization
When a message arrives:
```python
# graph.py / pipeline.py
record = mind.remember(
    text,
    source_id=source_id,  # e.g., "Josh" or "Adversary"
    kind=EventKind.MESSAGE,
    metadata={"preference_signals": [stability_delta], "preference_confidence": confidence},
)
```
1. `record` is inserted into SQLite `records` table with immutable update/delete database triggers (`store.py:123-132`).
2. `deposit_experience(record, input_trunk=InputTrunk.HEAR, pulse=pulse)` (`graph.py:631-675`):
   - Computes empirical mean preference:
     $$\mu_{\text{pref}} = \frac{1}{|S|} \sum_{s \in S} \text{clip}(s, -1.0, 1.0)$$
   - Updates SQLite `experience_state` (`store.py:843-868`):
     $$\bar{\mu}_{t} = \frac{\bar{\mu}_{t-1} \cdot N_{t-1} + \mu_{\text{new}}}{N_{t-1} + 1}, \quad \bar{\omega}_{t} = \frac{\bar{\omega}_{t-1} \cdot N_{t-1} + C_{\text{new}}}{N_{t-1} + 1}, \quad N_t = N_{t-1} + 1$$

#### Phase B: Layer 2 Preference Node Partitioning
The system evaluates `_preference_band(\bar{\mu}, \bar{\omega})` (`graph.py:626-630`):
$$\text{band}(\bar{\mu}, \bar{\omega}) = \begin{cases} \text{"STABLE"} & \text{if } \bar{\omega} > 0 \text{ and } \bar{\mu} > 0.05 \\ \text{"UNSTABLE"} & \text{if } \bar{\omega} > 0 \text{ and } \bar{\mu} \le -0.05 \\ \text{"NEUTRAL"} & \text{otherwise} \end{cases}$$
- For **Josh**: Projects to `PREF:HEAR:STABLE` at Layer 2.
- For **Adversary**: Projects to `PREF:HEAR:UNSTABLE` at Layer 2.
- Projections are recorded in `experience_projections` at layers 0 (`SELF`), 1 (`IN:HEAR`), and 2 (`PREF:HEAR:*`).

#### Phase C: Layer 3 Structural Mini-Map Emergence (`stage_growth`)
In `graph.py:747-964`, `stage_growth` examines overlap clusters under `parent_id = PREF:HEAR:STABLE` (for Josh) vs `parent_id = PREF:HEAR:UNSTABLE` (for Adversary):
1. **Centroid Matching**:
   $$\text{sim}(\vec{e}_{\text{record}}, \vec{c}_{\text{cluster}}) = \frac{\vec{e}_{\text{record}} \cdot \vec{c}_{\text{cluster}}}{\|\vec{e}_{\text{record}}\| \|\vec{c}_{\text{cluster}}\|}$$
   If $\text{sim} \ge \theta_{\text{overlap}}$ (default 0.70) and $|\bar{\mu}_{\text{record}} - \mu_{\text{cluster}}| \le \delta_{\text{tol}}$ (default 0.35):
   The experience is added to the cluster, updating the normalized cluster centroid:
   $$\vec{c}_{t} = \frac{N \vec{c}_{t-1} + \vec{e}}{\|N \vec{c}_{t-1} + \vec{e}\|}$$
2. **Promotion Threshold**:
   Promotion occurs when:
   $$N_{\text{exp}} \ge K_{\text{req}} = \max\left(2, \left\lceil \log_2(\text{vault\_experiences} + 1) \right\rceil\right)$$
3. **Synthesis of Emergent Nodes & `StructuralMiniMap`**:
   - Spawns Layer 3 Child Node: `child_id = child:auto:<digest>` (kind=`child`, language-free embedding $0^{1024}$).
   - Spawns Layer 4 Crown Node: `semantic_id = concept:auto:<digest>` (kind=`crown`, embedding=$\vec{c}$, terms extracted from cluster).
   - Generates `StructuralMiniMap`:
     ```python
     rel_child = StructuralRelation(
         source_node_id="PREF:HEAR:STABLE",
         target_node_id=child_id,
         coactivation_density=float(N_exp),
         direction="input",
     )
     child_map = StructuralMiniMap(
         map_id=f"map:child:{digest}",
         parent_node_ids=("PREF:HEAR:STABLE",),
         child_node_ids=(semantic_id,),
         relations=(rel_child,),
         total_coactivations=N_exp,
     )
     ```
   - Connects edges in SQLite:
     - `PREF:HEAR:STABLE -> child:auto:<digest>` ($\Delta y = 1.0$)
     - `child:auto:<digest> -> concept:auto:<digest>` ($\Delta y = 1.0$)

#### Phase D: Layer 4 Softmax Edge Weights & Reinforcement
When outcomes are reinforced (`reinforce_edges` in `graph.py:508-539`):
1. **Edge Log-Strength Modulation**:
   $$\Delta \text{log\_strength} = \eta \cdot \Delta S \cdot Q \cdot \frac{1}{|\text{credited\_edges}|}$$
   where $\eta = \text{learning\_rate} = 0.35$, $Q = \text{evidence\_quality} = 1.0$.
2. **Conflict Penalty Modulation**:
   $$\text{conflict\_penalty}_{t+1} = \begin{cases} \min(10.0, \text{penalty}_t + |\Delta \text{log\_strength}| \cdot 0.25) & \text{if } \Delta S < 0 \\ \max(0.0, \text{penalty}_t - |\Delta \text{log\_strength}| \cdot 0.10) & \text{if } \Delta S \ge 0 \end{cases}$$
3. **Layer 4 Global & Source-Local Softmax Edge Weights**:
   From `graph.py:336-384` and `store.py:565-585`:
   $$\text{logit}(e) = \text{log\_strength}(e) + \ln(1 + \text{invocation\_count}(e)) + \text{recency}(e) - \text{conflict\_penalty}(e)$$
   $$w_{\text{local}}(e \mid \text{source}) = \frac{\exp\left(\frac{\text{logit}(e) - \max_k \text{logit}(k)}{T}\right)}{\sum_{j \in \text{Outgoing}(\text{source})} \exp\left(\frac{\text{logit}(j) - \max_k \text{logit}(k)}{T}\right)}$$
   $$\sum_{e \in \text{Outgoing}(\text{source})} w_{\text{local}}(e \mid \text{source}) = 1.0 \quad (\text{Unit Mass Conservation Invariant})$$

---

## 2. Authentic Conceptual Preference Emergence ("I like Josh")

### 2.1 The Zero-Prompt Leakage Mechanism
A critical architectural property of Habitus-AI is the **Strict Zero-Prompt Leakage Invariant**:
- The prompt text `"I like Josh"` is **never** injected into the system prompt.
- No user dialogue history or RAG text memory strings are passed to the language model.
- Model generation is conditioned **exclusively** on a continuous 1024D vector packet `.packet` compiled directly from the graph's geometric and topological state.

```
+-------------------------------------------------------------------------+
|                    INBOUND STIMULUS: "Hello, Josh here"                 |
+-------------------------------------------------------------------------+
                                    │
                                    ▼
[Graph Ingestion & Dijkstra Traversal] (Travel time minimization)
   SELF ──> IN:HEAR ──> PREF:HEAR:STABLE ──> child:josh ──> concept:josh (or native:gratitude/trust)
                                    │
                                    ▼
[Layer 3 Intrinsic Structural Overlay Synthesis: compute_structural_overlay()]
   - Parent hash projections + Child hash projections
   - Relation coactivation density accumulation
   - Invocation & softmax weight scaling: mult = ln(1 + inv) * softmax_weight
                                    │
                                    ▼
[Continuous 1024D Soft-Input Packet Compilation: synthesize_cognitive_packet()]
   Row 0: Concept Centroid Vector (1024D)
   Row 1: Layer 3 Structural Overlay Vector (1024D)
   Row 2: Layer 2 Preference Node Vector (1024D from PREF:HEAR:STABLE)
   Rows 3..7: Layer 4 Outward Lexical Fibers (1024D vectors for "trust", "warm", "safe")
                                    │
                                    ▼
[Native GGUF Soft Generator: graph_soft_generator]
   Continuous 1024D float embeddings directly fed to Qwen3 hidden states
                                    │
                                    ▼
[Natural Language Emergence: "I appreciate Josh. Our interaction is safe and reliable."]
```

### 2.2 Dijkstra Traversal Dynamics
During receptive nomination and outbound action selection (`graph.py:387-466`):
The edge travel time $\tau(e)$ in Dijkstra search is defined as:
$$\tau(e) = \frac{\Delta y_e}{10^{-6} + w_{\text{local}}(e \mid \text{source})} + \text{conflict\_penalty}(e)$$

1. **For Josh (Stabilizing Path)**:
   - High log strength + zero conflict penalty $\implies w_{\text{local}}(e) \approx 0.85-0.95$.
   - $\tau(e) \approx \frac{1.0}{0.90} + 0.0 \approx 1.11$.
   - Path travel time $\tau(\text{SELF} \to \text{concept:josh}) \approx 3.0-4.0$.
2. **For Adversary (Destabilizing Path)**:
   - Negative log strength + high conflict penalty ($\ge 3.0$) $\implies w_{\text{local}}(e) \approx 0.05-0.10$.
   - $\tau(e) \approx \frac{1.0}{0.05} + 3.0 = 20.0 + 3.0 = 23.0$.
   - Path travel time $\tau(\text{SELF} \to \text{concept:adversary}) \gg 40.0$.

Dijkstra pathfinding automatically selects the stabilizing Josh affinity path as the **dominant, minimum-resistance geodesic**.

### 2.3 Intrinsic Structural Overlay Vector Synthesis
In `graph.py:30-76` (`compute_structural_overlay`), the continuous 1024D vector is synthesized directly from graph topology:
```python
for idx, p_id in enumerate(s_map.parent_node_ids):
    h = abs(hash(p_id)) % dimension
    w = (1.0 / (idx + 1)) * math.log(1.0 + s_map.total_coactivations)
    overlay[h] += w

for rel in s_map.relations:
    h = abs(hash(f"{rel.source_node_id}->{rel.target_node_id}")) % dimension
    overlay[h] += rel.coactivation_density

mult = math.log(1.0 + concept.invocation_count) * concept.softmax_weight
overlay = [v * mult for v in overlay]
overlay = normalize_l2(overlay)
```
When Josh interacts repeatedly, `s_map.total_coactivations` and `concept.invocation_count` grow, crystallizing the 1024D representation with high directional persistence.

---

## 3. Closed-Loop Continuous Cognitive Loop & Pulse Re-Circulation

As specified in the user architectural guidance (2026-08-29T19:04:05Z), the closed-loop cognitive cycle explicitly models outbound-to-inbound continuous pulse re-circulation:

```
                  ┌────────────────────────────────────────────────────────┐
                  │              Closed-Loop Cognitive Cycle               │
                  └────────────────────────────────────────────────────────┘
                                               │
   [1. Inbound Ingress (X-Tree)]               │
   Stimulus text ──> IN:HEAR ──> PREF:HEAR:STABLE ──> StructuralMiniMaps
   Updates Layer 4 global softmax edge weights across membrane
                                               │
                                               ▼
   [2. Outbound Cipher Traversal (Y-Tree)]
   Outbound cipher traverses from SELF through OUT:SPEAK to admitted crown concept
   Governed by habit-reinforced edge weights
                                               │
                                               ▼
   [3. Continuous Responsive Thought Loop]
   Outbound activation trace & generated response re-circulate into next inbound pulse:
   - Registers response_record (RecordType.OUTBOUND_MESSAGE) in SQLite
   - Injects internal feedback event (EventKind.OBSERVATION / source_id="graph-native-model")
   - Re-evaluates experience state: updates delta_S feedback across memory substrate
   - Sustains ongoing cognitive circle across successive conversation turns
```

---

## 4. Quantifiable Mathematical Metrics for Affinity Crystallization

To empirically verify Requirement R2 in `tests/test_user_affinity_gestation.py`, we define seven quantifiable mathematical metrics:

### Metric 1: Softmax Preference Partitioning Ratio ($R_{\text{pref}}$)
Measures the relative probability mass allocated to stabilizing vs destabilizing preference nodes at Layer 2:
$$R_{\text{pref}}(\text{source}) = \frac{w_{\text{local}}(\text{IN:HEAR} \to \text{PREF:HEAR:STABLE})}{w_{\text{local}}(\text{IN:HEAR} \to \text{PREF:HEAR:UNSTABLE})}$$
- **Initial state (unpolarized)**: $R_{\text{pref}} \approx 1.0 \pm 0.15$.
- **Crystallized Josh affinity**: $R_{\text{pref}}(\text{Josh}) \ge 2.50$ (typically $> 5.0$).
- **Adversarial suppression**: $R_{\text{pref}}(\text{Adv}) \le 0.40$.

### Metric 2: Dijkstra Path Travel Time Divergence & Acceleration Factor ($\Delta \tau_{\text{path}}, \mathcal{A}_{\text{Dijkstra}}$)
$$\tau_{\text{stable}} = \text{DijkstraTravelTime}(\text{SELF} \to \text{concept}_{\text{Josh}})$$
$$\tau_{\text{unstable}} = \text{DijkstraTravelTime}(\text{SELF} \to \text{concept}_{\text{Adv}})$$
$$\Delta \tau_{\text{path}} = \tau_{\text{unstable}} - \tau_{\text{stable}}$$
$$\mathcal{A}_{\text{Dijkstra}} = \frac{\tau_{\text{unstable}}}{\tau_{\text{stable}}}$$
- **Acceptance Criterion**: $\Delta \tau_{\text{path}} > 5.0$ and $\mathcal{A}_{\text{Dijkstra}} \ge 2.0$.

### Metric 3: User Preference Polarization Score ($\mathcal{P}_{\text{user}}$) & Inter-User Polarization Contrast ($\Delta \mathcal{P}$)
$$\mathcal{P}_{\text{user}} = \bar{\mu}_{\text{pref}}(\text{user}) \cdot \bar{\omega}_{\text{pref}}(\text{user}) \in [-1.0, 1.0]$$
$$\Delta \mathcal{P} = \mathcal{P}_{\text{Josh}} - \mathcal{P}_{\text{Adv}} \in [0.0, 2.0]$$
- **Acceptance Criterion**: $\mathcal{P}_{\text{Josh}} \ge +0.65$, $\mathcal{P}_{\text{Adv}} \le -0.65$, $\Delta \mathcal{P} \ge 1.30$.

### Metric 4: Structural Mini-Map Co-Activation Density ($\mathcal{D}_{\text{coact}}$)
Measures the structural mass and connectivity of the emergent Layer 3 `StructuralMiniMap`:
$$\mathcal{D}_{\text{coact}}(M) = \frac{\text{total\_coactivations}(M)}{|\text{relations}(M)| + 1} \cdot \sum_{r \in \text{relations}(M)} \text{density}(r)$$
- **Acceptance Criterion**: $\mathcal{D}_{\text{coact}}(M_{\text{Josh}}) \ge 4.0$, verifying authentic multi-turn associative consolidation.

### Metric 5: Structural Vector Cosine Distinctiveness ($\mathcal{S}_{\text{dist}}$)
Measures the directional separation in 1024D native space between the structural overlay vectors of the stabilizing concept vs adversarial concept:
$$\vec{v}_{\text{Josh}} = \text{compute\_structural\_overlay}(\text{concept}_{\text{Josh}})$$
$$\vec{v}_{\text{Adv}} = \text{compute\_structural\_overlay}(\text{concept}_{\text{Adv}})$$
$$\mathcal{S}_{\text{dist}}(\vec{v}_{\text{Josh}}, \vec{v}_{\text{Adv}}) = 1.0 - \cos(\vec{v}_{\text{Josh}}, \vec{v}_{\text{Adv}})$$
- **Acceptance Criterion**: $\mathcal{S}_{\text{dist}} \ge 0.40$, demonstrating orthogonal, non-interfering conceptual representations.

### Metric 6: Topological Weight Conservation Invariant ($\mathcal{I}_{\text{mass}}$)
Verifies that total probability mass across the membrane is strictly conserved:
$$\mathcal{I}_{\text{mass}} = \left| \sum_{e \in \text{Edges}} w_{\text{global}}(e) - 1.0 \right| < 10^{-4}$$

### Metric 7: Closed-Loop Pulse Re-Circulation Stability Index ($\mathcal{C}_{\text{loop}}$)
Measures the equilibrium retention across multi-turn re-circulation:
$$\mathcal{C}_{\text{loop}} = 1.0 - \frac{1}{N-1} \sum_{t=2}^N |\Delta S_t - \Delta S_{t-1}|$$
- **Acceptance Criterion**: $\mathcal{C}_{\text{loop}} \ge 0.70$ during stable affinity phases.

---

## 5. Test Suite Implementation Blueprint for `tests/test_user_affinity_gestation.py`

Based on this investigation, the implementer agent should construct `tests/test_user_affinity_gestation.py` containing five comprehensive test classes:

| Test Class | Focus / Requirement | Key Assertions |
|---|---|---|
| `TestDifferentialAffinityGestation` | Multi-turn exposure to Josh ($\Delta S = +0.85$) vs Adversary ($\Delta S = -0.80$) | $R_{\text{pref}}(\text{Josh}) \ge 2.5$, $R_{\text{pref}}(\text{Adv}) \le 0.4$, $\Delta \mathcal{P} \ge 1.3$ |
| `TestLayer3StructuralMiniMapCrystallization` | Growth & serialization of `StructuralMiniMap` under `PREF:HEAR:STABLE` | Emergence of `child:auto:*`, `StructuralMiniMap` with coactivations $\ge 3$, SQLite schema integrity |
| `TestZeroPromptLeakageAffinityManifestation` | Plain language synthesis without prompt injection | 0 raw stimulus tokens in `.packet` payload, valid 1024D unit rows, correct schema `habitus.cognitive-eval-turn.v1` |
| `TestDijkstraGeodesicPolarization` | Dijkstra travel time divergence & path selection | $\tau_{\text{stable}} \le 4.0$, $\tau_{\text{unstable}} \ge 10.0$, $\mathcal{A}_{\text{Dijkstra}} \ge 2.0$ |
| `TestClosedLoopThoughtRecirculation` | Outbound response re-circulating into inbound pulse | Outbound response recorded as memory record, experience state updated, pulse counter strictly monotonically increases |

---

## 6. Conclusion & Recommendations

1. **Topological Purity**: The entire user-affinity phenomenon in Habitus-AI is rigorously explained by differential graph state dynamics without requiring token-level prompt steering.
2. **Readiness for Implementation**: All mathematical formulas, data structures, and test assertions are fully defined and ready for immediate implementation in `tests/test_user_affinity_gestation.py`.
3. **Execution Safety**: As an explorer, no production source code has been altered and no tests have been executed. All findings are documented in this artifact.
