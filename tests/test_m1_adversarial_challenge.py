from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import random
import sys

import pytest

from habitus_ai import BaseAgenticMemoryRAG, GraphSide, InputTrunk, OutputTrunk
from habitus_ai.graph import (
    INPUT_NODE_IDS,
    OUTPUT_NODE_IDS,
    PREFERENCE_NODE_IDS,
    SELF_ID,
)
from habitus_ai.types import ConceptNode, GraphEdge, OverlapCluster, as_tuple


EXPERIMENT_DIR = Path(__file__).resolve().parents[1] / "experiments" / "graph_native_live"
for import_root in (Path(__file__).resolve().parents[1] / "src", EXPERIMENT_DIR):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

NURSERY_PATH = EXPERIMENT_DIR / "nursery.py"
NURSERY_SPEC = importlib.util.spec_from_file_location("nursery_module", NURSERY_PATH)
assert NURSERY_SPEC is not None and NURSERY_SPEC.loader is not None
NURSERY = importlib.util.module_from_spec(NURSERY_SPEC)
sys.modules[NURSERY_SPEC.name] = NURSERY
NURSERY_SPEC.loader.exec_module(NURSERY)

REVERSE_PATH = EXPERIMENT_DIR / "reverse_nursery.py"
REVERSE_SPEC = importlib.util.spec_from_file_location("reverse_nursery_module", REVERSE_PATH)
assert REVERSE_SPEC is not None and REVERSE_SPEC.loader is not None
REVERSE = importlib.util.module_from_spec(REVERSE_SPEC)
sys.modules[REVERSE_SPEC.name] = REVERSE
REVERSE_SPEC.loader.exec_module(REVERSE)

GESTATION_PATH = EXPERIMENT_DIR / "accelerated_gestation.py"
GESTATION_SPEC = importlib.util.spec_from_file_location("accelerated_gestation_module", GESTATION_PATH)
assert GESTATION_SPEC is not None and GESTATION_SPEC.loader is not None
GESTATION = importlib.util.module_from_spec(GESTATION_SPEC)
sys.modules[GESTATION_SPEC.name] = GESTATION
GESTATION_SPEC.loader.exec_module(GESTATION)


# ==============================================================================
# CHALLENGE 1: GRAPH INVARIANTS & CONSERVED EDGE MASS UNDER MUTATED CONDITIONS
# ==============================================================================

def test_edge_conservation_across_mutated_conditions() -> None:
    """Stress test edge conservation across extreme feedback, aging, temp, and growth."""
    with BaseAgenticMemoryRAG(":memory:") as mind:
        # 1. Verify seed topology conservation
        snap = mind.graph.weight_snapshot()
        assert snap.total == pytest.approx(1.0, rel=1e-9, abs=1e-9)
        assert mind.graph.validate_invariants() == []

        # 2. Add multiple concept nodes and relations
        for i in range(30):
            mind.add_concept(
                f"concept_{i}",
                f"Concept {i}",
                terms=[f"term_{i}", "general"],
                input_trunks=[InputTrunk.HEAR, InputTrunk.SEE],
                output_trunks=[OutputTrunk.SPEAK, OutputTrunk.DO],
            )
        
        # Interconnect concepts with lateral and vertical relations
        for i in range(29):
            mind.graph.add_relation(
                f"concept_{i}",
                f"concept_{i+1}",
                side=GraphSide.INPUT,
                delta_y=1.0,
            )
            mind.graph.add_relation(
                f"concept_{i}",
                f"concept_{i+1}",
                side=GraphSide.OUTPUT,
                delta_y=1.0,
            )

        snap = mind.graph.weight_snapshot()
        assert snap.total == pytest.approx(1.0, rel=1e-9, abs=1e-9)
        assert mind.graph.validate_invariants() == []

        # 3. Apply extreme and chaotic reinforcement sequences
        rng = random.Random(42)
        all_edges = [edge.edge_id for edge in mind.store.list_edges()]
        
        for step in range(100):
            sample_edges = rng.sample(all_edges, k=min(10, len(all_edges)))
            # Alternate between extreme positive, extreme negative, zero, and fractional deltas
            delta_case = step % 5
            if delta_case == 0:
                delta = 1.0
            elif delta_case == 1:
                delta = -1.0
            elif delta_case == 2:
                delta = 0.0
            elif delta_case == 3:
                delta = rng.uniform(-1.0, 1.0)
            else:
                delta = 0.999999

            mind.graph.reinforce_edges(
                sample_edges,
                stability_delta=delta,
                verified=True,
                evidence_quality=rng.uniform(0.1, 1.0),
            )

            # Test edge conservation at each step
            snap = mind.graph.weight_snapshot()
            assert snap.total == pytest.approx(1.0, rel=1e-9, abs=1e-9)

        # 4. Stress-test temporal decay / extreme recency jumps
        for fake_time in [0.0, 100.0, 300.0, 3600.0, 86400.0, 1000000.0]:
            snap = mind.graph.weight_snapshot(now=fake_time)
            assert snap.total == pytest.approx(1.0, rel=1e-9, abs=1e-9)
            assert all(0.0 <= w <= 1.0 for w in snap.global_weights.values())

        # 5. Stress-test extreme temperatures
        for temp in [0.05, 0.1, 0.5, 1.0, 5.0, 20.0, 100.0]:
            mind.graph.temperature = temp
            snap = mind.graph.weight_snapshot()
            assert snap.total == pytest.approx(1.0, rel=1e-9, abs=1e-9)

            # Verify local partition probabilities for all source nodes
            for side in GraphSide:
                sources = {e.source_id for e in mind.store.list_edges(side)}
                for source_id in sources:
                    local = mind.graph.local_probabilities(source_id, side, snapshot=snap)
                    if local:
                        assert sum(local.values()) == pytest.approx(1.0, rel=1e-9, abs=1e-9)
                        assert all(0.0 <= p <= 1.0 for p in local.values())

        # 6. Verify full structural invariants after extreme mutations
        mind.graph.temperature = 1.0
        assert mind.graph.validate_invariants() == []


# ==============================================================================
# CHALLENGE 2: INVARIANT ROBUSTNESS & MALFORMED / ADVERSARIAL INJECTION
# ==============================================================================

def test_validate_invariants_catches_missing_self() -> None:
    with BaseAgenticMemoryRAG(":memory:") as mind:
        assert mind.graph.validate_invariants() == []
        # Disable foreign keys temporarily to corrupt store
        mind.store.connection.execute("PRAGMA foreign_keys = OFF")
        mind.store.connection.execute("DELETE FROM concepts WHERE concept_id = ?", (SELF_ID,))
        mind.store.connection.commit()
        errors = mind.graph.validate_invariants()
        assert any("SELF is missing" in err for err in errors)


def test_validate_invariants_catches_missing_seed_trunks() -> None:
    for trunk_id in (*INPUT_NODE_IDS.values(), *OUTPUT_NODE_IDS.values()):
        with BaseAgenticMemoryRAG(":memory:") as mind:
            assert mind.graph.validate_invariants() == []
            mind.store.connection.execute("PRAGMA foreign_keys = OFF")
            mind.store.connection.execute("DELETE FROM concepts WHERE concept_id = ?", (trunk_id,))
            mind.store.connection.commit()
            errors = mind.graph.validate_invariants()
            assert any(f"seed trunk is missing: {trunk_id}" in err for err in errors)


def test_validate_invariants_catches_lower_preference_corruptions() -> None:
    # 1. Missing lower preference node
    with BaseAgenticMemoryRAG(":memory:") as mind:
        target_pref = list(PREFERENCE_NODE_IDS.values())[0]
        mind.store.connection.execute("PRAGMA foreign_keys = OFF")
        mind.store.connection.execute("DELETE FROM concepts WHERE concept_id = ?", (target_pref,))
        mind.store.connection.commit()
        errors = mind.graph.validate_invariants()
        assert any(f"lower preference node is missing: {target_pref}" in err for err in errors)

    # 2. Missing lower preference vault
    with BaseAgenticMemoryRAG(":memory:") as mind:
        target_pref = list(PREFERENCE_NODE_IDS.values())[0]
        mind.store.connection.execute(
            "UPDATE concepts SET vault_id = '' WHERE concept_id = ?", (target_pref,)
        )
        mind.store.connection.commit()
        errors = mind.graph.validate_invariants()
        assert any(f"lower preference vault is missing: {target_pref}" in err for err in errors)

    # 3. Missing lower preference edge
    with BaseAgenticMemoryRAG(":memory:") as mind:
        target_pref = list(PREFERENCE_NODE_IDS.values())[0]
        mind.store.connection.execute(
            "DELETE FROM edges WHERE target_id = ?", (target_pref,)
        )
        mind.store.connection.commit()
        errors = mind.graph.validate_invariants()
        assert any("lower preference edge is missing" in err for err in errors)


def test_validate_invariants_catches_self_frontier_violations() -> None:
    # 1. Mutate SELF input frontier by adding extra edge
    with BaseAgenticMemoryRAG(":memory:") as mind:
        mind.store.add_concept(
            ConceptNode("EXTRA_NODE", "Extra", "custom", as_tuple([0.0]*mind.embedder.dimension), (), None, 0, 0)
        )
        mind.store.add_edge(
            GraphEdge("edge:fake:1", GraphSide.INPUT, SELF_ID, "EXTRA_NODE", 1.0, 0.0, 0.0, None, 0)
        )
        errors = mind.graph.validate_invariants()
        assert any("SELF input frontier is not exactly HEAR/SEE/NOTICE" in err for err in errors)

    # 2. Mutate SELF output frontier by deleting an edge
    with BaseAgenticMemoryRAG(":memory:") as mind:
        mind.store.connection.execute(
            "DELETE FROM edges WHERE source_id = ? AND target_id = ?", (SELF_ID, "OUT:SPEAK")
        )
        mind.store.connection.commit()
        errors = mind.graph.validate_invariants()
        assert any("SELF output frontier is not exactly SPEAK/LOOK/DO" in err for err in errors)


def test_validate_invariants_catches_child_node_violations() -> None:
    # 1. Child node without overlap cluster
    with BaseAgenticMemoryRAG(":memory:") as mind:
        mind.store.add_concept(
            ConceptNode("child_orphan", "child_orphan", "child", as_tuple([0.0]*mind.embedder.dimension), (), "lower-vault:child_orphan", 0, 0)
        )
        errors = mind.graph.validate_invariants()
        assert any("child has no overlap cluster: child_orphan" in err for err in errors)

    # 2. Child node carrying non-zero semantic embedding
    with BaseAgenticMemoryRAG(":memory:") as mind:
        mind.store.add_concept(
            ConceptNode("CROWN_1", "Crown 1", "crown", as_tuple([0.1]*mind.embedder.dimension), ("crown",), "vault:CROWN_1", 0, 0)
        )
        # Child with non-zero embedding
        mind.store.add_concept(
            ConceptNode("child_carrier", "child_carrier", "child", as_tuple([0.5]*mind.embedder.dimension), (), "lower-vault:child_carrier", 0, 0)
        )
        cluster = OverlapCluster(
            cluster_id="cluster_1",
            parent_node_id="IN:HEAR",
            centroid=as_tuple([0.0]*mind.embedder.dimension),
            record_ids=(),
            experience_ids=(),
            preference_mean=0.0,
            confidence_mean=1.0,
            first_pulse=0,
            last_pulse=0,
            child_node_id="child_carrier",
            semantic_node_id="CROWN_1",
        )
        mind.store.put_overlap_cluster(cluster)
        errors = mind.graph.validate_invariants()
        assert any("lower child carries semantic payload: child_carrier" in err for err in errors)

    # 3. Child node carrying lexical terms
    with BaseAgenticMemoryRAG(":memory:") as mind:
        mind.store.add_concept(
            ConceptNode("CROWN_2", "Crown 2", "crown", as_tuple([0.1]*mind.embedder.dimension), ("crown",), "vault:CROWN_2", 0, 0)
        )
        mind.store.add_concept(
            ConceptNode("child_terms", "child_terms", "child", as_tuple([0.0]*mind.embedder.dimension), ("leaked_term",), "lower-vault:child_terms", 0, 0)
        )
        cluster = OverlapCluster(
            cluster_id="cluster_2",
            parent_node_id="IN:HEAR",
            centroid=as_tuple([0.0]*mind.embedder.dimension),
            record_ids=(),
            experience_ids=(),
            preference_mean=0.0,
            confidence_mean=1.0,
            first_pulse=0,
            last_pulse=0,
            child_node_id="child_terms",
            semantic_node_id="CROWN_2",
        )
        mind.store.put_overlap_cluster(cluster)
        errors = mind.graph.validate_invariants()
        assert any("lower child carries semantic payload: child_terms" in err for err in errors)

    # 4. Child node missing lower vault
    with BaseAgenticMemoryRAG(":memory:") as mind:
        mind.store.add_concept(
            ConceptNode("CROWN_3", "Crown 3", "crown", as_tuple([0.1]*mind.embedder.dimension), ("crown",), "vault:CROWN_3", 0, 0)
        )
        mind.store.add_concept(
            ConceptNode("child_no_vault", "child_no_vault", "child", as_tuple([0.0]*mind.embedder.dimension), (), None, 0, 0)
        )
        cluster = OverlapCluster(
            cluster_id="cluster_3",
            parent_node_id="IN:HEAR",
            centroid=as_tuple([0.0]*mind.embedder.dimension),
            record_ids=(),
            experience_ids=(),
            preference_mean=0.0,
            confidence_mean=1.0,
            first_pulse=0,
            last_pulse=0,
            child_node_id="child_no_vault",
            semantic_node_id="CROWN_3",
        )
        mind.store.put_overlap_cluster(cluster)
        errors = mind.graph.validate_invariants()
        assert any("child lower vault is missing: child_no_vault" in err for err in errors)

    # 5. Child node whose overlap cluster references missing semantic port
    with BaseAgenticMemoryRAG(":memory:") as mind:
        mind.store.add_concept(
            ConceptNode("child_no_port", "child_no_port", "child", as_tuple([0.0]*mind.embedder.dimension), (), "lower-vault:child_no_port", 0, 0)
        )
        mind.store.connection.execute("PRAGMA foreign_keys = OFF")
        cluster = OverlapCluster(
            cluster_id="cluster_4",
            parent_node_id="IN:HEAR",
            centroid=as_tuple([0.0]*mind.embedder.dimension),
            record_ids=(),
            experience_ids=(),
            preference_mean=0.0,
            confidence_mean=1.0,
            first_pulse=0,
            last_pulse=0,
            child_node_id="child_no_port",
            semantic_node_id="MISSING_CROWN",
        )
        mind.store.put_overlap_cluster(cluster)
        errors = mind.graph.validate_invariants()
        assert any("child semantic port is missing: child_no_port" in err for err in errors)


def test_extreme_numerical_weights_cannot_break_softmax_normalizer() -> None:
    """Check that extreme log strengths (+1e6, -1e6) do not cause NaN or break edge mass 1.0."""
    with BaseAgenticMemoryRAG(":memory:") as mind:
        edges = mind.store.list_edges()
        assert len(edges) > 0
        first_edge = edges[0]
        # Injected extreme positive log strength
        mind.store.update_edge_state(first_edge.edge_id, log_strength=1000.0)
        snap = mind.graph.weight_snapshot()
        assert not math.isnan(snap.total)
        assert snap.total == pytest.approx(1.0, rel=1e-9, abs=1e-9)

        # Injected extreme negative log strength
        mind.store.update_edge_state(first_edge.edge_id, log_strength=-1000.0)
        snap = mind.graph.weight_snapshot()
        assert not math.isnan(snap.total)
        assert snap.total == pytest.approx(1.0, rel=1e-9, abs=1e-9)


# ==============================================================================
# CHALLENGE 3: SHUFFLED / UNTRAINED CONTROLS & HATCH GATE EMPIRICAL VERIFICATION
# ==============================================================================

@pytest.mark.skipif(
    not NURSERY.MODEL.is_file() or not NURSERY.CODEC.is_file(),
    reason="local Qwen3 nursery assets unavailable",
)
def test_adversarial_nursery_controls(tmp_path: Path) -> None:
    """Assert shuffled and untrained conditions strictly fail hatch gate."""
    primary = NURSERY.run_one_nursery(
        tmp_path / "primary.sqlite",
        NURSERY.MODEL,
        NURSERY.CODEC,
        ("I", " like", " Josh"),
        cycles=4,
    )
    shuffled = NURSERY.run_one_nursery(
        tmp_path / "shuffled.sqlite",
        NURSERY.MODEL,
        NURSERY.CODEC,
        ("I", " like", " Josh"),
        assignment=(2, 0, 1),
        cycles=4,
    )
    untrained = NURSERY.run_one_nursery(
        tmp_path / "untrained.sqlite",
        NURSERY.MODEL,
        NURSERY.CODEC,
        ("I", " like", " Josh"),
        cycles=0,
    )

    # Primary verification
    assert primary["hatch_ready"] is True
    assert primary["speech"]["exact"] is True
    assert primary["speech"]["surface"] == "I like Josh"
    assert sum(item["passed"] for item in primary["comprehension"]) == 3

    # Shuffled control verification (Adversarial check: exact MUST be False, hatch_ready MUST be False)
    assert shuffled["hatch_ready"] is False
    assert shuffled["speech"]["exact"] is False
    assert shuffled["speech"]["surface"] != "I like Josh"
    assert shuffled["speech"]["surface"] == " JoshI like"

    # Untrained control verification (Adversarial check: zero accuracy, no speech)
    assert untrained["hatch_ready"] is False
    assert untrained["speech"]["exact"] is False
    assert untrained["speech"]["surface"] == ""
    assert sum(item["passed"] for item in untrained["comprehension"]) == 0


@pytest.mark.skipif(
    not REVERSE.nursery.MODEL.is_file() or not REVERSE.nursery.CODEC.is_file(),
    reason="local Qwen3 reverse-nursery assets unavailable",
)
def test_adversarial_reverse_nursery_controls(tmp_path: Path) -> None:
    """Assert reverse nursery (geometry-only) fails hatch gate on shuffled / untrained."""
    primary = REVERSE.run_reverse_nursery(
        tmp_path / "rev_primary.sqlite",
        REVERSE.nursery.MODEL,
        REVERSE.nursery.CODEC,
        ("I", " like", " Josh"),
        cycles=4,
    )
    shuffled = REVERSE.run_reverse_nursery(
        tmp_path / "rev_shuffled.sqlite",
        REVERSE.nursery.MODEL,
        REVERSE.nursery.CODEC,
        ("I", " like", " Josh"),
        assignment=(2, 0, 1),
        cycles=4,
    )
    untrained = REVERSE.run_reverse_nursery(
        tmp_path / "rev_untrained.sqlite",
        REVERSE.nursery.MODEL,
        REVERSE.nursery.CODEC,
        ("I", " like", " Josh"),
        cycles=0,
    )

    # Primary verification
    assert primary["hatch_ready"] is True
    assert primary["speech"]["exact"] is True
    assert primary["speech"]["surface"] == "I like Josh"
    assert primary["lexical_nodes_store_token_ids"] is False
    assert primary["production_reads_token_ids_from_graph"] is False

    # Shuffled control verification
    assert shuffled["hatch_ready"] is False
    assert shuffled["speech"]["exact"] is False
    assert shuffled["speech"]["surface"] == " JoshI like"

    # Untrained control verification
    assert untrained["hatch_ready"] is False
    assert untrained["speech"]["exact"] is False
    assert untrained["speech"]["surface"] == ""


@pytest.mark.skipif(
    not GESTATION.nursery.MODEL.is_file() or not GESTATION.nursery.CODEC.is_file(),
    reason="local Qwen3 accelerated-gestation assets unavailable",
)
def test_adversarial_gestation_evaluation_and_shuffled_control(tmp_path: Path) -> None:
    """Assert accelerated gestation curriculum achieves high generalization while shuffled baseline is near zero."""
    database = tmp_path / "gestation_test.sqlite"
    manifest = GESTATION.compile_mind(
        database,
        GESTATION.nursery.MODEL,
        GESTATION.nursery.CODEC,
        human_name="Josh",
        agent_name="Testling",
        taste_schema="curious",
        replay_cycles=1,
    )

    assert manifest["hatch_ready"] is True
    assert manifest["graph"]["global_edge_mass"] == pytest.approx(1.0, rel=1e-9, abs=1e-9)
    assert manifest["graph"]["invariants"] == []

    # Receptive & Generalization checks
    receptive = manifest["evaluation"]["receptive"]
    assert receptive["semantic_accuracy_at_1"] >= 0.75
    assert receptive["semantic_y_reachable"] == 1.0
    assert receptive["semantic_probe_text_leakage"] == []

    # Productive decoding vs Shuffled control
    productive = manifest["evaluation"]["productive"]
    assert productive["accuracy_at_1"] >= 0.75
    assert productive["shuffled_control_at_1"] <= 0.20
    # Adversarial delta check: productive accuracy must strongly outperform shuffled control
    assert (productive["accuracy_at_1"] - productive["shuffled_control_at_1"]) >= 0.55
