import pytest
from habitus_ai import HabitusAI, OutputTrunk, GraphSide, RecordType
from habitus_ai.graph import OUTPUT_NODE_IDS
from habitus_ai.tools import (
    ToolDefinition,
    ToolReceipt,
    ToolRegistry,
    BUILTIN_OPERATIONAL_TOOLS,
)

def test_tool_registry_binding(tmp_path):
    mind = HabitusAI(tmp_path / "test_tools_mind.sqlite")
    registry = ToolRegistry(mind)

    # Register built-in operational tools
    for tool in BUILTIN_OPERATIONAL_TOOLS:
        registry.register_tool(tool)

    # Verify tool concepts exist in store under correct output trunks
    read_concept = mind.store.get_concept("tool:read_file")
    assert read_concept is not None

    read_edge = mind.store.find_edge(GraphSide.OUTPUT, OUTPUT_NODE_IDS[OutputTrunk.LOOK], "tool:read_file")
    assert read_edge is not None

    write_edge = mind.store.find_edge(GraphSide.OUTPUT, OUTPUT_NODE_IDS[OutputTrunk.DO], "tool:write_file")
    assert write_edge is not None

    # Execute tool and verify receipt
    target_file = tmp_path / "sample.txt"
    write_receipt = registry.execute("tool:write_file", {"filepath": str(target_file), "content": "hello habitus"})
    assert write_receipt.verified is True
    assert write_receipt.output["bytes_written"] > 0
    assert write_receipt.cycle_id is not None
    assert write_receipt.output_record_id is not None
    assert write_receipt.return_record_id == write_receipt.receipt_id
    cycle = mind.experience_cycle(write_receipt.cycle_id)
    assert cycle.status == "closed"
    assert cycle.output_record_id == write_receipt.output_record_id
    assert cycle.terminal_return_record_id == write_receipt.return_record_id
    assert mind.store.get_record(cycle.output_record_id).record_type == RecordType.TOOL_CALL
    assert mind.store.get_record(write_receipt.return_record_id).record_type == RecordType.TOOL_RESULT
    assert mind.store.get_record(cycle.output_record_id).metadata["membrane_words"] is False
    assert mind.store.get_record(write_receipt.return_record_id).metadata["membrane_words"] is False
    returned = mind.store.returns_for_experience_cycle(cycle.cycle_id)
    assert [(item.status, item.terminal, item.verified) for item in returned] == [
        ("success", True, True)
    ]
    link = mind.store.connection.execute(
        """SELECT relation FROM record_links
           WHERE source_record_id = ? AND target_record_id = ?""",
        (write_receipt.return_record_id, write_receipt.output_record_id),
    ).fetchone()
    assert link["relation"] == "returns_to"
    state = mind.experience_state(cycle.cycle_id)
    assert state.preference_mean == pytest.approx(0.20)
    assert any(
        projection.side == GraphSide.OUTPUT
        for projection in mind.experience_projections(cycle.cycle_id)
    )
    assert any(
        projection.side == GraphSide.INPUT
        for projection in mind.experience_projections(cycle.cycle_id)
    )

    read_receipt = registry.execute("tool:read_file", {"filepath": str(target_file)})
    assert read_receipt.verified is True
    assert read_receipt.output["content"] == "hello habitus"

    error_receipt = registry.execute(
        "tool:read_file",
        {"filepath": str(tmp_path / "missing.txt")},
    )
    assert error_receipt.status == "error"
    assert error_receipt.verified is True
    assert mind.experience_cycle(error_receipt.cycle_id).status == "closed"
    assert mind.experience_state(error_receipt.cycle_id).preference_mean == pytest.approx(-0.20)

    mind.close()
