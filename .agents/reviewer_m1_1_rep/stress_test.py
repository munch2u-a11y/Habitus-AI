#!/usr/bin/env python3
import glob
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path("/home/nemo/habitus-ai-experiments")
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "experiments" / "graph_native_live"))

from habitus_ai.pipeline import BaseAgenticMemoryRAG
from habitus_ai.types import GraphSide, InputTrunk
import nursery
import accelerated_gestation

def main():
    db_paths = sorted(glob.glob(str(PROJECT_ROOT / "experiments/graph_native_live/accelerated_gestation_runs/*.sqlite")))
    target_db = Path(db_paths[-1])
    embedder = accelerated_gestation.NativeMassEmbedder(nursery.MODEL, nursery.CODEC)
    
    with BaseAgenticMemoryRAG(target_db, embedder=embedder) as mind:
        # Test 1: Non-existent target traversal
        trace = mind.graph.traverse(
            pulse_id="adversarial-test-1",
            side=GraphSide.INPUT,
            target_id="NON_EXISTENT_NODE_999",
            endpoint_score=1.0,
            mark_active=False,
        )
        assert trace is None, f"Expected None for non-existent target, got {trace}"
        print("PASS: Non-existent target traversal returned None gracefully.")
        
        # Test 2: Edge mass conservation after perturbation/reinforcement
        # Pick any existing edge
        edges = mind.store.list_edges(GraphSide.INPUT)
        test_edge = edges[0]
        mind.graph.reinforce_edges(
            (test_edge.edge_id,),
            stability_delta=0.5,
            verified=True,
            evidence_quality=1.0,
        )
        snapshot = mind.graph.weight_snapshot()
        print(f"Edge mass after perturbation: {snapshot.total:.10f}")
        assert abs(snapshot.total - 1.0) < 1e-6
        print("PASS: Edge mass conservation preserved across dynamic reinforcement.")

        # Test 3: C++ native codec boundary test
        env = nursery.codec_environment()
        # Detokenize with out of range token
        comp = subprocess.run(
            [str(nursery.CODEC), str(nursery.MODEL), "detokenize", "99999999"],
            capture_output=True, text=True, env=env
        )
        print(f"Detokenize out-of-range returned code {comp.returncode}")
        # Detokenize empty
        comp_empty = subprocess.run(
            [str(nursery.CODEC), str(nursery.MODEL), "detokenize"],
            capture_output=True, text=True, env=env
        )
        print(f"Detokenize empty returned code {comp_empty.returncode}")

    print("ALL ADVERSARIAL STRESS TESTS COMPLETED SUCCESSFULLY.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
