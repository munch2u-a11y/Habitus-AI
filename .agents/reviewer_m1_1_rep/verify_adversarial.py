#!/usr/bin/env python3
import glob
import json
from pathlib import Path
import sqlite3
import sys

PROJECT_ROOT = Path("/home/nemo/habitus-ai-experiments")
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "experiments" / "graph_native_live"))

from habitus_ai.pipeline import BaseAgenticMemoryRAG
import nursery
import accelerated_gestation

def main():
    db_paths = sorted(glob.glob(str(PROJECT_ROOT / "experiments/graph_native_live/accelerated_gestation_runs/*.sqlite")))
    if not db_paths:
        print("No sqlite found in accelerated_gestation_runs")
        return 1
    
    target_db = Path(db_paths[-1])
    print(f"Inspecting DB: {target_db}")
    
    # 1. SQLite Trigger / Immutability Test
    conn = sqlite3.connect(str(target_db))
    conn.row_factory = sqlite3.Row
    triggers = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()]
    print(f"Triggers found: {triggers}")
    assert "records_are_immutable_update" in triggers
    assert "records_are_immutable_delete" in triggers
    
    # Test update immutability
    rec = conn.execute("SELECT record_id FROM records LIMIT 1").fetchone()
    if rec:
        try:
            conn.execute("UPDATE records SET text = 'MUTATED' WHERE record_id = ?", (rec[0],))
            print("FAIL: UPDATE on records succeeded, should have raised error!")
            return 1
        except sqlite3.DatabaseError as e:
            print(f"PASS: UPDATE prevented by trigger: {e}")
            
        try:
            conn.execute("DELETE FROM records WHERE record_id = ?", (rec[0],))
            print("FAIL: DELETE on records succeeded, should have raised error!")
            return 1
        except sqlite3.DatabaseError as e:
            print(f"PASS: DELETE prevented by trigger: {e}")
            
    conn.close()
    
    # 2. Graph Invariants & Edge Mass Verification
    embedder = accelerated_gestation.NativeMassEmbedder(nursery.MODEL, nursery.CODEC)
    with BaseAgenticMemoryRAG(target_db, embedder=embedder) as mind:
        invariants = mind.graph.validate_invariants()
        print(f"Graph invariants check: {invariants} (len={len(invariants)})")
        assert invariants == []
        
        snapshot = mind.graph.weight_snapshot()
        print(f"Global edge mass sum: {snapshot.total:.10f}")
        assert abs(snapshot.total - 1.0) < 1e-6
        
        # 3. Tokenless verification
        concepts = mind.store.list_concepts()
        lexeme_nodes = [c for c in concepts if c.kind == "lexeme"]
        child_nodes = [c for c in concepts if c.kind == "child"]
        crown_nodes = [c for c in concepts if c.kind == "crown"]
        print(f"Total concepts: {len(concepts)} (lexeme={len(lexeme_nodes)}, child={len(child_nodes)}, crown={len(crown_nodes)})")
        
        for lx in lexeme_nodes:
            assert lx.terms == (), f"Lexeme node {lx.concept_id} has terms: {lx.terms}"
            assert lx.concept_id.startswith("LXG:"), f"Lexeme node id {lx.concept_id} does not start with LXG:"
            
        for ch in child_nodes:
            assert ch.terms == (), f"Child node {ch.concept_id} has terms: {ch.terms}"
            assert not any(ch.embedding), f"Child node {ch.concept_id} has non-zero embedding"
            
        print("PASS: Tokenless representation verified for all lexemes and child routing nodes.")
        
    print("ALL ADVERSARIAL CHECKS PASSED.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
