from __future__ import annotations

import pytest

from agentic_memory_rag import BaseAgenticMemoryRAG
from agentic_memory_rag.graph import PREFERENCE_NODE_IDS
from agentic_memory_rag.types import EventKind, GraphSide, InputTrunk


def test_one_experience_deposits_language_free_lower_projections():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        record = mind.remember(
            "The exact natural-language episode remains canonical up here.",
            record_id="episode-one",
            event_id="event-one",
            metadata={
                "experience_id": "experience-one",
                "preference_signals": [0.2, 0.6],
                "preference_confidence": 0.8,
            },
            allow_growth=False,
        )
        preference_node = PREFERENCE_NODE_IDS[(InputTrunk.HEAR, "STABLE")]
        projections = mind.store.projections_for_experience("experience-one")
        assert {projection.node_id for projection in projections} == {
            "SELF",
            "IN:HEAR",
            preference_node,
        }
        assert all(projection.record_id == record.record_id for projection in projections)
        assert all(projection.preference == pytest.approx(0.4) for projection in projections)
        assert all("text" not in projection.metadata for projection in projections)
        columns = {
            row["name"]
            for row in mind.store.connection.execute(
                "PRAGMA table_info(experience_projections)"
            ).fetchall()
        }
        assert "text" not in columns
        lower = mind.store.get_concept(preference_node)
        assert mind.store.vault_record_ids(lower.vault_id) == [record.record_id]
        assert mind.store.lower_vault_stats(preference_node)["experience_count"] == 1


def test_later_outcome_updates_shared_experience_preference_across_projections():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        mind.remember(
            "An action began.",
            event_id="action-start",
            metadata={
                "experience_id": "shared-turn",
                "stability_delta": 0.6,
            },
            allow_growth=False,
        )
        mind.remember(
            "The observed result introduced some instability.",
            kind=EventKind.OBSERVATION,
            correlation_id="action-start",
            event_id="action-result",
            metadata={
                "experience_id": "shared-turn",
                "stability_delta": -0.2,
            },
            allow_growth=False,
        )
        state = mind.store.get_experience_state("shared-turn")
        assert state.preference_mean == pytest.approx(0.2)
        assert state.observation_count == 2
        projections = mind.store.projections_for_experience("shared-turn")
        assert len(projections) == 6
        assert all(projection.preference == pytest.approx(0.2) for projection in projections)


def test_lower_vault_overlap_promotes_child_then_semantic_port():
    with BaseAgenticMemoryRAG(":memory:", growth_promotion_count=3) as mind:
        for index in range(2):
            mind.remember(
                "Quasar orchard calibration protocol repeats.",
                record_id=f"support-{index}",
                event_id=f"support-event-{index}",
            )
        assert mind.store.list_concepts(kind="child") == []
        assert mind.store.list_concepts(kind="crown") == []

        mind.remember(
            "Quasar orchard calibration protocol repeats.",
            record_id="support-2",
            event_id="support-event-2",
        )
        children = mind.store.list_concepts(kind="child")
        crown = mind.store.list_concepts(kind="crown")
        assert len(children) == 1
        assert len(crown) == 1
        child, semantic = children[0], crown[0]
        assert not any(child.embedding)
        assert child.terms == ()
        assert any(semantic.embedding)
        assert "quasar" in semantic.terms
        assert set(mind.store.vault_record_ids(child.vault_id)) == {
            "support-0",
            "support-1",
            "support-2",
        }
        assert set(mind.store.vault_record_ids(semantic.vault_id)) == {
            "support-0",
            "support-1",
            "support-2",
        }
        parent = PREFERENCE_NODE_IDS[(InputTrunk.HEAR, "NEUTRAL")]
        parent_edge = mind.store.find_edge(
            side=GraphSide.INPUT,
            source_id=parent,
            target_id=child.concept_id,
        )
        semantic_edge = mind.store.find_edge(
            side=GraphSide.INPUT,
            source_id=child.concept_id,
            target_id=semantic.concept_id,
        )
        assert parent_edge is not None
        assert semantic_edge is not None
        result = mind.recall("What is the quasar orchard calibration protocol?")
        assert any(
            child.concept_id in trace.path_node_ids
            and semantic.concept_id in trace.path_node_ids
            for trace in result.packet.y_paths
        )


def test_opposing_preference_vaults_do_not_collapse_into_one_child():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        mind.remember(
            "The same recurring signal appeared.",
            record_id="liked",
            event_id="liked-event",
            metadata={"preference": 0.8},
        )
        mind.remember(
            "The same recurring signal appeared.",
            record_id="disliked",
            event_id="disliked-event",
            metadata={"preference": -0.8},
        )
        assert mind.store.list_concepts(kind="child") == []
        stable = PREFERENCE_NODE_IDS[(InputTrunk.HEAR, "STABLE")]
        unstable = PREFERENCE_NODE_IDS[(InputTrunk.HEAR, "UNSTABLE")]
        assert mind.store.lower_vault_stats(stable)["experience_count"] == 1
        assert mind.store.lower_vault_stats(unstable)["experience_count"] == 1


def test_promoted_child_vault_keeps_accumulating_matching_experiences():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        for index in range(3):
            mind.remember(
                "Cobalt garden synchronization routine repeats.",
                record_id=f"cobalt-{index}",
                event_id=f"cobalt-event-{index}",
            )
        child = mind.store.list_concepts(kind="child")[0]
        cluster = mind.store.overlap_cluster_for_child(child.concept_id)
        assert len(cluster.experience_ids) == 3
        assert set(mind.store.vault_record_ids(child.vault_id)) == {
            "cobalt-0",
            "cobalt-1",
            "cobalt-2",
        }


def test_existing_canonical_records_backfill_into_lower_vaults(tmp_path):
    database = tmp_path / "migration.sqlite"
    with BaseAgenticMemoryRAG(database) as mind:
        mind.remember(
            "A pre-migration canonical memory.",
            record_id="legacy-record",
            event_id="legacy-event",
            allow_growth=False,
        )
        mind.store.connection.execute(
            "DELETE FROM experience_projections WHERE record_id = ?",
            ("legacy-record",),
        )
        mind.store.connection.execute(
            "DELETE FROM experience_state WHERE experience_id = ?",
            ("legacy-event",),
        )
        mind.store.connection.commit()
        mind.store.set_metadata("lower_memory_schema_version", "0")

    with BaseAgenticMemoryRAG(database) as migrated:
        projections = migrated.store.projections_for_experience("legacy-event")
        assert {projection.node_id for projection in projections} == {
            "SELF",
            "IN:HEAR",
            PREFERENCE_NODE_IDS[(InputTrunk.HEAR, "NEUTRAL")],
        }
        assert migrated.store.get_metadata("lower_memory_schema_version") == "1"
