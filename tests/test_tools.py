import pytest
from habitus_ai import HabitusAI, OutputTrunk, GraphSide
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

    read_receipt = registry.execute("tool:read_file", {"filepath": str(target_file)})
    assert read_receipt.verified is True
    assert read_receipt.output["content"] == "hello habitus"

    mind.close()
