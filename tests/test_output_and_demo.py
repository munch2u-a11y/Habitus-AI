from __future__ import annotations

from agentic_memory_rag import BaseAgenticMemoryRAG
from agentic_memory_rag.types import OutputTrunk


def test_basal_output_classification_uses_three_trunks():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        assert mind.classify_output("reply and explain the answer").trunk == OutputTrunk.SPEAK
        assert mind.classify_output("search inspect read open file").trunk == OutputTrunk.LOOK
        assert mind.classify_output("run execute edit create file").trunk == OutputTrunk.DO


def test_private_output_never_reaches_external_trunk():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        decision = mind.classify_output("I should run the command", private=True)
        assert decision.trunk is None
        assert decision.trace is None
        assert decision.private is True


def test_shared_concept_has_distinct_input_and_output_paths():
    with BaseAgenticMemoryRAG(":memory:") as mind:
        mind.add_concept(
            "workspace",
            "Workspace",
            terms=("workspace", "files", "inspect"),
            input_trunks=("SEE",),
            output_trunks=("LOOK", "DO"),
        )
        concept = mind.store.get_concept("workspace")
        assert concept.vault_id == "vault:workspace"
        input_edges = [
            edge for edge in mind.store.list_edges()
            if edge.target_id == "workspace" and edge.side.value == "input"
        ]
        output_edges = [
            edge for edge in mind.store.list_edges()
            if edge.target_id == "workspace" and edge.side.value == "output"
        ]
        assert len(input_edges) == 1
        assert len(output_edges) == 2
        assert mind.store.get_concept("workspace") is concept or mind.store.get_concept("workspace") == concept
