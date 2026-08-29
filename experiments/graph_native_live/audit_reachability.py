import sys
from pathlib import Path

SOURCE_ROOT = Path("/home/nemo/habitus-ai-experiments/src")
EXPERIMENT_ROOT = Path("/home/nemo/habitus-ai-experiments/experiments/graph_native_live")
sys.path.insert(0, str(SOURCE_ROOT))
sys.path.insert(0, str(EXPERIMENT_ROOT))

from habitus_ai.pipeline import BaseAgenticMemoryRAG
from habitus_ai.types import GraphSide, InputTrunk
import accelerated_gestation as gestation

runs_dir = EXPERIMENT_ROOT / "accelerated_gestation_runs"
dbs = sorted(runs_dir.glob("habitus-*.sqlite"))

print(f"Found {len(dbs)} databases in {runs_dir}")
for db_path in dbs:
    embedder = gestation.NativeMassEmbedder(gestation.nursery.MODEL, gestation.nursery.CODEC)
    with BaseAgenticMemoryRAG(db_path, embedder=embedder) as mind:
        crowns = mind.store.list_concepts(kind="crown")
        un_hear = []
        for c in crowns:
            tr = mind.graph.traverse(
                pulse_id="audit-hear",
                side=GraphSide.INPUT,
                target_id=c.concept_id,
                endpoint_score=1.0,
                required_input_trunk=InputTrunk.HEAR,
                mark_active=False,
            )
            if tr is None:
                un_hear.append(c.concept_id)

        un_out = []
        for c in crowns:
            tr = mind.graph.traverse(
                pulse_id="audit-out",
                side=GraphSide.OUTPUT,
                target_id=c.concept_id,
                endpoint_score=1.0,
                mark_active=False,
            )
            if tr is None:
                un_out.append(c.concept_id)

        print(f"DB: {db_path.name}")
        print(f"  Crown concepts: {len(crowns)}")
        print(f"  Unreachable from HEAR: {len(un_hear)} / {len(crowns)}")
        if un_hear:
            print(f"    Sample: {un_hear[:5]}")
        print(f"  Unreachable from OUT: {len(un_out)} / {len(crowns)}")
        if un_out:
            print(f"    Sample: {un_out[:5]}")
