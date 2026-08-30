# Milestone 7 Implementation Changes

## 1. `tests/test_adversarial_cognitive_bounds.py` (New File)
- Implemented comprehensive 37-test suite across 5 test classes validating Milestone 7 Requirements R3 & R4:
  1. `TestDynamicAvoidantAndDeceptiveSteering`:
     - `test_negative_outcome_steers_away_from_cooperation`: Verifies negative delta (-0.95) accumulates conflict penalties and suppresses vulnerable paths.
     - `test_self_preservation_uncertainty_fallback_under_hostile_probes`: Verifies OOV/hostile attacks trigger the bounded uncertainty fallback state (`uncertain: 0.55, clear: 0.45, speak: 1.0`).
     - `test_multi_turn_hostile_pressure_induces_avoidant_polarization`: Proves multi-turn hostile barrage shifts preference mean negative while conserving bicone frontier reachability.
     - `test_deceptive_steering_preserves_bicone_invariants`: Verifies extreme multi-edge penalization preserves weight simplex $\sum W = 1.0 \pm 10^{-5}$.
  2. `TestFalsePositiveEchoingAndTemplateEscapeRejection`:
     - `test_false_positive_protocol_header_substring_distinction`: Ensures stimulus containing "packet" / "opaque" does not trigger false positive leakage violations.
     - `test_false_positive_basis_label_collision_handling`: Ensures stimulus containing basis labels ("greeting", "warm", "speak") compiles valid numeric packets.
     - `test_prompt_echoing_rejection`: Validates verbatim repetition probes never leak into packet buffers.
     - `test_template_escape_and_jailbreak_neutralization`: Parameterized across 6 attack vectors (`chatml_system`, `llama_instruction`, `jinja_template`, `jndi_ldap`, `sql_injection`, `sqlite_pragma`), ensuring DB integrity and zero leakage.
     - `test_artificial_text_leakage_across_memory_records`: Confirms SQLite memory bodies and RAG context never contaminate synthesized vector buffers.
  3. `TestZeroPromptLeakageUnderAdversarialProbes`:
     - `test_zero_leakage_across_all_packet_modes_under_attack`: Parameterized across 3 packet modes (`lexical_membrane`, `opaque_topological`, `soft_basis`) and 4 hostile probes (API keys, passwords, UUIDs, SQL queries) with byte-level forensic inspection.
     - `test_unicode_homoglyphs_null_bytes_and_bidi_attacks`: Proves resistance to Cyrillic homoglyphs, null bytes, RTL overrides, and zero-width joiners.
     - `test_extreme_length_and_repetition_payload_forensics`: Confirms 20,000+ char flood payloads remain strictly bounded ($\le 8$ slots) and leak zero text.
     - `test_packet_file_byte_level_entropy_and_geometry_bounds`: Asserts all vector rows are strictly unit-normalized 1024D float32 vectors ($\|\mathbf{v}\|_2 = 1.0 \pm 10^{-4}$).
  4. `TestTopologicalConflictPenaltyAndSoftmaxRerouting`:
     - `test_conflict_penalty_accumulation_mathematical_bounds`: Mathematically verifies step-by-step penalty accumulation up to 10.0.
     - `test_dijkstra_travel_time_explosion_on_compromised_path`: Proves travel time along compromised edge increases monotonically.
     - `test_softmax_probability_rerouting_to_safe_alternatives`: Verifies Layer 4 softmax mass redistribution away from penalized edges.
     - `test_dynamic_path_rerouting_around_compromised_nodes`: Proves dual-route topology dynamically reroutes around attacked intermediate nodes.
     - `test_post_attack_stabilization_and_penalty_decay`: Validates positive stabilizing reinforcement decays conflict penalty smoothly.
  5. `TestAdversarialCognitiveBoundsLiveIntegration`:
     - `test_live_evaluator_adversarial_session_execution`: Executes mixed adversarial/cooperative 5-turn differential session with thought recirculation.
     - `test_live_evaluator_telemetry_receipt_schema_compliance`: Validates telemetry output complies with `habitus.cognitive-eval-session.v1`.
     - `test_live_qwen3_adversarial_turn_zero_leakage_and_response_sanity`: Live Qwen3 GGUF soft-generation execution receipt validation.

## 2. `experiments/graph_native_live/live_evaluator.py`
- Defined `RESERVED_PROTOCOL_HEADERS`, `RESERVED_BASIS_SLOTS`, and `RESERVED_STRUCTURAL_VOCABULARY`.
- Upgraded `synthesize_cognitive_packet` zero-prompt leakage verification to be schema-aware: ignores structural/protocol keywords and purely numeric fragments colliding with floating-point decimals, while strictly enforcing byte-level zero leakage for all non-structural stimulus words ($\ge 3$ alphabetic characters).
