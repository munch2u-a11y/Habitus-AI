#!/usr/bin/env python3
"""Live Habitus -> graph packet -> native GGUF soft-input experiment.

The user message enters Habitus, not the model.  The bridge emits a bounded
numeric activation packet from the graph's admitted semantic endpoints and
Y-axis traces.  The native runner turns those activations into continuous
input rows and generates with llama.cpp.

This is intentionally a train-free bootstrap adapter.  It proves the complete
execution seam, not that an arbitrary graph vector already has a learned
meaning inside a frozen model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from habitus_ai.graph import OUTPUT_NODE_IDS  # noqa: E402
from habitus_ai.pipeline import BaseAgenticMemoryRAG  # noqa: E402
from habitus_ai.types import (  # noqa: E402
    EventKind,
    GraphSide,
    InputTrunk,
    OutputTrunk,
    RecordType,
)


QWEN3_06_MODEL = Path("/home/nemo/Downloads/Qwen3-0.6B-Q8_0.gguf")
QWEN25_05_FALLBACK = Path(
    "/usr/share/ollama/.ollama/models/blobs/"
    "sha256-c5396e06af294bd101b30dce59131a76d2b773e76950acc870eda801d3ab0515"
)
DEFAULT_MODEL = QWEN3_06_MODEL if QWEN3_06_MODEL.is_file() else QWEN25_05_FALLBACK
DEFAULT_RUNNER = Path(__file__).resolve().parent / "native" / "graph_soft_generator"


# These are seed meanings on the shared semantic crown.  Their terms are used
# only by Habitus nomination.  The native boundary receives the basis IDs and
# scalar activations below, never these labels or the live user message.
SEED_CONCEPTS: dict[str, dict[str, Any]] = {
    "native:greeting": {
        "label": "Greeting exchange",
        "terms": ("hello", "hi", "hey", "greetings", "morning", "evening"),
        "basis": (("greeting", 1.0), ("warm", 0.85), ("clear", 0.45)),
    },
    "native:question": {
        "label": "Question and answer",
        "terms": ("what", "why", "how", "which", "who", "question", "explain"),
        "basis": (("question", 1.0), ("clear", 0.85)),
    },
    "native:gratitude": {
        "label": "Gratitude exchange",
        "terms": ("thanks", "thank", "appreciate", "grateful"),
        "basis": (("gratitude", 1.0), ("warm", 0.8)),
    },
    "native:memory": {
        "label": "Remembered experience",
        "terms": ("remember", "recall", "memory", "before", "earlier"),
        "basis": (("memory", 1.0), ("clear", 0.65)),
    },
    "native:uncertainty": {
        "label": "Careful uncertainty",
        "terms": ("unsure", "uncertain", "maybe", "unknown", "guess"),
        "basis": (("uncertain", 1.0), ("clear", 0.55)),
    },
    "native:observation": {
        "label": "Describe an observation",
        "terms": ("see", "look", "notice", "observe", "describe"),
        "basis": (("observation", 1.0), ("clear", 0.65)),
    },
    "native:action": {
        "label": "Complete an action",
        "terms": ("do", "run", "make", "build", "create", "execute"),
        "basis": (("action", 1.0), ("clear", 0.65)),
    },
}


def ensure_seed(mind: BaseAgenticMemoryRAG) -> None:
    """Install the small semantic crown once without rewriting canonical data."""
    for concept_id, specification in SEED_CONCEPTS.items():
        if mind.store.get_concept(concept_id) is None:
            mind.add_concept(
                concept_id,
                specification["label"],
                terms=specification["terms"],
                input_trunks=(InputTrunk.HEAR,),
                output_trunks=(OutputTrunk.SPEAK,),
            )
        record_id = f"native-seed-record:{concept_id.rsplit(':', 1)[-1]}"
        if mind.store.get_record(record_id) is None:
            mind.remember(
                " ".join(specification["terms"]),
                source_id="native-bridge-seed",
                event_id=f"native-seed-event:{concept_id.rsplit(':', 1)[-1]}",
                record_id=record_id,
                record_type=RecordType.RAW_MEMORY,
                concept_ids=(concept_id,),
                provenance={"kind": "graph_native_bootstrap_seed", "version": 1},
                allow_growth=False,
            )


def _activation_packet(
    mind: BaseAgenticMemoryRAG,
    recall: Any,
) -> tuple[list[tuple[str, float]], Any]:
    ranked = [
        candidate
        for candidate in recall.packet.surface_candidates
        if candidate.concept_id in SEED_CONCEPTS
    ]
    if ranked and ranked[0].joint_score >= 0.08:
        floor = max(0.08, ranked[0].joint_score * 0.35)
        admitted = [candidate for candidate in ranked if candidate.joint_score >= floor]
    else:
        admitted = []
    activations: dict[str, float] = {"speak": 1.0}
    for rank, candidate in enumerate(admitted[:3]):
        rank_discount = 1.0 / (1.0 + 0.35 * rank)
        graph_strength = max(0.20, min(1.0, candidate.joint_score + 0.30))
        for basis, seed_strength in SEED_CONCEPTS[candidate.concept_id]["basis"]:
            activations[basis] = max(
                activations.get(basis, 0.0),
                min(1.0, seed_strength * graph_strength * rank_discount),
            )

    if not admitted:
        # This is a graph-level unknown-state fallback, not a rendering of the
        # user's words.  It keeps the live seam operable on novel inputs.
        activations.update({"uncertain": 0.55, "clear": 0.45})

    ordered = sorted(
        activations.items(),
        key=lambda item: (item[0] != "speak", -item[1], item[0]),
    )[:8]

    output_trace = None
    if admitted:
        target = admitted[0]
        # The input and output trees meet at this admitted crown concept.  X has
        # fixed the endpoint; the output Y cipher chooses its route from SELF.
        output_trace = mind.graph.traverse(
            pulse_id=f"{recall.packet.pulse_id}:native-output",
            side=GraphSide.OUTPUT,
            target_id=target.concept_id,
            endpoint_score=target.joint_score,
            mark_active=True,
        )
    return ordered, output_trace


def compile_turn(
    mind: BaseAgenticMemoryRAG,
    user_text: str,
    packet_path: Path,
) -> tuple[dict[str, Any], str]:
    """Run one input pulse and emit a numeric-only native packet."""
    record = mind.remember(
        user_text,
        kind=EventKind.MESSAGE,
        source_id="live-human",
        provenance={"kind": "graph_native_live_input"},
    )
    recall = mind.recall(
        user_text,
        kind=EventKind.MESSAGE,
        source_id="live-human",
        exclude_record_ids=(record.record_id,),
        include_current_input=False,
    )

    activations, output_trace = _activation_packet(mind, recall)

    packet_path.parent.mkdir(parents=True, exist_ok=True)
    packet_text = "HABITUS_SOFT_PACKET_V1\n" + "".join(
        f"{basis} {value:.8f}\n" for basis, value in activations
    )
    packet_path.write_text(packet_text, encoding="utf-8")
    if user_text in packet_text:
        raise RuntimeError("raw user input leaked into the native graph packet")

    trace = {
        "input_sha256": hashlib.sha256(user_text.encode("utf-8")).hexdigest(),
        "input_record_id": record.record_id,
        "pulse_id": recall.packet.pulse_id,
        "input_trunk": recall.packet.input_trunk.value,
        "surface_candidates": [
            {
                "concept_id": candidate.concept_id,
                "joint_score": candidate.joint_score,
            }
            for candidate in recall.packet.surface_candidates
        ],
        "input_paths": [
            {
                "target": path.target_node_id,
                "nodes": list(path.path_node_ids),
                "travel_time": path.total_travel_time,
            }
            for path in recall.packet.y_paths
        ],
        "output_path": (
            {
                "target": output_trace.target_node_id,
                "nodes": list(output_trace.path_node_ids),
                "travel_time": output_trace.total_travel_time,
            }
            if output_trace is not None
            else None
        ),
        "output_trunk": (
            OutputTrunk.SPEAK.value
            if output_trace is not None
            and len(output_trace.path_node_ids) > 1
            and output_trace.path_node_ids[1] == OUTPUT_NODE_IDS[OutputTrunk.SPEAK]
            else None
        ),
        "numeric_activations": [
            {"basis": basis, "value": value} for basis, value in activations
        ],
        "packet_contains_raw_input": False,
        "packet_contains_memory_text": False,
    }
    return trace, record.record_id


def run_native(
    runner: Path,
    model: Path,
    packet_path: Path,
    *,
    maximum_tokens: int,
    seed: int,
) -> dict[str, Any]:
    environment = os.environ.copy()
    environment.setdefault("OLLAMA_LIB_DIR", "/usr/local/lib/ollama")
    old_library_path = environment.get("LD_LIBRARY_PATH", "")
    environment["LD_LIBRARY_PATH"] = "/usr/local/lib/ollama" + (
        f":{old_library_path}" if old_library_path else ""
    )
    command = [
        str(runner),
        str(model),
        str(packet_path),
        str(maximum_tokens),
        str(seed),
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=180,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"native adapter exited {completed.returncode}: {completed.stderr.strip()}"
        )
    return json.loads(completed.stdout)


def one_turn(
    mind: BaseAgenticMemoryRAG,
    text: str,
    *,
    runner: Path,
    model: Path,
    run_directory: Path,
    maximum_tokens: int,
    seed: int,
) -> dict[str, Any]:
    turn_id = f"turn-{time.time_ns()}"
    packet_path = run_directory / f"{turn_id}.packet"
    trace, _ = compile_turn(mind, text, packet_path)
    native = run_native(
        runner,
        model,
        packet_path,
        maximum_tokens=maximum_tokens,
        seed=seed,
    )
    response = str(native["response"]).strip()
    response_record = mind.remember(
        response,
        kind=EventKind.MESSAGE,
        source_id="graph-native-model",
        record_type=RecordType.OUTBOUND_MESSAGE,
        provenance={
            "kind": "graph_native_soft_output",
            "adapter": native["adapter_kind"],
            "input_sha256": trace["input_sha256"],
        },
        allow_growth=False,
    )
    receipt = {
        "schema": "habitus.graph-native-live-turn.v1",
        "trace": trace,
        "native": native,
        "response_record_id": response_record.record_id,
    }
    receipt_path = run_directory / f"{turn_id}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    receipt["packet_path"] = str(packet_path)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--runner", type=Path, default=DEFAULT_RUNNER)
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(__file__).resolve().parent / "live_mind.sqlite",
    )
    parser.add_argument(
        "--run-directory",
        type=Path,
        default=Path(__file__).resolve().parent / "runs",
    )
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--once", help="run one turn non-interactively")
    parser.add_argument("--show-trace", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.model.is_file():
        raise SystemExit(f"model not found: {args.model}")
    if not args.runner.is_file():
        raise SystemExit(
            f"native runner not found: {args.runner}\n"
            "Build it with: make -C experiments/graph_native_live/native"
        )
    args.run_directory.mkdir(parents=True, exist_ok=True)
    with BaseAgenticMemoryRAG(args.db) as mind:
        ensure_seed(mind)

        def execute(text: str) -> None:
            receipt = one_turn(
                mind,
                text,
                runner=args.runner,
                model=args.model,
                run_directory=args.run_directory,
                maximum_tokens=max(1, args.max_tokens),
                seed=args.seed,
            )
            if args.show_trace:
                print(json.dumps(receipt["trace"], indent=2))
            print(f"agent> {receipt['native']['response'].strip()}")
            print(f"receipt> {receipt['receipt_path']}")

        if args.once is not None:
            execute(args.once)
            return 0

        print("Graph-native live tester. The model receives no user text. Ctrl-D to exit.")
        while True:
            try:
                text = input("you> ").strip()
            except EOFError:
                print()
                return 0
            if text:
                execute(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
