from __future__ import annotations

import sqlite3

import pytest

from agentic_memory_rag import BaseAgenticMemoryRAG, DeterministicHashEmbedder, RecordType
from agentic_memory_rag.graph import (
    INPUT_NODE_IDS,
    OUTPUT_NODE_IDS,
    PREFERENCE_NODE_IDS,
    SELF_ID,
)


def test_seed_topology_and_conservation_are_exact():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        assert mind.store.get_concept(SELF_ID) is not None
        assert all(mind.store.get_concept(node_id) for node_id in INPUT_NODE_IDS.values())
        assert all(mind.store.get_concept(node_id) for node_id in OUTPUT_NODE_IDS.values())
        assert len(mind.store.list_edges()) == 6 + len(PREFERENCE_NODE_IDS)
        snapshot = mind.graph.weight_snapshot(now=0.0)
        assert sum(snapshot.global_weights.values()) == pytest.approx(1.0)
        assert mind.graph.validate_invariants() == []


def test_canonical_records_cannot_be_updated_or_deleted():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        record = mind.remember("The immutable source statement.", allow_growth=False)
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            mind.store.connection.execute(
                "UPDATE records SET text = 'changed' WHERE record_id = ?",
                (record.record_id,),
            )
        mind.store.connection.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            mind.store.connection.execute(
                "DELETE FROM records WHERE record_id = ?", (record.record_id,)
            )
        mind.store.connection.rollback()
        assert mind.store.get_record(record.record_id).text == "The immutable source statement."


def test_supersession_preserves_old_record_but_removes_it_from_active_retrieval():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        old = mind.remember(
            "The launch date was April 11.",
            record_id="old",
            event_id="event-old",
            record_type=RecordType.FACT,
            allow_growth=False,
        )
        new = mind.remember(
            "The launch date is April 18, not April 11.",
            record_id="new",
            event_id="event-new",
            record_type=RecordType.FACT,
            supersedes_id=old.record_id,
            allow_growth=False,
        )
        assert mind.store.get_record(old.record_id) is not None
        assert {record.record_id for record in mind.store.list_active_records()} == {new.record_id}


def test_embedding_space_is_bound_to_persisted_mind(tmp_path):
    path = tmp_path / "mind.sqlite"
    with BaseAgenticMemoryRAG(path, embedder=DeterministicHashEmbedder(128)):
        pass
    with pytest.raises(ValueError, match="embedding"):
        BaseAgenticMemoryRAG(path, embedder=DeterministicHashEmbedder(256))


def test_default_store_is_persistent_across_sessions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with BaseAgenticMemoryRAG() as mind:
        mind.remember(
            "The persistent vault contains the amber continuity marker.",
            record_id="continuity",
            event_id="continuity-event",
        )
    assert (tmp_path / "agentic_memory.sqlite").is_file()

    with BaseAgenticMemoryRAG() as reloaded:
        result = reloaded.recall("What continuity marker is in the persistent vault?")
        assert "continuity" in result.packet.direct_record_ids
        assert "amber continuity marker" in result.context
