from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from .pipeline import BaseAgenticMemoryRAG
from .types import EventKind, GraphSide, RecordType


def build_demo(mind: BaseAgenticMemoryRAG) -> None:
    mind.add_concept(
        "project_helios",
        "Project Helios",
        terms=("helios", "deployment", "release"),
        input_trunks=("HEAR", "NOTICE"),
        output_trunks=("LOOK", "DO"),
    )
    mind.add_concept(
        "deployment_logs",
        "Deployment Logs",
        terms=("logs", "deployment", "status"),
        input_trunks=("SEE", "NOTICE"),
        output_trunks=("LOOK",),
    )
    old = mind.remember(
        "Project Helios was initially scheduled for 2027-04-11.",
        source_id="josh",
        timestamp="2026-08-20T12:00:00+00:00",
        record_type=RecordType.FACT,
        concept_ids=("project_helios",),
        metadata={"fact_key": "helios_date", "fact_value": "2027-04-11"},
    )
    current = mind.remember(
        "Project Helios deployment is now 2027-04-18, not 2027-04-11.",
        source_id="josh",
        timestamp="2026-08-27T12:00:00+00:00",
        record_type=RecordType.FACT,
        concept_ids=("project_helios",),
        supersedes_id=old.record_id,
        metadata={"fact_key": "helios_date", "fact_value": "2027-04-18"},
    )
    observed = mind.remember(
        "The deployment status log says staging checks passed 17 of 17.",
        kind=EventKind.OBSERVATION,
        source_id="workspace",
        correlation_id="read:deployment-log",
        record_type=RecordType.OBSERVATION,
        concept_ids=("deployment_logs",),
        metadata={"verified": True},
    )
    mind.add_relation(
        "project_helios",
        "deployment_logs",
        side=GraphSide.INPUT,
        evidence_record_ids=(current.record_id, observed.record_id),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the base agentic-memory RAG demonstration")
    parser.add_argument("--database", help="Persist the demonstration to this SQLite path")
    args = parser.parse_args()
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if args.database:
        database = Path(args.database)
    else:
        temporary = tempfile.TemporaryDirectory(prefix="agentic-memory-demo-")
        database = Path(temporary.name) / "mind.sqlite"

    with BaseAgenticMemoryRAG(database) as mind:
        build_demo(mind)
        result = mind.recall("When is Project Helios deploying, and what passed in staging?")
        print("\nRETRIEVED CONTEXT\n")
        print(result.context)
        print("\nTRACE\n")
        print(f"input trunk: {result.packet.input_trunk.value}")
        print(f"direct safety rail: {list(result.packet.direct_record_ids)}")
        print(f"vault candidates: {list(result.packet.vault_record_ids)}")
        for trace in result.packet.y_paths:
            print(f"{' -> '.join(trace.path_node_ids)} | travel={trace.total_travel_time:.4f}")

        decision = mind.classify_output("I should inspect and read the status log before answering.")
        print("\nOUTPUT CLASSIFICATION\n")
        print(f"trunk: {decision.trunk.value if decision.trunk else 'NONE'}")
        print(f"confidence: {decision.confidence:.4f}")
        print(f"invariants: {mind.graph.validate_invariants() or 'all satisfied'}")

    if temporary is not None:
        temporary.cleanup()


if __name__ == "__main__":
    main()
