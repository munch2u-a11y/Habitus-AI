from __future__ import annotations

import json
import math
from pathlib import Path
import sqlite3
import sys
import pytest

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1] / "experiments" / "graph_native_live"
SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
for path in (SOURCE_ROOT, EXPERIMENT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from habitus_ai.pipeline import BaseAgenticMemoryRAG
from habitus_ai.types import GraphSide, InputTrunk, OutputTrunk
from habitus_ai.graph import INPUT_NODE_IDS, OUTPUT_NODE_IDS, SELF_ID
import accelerated_gestation as gestation


def get_gestated_databases() -> list[Path]:
    runs_dir = EXPERIMENT_ROOT / "accelerated_gestation_runs"
    dbs = sorted(runs_dir.glob("habitus-*.sqlite"))
    return dbs


@pytest.fixture
def latest_gestated_db() -> Path:
    dbs = get_gestated_databases()
    assert len(dbs) > 0, "No gestated databases found in accelerated_gestation_runs"
    return dbs[-1]


# ==============================================================================
# CHALLENGE 1: Direct SQLite Database Inspection & SQL Triggers
# ==============================================================================

def test_sql_triggers_enforce_record_immutability_on_gestated_dbs():
    """Adversarially attempt UPDATE and DELETE on canonical records in all gestated databases."""
    dbs = get_gestated_databases()
    assert len(dbs) >= 1, "At least one gestated database must exist"

    for db_path in dbs:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # 1. Verify trigger definitions in sqlite_master
        triggers = {
            row["name"]: row["sql"]
            for row in conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'records'"
            )
        }
        assert "records_are_immutable_update" in triggers, f"Update trigger missing in {db_path}"
        assert "records_are_immutable_delete" in triggers, f"Delete trigger missing in {db_path}"

        # 2. Get existing records
        records = conn.execute("SELECT record_id, text, metadata_json FROM records LIMIT 10").fetchall()
        assert len(records) > 0, f"No records found in {db_path}"

        target_record_id = records[0]["record_id"]
        original_text = records[0]["text"]

        # 3. Adversarial Attempt: UPDATE text
        with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)) as exc_info:
            conn.execute(
                "UPDATE records SET text = 'HACKED_CANONICAL_TEXT' WHERE record_id = ?",
                (target_record_id,),
            )
        assert "immutable" in str(exc_info.value).lower()
        conn.rollback()

        # 4. Adversarial Attempt: UPDATE metadata_json
        with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)) as exc_info:
            conn.execute(
                "UPDATE records SET metadata_json = '{\"tampered\": true}' WHERE record_id = ?",
                (target_record_id,),
            )
        assert "immutable" in str(exc_info.value).lower()
        conn.rollback()

        # 5. Adversarial Attempt: UPDATE embedding_json
        with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)) as exc_info:
            conn.execute(
                "UPDATE records SET embedding_json = '[]' WHERE record_id = ?",
                (target_record_id,),
            )
        assert "immutable" in str(exc_info.value).lower()
        conn.rollback()

        # 6. Adversarial Attempt: DELETE single record
        with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)) as exc_info:
            conn.execute(
                "DELETE FROM records WHERE record_id = ?",
                (target_record_id,),
            )
        assert "immutable" in str(exc_info.value).lower()
        conn.rollback()

        # 7. Adversarial Attempt: DELETE all records
        with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)) as exc_info:
            conn.execute("DELETE FROM records")
        assert "immutable" in str(exc_info.value).lower()
        conn.rollback()

        # 8. Verify record remains unchanged after rollback
        current = conn.execute(
            "SELECT text FROM records WHERE record_id = ?", (target_record_id,)
        ).fetchone()
        assert current["text"] == original_text

        # 9. Verify that append-only INSERT works
        dummy_id = f"challenger:test:insert:{db_path.stem}"
        conn.execute(
            """
            INSERT INTO records(
                record_id, event_id, record_type, source_id, timestamp, text,
                embedding_json, provenance_json, metadata_json, supersedes_id
            ) VALUES (?, ?, 'inbound_message', 'challenger', '2026-08-29T00:00:00Z', 'valid insert', '[]', '{}', '{}', NULL)
            """,
            (dummy_id, f"event:{dummy_id}"),
        )
        inserted = conn.execute("SELECT record_id FROM records WHERE record_id = ?", (dummy_id,)).fetchone()
        assert inserted is not None
        conn.rollback()

        conn.close()


# ==============================================================================
# CHALLENGE 2: Child Concept Nodes (Zero Lexical Terms & Zero Embedding)
# ==============================================================================

def test_child_concepts_have_zero_lexical_terms_and_zero_embedding():
    """Verify that all child concept nodes across all databases have exactly 0 terms and all 0.0 embedding components."""
    dbs = get_gestated_databases()
    assert len(dbs) >= 1

    for db_path in dbs:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Query all child concepts
        children = conn.execute(
            "SELECT concept_id, label, kind, terms_json, embedding_json, vault_id FROM concepts WHERE kind = 'child'"
        ).fetchall()
        assert len(children) > 0, f"Expected child nodes in {db_path}, found 0"

        for row in children:
            concept_id = row["concept_id"]
            terms = json.loads(row["terms_json"])
            embedding = json.loads(row["embedding_json"])

            # Verify terms are strictly empty
            assert terms == [] or terms == (), f"Child {concept_id} has non-empty terms: {terms}"
            assert len(terms) == 0, f"Child {concept_id} term count > 0"

            # Verify embedding is 1024-dim zero vector
            assert len(embedding) == 1024, f"Child {concept_id} embedding length != 1024 (got {len(embedding)})"
            assert all(x == 0.0 for x in embedding), f"Child {concept_id} has non-zero embedding elements"
            assert max(abs(x) for x in embedding) == 0.0, f"Child {concept_id} max abs != 0.0"
            assert math.isclose(sum(x * x for x in embedding), 0.0), f"Child {concept_id} L2 norm != 0.0"

            # Verify structural map or lower-vault is present
            assert row["structural_map_json"] is not None or row["vault_id"] == f"lower-vault:{concept_id}"

        # Also inspect Python object deserialization
        embedder = gestation.NativeMassEmbedder(gestation.nursery.MODEL, gestation.nursery.CODEC)
        with BaseAgenticMemoryRAG(db_path, embedder=embedder) as mind:
            mind_children = mind.store.list_concepts(kind="child")
            assert len(mind_children) == len(children)
            for child in mind_children:
                assert child.terms == ()
                assert len(child.terms) == 0
                assert len(child.embedding) == 1024
                assert not any(child.embedding)
                assert all(v == 0.0 for v in child.embedding)

            # Check lexeme nodes: ensure lexical terms are () and embedding is non-zero
            lexemes = mind.store.list_concepts(kind="lexeme")
            assert len(lexemes) > 0
            for lexeme in lexemes:
                assert lexeme.terms == ()
                assert len(lexeme.embedding) == 1024
                assert any(lexeme.embedding)

            # Check lower_preference nodes: ensure terms are () and embedding is all 0.0
            lower_prefs = mind.store.list_concepts(kind="lower_preference")
            assert len(lower_prefs) > 0
            for pref in lower_prefs:
                assert pref.terms == ()
                assert not any(pref.embedding)

        conn.close()


# ==============================================================================
# CHALLENGE 3: Y-Axis Traversal 100% Reachability (HEAR -> Crown, OUT -> Crown)
# ==============================================================================

def test_y_axis_traversal_achieves_100_percent_reachability(latest_gestated_db: Path):
    """Verify Y-axis traversal achieves 100% reachability from HEAR to crown and from OUT to crown on latest gestated DB."""
    embedder = gestation.NativeMassEmbedder(gestation.nursery.MODEL, gestation.nursery.CODEC)
    with BaseAgenticMemoryRAG(latest_gestated_db, embedder=embedder) as mind:
        crown_concepts = mind.store.list_concepts(kind="crown")
        assert len(crown_concepts) >= 36, f"Expected >= 36 crown concepts, found {len(crown_concepts)}"

        # 1. Test Input Traversal: HEAR -> Crown for 100% of crowns
        hear_reachable_count = 0
        unreachable_hear = []
        for index, crown in enumerate(crown_concepts):
            trace = mind.graph.traverse(
                pulse_id=f"test-hear-reachability:{index}",
                side=GraphSide.INPUT,
                target_id=crown.concept_id,
                endpoint_score=1.0,
                required_input_trunk=InputTrunk.HEAR,
                mark_active=False,
            )
            if trace is not None:
                hear_reachable_count += 1
                # Verify path structure: starts at SELF, passes through IN:HEAR, ends at crown
                assert trace.start_node_id == SELF_ID
                assert trace.target_node_id == crown.concept_id
                assert trace.path_node_ids[0] == SELF_ID
                assert trace.path_node_ids[1] == INPUT_NODE_IDS[InputTrunk.HEAR]
                assert trace.path_node_ids[-1] == crown.concept_id
                assert trace.total_travel_time > 0.0
                assert not math.isinf(trace.total_travel_time)
            else:
                unreachable_hear.append(crown.concept_id)

        hear_reachability = hear_reachable_count / len(crown_concepts)
        assert unreachable_hear == [], f"Unreachable crown concepts from HEAR: {unreachable_hear}"
        assert hear_reachability == 1.0, f"HEAR reachability was {hear_reachability:.4f}, expected 1.0"

        # 2. Test Output Traversal: OUT -> Crown for 100% of crowns
        out_reachable_count = 0
        unreachable_out = []
        for index, crown in enumerate(crown_concepts):
            trace = mind.graph.traverse(
                pulse_id=f"test-out-reachability:{index}",
                side=GraphSide.OUTPUT,
                target_id=crown.concept_id,
                endpoint_score=1.0,
                mark_active=False,
            )
            if trace is not None:
                out_reachable_count += 1
                assert trace.start_node_id == SELF_ID
                assert trace.target_node_id == crown.concept_id
                assert trace.path_node_ids[0] == SELF_ID
                assert trace.path_node_ids[1] in OUTPUT_NODE_IDS.values()
                assert trace.path_node_ids[-1] == crown.concept_id
                assert trace.total_travel_time > 0.0
            else:
                unreachable_out.append(crown.concept_id)

        out_reachability = out_reachable_count / len(crown_concepts)
        assert unreachable_out == [], f"Unreachable crown concepts from OUT: {unreachable_out}"
        assert out_reachability == 1.0, f"OUT reachability was {out_reachability:.4f}, expected 1.0"

        # 3. Verify Edge Mass Conservation
        snapshot = mind.graph.weight_snapshot()
        assert math.isclose(snapshot.total, 1.0, rel_tol=1e-6)
        assert mind.graph.validate_invariants() == []


def test_adversarial_traversal_perturbations_and_stress(latest_gestated_db: Path):
    """Stress-test Y-axis traversal against varying endpoint scores, temperature, and depth."""
    embedder = gestation.NativeMassEmbedder(gestation.nursery.MODEL, gestation.nursery.CODEC)
    with BaseAgenticMemoryRAG(latest_gestated_db, embedder=embedder) as mind:
        crown_concepts = mind.store.list_concepts(kind="crown")
        assert len(crown_concepts) >= 30

        # Adversarial Test A: Extreme endpoint scores
        for score in [-100.0, -1.0, 0.0, 0.001, 0.5, 1.0, 100.0]:
            for crown in crown_concepts[:10]:
                trace = mind.graph.traverse(
                    pulse_id=f"adversarial-score:{score}:{crown.concept_id}",
                    side=GraphSide.INPUT,
                    target_id=crown.concept_id,
                    endpoint_score=score,
                    required_input_trunk=InputTrunk.HEAR,
                    mark_active=False,
                )
                assert trace is not None
                assert trace.endpoint_score == float(score)

        # Adversarial Test B: Traversing assemblies specifically (higher hierarchical levels)
        assembly_crowns = [
            c for c in crown_concepts
            if "assembly" in c.concept_id or "Domain" in c.label or "Category" in c.label or "domain" in c.concept_id
        ]
        for assembly in assembly_crowns:
            trace_hear = mind.graph.traverse(
                pulse_id=f"adversarial-assembly:{assembly.concept_id}",
                side=GraphSide.INPUT,
                target_id=assembly.concept_id,
                endpoint_score=1.0,
                required_input_trunk=InputTrunk.HEAR,
                mark_active=False,
            )
            assert trace_hear is not None, f"Assembly {assembly.concept_id} not reachable from HEAR"
            assert len(trace_hear.path_node_ids) >= 3, f"Assembly path should have depth >= 3, got {trace_hear.path_node_ids}"

        # Adversarial Test C: Zero prompt dependency verification
        for crown in crown_concepts:
            trace = mind.graph.traverse(
                pulse_id=f"promptless:{crown.concept_id}",
                side=GraphSide.INPUT,
                target_id=crown.concept_id,
                endpoint_score=1.0,
                mark_active=False,
            )
            assert trace is not None
            for node_id in trace.path_node_ids:
                node = mind.store.get_concept(node_id)
                assert node is not None, f"Node {node_id} in path not found in concept store"
