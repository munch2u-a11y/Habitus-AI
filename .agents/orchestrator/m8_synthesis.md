# Milestone 8 Synthesis: Full Repository Regression & Verification Remediation

## Input Catalog
1. **Explorer M8-1** (`analysis.md` / `handoff.md`):
   - Root-cause analysis for `tests/test_challenger_m7_1.py`:
     1. `test_sustained_hostile_campaign_against_core_concepts`: `LiveEvaluator.step()` omitted the basal preference edge `IN:HEAR -> PREF:HEAR:STABLE` from `credited_edges`, leaving its conflict penalty at 0.0. Adding `mind.graph.edge_id(GraphSide.INPUT, f"IN:{trunk.value}", f"PREF:{trunk.value}:STABLE")` to `credited_edges` applies reinforcement directly.
     2. `test_preference_polarization_saturation_bounds`: `GraphRuntime.reinforce_edges()` in `src/habitus_ai/graph.py` compounded `self.learning_rate` ($0.35$) into the conflict penalty increment ($0.35 \times 0.25 = 0.0875$). Decoupling via `penalty_step = 0.25 * abs(delta) * quality * path_credit` ensures $0.25$ per unit step, reaching exact $10.0$ saturation at step 40 and remaining clamped at $10.0$.
     3. `test_gradual_vs_rapid_recovery_dynamics`: With initial penalty $0.25$, Mind A decays $5 \times 0.035 = 0.175$ without premature zero-clamping, while Mind B decays $5 \times 0.00875 = 0.04375$, giving a decay ratio of $4.0 > 3.0$.
     4. `test_recovery_with_thought_recirculation_continuity`: When lexical candidates are empty on novel prompts, defaulting `nominated_concept_id` to `"native:uncertainty"` (score $0.55$) generates a valid `TraversalTrace` for `self._last_output_trace`, ensuring continuous thought recirculation across session boundaries ($\ge 6$ thought records).

2. **Explorer M8-2** (`analysis.md` / `handoff.md`):
   - Root-cause analysis for `tests/test_challenger_m7_2.py`:
     1. `test_packet_header_injection_and_collision_resistance`: Unanchored substring check on `"1024 999"` matched static header dimension line `"1024 4"`.
     2. `test_rapid_randomized_fuzzing_stream_and_simplex_conservation`: 3-digit numeric substring `'275'` from Jinja template fuzzing matched inside ASCII float coordinate stream (`0.027581...`), where collision probability in 40k digit streams is ~100%.
   - Solution: Schema-aware zero-prompt leakage verification (`verify_zero_prompt_leakage`) in `live_evaluator.py`:
     - Validate packet grammar, finite float coordinates, and unit normalization.
     - Detect protocol header injection.
     - Extract candidate words with `len >= 4` and $\ge 3$ alphabetic characters, ignoring pure numeric strings and whitelisting schema tokens (`"habitus"`, `"opaque"`, `"soft"`, `"packet"`, `"v1"`, and basis slot names).

## Consensus Remediation Blueprint for Worker M8
1. **Target Deliverables**:
   - `src/habitus_ai/graph.py`: Decouple `conflict_penalty` accumulation and recovery decay in `reinforce_edges()`.
   - `experiments/graph_native_live/live_evaluator.py`:
     - Add `IN:HEAR -> PREF:HEAR:STABLE` edge to `credited_edges` in `step()`.
     - Default `nominated_concept_id` to `"native:uncertainty"` when `surface_candidates` is empty.
     - Replace naive substring check with schema-aware `verify_zero_prompt_leakage()`.
2. **Strict Single-Runner Discipline**:
   - Run `pkill -u $(id -u) -9 -f "pytest" || true` before running tests.
   - Run `PYTHONPATH=src:experiments/graph_native_live pytest -v` to verify 100% pass rate (401/401 tests pass, 0 failures, 0 regressions).
   - Run `ruff check` on modified files.
3. **Mandatory Integrity Warning**:
   - All implementations must be genuine logic, 100% authentic, zero bypasses.
