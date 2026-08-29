from __future__ import annotations

import importlib.util
from pathlib import Path

from habitus_ai.pipeline import BaseAgenticMemoryRAG


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "graph_native_live"
    / "live_tester.py"
)
SPEC = importlib.util.spec_from_file_location("graph_native_live_tester", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
LIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LIVE)


def test_graph_packet_omits_raw_input_and_memory_text(tmp_path: Path) -> None:
    with BaseAgenticMemoryRAG(tmp_path / "mind.sqlite") as mind:
        LIVE.ensure_seed(mind)
        packet = tmp_path / "greeting.packet"
        trace, _ = LIVE.compile_turn(mind, "hello there", packet)

    payload = packet.read_text(encoding="utf-8")
    assert "hello there" not in payload
    assert "Greeting exchange" not in payload
    assert trace["packet_contains_raw_input"] is False
    assert trace["packet_contains_memory_text"] is False
    assert trace["output_trunk"] == "SPEAK"
    assert trace["output_path"]["target"] == "native:greeting"
    assert {item["basis"] for item in trace["numeric_activations"]} >= {
        "speak",
        "greeting",
        "warm",
    }


def test_novel_input_uses_bounded_unknown_state(tmp_path: Path) -> None:
    with BaseAgenticMemoryRAG(tmp_path / "mind.sqlite") as mind:
        LIVE.ensure_seed(mind)
        packet = tmp_path / "unknown.packet"
        trace, _ = LIVE.compile_turn(
            mind,
            "violet engines drift sideways",
            packet,
        )

    activations = {
        item["basis"]: item["value"] for item in trace["numeric_activations"]
    }
    assert activations == {"speak": 1.0, "uncertain": 0.55, "clear": 0.45}
    assert trace["output_path"] is None
    assert len(activations) <= 8
