from __future__ import annotations

from agentic_memory_rag import BaseAgenticMemoryRAG, EventKind, RecordType
from agentic_memory_rag.types import InputTrunk


def _seed_project(mind):
    mind.add_concept(
        "helios",
        "Project Helios",
        terms=("helios", "deployment"),
        input_trunks=("HEAR", "NOTICE"),
        output_trunks=("LOOK", "DO"),
    )


def test_direct_safety_rail_and_vault_lane_meet_by_canonical_id():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        _seed_project(mind)
        record = mind.remember(
            "Project Helios deployment is 2027-04-18.",
            record_id="helios-date",
            event_id="helios-date-event",
            record_type=RecordType.FACT,
            concept_ids=("helios",),
        )
        result = mind.recall("When is the Project Helios deployment?")
        assert record.record_id in result.packet.direct_record_ids
        assert record.record_id in result.packet.vault_record_ids
        assert result.packet.selected_record_ids.count(record.record_id) == 1
        assert result.packet.input_trunk == InputTrunk.HEAR
        assert result.packet.y_paths[0].path_node_ids[:2] == ("SELF", "IN:HEAR")


def test_graph_candidates_cannot_evict_three_direct_records():
    with BaseAgenticMemoryRAG(":memory:", direct_top_k=3) as mind:
        _seed_project(mind)
        direct_ids = []
        for index, detail in enumerate(("date", "owner", "region")):
            record = mind.remember(
                f"Project Helios {detail} deployment detail {index}.",
                record_id=f"direct-{index}",
                event_id=f"direct-event-{index}",
                concept_ids=("helios",),
            )
            direct_ids.append(record.record_id)
        mind.add_concept(
            "distractor",
            "Distractor",
            terms=("unrelated",),
            input_trunks=("HEAR",),
        )
        for index in range(8):
            mind.remember(
                f"Unrelated distractor material {index}.",
                record_id=f"noise-{index}",
                event_id=f"noise-event-{index}",
                concept_ids=("distractor",),
            )
        result = mind.recall("Project Helios deployment date owner region")
        assert set(direct_ids).issubset(set(result.packet.direct_record_ids))
        assert result.packet.selected_record_ids[:3] == result.packet.direct_record_ids


def test_exact_date_and_negation_survive_context_rendering():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        _seed_project(mind)
        mind.remember(
            "Deployment is 2027-04-18, not 2027-04-11; retries must remain disabled.",
            record_id="exact",
            event_id="exact-event",
            record_type=RecordType.FACT,
            concept_ids=("helios",),
        )
        result = mind.recall("What is the deployment date and retry setting?")
        assert "2027-04-18, not 2027-04-11" in result.context
        assert "retries must remain disabled" in result.context


def test_prior_injection_remains_in_working_memory_on_unrelated_next_pulse():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        _seed_project(mind)
        record = mind.remember(
            "Project Helios uses the cobalt launch key.",
            record_id="cobalt",
            event_id="cobalt-event",
            concept_ids=("helios",),
        )
        first = mind.recall("Which launch key does Project Helios use?")
        assert record.record_id in first.packet.selected_record_ids
        second = mind.recall("Completely unrelated zephyr question")
        assert record.record_id in second.packet.retained_record_ids
        assert "cobalt launch key" in second.context


def test_repeated_novelty_promotes_one_evidence_backed_concept():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        mind.remember(
            "Quasar orchard calibration protocol appeared.",
            record_id="novel-1",
            event_id="novel-event-1",
        )
        assert mind.store.list_concepts(kind="crown") == []
        mind.remember(
            "Quasar orchard calibration protocol appeared again.",
            record_id="novel-2",
            event_id="novel-event-2",
        )
        crown = mind.store.list_concepts(kind="crown")
        assert len(crown) == 1
        assert set(mind.store.vault_record_ids(crown[0].vault_id)) == {"novel-1", "novel-2"}


def test_reload_preserves_authority_and_retrieval(tmp_path):
    path = tmp_path / "mind.sqlite"
    with BaseAgenticMemoryRAG(path) as mind:
        _seed_project(mind)
        mind.remember(
            "Project Helios owner is Mira.",
            record_id="owner",
            event_id="owner-event",
            concept_ids=("helios",),
        )
        assert "owner" in mind.recall("Who owns Project Helios?").packet.direct_record_ids
    with BaseAgenticMemoryRAG(path) as reloaded:
        result = reloaded.recall("Who owns Project Helios?")
        assert "owner" in result.packet.direct_record_ids
        assert "Mira" in result.context
        assert reloaded.graph.validate_invariants() == []

