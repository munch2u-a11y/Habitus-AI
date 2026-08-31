import asyncio
import json

import pytest

from habitus_actualizer import Actualizer
from habitus_actualizer.mcp_adapter import MCPActualizerBridge, create_mcp_server


def test_probe_bridge_routes_without_executing_or_reinforcing(tmp_path):
    (tmp_path / "README.md").write_text("proof", encoding="utf-8")

    async def scenario():
        async with Actualizer(tmp_path) as actualizer:
            pulse_before = actualizer.mind.pulse
            bridge = MCPActualizerBridge(actualizer)
            result = await bridge.process_assistant_output("I'll read `README.md`.")

            assert result["mode"] == "probe"
            assert result["batch"]["requests"][0]["ability_id"] == "workspace.read"
            assert result["batch"]["receipts"] == ()
            assert result["observation"]["acted"] is False
            assert actualizer.mind.pulse == pulse_before

    asyncio.run(scenario())


def test_execute_bridge_returns_verified_observation(tmp_path):
    (tmp_path / "README.md").write_text("proof", encoding="utf-8")

    async def scenario():
        async with Actualizer(tmp_path) as actualizer:
            bridge = MCPActualizerBridge(actualizer, execution_enabled=True)
            result = await bridge.process_assistant_output("I'll read `README.md`.")

            assert result["mode"] == "execute"
            assert result["observation"]["acted"] is True
            receipt = result["observation"]["results"][0]
            assert receipt["ability"] == "workspace.read"
            assert receipt["verified"] is True
            assert receipt["output"]["content"] == "proof"

    asyncio.run(scenario())


def test_empty_output_is_rejected(tmp_path):
    async def scenario():
        async with Actualizer(tmp_path) as actualizer:
            bridge = MCPActualizerBridge(actualizer)
            with pytest.raises(ValueError, match="must not be empty"):
                await bridge.process_assistant_output("   ")

    asyncio.run(scenario())


def test_contract_keeps_capabilities_behind_one_host_bridge():
    contract = MCPActualizerBridge.contract()
    assert contract["bridge_tool"] == "actualize_assistant_output"
    assert contract["model_tool_catalog_required"] is False
    assert len(contract["abilities"]) == 5


def test_official_mcp_client_sees_one_tool_and_can_probe(tmp_path):
    mcp = pytest.importorskip("mcp")
    Client = mcp.Client
    (tmp_path / "README.md").write_text("proof", encoding="utf-8")

    async def scenario():
        async with Actualizer(tmp_path) as actualizer:
            server = create_mcp_server(actualizer)
            async with Client(server) as client:
                listed = await client.list_tools()
                assert [tool.name for tool in listed.tools] == [
                    "actualize_assistant_output"
                ]
                schema = listed.tools[0].input_schema
                assert set(schema["properties"]) == {"text"}
                called = await client.call_tool(
                    "actualize_assistant_output",
                    {"text": "I'll read `README.md`."},
                )
                assert called.is_error is False
                payload = called.structured_content
                assert payload is not None
                assert payload["mode"] == "probe"
                assert payload["batch"]["requests"][0]["ability_id"] == "workspace.read"

                resources = await client.list_resources()
                assert {str(item.uri) for item in resources.resources} == {
                    "actualizer://contract",
                    "actualizer://status",
                }
                status = await client.read_resource("actualizer://status")
                status_payload = json.loads(status.contents[0].text)
                assert status_payload["mode"] == "probe"
                assert status_payload["graph"]["healthy"] is True

    asyncio.run(scenario())


def test_official_mcp_client_receives_verified_live_receipt(tmp_path):
    mcp = pytest.importorskip("mcp")
    Client = mcp.Client
    (tmp_path / "README.md").write_text("live proof", encoding="utf-8")

    async def scenario():
        async with Actualizer(tmp_path) as actualizer:
            server = create_mcp_server(actualizer, execution_enabled=True)
            async with Client(server) as client:
                called = await client.call_tool(
                    "actualize_assistant_output",
                    {"text": "I'll read `README.md`."},
                )
                assert called.is_error is False
                payload = called.structured_content
                assert payload is not None
                assert payload["mode"] == "execute"
                result = payload["observation"]["results"][0]
                assert result["verified"] is True
                assert result["output"]["content"] == "live proof"

    asyncio.run(scenario())
