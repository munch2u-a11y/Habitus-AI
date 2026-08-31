from habitus_actualizer._engine.pipeline import BaseAgenticMemoryRAG
from habitus_actualizer._engine.types import MemoryRecord, RecordType, RetrievalHit


class ZeroEmbedder:
    """Make retrieval-lane tests independent of hash collisions."""

    dimension = 16
    space_id = "test-zero-16-v1"

    def embed(self, _text):
        return [0.0] * self.dimension


def _hit(record_id, lane):
    return RetrievalHit(
        MemoryRecord(
            record_id=record_id,
            event_id=record_id,
            record_type=RecordType.INBOUND_MESSAGE,
            source_id="test",
            timestamp="",
            text=record_id,
            embedding=(0.0,) * 16,
        ),
        lane,
        0.0,
        0.0,
    )


def test_context_projection_interleaves_independent_retrieval_lanes():
    ordered = BaseAgenticMemoryRAG._interleave_retrieval_hits(
        [
            _hit("direct-1", "direct"),
            _hit("direct-2", "direct"),
            _hit("direct-3", "direct"),
            _hit("lexical-1", "lexical"),
            _hit("lexical-2", "lexical"),
            _hit("vault-1", "vault"),
        ]
    )

    assert [hit.record.record_id for hit in ordered] == [
        "direct-1",
        "lexical-1",
        "vault-1",
        "direct-2",
        "lexical-2",
        "direct-3",
    ]


def test_global_bm25_complements_cosine_without_needing_a_concept(tmp_path):
    with BaseAgenticMemoryRAG(
        tmp_path / "mind.sqlite",
        embedder=ZeroEmbedder(),
        direct_similarity_floor=0.08,
        lexical_top_k=3,
    ) as mind:
        target = mind.remember(
            "The amber launch code is ORBIT-73.",
            record_id="target",
            allow_growth=False,
        )
        mind.remember(
            "The greenhouse irrigation check is complete.",
            record_id="distractor",
            allow_growth=False,
        )

        result = mind.recall(
            "What is the amber launch code?",
            include_current_input=False,
        )

        assert result.packet.direct_record_ids == ()
        assert result.packet.lexical_record_ids[0] == target.record_id
        assert result.hits[0].lane == "lexical"
        assert "ORBIT-73" in result.context


def test_repeated_experience_promotes_a_lower_child_and_semantic_port(tmp_path):
    with BaseAgenticMemoryRAG(tmp_path / "mind.sqlite") as mind:
        first = mind.remember(
            "Josh keeps the copper key beside the blue atlas.",
            record_id="experience-1",
        )
        second = mind.remember(
            "Josh keeps the copper key beside the blue atlas.",
            record_id="experience-2",
        )

        children = mind.store.list_concepts(kind="child")
        promoted = [
            cluster
            for parent in mind.store.list_concepts(kind="lower_preference")
            for cluster in mind.overlap_clusters(parent.concept_id)
            if cluster.child_node_id is not None
        ]

        assert len(children) == 1
        assert len(promoted) == 1
        assert promoted[0].semantic_node_id is not None
        assert set(promoted[0].record_ids) == {first.record_id, second.record_id}
        assert mind.graph.validate_invariants() == []


def test_superseded_fact_is_not_returned_as_active_memory(tmp_path):
    with BaseAgenticMemoryRAG(tmp_path / "mind.sqlite") as mind:
        old = mind.remember(
            "My office is in Boston.",
            record_id="old-office",
            allow_growth=False,
        )
        new = mind.remember(
            "My office is now in Portland.",
            record_id="new-office",
            supersedes_id=old.record_id,
            allow_growth=False,
        )

        result = mind.recall("Where is my office now?", include_current_input=False)

        assert new.record_id in result.packet.selected_record_ids
        assert old.record_id not in result.packet.selected_record_ids
        assert "Portland" in result.context
        assert "Boston" not in result.context


def test_language_context_omits_timestamps_and_backend_metadata(tmp_path):
    with BaseAgenticMemoryRAG(tmp_path / "mind.sqlite") as mind:
        mind.remember(
            "The calibration word is marigold.",
            source_id="Rina",
            timestamp="2026-08-30T12:34:56+00:00",
            metadata={"private_score": 0.991, "trace_id": "secret-trace"},
            allow_growth=False,
        )

        result = mind.recall("What is the calibration word?", include_current_input=False)

        assert "marigold" in result.context
        assert "Rina" in result.context
        assert "2026-08-30" not in result.context
        assert "private_score" not in result.context
        assert "secret-trace" not in result.context
