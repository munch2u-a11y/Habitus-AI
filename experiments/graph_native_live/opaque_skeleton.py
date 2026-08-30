#!/usr/bin/env python3
"""Label-free graph skeleton -> native 1024D Qwen input experiment.

This experiment deliberately provides no semantic anchors. Opaque nodes are
created below the shared crown, pulsed with numeric stability, connected, and
encoded from topology, traversal weights, and pulse history. The native runner
receives only dense float rows plus fixed empty-chat role delimiters.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
from typing import Iterable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from habitus_ai.graph import (  # noqa: E402
    INPUT_NODE_IDS,
    OUTPUT_NODE_IDS,
    PREFERENCE_NODE_IDS,
    SELF_ID,
)
from habitus_ai.pipeline import BaseAgenticMemoryRAG  # noqa: E402
from habitus_ai.types import GraphSide, InputTrunk, OutputTrunk  # noqa: E402


DIMENSION = 1024
OPAQUE_A = "U3:00000000"
OPAQUE_B = "U3:00000001"
OPAQUE_JOIN = "U3:00000002"
MODEL = Path("/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf")
RUNNER = Path(__file__).resolve().parent / "native" / "graph_soft_generator"


def decode_native(stream: bytes) -> str:
    """Decode native adapter output leniently.

    A generated token piece can be a partial UTF-8 sequence, and strict decoding would
    abort an entire run over one BPE fragment.
    """
    return stream.decode("utf-8", "replace").strip()


def opaque_unit_vector(key: str, dimension: int = DIMENSION) -> list[float]:
    """Return a stable dense direction with no lexical similarity behavior."""
    payload = hashlib.shake_256(key.encode("utf-8")).digest(dimension * 2)
    unsigned = struct.unpack(f"<{dimension}H", payload)
    values = [(value / 32767.5) - 1.0 for value in unsigned]
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


class OpaqueIdentityEmbedder:
    dimension = DIMENSION
    space_id = "opaque_identity_1024_v1"

    def embed(self, text: str) -> list[float]:
        # Equal strings retain identity. Different strings receive unrelated
        # dense directions; no word, trigram, or pretrained semantics exist.
        return opaque_unit_vector(f"symbol:{text}")


def ensure_node(mind: BaseAgenticMemoryRAG, node_id: str) -> None:
    if mind.store.get_concept(node_id) is not None:
        return
    mind.graph.add_concept(
        node_id,
        node_id,
        terms=(),
        embedding=opaque_unit_vector(f"node:{node_id}"),
        pulse=mind.pulse,
    )


def ensure_relation(
    mind: BaseAgenticMemoryRAG,
    source: str,
    target: str,
    side: GraphSide,
    *,
    delta_y: float = 1.0,
) -> None:
    if mind.store.find_edge(side, source, target) is None:
        mind.graph.add_relation(
            source,
            target,
            side=side,
            delta_y=delta_y,
            pulse=mind.pulse,
        )


def seed_skeleton(mind: BaseAgenticMemoryRAG) -> None:
    """Create two separate upper branches without their joining node."""
    for node_id in (OPAQUE_A, OPAQUE_B):
        ensure_node(mind, node_id)

    stable = PREFERENCE_NODE_IDS[(InputTrunk.HEAR, "STABLE")]
    unstable = PREFERENCE_NODE_IDS[(InputTrunk.HEAR, "UNSTABLE")]
    ensure_relation(mind, stable, OPAQUE_A, GraphSide.INPUT)
    ensure_relation(mind, unstable, OPAQUE_B, GraphSide.INPUT)
    ensure_relation(
        mind,
        OUTPUT_NODE_IDS[OutputTrunk.SPEAK],
        OPAQUE_A,
        GraphSide.OUTPUT,
    )
    ensure_relation(
        mind,
        OUTPUT_NODE_IDS[OutputTrunk.SPEAK],
        OPAQUE_B,
        GraphSide.OUTPUT,
    )


def connect_branches(mind: BaseAgenticMemoryRAG) -> None:
    """Promote an opaque conjunction reached through either learned branch."""
    ensure_node(mind, OPAQUE_JOIN)
    for parent in (OPAQUE_A, OPAQUE_B):
        ensure_relation(mind, parent, OPAQUE_JOIN, GraphSide.INPUT)
        ensure_relation(mind, parent, OPAQUE_JOIN, GraphSide.OUTPUT)


def next_pulse(mind: BaseAgenticMemoryRAG) -> tuple[int, str]:
    mind.pulse += 1
    mind.store.set_metadata("pulse_counter", str(mind.pulse))
    return mind.pulse, f"opaque-pulse:{mind.pulse}"


def fire(
    mind: BaseAgenticMemoryRAG,
    target: str,
    stability: float,
    history: list[dict[str, object]],
) -> dict[str, object]:
    pulse, pulse_id = next_pulse(mind)
    input_trace = mind.graph.traverse(
        pulse_id=pulse_id,
        side=GraphSide.INPUT,
        target_id=target,
        endpoint_score=1.0,
        required_input_trunk=InputTrunk.HEAR,
        mark_active=True,
    )
    output_trace = mind.graph.traverse(
        pulse_id=pulse_id,
        side=GraphSide.OUTPUT,
        target_id=target,
        endpoint_score=1.0,
        mark_active=True,
    )
    if input_trace is None or output_trace is None:
        raise RuntimeError(f"opaque target is unreachable: {target}")
    credited = (*input_trace.path_edge_ids, *output_trace.path_edge_ids)
    mind.graph.reinforce_edges(
        credited,
        stability_delta=stability,
        verified=True,
        evidence_quality=1.0,
    )
    event: dict[str, object] = {
        "pulse": pulse,
        "target": target,
        "stability": float(stability),
        "input_nodes": list(input_trace.path_node_ids),
        "input_edges": list(input_trace.path_edge_ids),
        "output_nodes": list(output_trace.path_node_ids),
        "output_edges": list(output_trace.path_edge_ids),
    }
    history.append(event)
    return event


def weighted_sum(
    vectors: Iterable[tuple[Sequence[float], float]],
) -> list[float]:
    result = [0.0] * DIMENSION
    for vector, weight in vectors:
        for index, value in enumerate(vector):
            result[index] += float(value) * float(weight)
    norm = math.sqrt(sum(value * value for value in result)) or 1.0
    return [value / norm for value in result]


def node_vector(mind: BaseAgenticMemoryRAG, node_id: str) -> Sequence[float]:
    node = mind.store.get_concept(node_id)
    if node is None:
        raise KeyError(node_id)
    return node.embedding


def trace_for(
    mind: BaseAgenticMemoryRAG,
    target: str,
    side: GraphSide,
    pulse_id: str,
):
    return mind.graph.traverse(
        pulse_id=pulse_id,
        side=side,
        target_id=target,
        endpoint_score=1.0,
        required_input_trunk=(InputTrunk.HEAR if side == GraphSide.INPUT else None),
        mark_active=False,
    )


def encode_state(
    mind: BaseAgenticMemoryRAG,
    target: str,
    history: Sequence[dict[str, object]],
) -> tuple[list[list[float]], dict[str, object]]:
    """Encode topology and state without node labels or language anchors."""
    stamp = f"opaque-probe:{mind.pulse}:{target}"
    input_trace = trace_for(mind, target, GraphSide.INPUT, f"{stamp}:in")
    output_trace = trace_for(mind, target, GraphSide.OUTPUT, f"{stamp}:out")
    if input_trace is None or output_trace is None:
        raise RuntimeError(f"cannot encode unreachable target: {target}")

    snapshot = mind.graph.weight_snapshot()
    input_slot = weighted_sum(
        (
            node_vector(mind, node_id),
            0.35 + (depth + 1) / len(input_trace.path_node_ids),
        )
        for depth, node_id in enumerate(input_trace.path_node_ids)
    )
    output_slot = weighted_sum(
        (
            node_vector(mind, node_id),
            0.35 + (depth + 1) / len(output_trace.path_node_ids),
        )
        for depth, node_id in enumerate(output_trace.path_node_ids)
    )
    edge_slot = weighted_sum(
        (
            opaque_unit_vector(f"edge-code:{edge_id}"),
            0.10 + snapshot.global_weights.get(edge_id, 0.0),
        )
        for edge_id in (*input_trace.path_edge_ids, *output_trace.path_edge_ids)
    )

    recent = list(history[-8:])
    temporal_terms: list[tuple[Sequence[float], float]] = []
    for age, event in enumerate(reversed(recent)):
        target_id = str(event["target"])
        stability = float(event["stability"])
        recency = 1.0 / (1.0 + age)
        temporal_terms.append((node_vector(mind, target_id), recency))
        # A fixed, opaque polarity axis encodes sign and magnitude without
        # assigning a linguistic emotion or preference label.
        temporal_terms.append(
            (opaque_unit_vector("scalar-axis:0"), recency * stability)
        )
    if not temporal_terms:
        temporal_terms.append((opaque_unit_vector("empty-history"), 1.0))
    temporal_slot = weighted_sum(temporal_terms)

    rows = [input_slot, edge_slot, temporal_slot, output_slot]
    trace = {
        "target": target,
        "input_path": list(input_trace.path_node_ids),
        "output_path": list(output_trace.path_node_ids),
        "input_edge_weights": [
            snapshot.global_weights.get(edge_id, 0.0)
            for edge_id in input_trace.path_edge_ids
        ],
        "output_edge_weights": [
            snapshot.global_weights.get(edge_id, 0.0)
            for edge_id in output_trace.path_edge_ids
        ],
        "history_pulses": len(history),
        "rows": len(rows),
        "dimension": DIMENSION,
        "semantic_labels": [],
        "language_anchors": [],
    }
    return rows, trace


def control_rows() -> list[list[float]]:
    return [opaque_unit_vector(f"unconnected-control:{index}") for index in range(4)]


def write_packet(path: Path, rows: Sequence[Sequence[float]]) -> None:
    if not rows or any(len(row) != DIMENSION for row in rows):
        raise ValueError("invalid opaque packet rows")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii") as output:
        output.write("HABITUS_OPAQUE_PACKET_V1\n")
        output.write(f"{DIMENSION} {len(rows)}\n")
        for row in rows:
            output.write(" ".join(f"{value:.9g}" for value in row))
            output.write("\n")


def run_native(
    model: Path,
    runner: Path,
    packet: Path,
    *,
    maximum_tokens: int,
    seed: int,
    skip_think: bool = False,
) -> dict[str, object]:
    environment = os.environ.copy()
    environment.setdefault("OLLAMA_LIB_DIR", "/usr/local/lib/ollama")
    environment["LD_LIBRARY_PATH"] = "/usr/local/lib/ollama"
    if skip_think:
        environment["HABITUS_NATIVE_SKIP_THINK"] = "1"
    completed = subprocess.run(
        [str(runner), str(model), str(packet), str(maximum_tokens), str(seed)],
        check=False,
        capture_output=True,
        env=environment,
        timeout=180,
    )
    if completed.returncode != 0:
        raise RuntimeError(decode_native(completed.stderr))
    return json.loads(decode_native(completed.stdout))


def run_experiment(args: argparse.Namespace) -> dict[str, object]:
    args.run_directory.mkdir(parents=True, exist_ok=True)
    history: list[dict[str, object]] = []
    with BaseAgenticMemoryRAG(
        args.database,
        embedder=OpaqueIdentityEmbedder(),
    ) as mind:
        seed_skeleton(mind)
        for _ in range(4):
            fire(mind, OPAQUE_A, 0.8, history)
        for _ in range(3):
            fire(mind, OPAQUE_B, -0.6, history)
        connect_branches(mind)
        for stability in (0.25, 0.40, 0.55, 0.70):
            fire(mind, OPAQUE_JOIN, stability, history)

        cases: list[tuple[str, list[list[float]], dict[str, object]]] = []
        connected_rows: list[list[float]] | None = None
        connected_trace: dict[str, object] | None = None
        for case_id, target in (
            ("branch_a", OPAQUE_A),
            ("branch_b", OPAQUE_B),
            ("connected", OPAQUE_JOIN),
        ):
            rows, trace = encode_state(mind, target, history)
            cases.append((case_id, rows, trace))
            if case_id == "connected":
                connected_rows = rows
                connected_trace = trace
        if connected_rows is None or connected_trace is None:
            raise RuntimeError("connected state was not encoded")
        cases.extend(
            (
                (
                    "connected_repeat",
                    [list(row) for row in connected_rows],
                    {**connected_trace, "control": "exact_repeat"},
                ),
                (
                    "connected_row_reversal",
                    [list(row) for row in reversed(connected_rows)],
                    {**connected_trace, "control": "row_order_reversed"},
                ),
                (
                    "connected_sign_inversion",
                    [[-value for value in row] for row in connected_rows],
                    {**connected_trace, "control": "all_values_negated"},
                ),
            )
        )
        cases.append(
            (
                "unconnected_control",
                control_rows(),
                {
                    "target": None,
                    "semantic_labels": [],
                    "language_anchors": [],
                    "rows": 4,
                    "dimension": DIMENSION,
                },
            )
        )

        results = []
        for case_id, rows, trace in cases:
            packet = args.run_directory / f"{case_id}.packet"
            write_packet(packet, rows)
            native = run_native(
                args.model,
                args.runner,
                packet,
                maximum_tokens=args.max_tokens,
                seed=args.seed,
            )
            results.append(
                {
                    "case_id": case_id,
                    "packet_sha256": hashlib.sha256(packet.read_bytes()).hexdigest(),
                    "packet": str(packet),
                    "trace": trace,
                    "native": native,
                }
            )

        receipt: dict[str, object] = {
            "schema": "habitus.opaque-graph-native.v1",
            "created_ns": time.time_ns(),
            "model": str(args.model),
            "dimension": DIMENSION,
            "skeleton": {
                "nodes": [SELF_ID, OPAQUE_A, OPAQUE_B, OPAQUE_JOIN],
                "language_labels_attached": False,
                "semantic_embedding_model_used": False,
                "handwritten_semantic_codebook_used": False,
            },
            "developmental_pulses": history,
            "graph_invariants": mind.graph.validate_invariants(),
            "cases": results,
        }
        receipt_path = args.run_directory / "matrix.json"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        receipt["receipt_path"] = str(receipt_path)
        return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=MODEL)
    parser.add_argument("--runner", type=Path, default=RUNNER)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(__file__).resolve().parent / "opaque_skeleton.sqlite",
    )
    parser.add_argument(
        "--run-directory",
        type=Path,
        default=Path(__file__).resolve().parent / "opaque_runs",
    )
    parser.add_argument("--max-tokens", type=int, default=192)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.model.is_file():
        raise SystemExit(f"model not found: {args.model}")
    if not args.runner.is_file():
        raise SystemExit(f"runner not found: {args.runner}")
    receipt = run_experiment(args)
    for case in receipt["cases"]:  # type: ignore[union-attr]
        native = case["native"]
        print(f"\n[{case['case_id']}]\n{native['response']}")
    print(f"\nreceipt> {receipt['receipt_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
