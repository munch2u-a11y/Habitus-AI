# Milestone 1: Accelerated Gestation Pipeline Analysis

## Executive Summary
This document provides a comprehensive technical investigation of the **Milestone 1 - Gestation Pipeline** for Habitus-AI (`experiments/graph_native_live/accelerated_gestation.py` and `tests/test_accelerated_gestation.py`). The gestation pipeline builds, populates, and stabilizes the internal preference matrix, concept nodes, hierarchical category/domain assemblies, and lexical membranes directly grounded in Qwen3's native 1024D embedding space without using prompt serialization or artificial graph fixtures.

---

## 1. Growth of Concept Nodes, Categories, and Domain Assemblies

### 1.1 Developmental Curriculum Structure
The curriculum is generated deterministically by `curriculum()` in `accelerated_gestation.py`:
- **36 Topics** across 6 distinct categories:
  1. `social` (6 topics: *trust, kindness, friendship, honesty, gratitude, boundaries*)
  2. `affect` (6 topics: *calm, joy, fear, anger, curiosity, confidence*)
  3. `knowledge` (6 topics: *evidence, memory, learning, language, causality, comparison*)
  4. `digital` (6 topics: *files, search, tools, commands, code, tests*)
  5. `agency` (6 topics: *planning, speaking, observing, executing, verifying, adapting*)
  6. `world` (6 topics: *music, color, food, weather, space, motion*)
- **Topic Attributes**:
  - `word`: Grounding lexical surface form (e.g., `"trust"`).
  - `category`: Category grouping (e.g., `"social"`).
  - `description`: Grounded definition (e.g., `"reliable behavior makes cooperation feel safe"`).
  - `input_trunk`: Anatomical input sensory portal (`InputTrunk.HEAR`, `NOTICE`, or `SEE`).
  - `output_trunk`: Anatomical effector portal (`OutputTrunk.SPEAK`, `LOOK`, or `DO`).
  - `preference`: Continuous scalar evaluation value in $[-1.0, 1.0]$.
- **6 Syntactic Frames**:
  - Encapsulate topic and description into developmental episodes (e.g., `"I recognize {topic} when {description}."`, `"Repeated experience teaches me that {topic} means {description}."`).
- **Replay Cycles**:
  - Default `replay_cycles = 2` yields $2 \times 6 \text{ frames} \times 36 \text{ topics} = 432$ episodes.
  - Grouped into deterministic sessions per `(category, cycle, frame_index)`.

### 1.2 Mass Embedding & Overlap Calibration
- **Native Geometry**: Surface episodes are mass-tokenized and embedded into Qwen3-0.6B's native 1024D token embedding space (`qwen3-0.6b-gguf-token-mean-1024-v1`) via the C++ `lexeme_codec` binary.
- **Dynamic Overlap Calibration (`calibrate_overlap`)**:
  - Measures cosine similarity across intra-topic episodes (15th percentile floor: `intra_p15`) and inter-topic episodes sharing trunk/polarity (90th percentile ceiling: `inter_p90`).
  - Calculates optimal cluster growth threshold:
    $$\text{threshold} = \max\left(0.58, \min\left(0.92, \frac{\text{intra\_p15} + \text{inter\_p90}}{2.0}\right)\right)$$
  - Ensures tight cluster separation without splitting identical topics.

### 1.3 Basal Gestation & Episode Ingestion
1. **Basal Seeding (`habitus_ai.gestation.gestate`)**:
   - Seeds `SELF`, `identity:self`, `identity:human`, `taste:<schema>` (e.g., `taste:curious`).
   - Seeds 3 input trunks (`IN:HEAR`, `IN:SEE`, `IN:NOTICE`), 3 output trunks (`OUT:SPEAK`, `OUT:LOOK`, `OUT:DO`), and 9 lower preference nodes (`PREF:<trunk>:<band>` where band $\in \{\text{STABLE}, \text{NEUTRAL}, \text{UNSTABLE}\}$).
2. **Episode Ingestion (`add_episode`)**:
   - Each curriculum episode creates an immutable `MemoryRecord` in SQLite `records`.
   - `deposit_experience()`: Projections placed into basal vaults (`SELF`, `IN:<trunk>`, `PREF:<trunk>:<band>`).
   - `stage_growth()`: Finds or creates an `OverlapCluster` under the parent preference node.
   - When a cluster accumulates $\ge 3$ supporting experiences (`promotion_count=3`), it triggers emergent node promotion:
     - **Child Node** (`child:auto:<hash>`): Kind `child`, embedding vector all zeros (strictly non-semantic structural node), terms empty `()`, and dedicated lower vault.
     - **Crown Concept Node** (`concept:auto:<hash>`): Kind `crown`, embedding vector set to the centroid of member embeddings, label and terms derived from top content words.
     - **Input Edges**: Created from `parent_preference_node -> child` and `child -> crown_concept`.

### 1.4 Mirrored Output Paths & Cross-Modal Language Schooling
- **Mirrored Output Paths (`add_mirrored_output_paths`)**:
  - For each topic concept, links `OUT:<output_trunk> -> child -> crown_concept` on `GraphSide.OUTPUT`.
  - Reinforces edges with `stability_delta=0.45`, `verified=True`, `evidence_quality=0.8`.
- **Cross-Modal Language Schooling (`cross_modal_language_schooling`)**:
  - Nonverbal concepts (e.g., discovered via `SEE` or `NOTICE`) need to be reachable via spoken `HEAR` inputs.
  - Generates caregiver coactivation episodes (`"I use the spoken label {topic} while this familiar pattern is active."`).
  - Deposits a `HEAR` parent experience, bridges `hear_parent -> child` on `GraphSide.INPUT`, reinforces with `stability_delta=0.75`, and validates full Y-traversal from `HEAR` to the semantic node.

### 1.5 Temporal Coactivation Relations
- **`add_temporal_relations()`**:
  - Scans episodes ordered by sequence within each session.
  - Constructs bidirectional transition edges (`GraphSide.INPUT` and `GraphSide.OUTPUT`) between consecutively active concepts.
  - Reinforces edges with `stability_delta=0.25`, capturing sequential temporal associations across concepts.

### 1.6 Recursive Hierarchy Growth (Categories and Domains)
- **Assembly Growth Engine (`grow_assembly`)**:
  - Given a list of concept IDs, calculates their normalized centroid embedding in 1024D.
  - Executes 3 coactivation thought episodes (`assembly:record:<level>:<name>:<repetition>`).
  - Stages growth under `members[0]` with a strict `overlap_threshold=0.96`.
  - Connects all member concepts to the new child node on both INPUT and OUTPUT sides, and connects child to assembly crown on OUTPUT side.
- **Level 5 Category Assemblies**:
  - 6 assemblies: `category:social`, `category:affect`, `category:knowledge`, `category:digital`, `category:agency`, `category:world`.
- **Level 7 Domain Assemblies**:
  - 2 overarching domain assemblies:
    - `domain:relational` (joins `social`, `affect`, `knowledge`; effector `SPEAK`).
    - `domain:operational` (joins `digital`, `agency`, `world`; effector `LOOK`).

### 1.7 Lexical Membrane Attachment
- **`attach_lexical_membrane()`**:
  - Gathers top content words for each topic concept (e.g. 6 words per concept).
  - Surface forms (e.g. `" trust"`) are tokenized and embedded into 1024D using `mass_embed`.
  - **Geometry Lexemes (`reverse_nursery.ensure_geometry_lexeme`)**:
    - Creates lexeme nodes with kind `lexeme`, `terms = ()`, and pure 1024D embedding geometry. No token IDs or text strings are stored in node metadata.
  - **Bidirectional Lexical Fibers**:
    - Creates `crown_concept -> lexeme_node` edges on both `GraphSide.INPUT` and `GraphSide.OUTPUT`.
    - Repeatedly reinforces primary topic word fibers ($4\times$) and secondary word fibers.
  - **Directed Lexical Transition Edges**:
    - Adds transition edges `lexeme_A -> lexeme_B` on both graph sides following exact word order in supporting episode texts.

---

## 2. SQLite Database Structure and JSON Receipts

### 2.1 SQLite Schema (`habitus_ai.store.MindStore`)

The SQLite database uses WAL mode and foreign key constraints:

| Table Name | Purpose | Primary Key / Constraints | Key Columns |
|------------|---------|---------------------------|-------------|
| `metadata` | Key-value system metadata | `key TEXT PRIMARY KEY` | `key`, `value` (`embedding_space_id`, `embedding_dimension`, `pulse_counter`, `gestation_profile`, `accelerated_gestation_manifest`) |
| `records` | Canonical immutable memory records | `record_id TEXT PRIMARY KEY` (Triggers abort UPDATE/DELETE) | `record_id`, `event_id`, `record_type`, `source_id`, `timestamp`, `text`, `embedding_json`, `provenance_json`, `metadata_json`, `supersedes_id` |
| `record_links` | Directed relations between records | `(source_record_id, relation, target_record_id)` | `source_record_id`, `relation`, `target_record_id`, `evidence_json` |
| `concepts` | All graph concept nodes | `concept_id TEXT PRIMARY KEY` | `concept_id`, `label`, `kind` (`self`, `input_trunk`, `output_trunk`, `lower_preference`, `child`, `crown`, `lexeme`), `embedding_json`, `terms_json`, `vault_id`, `created_pulse`, `last_active_pulse` |
| `edges` | Dual-sided directional graph edges | `edge_id TEXT PRIMARY KEY`, `UNIQUE(side, source_id, target_id)` | `edge_id`, `side` (`input`, `output`), `source_id`, `target_id`, `delta_y`, `log_strength`, `conflict_penalty`, `last_active_time`, `created_pulse`, `archived` |
| `edge_evidence` | Supporting records for edges | `(edge_id, record_id, relation)` | `edge_id`, `record_id`, `relation` |
| `vault_membership`| Vault index mapping records to concepts | `(vault_id, record_id, concept_id)` | `vault_id`, `record_id`, `concept_id` |
| `traces` | Recorded graph traversal paths | `trace_id TEXT PRIMARY KEY` | `trace_id`, `pulse_id`, `side`, `payload_json`, `created_at` |
| `outcomes` | Reinforcement/feedback outcomes | `outcome_id TEXT PRIMARY KEY` | `outcome_id`, `pulse_id`, `payload_json`, `created_at` |
| `experience_state`| Cumulative preference tracking | `experience_id TEXT PRIMARY KEY` | `experience_id`, `preference_mean`, `preference_weight`, `observation_count`, `last_pulse` |
| `experience_projections` | Node activation projections | `(record_id, node_id, side)` | `experience_id`, `record_id`, `node_id`, `layer`, `side`, `activation`, `preference`, `confidence`, `pulse`, `metadata_json` |
| `overlap_clusters` | Clustered experiences for growth | `cluster_id TEXT PRIMARY KEY` | `cluster_id`, `parent_node_id`, `centroid_json`, `record_ids_json`, `experience_ids_json`, `preference_mean`, `confidence_mean`, `first_pulse`, `last_pulse`, `child_node_id`, `semantic_node_id` |

### 2.2 JSON Receipt Structure (`gestation-<timestamp>.json`)

The JSON receipt (and the metadata manifest in `accelerated_gestation_manifest`) contains:
- `schema`: `"habitus.accelerated-gestation.v1"`
- `human_name`, `agent_name`, `taste_schema`, `model`, `embedding_space`
- `curriculum_episodes`: e.g. 432 (or 216 for 1 cycle)
- `curriculum_topics`: 36
- `replay_cycles`: integer (e.g. 2 or 1)
- `overlap_calibration`: `{intra_median, intra_p15, inter_median, inter_p90, selected_threshold}`
- `topic_concepts`: count of successfully clustered topic concepts ($\ge 30$)
- `language_schooled_concepts`: count of concepts schooled via `HEAR`
- `recursive_assemblies`: map of 6 categories and 2 domains to concept IDs
- `assembly_depths`: `{category:..., domain:...}` with `{input_reachable, input_depth, output_reachable, output_depth}`
- `temporal_edges`: count of temporal coactivation edges
- `membrane`: `{surface_forms, lexeme_nodes, fibers, lexical_transition_edges, selected_words}`
- `evaluation`:
  - `receptive`: `{coverage_count, coverage_accuracy_at_1, coverage_accuracy_at_3, semantic_count, semantic_accuracy_at_1, semantic_accuracy_at_3, semantic_y_reachable, semantic_probe_text_leakage, coverage_probes, semantic_probes}`
  - `productive`: `{count, accuracy_at_1, accuracy_at_5, shuffled_control_at_1, projection_tensor, probes}`
  - `average_cluster_purity`: mean cluster topic purity ($\ge 0.90$)
  - `membrane_surface_forms`: count of vocabulary items
- `graph`: `{records, concepts, concept_kinds, edges, edges_by_side, overlap_clusters, pulse, global_edge_mass, invariants}`
- `restart_check`: `{counts_match, global_edge_mass, invariants}`
- `hatch_ready`: Boolean flag indicating whether all gating checks passed
- `elapsed_seconds`, `database`, `database_bytes`

---

## 3. Exact Assertions and Requirements in `tests/test_accelerated_gestation.py`

### 3.1 Skip Condition
```python
@pytest.mark.skipif(
    not GESTATION.nursery.MODEL.is_file() or not GESTATION.nursery.CODEC.is_file(),
    reason="local Qwen3 accelerated-gestation assets are unavailable",
)
```
Requires `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf` and `experiments/graph_native_live/native/lexeme_codec`.

### 3.2 Compilation Parameterization in Test
- `database = tmp_path / "hatch.sqlite"`
- `human_name = "Josh"`
- `agent_name = "Testling"`
- `taste_schema = "curious"`
- `replay_cycles = 1` (Fast execution mode: $1 \times 6 \times 36 = 216$ episodes)

### 3.3 Manifest Assertions Table
| Assertion Target | Required Threshold / Value | Rationale |
|------------------|---------------------------|-----------|
| `manifest["hatch_ready"]` | `is True` | Master boolean gating condition |
| `manifest["graph"]["records"]` | `elem >= 200` | Ensures curriculum episodes deposited |
| `manifest["graph"]["concepts"]` | `elem >= 200` | Ensures baseline + crowns + lexemes + children |
| `manifest["graph"]["edges"]` | `elem >= 500` | Ensures trunks, children, assemblies, fibers created |
| `manifest["graph"]["global_edge_mass"]` | `== pytest.approx(1.0)` | Conservation of total edge weight probability |
| `manifest["graph"]["invariants"]` | `== []` | Validates graph structural rules without violations |
| `manifest["topic_concepts"]` | `elem >= 30` | Minimum 30 of 36 topics clustered |
| `manifest["evaluation"]["average_cluster_purity"]` | `elem >= 0.90` | Clusters must not heavily cross-contaminate |
| `receptive.semantic_accuracy_at_1` | `elem >= 0.75` | Paraphrased unseen probes top-1 concept match |
| `receptive.semantic_y_reachable` | `== 1.0` | 100% of semantic probes traverse Y-axis from HEAR |
| `receptive.semantic_probe_text_leakage`| `== []` | Zero lexical verbatim overlap with training episodes |
| `productive.accuracy_at_1` | `elem >= 0.75` | Graph output state decoded via GGUF vocab matches topic |
| `productive.shuffled_control_at_1` | `elem <= 0.20` | Shuffled label control fails as expected |
| `max(manifest["assembly_depths"].input_depth)` | `elem >= 8` | Deep recursive assemblies reach depth $\ge 8$ |
| `manifest["restart_check"]["counts_match"]` | `is True` | SQLite persistence integrity across DB close/re-open |

### 3.4 Substrate Integrity Assertions (Direct SQLite Checks)
- `all(node.terms == () for node in mind.store.list_concepts(kind="lexeme"))`:
  - Lexeme nodes must NOT contain raw string tokens in `terms`. They must be pure geometry.
- `all(not any(node.embedding) for node in mind.store.list_concepts(kind="child"))`:
  - Intermediate child nodes must have all-zero embeddings. They are purely structural topological routing nodes.
- `stored["hatch_ready"] is True`:
  - The metadata manifest stored in SQLite matches the in-memory manifest.

### 3.5 Live Hatched Mind Probe Assertions (`HATCH_PROBE.probe`)
- Evaluated on probes: `("trust", ...)`, `("fear", ...)`, `("music", ...)`:
  - `live["hear_reachability"] == 1.0`: All queries traverse through the `HEAR` trunk to a concept.
  - `live["strict_output_accuracy"] == 1.0`: Concept output fibers project to the exact expected topic piece.

### 3.6 Transformer Hatch Generation Assertions (`TRANSFORMER.run_probe_matrix`)
- Evaluated on probe `("trust", "People keep promises, making cooperation feel safe.")`:
  - `generated["expected_word_rate"] == 1.0`: Model output contains the target word (`"trust"`).
  - `generated["target_beats_unrelated_rate"] == 1.0`: Target concept response similarity > unrelated concept response similarity.
  - `generated["target_beats_random_rate"] == 1.0`: Target concept response similarity > random noise response similarity.
  - `generated["prompt_text_crossed_native_boundary"] is False`: Strict security/architecture invariant.
  - `generated["retrieved_memory_text_crossed_native_boundary"] is False`: Strict security/architecture invariant.
  - `generated["semantic_codebook_used"] is False`: No static discrete lookup table.
  - `target_trace["missing_transition_count"] == 0`: Directed lexeme transition graph is complete.

---

## 4. Prerequisites, Commands, and Potential Failure Modes

### 4.1 Prerequisites
1. **GGUF Model File**: `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf`
   - Must be present and readable.
   - Must have native token embedding dimension of 1024.
2. **Native C++ Helper Binaries**:
   - `experiments/graph_native_live/native/lexeme_codec`
   - `experiments/graph_native_live/native/graph_soft_generator`
   - Built against `llama.cpp` using `/usr/local/lib/ollama` shared libraries (`libllama.so`).
3. **Environment Variables**:
   - `OLLAMA_LIB_DIR=/usr/local/lib/ollama`
   - `LD_LIBRARY_PATH=/usr/local/lib/ollama`
   - `PYTHONPATH=src:experiments/graph_native_live`

### 4.2 Execution Commands
- **Compile Native C++ Binaries**:
  ```bash
  make -C experiments/graph_native_live build
  ```
- **Execute Standalone Accelerated Gestation (Full 2-cycle run)**:
  ```bash
  make -C experiments/graph_native_live gestate-fast
  # Or directly:
  PYTHONPATH=src python3 experiments/graph_native_live/accelerated_gestation.py \
    --model /home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf \
    --replay-cycles 2
  ```
- **Probe a Hatched Mind**:
  ```bash
  PYTHONPATH=src python3 experiments/graph_native_live/probe_hatched_mind.py \
    --database experiments/graph_native_live/accelerated_gestation_runs/<db_file>.sqlite \
    --model /home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf
  ```
- **Run Transformer Soft-Input Generation**:
  ```bash
  PYTHONPATH=src python3 experiments/graph_native_live/transformer_hatch.py \
    --database experiments/graph_native_live/accelerated_gestation_runs/<db_file>.sqlite \
    --model /home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf
  ```
- **Run the Milestone 1 Test Suite**:
  ```bash
  PYTHONPATH=src pytest tests/test_accelerated_gestation.py
  ```

### 4.3 Potential Failure Modes and Mitigations

| Failure Mode | Root Cause | Impact | Mitigation / Diagnostics |
|--------------|------------|--------|--------------------------|
| `FileExistsError` | Database path already exists when calling `compile_mind()` | Gestation immediately aborts | Ensure fresh destination path (e.g. `tmp_path` in pytest or timestamped name in CLI) |
| Missing GGUF / Native Helper | `/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf` or `lexeme_codec` missing | Test skips or script exits | Verify file presence; run `make -C experiments/graph_native_live build` |
| Dynamic Library Loading Error | `libllama.so` cannot be located by dynamic linker | Subprocess returns non-zero error | Ensure `LD_LIBRARY_PATH` and `OLLAMA_LIB_DIR` are set to `/usr/local/lib/ollama` |
| Invariant Violation | Global edge weight sum $\ne 1.0 \pm 10^{-6}$ or missing vault | `manifest["hatch_ready"]` is `False` | Check `graph_statistics(mind)["invariants"]` and verify edge reinforcement normalization |
| Y-Traversal Disconnection | Nonverbal concept unreachable from `HEAR` trunk | `cross_modal_language_schooling` throws `RuntimeError` | Ensure `cross_modal_language_schooling()` creates `HEAR` parent edges for all active concepts |
| Semantic Text Leakage | A probe text in `SEMANTIC_PROBES` matches a training episode string | Test fails `semantic_probe_text_leakage == []` | Maintain strict paraphrasing in `SEMANTIC_PROBES` without copying frame templates |
| Lexeme Transition Gaps | `missing_transition_count > 0` in transformer hatch | Test fails transformer assertions | Ensure `attach_lexical_membrane()` extracts transitions from all supporting episode token sequences |
| Process Concurrency Violations | Multiple Python test processes running concurrently | Violates test runner constraint | Run `pkill -9 -f "python3"` before running tests; maintain single test runner |

---

## 5. Architectural Alignment with Project Goals

Milestone 1 successfully proves the core Habitus-AI thesis:
1. **No Language Strings on Internal Concepts**: Internal child nodes have zero embedding and empty terms; crown concepts derive embeddings from continuous centroids; lexemes are pure 1024D vectors matching Qwen's token geometry.
2. **True Bicone Topology**: Inputs enter via $+Y$ Perceptual trunks (`HEAR`, `SEE`, `NOTICE`), pass through emergent intermediate child nodes to crown concepts, and descend through $-Y$ Effector trunks (`SPEAK`, `LOOK`, `DO`) to lexical membranes.
3. **Conserved Probability Mass**: Dynamic edge weights sum to 1.0 globally and locally across all graph sides, satisfying strict probabilistic invariants.
4. **Soft-Input Continuity**: Output generation maps directly from graph activation states to continuous 1024D vector slots without prompt injection.
