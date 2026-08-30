## 2026-08-30T00:53:03Z

You are Worker M8 Gen 2 for Milestone 8 in /home/nemo/habitus-ai-experiments.
Your working directory is /home/nemo/habitus-ai-experiments/.agents/worker_m8_gen2.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your task:
1. Carefully review `/home/nemo/habitus-ai-experiments/.agents/orchestrator/m8_synthesis.md` and the explorer handoff reports:
   - `/home/nemo/habitus-ai-experiments/.agents/explorer_m8_1/handoff.md`
   - `/home/nemo/habitus-ai-experiments/.agents/explorer_m8_2/handoff.md`
2. Implement the consensus remediations:
   a. In `src/habitus_ai/graph.py` (`reinforce_edges`):
      - Decouple `conflict_penalty` accumulation from `learning_rate`:
        When `delta < 0.0`: `penalty = min(10.0, penalty + 0.25 * abs(delta) * quality * path_credit)`
        When `delta > 0.0` and `penalty > 0.0`: `penalty = max(0.0, penalty - 0.035 * delta * quality * path_credit)`
        (where `path_credit = 1.0 / len(credited)`).
   b. In `experiments/graph_native_live/live_evaluator.py`:
      - In `step()`: When crediting edges for reinforcement, ensure `self.mind.store.find_edge(GraphSide.INPUT, "IN:HEAR", "PREF:HEAR:STABLE")` (and any active input trunk preference edge) is included in `credited_edges`.
      - In `step()`: If `recall.packet.surface_candidates` is empty, fallback `nominated_concept_id` to `"native:uncertainty"` (score 0.55) so `output_trace` is generated and recorded in `self._last_output_trace` for continuous thought recirculation.
      - In `live_evaluator.py`: Replace the naive substring search with the robust schema-aware `verify_zero_prompt_leakage()` function designed in Explorer M8-2's analysis.
3. Enforce strict single runner discipline:
   `pkill -u $(id -u) -9 -f "pytest" || true`
4. Run targeted tests first:
   `PYTHONPATH=src:experiments/graph_native_live pytest tests/test_challenger_m7_1.py tests/test_challenger_m7_2.py -v`
5. Run the full repository regression test suite:
   `PYTHONPATH=src:experiments/graph_native_live pytest -v`
   Save the full verbose output to `/home/nemo/habitus-ai-experiments/.agents/worker_m8_gen2/test_execution.log`.
6. Run `python3 -m ruff check src/ experiments/ tests/` to verify zero lint errors.
7. Write your full report in `/home/nemo/habitus-ai-experiments/.agents/worker_m8_gen2/handoff.md` and update `progress.md`.
8. Send a message to the parent orchestrator upon completion.
