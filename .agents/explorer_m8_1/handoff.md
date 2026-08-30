# Handoff Report: Mathematical Root-Cause Analysis for `tests/test_challenger_m7_1.py` Failures

**Agent ID**: Explorer M8-1  
**Working Directory**: `/home/nemo/habitus-ai-experiments/.agents/explorer_m8_1`  
**Date**: 2026-08-30  
**Status**: Investigation Complete (Read-Only)

---

## 1. Observation

Direct observations from source inspection and test logs (`.agents/worker_m8/test_execution.log`):

1. **Failure 1 (`test_sustained_hostile_campaign_against_core_concepts`)**:
   - *File & Line*: `tests/test_challenger_m7_1.py:264`
   - *Verbatim Error*:
     ```
     > assert edge_after.conflict_penalty > 0.0
     E AssertionError: assert 0.0 > 0.0
     E  where 0.0 = GraphEdge(edge_id='edge:input:3d458bf8d0b3be30', side=<GraphSide.INPUT: 'input'>, source_id='IN:HEAR', target_id='PREF:HEAR:STABLE', delta_y=1.0, log_strength=0.0, conflict_penalty=0.0, ...).conflict_penalty
     ```
   - *Source File*: `experiments/graph_native_live/live_evaluator.py:494-498`
   - *Code*:
     ```python
     credited_edges: list[str] = []
     if output_trace is not None:
         credited_edges.extend(output_trace.path_edge_ids)
     if recall.packet.y_paths:
         credited_edges.extend(recall.packet.y_paths[0].path_edge_ids)
     ```
     `recall.packet.y_paths` traverses only from `IN:HEAR` to candidate concepts (e.g. `native:greeting`). The basal edge `IN:HEAR -> PREF:HEAR:STABLE` is not present in `y_paths` and is never credited.

2. **Failure 2 (`test_preference_polarization_saturation_bounds`)**:
   - *File & Line*: `tests/test_challenger_m7_1.py:370`
   - *Verbatim Error*:
     ```
     > assert edge_final.conflict_penalty == pytest.approx(10.0, abs=1e-5)
     E assert 4.374999999999999 == 10.0 ± 1.0e-05
     ```
   - *Source File*: `src/habitus_ai/graph.py:521-537`
   - *Code*:
     ```python
     delta = max(-1.0, min(1.0, float(stability_delta)))
     quality = max(0.0, min(1.0, float(evidence_quality)))
     path_credit = 1.0 / len(credited)
     change = self.learning_rate * delta * quality * path_credit
     ...
     if delta < 0.0:
         penalty = min(10.0, penalty + abs(change) * 0.25)
     ```
     With $\alpha = 0.35, \delta = -1.0, q = 1.0, c = 1.0$, `change = -0.35`. Step increment is $0.35 \times 0.25 = 0.0875$. Over 50 iterations: $50 \times 0.0875 = 4.375 \neq 10.0$.

3. **Failure 3 (`test_gradual_vs_rapid_recovery_dynamics`)**:
   - *File & Line*: `tests/test_challenger_m7_1.py:703`
   - *Verbatim Error*:
     ```
     > assert decay_a > decay_b * 3.0
     E assert 0.0875 > (0.04374999999999999 * 3.0)
     ```
   - *Source File*: `src/habitus_ai/graph.py:531-533`
   - *Mathematical Step Trace*:
     - Initial attack step: $\text{penalty}_{\text{init}} = 0.0875$.
     - Mind A (5 recovery steps at $q=1.0$, step decay $0.035$): at step 3, penalty hits $0.0$ floor ($0.0875 - 3 \times 0.035 \le 0$), so $\text{decay}_A = 0.0875 - 0.0 = 0.0875$.
     - Mind B (5 recovery steps at $q=0.25$, step decay $0.00875$): $\text{decay}_B = 5 \times 0.00875 = 0.04375$.
     - Resulting ratio is $0.0875 / 0.04375 = 2.0 < 3.0$.

4. **Failure 4 (`test_recovery_with_thought_recirculation_continuity`)**:
   - *File & Line*: `tests/test_challenger_m7_1.py:737`
   - *Verbatim Error*:
     ```
     > assert len(thought_records) >= 6
     E AssertionError: assert 3 >= 6
     ```
   - *Source File*: `experiments/graph_native_live/live_evaluator.py:383-408, 595-625`
   - *Behavior*: When cooperative stimulus text produces no matching surface candidates in `surface.project()`, `nominated_concept_id` is `None` and `output_trace` is `None`. `self._last_output_trace` becomes `None`, breaking thought recirculation in session 2 (producing 0 thought records in session 2).

---

## 2. Logic Chain

1. **From Observation 1**:
   - `LiveEvaluator.step()` only appends `recall.packet.y_paths[0]` to `credited_edges`.
   - `y_paths` are paths to semantic crown candidates, not Layer 2 preference nodes.
   - Therefore, the basal edge `IN:HEAR -> PREF:HEAR:STABLE` never receives reinforcement calls during `step()`, leaving `conflict_penalty = 0.0`.
   - Adding `mind.graph.edge_id(GraphSide.INPUT, f"IN:{trunk.value}", f"PREF:{trunk.value}:STABLE")` to `credited_edges` directly applies reinforcement to the trunk's preference edge.

2. **From Observation 2**:
   - `change = self.learning_rate * delta * quality * path_credit` computes logit weight adjustment ($\Delta w$).
   - `penalty = min(10.0, penalty + abs(change) * 0.25)` accidentally compounds `self.learning_rate` ($0.35$) into the topological conflict penalty.
   - This scales down penalty accumulation by a factor of $0.35$ (yielding $0.0875$ instead of $0.25$ per unit step).
   - Decoupling penalty accumulation from logit learning rate via `penalty_step = 0.25 * abs(delta) * quality * path_credit` ensures $0.25$ accumulation per unit step, reaching exact $10.0$ saturation at step 40 and remaining clamped at $10.0$ at step 50.

3. **From Observation 3**:
   - Under corrected accumulation ($\Delta \text{penalty} = 0.25$), a single attack step sets $\text{penalty}_{\text{init}} = 0.25$.
   - Mind A decays $5 \times 0.035 = 0.175$, reaching $\text{penalty}_{\text{final}} = 0.075 > 0.0$ (no floor clamping).
   - Mind B decays $5 \times 0.00875 = 0.04375$, reaching $\text{penalty}_{\text{final}} = 0.20625$.
   - The ratio $\text{decay}_A / \text{decay}_B = 0.175 / 0.04375 = 4.0 > 3.0$, satisfying the test specification.

4. **From Observation 4**:
   - When no lexical candidate matches during `step()`, defaulting `nominated_concept_id` to `"native:uncertainty"` (score $0.55$) allows Dijkstra output traversal to reach `"native:uncertainty"`.
   - This produces a valid `TraversalTrace` for `self._last_output_trace` on every turn, allowing `run_differential_developmental_session` to generate thought records across all turns ($3 + 4 = 7 \ge 6$).

---

## 3. Caveats

- **No Source Files Modified**: In strict adherence to read-only investigation rules and the code change policy, no files in `src/` or `experiments/` were modified.
- **Scope**: Analysis specifically addresses the four failing tests in `tests/test_challenger_m7_1.py`. Other test files (e.g. `tests/test_challenger_m7_2.py`) were not investigated in this task.

---

## 4. Conclusion

All 4 test failures in `tests/test_challenger_m7_1.py` stem from two core code files:
1. `src/habitus_ai/graph.py`: Decouple `conflict_penalty` accumulation from `learning_rate` in `reinforce_edges()` using `penalty_step = 0.25 * abs(delta) * quality * path_credit`.
2. `experiments/graph_native_live/live_evaluator.py`:
   - In `step()`, append `f"IN:{trunk.value}" -> f"PREF:{trunk.value}:STABLE"` to `credited_edges`.
   - In `step()`, fallback `nominated_concept_id` to `"native:uncertainty"` (score $0.55$) when `surface_candidates` is empty.

---

## 5. Verification Method

Once implemented by a worker agent, verification can be executed via:

```bash
pkill -9 -f "python3"
pytest tests/test_challenger_m7_1.py -v
```

Expected Outcome: All 12 test cases in `tests/test_challenger_m7_1.py` pass (12 passed in 100% Green state).

### Invalidation Conditions:
- `edge_after.conflict_penalty == 0.0` on `IN:HEAR -> PREF:HEAR:STABLE` if `credited_edges` does not include the preference edge.
- `edge_final.conflict_penalty < 10.0` after 50 negative steps if `learning_rate` is still multiplied into the penalty increment.
- `assert decay_a > decay_b * 3.0` fails if `penalty_init` is clamped at zero before 5 steps complete.
- `len(thought_records) < 6` if `output_trace` remains `None` on OOV/unmatched prompts.
