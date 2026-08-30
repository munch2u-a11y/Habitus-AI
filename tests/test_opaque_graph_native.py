from __future__ import annotations

import importlib.util
from pathlib import Path

from habitus_ai.pipeline import BaseAgenticMemoryRAG


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "graph_native_live"
    / "opaque_skeleton.py"
)
SPEC = importlib.util.spec_from_file_location("opaque_graph_native", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
OPAQUE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OPAQUE)


def test_opaque_connected_packet_has_no_language_anchors(tmp_path: Path) -> None:
    history: list[dict[str, object]] = []
    with BaseAgenticMemoryRAG(
        tmp_path / "mind.sqlite",
        embedder=OPAQUE.OpaqueIdentityEmbedder(),
    ) as mind:
        OPAQUE.seed_skeleton(mind)
        OPAQUE.fire(mind, OPAQUE.OPAQUE_A, 0.8, history)
        OPAQUE.fire(mind, OPAQUE.OPAQUE_B, -0.6, history)
        OPAQUE.connect_branches(mind)
        OPAQUE.fire(mind, OPAQUE.OPAQUE_JOIN, 0.4, history)
        rows, trace = OPAQUE.encode_state(mind, OPAQUE.OPAQUE_JOIN, history)
        assert mind.graph.validate_invariants() == []

    packet = tmp_path / "opaque.packet"
    OPAQUE.write_packet(packet, rows)
    payload = packet.read_text(encoding="ascii")
    assert payload.startswith("HABITUS_OPAQUE_PACKET_V1\n1024 4\n")
    assert "hello" not in payload.casefold()
    assert "greeting" not in payload.casefold()
    assert "friendly" not in payload.casefold()
    assert trace["semantic_labels"] == []
    assert trace["language_anchors"] == []
    assert trace["input_path"][-1] == OPAQUE.OPAQUE_JOIN
    assert trace["output_path"][-1] == OPAQUE.OPAQUE_JOIN


def test_opaque_identity_has_no_lexical_similarity_rule() -> None:
    embedder = OPAQUE.OpaqueIdentityEmbedder()
    hello = embedder.embed("hello")
    greeting = embedder.embed("greeting")
    hello_again = embedder.embed("hello")

    assert hello == hello_again
    cosine = sum(left * right for left, right in zip(hello, greeting))
    assert abs(cosine) < 0.12
